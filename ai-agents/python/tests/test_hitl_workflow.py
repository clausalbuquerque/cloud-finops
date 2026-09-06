from __future__ import annotations

from datetime import datetime, timezone
import unittest
from unittest.mock import MagicMock
from uuid import uuid4

from finops_ai.hitl import (
    ApprovalEngine,
    ApprovalOutcome,
    ApprovalStatus,
    HumanFeedbackDecision,
)
from finops_ai.memory.contracts import OptimizationRecommendation
from finops_ai.tools.mutation_tools import (
    downgrade_resource_sku,
    execute_recommendation,
)


class TestHITLWorkflow(unittest.TestCase):
    def setUp(self) -> None:
        self.mock_sink = MagicMock()
        self.engine = ApprovalEngine(
            memory_repo=None,
            observability_sink=self.mock_sink,
            rbac_high_savings_threshold=500.0,
        )

    def test_full_approval_lifecycle(self) -> None:
        rec = OptimizationRecommendation(
            id=str(uuid4()),
            resource_id="projects/p1/zones/z1/instances/analytics-worker-02",
            resource_type="compute/instance",
            recommendation_type="rightsize",
            current_state={"machine_type": "n2-standard-16"},
            proposed_state={"target_sku": "n2-standard-8"},
            estimated_monthly_savings=142.25,
            confidence_score=90.0,
            provider_name="GCP",
            sre_assessment={"safe_to_modify": True, "headroom_pct": 56.0},
        )

        # 1. Propose
        proposed = self.engine.propose(rec, flow_id="flow-123")
        self.assertEqual(proposed.status, "proposed")

        # 2. Approve
        decision = HumanFeedbackDecision(
            recommendation_id=proposed.id,
            reviewer_id="lead@company.com",
            reviewer_role="finops_lead",
            outcome=ApprovalOutcome.APPROVED,
            feedback_notes="Approved for maintenance window.",
        )
        approved = self.engine.process_feedback(proposed.id, decision)
        self.assertEqual(approved.status, "approved")

        # 3. Execute
        result = self.engine.execute(
            recommendation_id=approved.id,
            executor_id="eng@company.com",
            actual_monthly_savings=142.25,
            dry_run=True,
        )
        self.assertEqual(result.status, ApprovalStatus.EXECUTED)
        self.assertIn("gcloud compute instances set-machine-type", result.execution_command)
        self.assertIn("n2-standard-8", result.execution_command)
        self.assertIn("n2-standard-16", result.rollback_command)
        self.assertFalse(result.drift_detected)

    def test_cannot_execute_unapproved(self) -> None:
        rec = OptimizationRecommendation(
            id=str(uuid4()),
            resource_id="analytics-worker-02",
            resource_type="compute/instance",
            recommendation_type="rightsize",
            current_state={"machine_type": "n2-standard-16"},
            proposed_state={"target_sku": "n2-standard-8"},
            estimated_monthly_savings=142.25,
            confidence_score=90.0,
            provider_name="GCP",
        )
        proposed = self.engine.propose(rec)

        with self.assertRaises(PermissionError) as ctx:
            self.engine.execute(proposed.id)
        self.assertIn("must be 'approved'", str(ctx.exception))

    def test_rejection_path_and_rejection_reason(self) -> None:
        rec = OptimizationRecommendation(
            id=str(uuid4()),
            resource_id="analytics-worker-02",
            resource_type="compute/instance",
            recommendation_type="rightsize",
            current_state={"machine_type": "n2-standard-16"},
            proposed_state={"target_sku": "n2-standard-8"},
            estimated_monthly_savings=142.25,
            confidence_score=90.0,
            provider_name="GCP",
        )
        proposed = self.engine.propose(rec)

        decision = HumanFeedbackDecision(
            recommendation_id=proposed.id,
            reviewer_id="lead@company.com",
            reviewer_role="finops_lead",
            outcome=ApprovalOutcome.REJECTED,
            feedback_notes="Workload peak scheduled next week.",
        )
        rejected = self.engine.process_feedback(proposed.id, decision)
        self.assertEqual(rejected.status, "rejected")
        self.assertEqual(rejected.rejection_reason, "Workload peak scheduled next week.")

        with self.assertRaises(PermissionError):
            self.engine.execute(rejected.id)

    def test_sre_safety_gate_enforcement(self) -> None:
        rec = OptimizationRecommendation(
            id=str(uuid4()),
            resource_id="analytics-worker-02",
            resource_type="compute/instance",
            recommendation_type="rightsize",
            current_state={"machine_type": "n2-standard-16"},
            proposed_state={"target_sku": "n2-standard-8"},
            estimated_monthly_savings=142.25,
            confidence_score=90.0,
            provider_name="GCP",
            sre_assessment={"safe_to_modify": False, "reason": "Insufficient CPU headroom"},
        )
        proposed = self.engine.propose(rec)

        decision = HumanFeedbackDecision(
            recommendation_id=proposed.id,
            reviewer_id="lead@company.com",
            reviewer_role="finops_lead",
            outcome=ApprovalOutcome.APPROVED,
        )
        with self.assertRaises(ValueError) as ctx:
            self.engine.process_feedback(proposed.id, decision)
        self.assertIn("SRE assessment marked safe_to_modify as False", str(ctx.exception))

    def test_rbac_high_savings_threshold(self) -> None:
        rec = OptimizationRecommendation(
            id=str(uuid4()),
            resource_id="prod-db-cluster",
            resource_type="sql/database",
            recommendation_type="downscale",
            current_state={"tier": "db-custom-32-128"},
            proposed_state={"target_sku": "db-custom-16-64"},
            estimated_monthly_savings=1500.0,  # > $500 threshold
            confidence_score=95.0,
            provider_name="GCP",
            sre_assessment={"safe_to_modify": True},
        )
        proposed = self.engine.propose(rec)

        # Standard engineer role cannot approve
        decision_junior = HumanFeedbackDecision(
            recommendation_id=proposed.id,
            reviewer_id="junior@company.com",
            reviewer_role="finops_junior",
            outcome=ApprovalOutcome.APPROVED,
        )
        with self.assertRaises(PermissionError) as ctx:
            self.engine.process_feedback(proposed.id, decision_junior)
        self.assertIn("not authorized to approve recommendations", str(ctx.exception))

        # Admin / Lead role CAN approve
        decision_lead = HumanFeedbackDecision(
            recommendation_id=proposed.id,
            reviewer_id="lead@company.com",
            reviewer_role="finops_lead",
            outcome=ApprovalOutcome.APPROVED,
        )
        approved = self.engine.process_feedback(proposed.id, decision_lead)
        self.assertEqual(approved.status, "approved")

    def test_savings_drift_detection(self) -> None:
        rec = OptimizationRecommendation(
            id=str(uuid4()),
            resource_id="analytics-worker-02",
            resource_type="compute/instance",
            recommendation_type="rightsize",
            current_state={"machine_type": "n2-standard-16"},
            proposed_state={"target_sku": "n2-standard-8"},
            estimated_monthly_savings=100.0,
            confidence_score=90.0,
            provider_name="GCP",
            sre_assessment={"safe_to_modify": True},
        )
        proposed = self.engine.propose(rec)
        decision = HumanFeedbackDecision(
            recommendation_id=proposed.id,
            reviewer_id="lead@company.com",
            reviewer_role="finops_lead",
            outcome=ApprovalOutcome.APPROVED,
        )
        self.engine.process_feedback(proposed.id, decision)

        # Actual savings is $75 instead of $100 (25% drift > 10% threshold)
        result = self.engine.execute(
            recommendation_id=proposed.id,
            actual_monthly_savings=75.0,
        )
        self.assertTrue(result.drift_detected)
        self.assertEqual(result.drift_pct, 25.0)

    def test_idempotent_execution_protection(self) -> None:
        rec = OptimizationRecommendation(
            id=str(uuid4()),
            resource_id="analytics-worker-02",
            resource_type="compute/instance",
            recommendation_type="rightsize",
            current_state={"machine_type": "n2-standard-16"},
            proposed_state={"target_sku": "n2-standard-8"},
            estimated_monthly_savings=142.25,
            confidence_score=90.0,
            provider_name="GCP",
            sre_assessment={"safe_to_modify": True},
        )
        proposed = self.engine.propose(rec)
        decision = HumanFeedbackDecision(
            recommendation_id=proposed.id,
            reviewer_id="lead@company.com",
            reviewer_role="finops_lead",
            outcome=ApprovalOutcome.APPROVED,
        )
        self.engine.process_feedback(proposed.id, decision)

        # First execution succeeds
        res1 = self.engine.execute(proposed.id)
        self.assertEqual(res1.status, ApprovalStatus.EXECUTED)

        # Second execution attempt is blocked
        with self.assertRaises(PermissionError) as ctx:
            self.engine.execute(proposed.id)
        self.assertIn("must be 'approved'", str(ctx.exception))


    def test_mutation_tools_execution(self) -> None:
        # Tool blocked on non-existent or unapproved ID
        res_blocked = execute_recommendation._run(recommendation_id="unknown-id-123")
        self.assertEqual(res_blocked["status"], "error")
        self.assertIn("Action execution blocked", res_blocked["message"])
