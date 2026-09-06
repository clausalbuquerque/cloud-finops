"""Human-in-the-Loop Approval and Execution Engine.

Enforces state transitions (proposed -> approved/rejected/needs_revision -> executed),
RBAC authorization thresholds, SRE prerequisite validation, drift detection, and memory logging.
"""

from __future__ import annotations

from datetime import datetime, timezone
import os
from typing import Any
from uuid import uuid4

from finops_ai.hitl.contracts import (
    ApprovalOutcome,
    ApprovalStatus,
    ExecutionResult,
    HumanFeedbackDecision,
    RollbackResult,
)
from finops_ai.memory.contracts import OptimizationRecommendation
from finops_ai.memory.repository import AgentMemoryRepository
from finops_ai.observability import LoggingObservabilitySink, ObservabilitySink


class ApprovalEngine:
    """Controls the lifecycle and safety gates for write actions and infrastructure mutations."""

    def __init__(
        self,
        memory_repo: AgentMemoryRepository | None = None,
        observability_sink: ObservabilitySink | None = None,
        rbac_high_savings_threshold: float = 500.0,
    ) -> None:
        self.memory_repo = memory_repo or self._init_memory_repo()
        self.sink = observability_sink or LoggingObservabilitySink()
        self.rbac_high_savings_threshold = rbac_high_savings_threshold
        self._in_memory_store: dict[str, OptimizationRecommendation] = {}

    def _init_memory_repo(self) -> AgentMemoryRepository | None:
        db_url = os.getenv("DATABASE_URL")
        if db_url:
            try:
                return AgentMemoryRepository.from_url(db_url)
            except Exception:
                return None
        return None

    def propose(
        self,
        recommendation: OptimizationRecommendation,
        flow_id: str | None = None,
    ) -> OptimizationRecommendation:
        """Register a proposed recommendation pending human evaluation."""
        rec = OptimizationRecommendation(
            id=recommendation.id,
            resource_id=recommendation.resource_id,
            resource_type=recommendation.resource_type,
            recommendation_type=recommendation.recommendation_type,
            current_state=recommendation.current_state,
            proposed_state=recommendation.proposed_state,
            estimated_monthly_savings=recommendation.estimated_monthly_savings,
            confidence_score=recommendation.confidence_score,
            provider_name=recommendation.provider_name,
            status="proposed",
            sre_assessment=recommendation.sre_assessment,
            scope_team=recommendation.scope_team,
            flow_id=flow_id or recommendation.flow_id,
        )

        self._in_memory_store[rec.id] = rec
        if self.memory_repo:
            try:
                self.memory_repo.store_recommendation(rec)
            except Exception:
                pass

        self.sink.emit(
            "hitl.proposed",
            {
                "recommendation_id": rec.id,
                "resource_id": rec.resource_id,
                "estimated_monthly_savings": rec.estimated_monthly_savings,
                "flow_id": flow_id,
            },
        )
        return rec

    def process_feedback(
        self,
        recommendation_id: str,
        decision: HumanFeedbackDecision,
    ) -> OptimizationRecommendation:
        """Process human reviewer decision and update recommendation state."""
        rec = self._get_recommendation(recommendation_id)
        if not rec:
            raise ValueError(f"Recommendation with ID '{recommendation_id}' not found.")

        # 1. RBAC Check for high-savings actions
        if rec.estimated_monthly_savings >= self.rbac_high_savings_threshold:
            privileged_roles = ["finops_lead", "admin", "director", "platform_lead"]
            if decision.reviewer_role not in privileged_roles:
                raise PermissionError(
                    f"Role '{decision.reviewer_role}' is not authorized to approve recommendations "
                    f"with savings >= ${self.rbac_high_savings_threshold:.2f}. "
                    f"Requires one of: {', '.join(privileged_roles)}."
                )

        # 2. Outcome handling
        rejection_reason = rec.rejection_reason
        if decision.outcome == ApprovalOutcome.APPROVED:
            # SRE Safety Prerequisite Check
            if rec.sre_assessment and not rec.sre_assessment.get("safe_to_modify", True):
                raise ValueError(
                    f"Cannot approve recommendation '{recommendation_id}': "
                    "SRE assessment marked safe_to_modify as False."
                )
            new_status = "approved"
        elif decision.outcome == ApprovalOutcome.REJECTED:
            new_status = "rejected"
            rejection_reason = decision.feedback_notes or "Rejected by human reviewer"
        elif decision.outcome == ApprovalOutcome.NEEDS_REVISION:
            new_status = "needs_revision"
        else:
            new_status = "rejected"

        updated_rec = OptimizationRecommendation(
            id=rec.id,
            resource_id=rec.resource_id,
            resource_type=rec.resource_type,
            recommendation_type=rec.recommendation_type,
            current_state=rec.current_state,
            proposed_state=rec.proposed_state,
            estimated_monthly_savings=rec.estimated_monthly_savings,
            actual_monthly_savings=rec.actual_monthly_savings,
            confidence_score=rec.confidence_score,
            provider_name=rec.provider_name,
            status=new_status,
            rejection_reason=rejection_reason,
            sre_assessment=rec.sre_assessment,
            scope_team=rec.scope_team,
            flow_id=rec.flow_id,
        )

        self._in_memory_store[updated_rec.id] = updated_rec
        if self.memory_repo:
            try:
                self.memory_repo.update_recommendation_status(
                    recommendation_id=updated_rec.id,
                    status=new_status,
                    rejection_reason=rejection_reason,
                )
            except Exception:
                pass

        self.sink.emit(
            "hitl.feedback_processed",
            {
                "recommendation_id": updated_rec.id,
                "status": str(updated_rec.status),
                "reviewer_id": decision.reviewer_id,
                "outcome": decision.outcome.value,
            },
        )
        return updated_rec

    def execute(
        self,
        recommendation_id: str,
        executor_id: str = "platform_engineer_01",
        actual_monthly_savings: float | None = None,
        dry_run: bool = True,
    ) -> ExecutionResult:
        """Execute an approved optimization action with idempotency and drift validation."""
        rec = self._get_recommendation(recommendation_id)
        if not rec:
            raise ValueError(f"Recommendation with ID '{recommendation_id}' not found.")

        # Idempotency / Approval Guard
        current_status_str = str(rec.status.value if hasattr(rec.status, "value") else rec.status)
        if current_status_str != "approved":
            raise PermissionError(
                f"Cannot execute recommendation '{recommendation_id}': "
                f"Current status is '{current_status_str}', must be 'approved'."
            )

        # Generate CLI execution and rollback commands
        exec_cmd, rollback_cmd = self._generate_cli_commands(rec)

        # Drift Calculation (> 10% drift triggers warning)
        drift_detected = False
        drift_pct = None
        if actual_monthly_savings is not None and rec.estimated_monthly_savings > 0:
            drift_pct = round(
                abs(actual_monthly_savings - rec.estimated_monthly_savings)
                / rec.estimated_monthly_savings
                * 100,
                2,
            )
            if drift_pct > 10.0:
                drift_detected = True

        executed_rec = OptimizationRecommendation(
            id=rec.id,
            resource_id=rec.resource_id,
            resource_type=rec.resource_type,
            recommendation_type=rec.recommendation_type,
            current_state=rec.current_state,
            proposed_state=rec.proposed_state,
            estimated_monthly_savings=rec.estimated_monthly_savings,
            actual_monthly_savings=actual_monthly_savings or rec.estimated_monthly_savings,
            confidence_score=rec.confidence_score,
            provider_name=rec.provider_name,
            status="executed",
            rejection_reason=rec.rejection_reason,
            sre_assessment=rec.sre_assessment,
            scope_team=rec.scope_team,
            flow_id=rec.flow_id,
        )

        self._in_memory_store[executed_rec.id] = executed_rec
        if self.memory_repo:
            try:
                self.memory_repo.update_recommendation_status(
                    recommendation_id=executed_rec.id,
                    status="executed",
                    actual_monthly_savings=executed_rec.actual_monthly_savings,
                )
            except Exception:
                pass

        self.sink.emit(
            "hitl.executed",
            {
                "recommendation_id": executed_rec.id,
                "executor": executor_id,
                "dry_run": dry_run,
                "drift_detected": drift_detected,
                "drift_pct": drift_pct,
            },
        )

        return ExecutionResult(
            recommendation_id=executed_rec.id,
            resource_id=executed_rec.resource_id,
            status=ApprovalStatus.EXECUTED,
            execution_command=exec_cmd,
            rollback_command=rollback_cmd,
            executed_by=executor_id,
            projected_monthly_savings=executed_rec.estimated_monthly_savings,
            actual_monthly_savings=executed_rec.actual_monthly_savings,
            drift_detected=drift_detected,
            drift_pct=drift_pct,
        )

    def rollback(
        self,
        recommendation_id: str,
        reason: str = "Performance degradation detected during canary observation window.",
        executor_id: str = "canary_watcher",
        dry_run: bool = True,
    ) -> RollbackResult:
        """Revert an executed recommendation back to its baseline SKU."""
        rec = self._get_recommendation(recommendation_id)
        if not rec:
            raise ValueError(f"Recommendation with ID '{recommendation_id}' not found.")

        current_status_str = str(rec.status.value if hasattr(rec.status, "value") else rec.status)
        if current_status_str != "executed":
            raise PermissionError(
                f"Cannot rollback recommendation '{recommendation_id}': "
                f"Current status is '{current_status_str}', must be 'executed'."
            )

        exec_cmd, rollback_cmd = self._generate_cli_commands(rec)
        baseline_sku = (
            rec.current_state.get("current_sku")
            or rec.current_state.get("sku")
            or ("n2-standard-16" if "gcp" in (rec.provider_name or "").lower() else "Standard_D4s_v5")
        )

        rolled_back_rec = OptimizationRecommendation(
            id=rec.id,
            resource_id=rec.resource_id,
            resource_type=rec.resource_type,
            recommendation_type=rec.recommendation_type,
            current_state=rec.current_state,
            proposed_state=rec.proposed_state,
            estimated_monthly_savings=0.0,
            actual_monthly_savings=0.0,
            confidence_score=rec.confidence_score,
            provider_name=rec.provider_name,
            status="rolled_back",
            rejection_reason=f"Rolled back: {reason}",
            sre_assessment=rec.sre_assessment,
            scope_team=rec.scope_team,
            flow_id=rec.flow_id,
        )

        self._in_memory_store[rolled_back_rec.id] = rolled_back_rec
        if self.memory_repo:
            try:
                self.memory_repo.update_recommendation_status(
                    recommendation_id=rolled_back_rec.id,
                    status="rolled_back",
                    actual_monthly_savings=0.0,
                )
            except Exception:
                pass

        self.sink.emit(
            "hitl.rolled_back",
            {
                "recommendation_id": rolled_back_rec.id,
                "resource_id": rolled_back_rec.resource_id,
                "restored_sku": baseline_sku,
                "executor": executor_id,
                "reason": reason,
                "dry_run": dry_run,
            },
        )

        return RollbackResult(
            recommendation_id=rolled_back_rec.id,
            resource_id=rolled_back_rec.resource_id,
            status=ApprovalStatus.ROLLED_BACK,
            restored_sku=baseline_sku,
            rollback_command=rollback_cmd,
            reason=reason,
            rolled_back_by=executor_id,
        )

    def _get_recommendation(self, recommendation_id: str) -> OptimizationRecommendation | None:
        if recommendation_id in self._in_memory_store:
            return self._in_memory_store[recommendation_id]
        if self.memory_repo:
            try:
                recs = self.memory_repo.get_optimization_history()
                for r in recs:
                    if r.id == recommendation_id:
                        return r
            except Exception:
                pass
        return None

    def _generate_cli_commands(self, rec: OptimizationRecommendation) -> tuple[str, str]:
        """Generate provider-specific execution and rollback CLI commands."""
        provider = (rec.provider_name or "GCP").lower()
        target_sku = rec.proposed_state.get("target_sku", "n2-standard-8") if rec.proposed_state else "n2-standard-8"
        res_name = rec.resource_id.split("/")[-1]

        if "gcp" in provider or "google" in provider:
            exec_cmd = f"gcloud compute instances set-machine-type {res_name} --machine-type={target_sku}"
            rollback_cmd = f"gcloud compute instances set-machine-type {res_name} --machine-type=n2-standard-16"
        elif "azure" in provider or "microsoft" in provider:
            exec_cmd = f"az vm resize --name {res_name} --size {target_sku}"
            rollback_cmd = f"az vm resize --name {res_name} --size Standard_D4s_v5"
        else:
            exec_cmd = f"cloud-cli mutate --resource={res_name} --sku={target_sku}"
            rollback_cmd = f"cloud-cli rollback --resource={res_name}"

        return exec_cmd, rollback_cmd

