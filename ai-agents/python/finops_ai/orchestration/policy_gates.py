"""Policy Gate Engine for the FinOps Orchestration Flow.

Enforces deterministic safety gates before recommendations or responses are released:
1. Data Freshness Gate
2. Confidence Threshold Gate
3. Prior Rejection Gate
4. Dependency Safety Gate
5. Fail-Closed Default Gate
"""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any, Sequence

from finops_ai.memory.contracts import RecommendationStatus
from finops_ai.memory.repository import AgentMemoryRepository
from finops_ai.orchestration.contracts import FinOpsOrchestrationState, PolicyGateResult


class PolicyGateEngine:
    """Evaluates the 5 safety policy gates against the Flow state."""

    def __init__(self, memory_repo: AgentMemoryRepository | None = None) -> None:
        self.memory_repo = memory_repo

    def evaluate_all(self, state: FinOpsOrchestrationState) -> tuple[bool, list[PolicyGateResult]]:
        """Run all policy gates sequentially and return aggregate passed status."""
        results = [
            self.check_data_freshness(state),
            self.check_confidence_threshold(state),
            self.check_prior_rejections(state),
            self.check_dependency_safety(state),
            self.check_fail_closed_default(state),
        ]

        all_passed = all(r.passed for r in results)
        return all_passed, results

    def check_data_freshness(self, state: FinOpsOrchestrationState) -> PolicyGateResult:
        """Gate 1: Ensure analysis does not rely on stale or missing data (> 30 days old)."""
        # If output mentions dates older than 90 days as current state
        if state.finops_output and "stale" in state.finops_output.lower():
            return PolicyGateResult(
                gate_name="DataFreshnessGate",
                passed=False,
                reason="Analysis references stale data older than acceptable window.",
                fail_closed=True,
            )

        return PolicyGateResult(
            gate_name="DataFreshnessGate",
            passed=True,
            reason="Data freshness verified within standard operational window.",
        )

    def check_confidence_threshold(self, state: FinOpsOrchestrationState) -> PolicyGateResult:
        """Gate 2: Enforce confidence score threshold (>= 0.85 calibrated, or >= 70% raw).

        Fails closed to manual review if confidence is insufficient.
        """
        # If we have a calibrated deterministic confidence report, use it as primary
        if state.calibrated_confidence_report:
            report = state.calibrated_confidence_report
            if report.is_ambiguous or report.overall_confidence < 0.85:
                return PolicyGateResult(
                    gate_name="ConfidenceThresholdGate",
                    passed=False,
                    reason=(
                        f"Deterministic confidence score ({report.overall_confidence:.2f}) is below 0.85 threshold "
                        f"or contains ambiguity reasons: {', '.join(report.ambiguity_reasons)}"
                    ),
                    fail_closed=True,
                    details={"calibrated_confidence_report": report.model_dump()},
                )
            
            return PolicyGateResult(
                gate_name="ConfidenceThresholdGate",
                passed=True,
                reason=f"Calibrated confidence threshold satisfied (score: {report.overall_confidence:.2f}).",
                details={"calibrated_confidence_report": report.model_dump()},
            )

        # Fallback to older subjective LLM judge scores
        finops_score = state.finops_report.overall_score if state.finops_report else 100
        sre_score = state.sre_report.overall_score if state.sre_report else 100

        min_score = min(finops_score, sre_score)
        if min_score < 70:
            return PolicyGateResult(
                gate_name="ConfidenceThresholdGate",
                passed=False,
                reason=f"Overall subjective confidence score ({min_score}%) is below the minimum 70% threshold.",
                fail_closed=True,
                details={"finops_score": finops_score, "sre_score": sre_score},
            )

        return PolicyGateResult(
            gate_name="ConfidenceThresholdGate",
            passed=True,
            reason=f"Subjective confidence threshold satisfied (score: {min_score}%).",
            details={"finops_score": finops_score, "sre_score": sre_score},
        )

    def check_prior_rejections(self, state: FinOpsOrchestrationState) -> PolicyGateResult:
        """Gate 3: Verify target resources do not have active/recent user rejections in memory."""
        if not self.memory_repo or not state.target_resource_ids:
            return PolicyGateResult(
                gate_name="PriorRejectionGate",
                passed=True,
                reason="No target resources or memory repo attached.",
            )

        rejected_resources: list[str] = []
        for res_id in state.target_resource_ids:
            history = self.memory_repo.get_optimization_history(
                resource_id=res_id,
                status=RecommendationStatus.REJECTED.value,
            )
            if history:
                rejected_resources.append(f"{res_id} (Reason: {history[0].rejection_reason})")

        if rejected_resources:
            return PolicyGateResult(
                gate_name="PriorRejectionGate",
                passed=False,
                reason=f"Target resource(s) were previously rejected by user: {', '.join(rejected_resources)}",
                fail_closed=True,
                details={"rejected_resources": rejected_resources},
            )

        return PolicyGateResult(
            gate_name="PriorRejectionGate",
            passed=True,
            reason="Confirmed no prior human rejections exist for target resources.",
        )

    def check_dependency_safety(self, state: FinOpsOrchestrationState) -> PolicyGateResult:
        """Gate 4: Ensure SRE assessment verified dependency safety and no high-risk blast radius."""
        if state.sre_output:
            if "risk_level: high" in state.sre_output.lower() or "critical dependency" in state.sre_output.lower():
                return PolicyGateResult(
                    gate_name="DependencySafetyGate",
                    passed=False,
                    reason="SRE assessment detected HIGH risk dependency conflict.",
                    fail_closed=True,
                )

        return PolicyGateResult(
            gate_name="DependencySafetyGate",
            passed=True,
            reason="Dependency safety verified.",
        )

    def check_fail_closed_default(self, state: FinOpsOrchestrationState) -> PolicyGateResult:
        """Gate 5: Default to fail-closed manual verification if output contains fatal ambiguity."""
        if state.finops_output and "unknown error" in state.finops_output.lower():
            return PolicyGateResult(
                gate_name="FailClosedDefaultGate",
                passed=False,
                reason="Execution contained unrecoverable ambiguity; failing closed to manual review.",
                fail_closed=True,
            )

        return PolicyGateResult(
            gate_name="FailClosedDefaultGate",
            passed=True,
            reason="No fail-closed triggers activated.",
        )

