from __future__ import annotations

import unittest
from unittest.mock import MagicMock

from finops_ai.policies.blast_radius import (
    AutonomyTier,
    BlastRadiusClassification,
    BlastRadiusPolicyEngine,
)
from finops_ai.agents.contracts import RecommendationCandidate
from finops_ai.orchestration import FinOpsFlow, FlowStatus


class TestBlastRadiusPolicyEngine(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = BlastRadiusPolicyEngine(high_spend_threshold_usd=50.0)

    def test_production_environment_strictly_tier_2_low_spend(self) -> None:
        # Production tag even with $10 savings MUST be Tier 2
        res = self.engine.classify(
            resource_name="worker-01",
            resource_type="compute/instance",
            tags={"env": "production"},
            estimated_monthly_savings_usd=10.0,
        )
        self.assertEqual(res.tier, AutonomyTier.TIER_2)
        self.assertFalse(res.can_be_batched)
        self.assertTrue(res.requires_individual_signoff)
        self.assertTrue(res.is_production)
        self.assertIn("production environment", res.reasons[0].lower())

    def test_production_inferred_from_name(self) -> None:
        # Resource named with 'prod' must be Tier 2
        res = self.engine.classify(
            resource_name="analytics-worker-prod-01",
            resource_type="compute/instance",
            estimated_monthly_savings_usd=15.0,
        )
        self.assertEqual(res.tier, AutonomyTier.TIER_2)
        self.assertTrue(res.is_production)
        self.assertFalse(res.can_be_batched)

    def test_stateful_database_strictly_tier_2(self) -> None:
        # Database in dev with low savings MUST be Tier 2
        res = self.engine.classify(
            resource_name="dev-users-db",
            resource_type="database/instance",
            tags={"env": "dev"},
            estimated_monthly_savings_usd=12.0,
        )
        self.assertEqual(res.tier, AutonomyTier.TIER_2)
        self.assertTrue(res.is_stateful)
        self.assertFalse(res.can_be_batched)
        self.assertTrue(res.requires_individual_signoff)

    def test_shared_cluster_strictly_tier_2(self) -> None:
        # Kubernetes cluster in dev is Tier 2
        res = self.engine.classify(
            resource_name="platform-dev-cluster",
            resource_type="container/cluster",
            tags={"env": "dev"},
            estimated_monthly_savings_usd=20.0,
        )
        self.assertEqual(res.tier, AutonomyTier.TIER_2)
        self.assertTrue(res.is_shared_or_critical)
        self.assertFalse(res.can_be_batched)

    def test_high_spend_dev_resource_tier_2(self) -> None:
        # Non-prod compute but savings >= $50/mo triggers Tier 2
        res = self.engine.classify(
            resource_name="dev-test-worker",
            resource_type="compute/instance",
            tags={"env": "dev"},
            estimated_monthly_savings_usd=85.50,
        )
        self.assertEqual(res.tier, AutonomyTier.TIER_2)
        self.assertTrue(res.is_high_spend)
        self.assertFalse(res.can_be_batched)
        self.assertTrue(res.requires_individual_signoff)

    def test_low_risk_non_prod_stateless_is_tier_1(self) -> None:
        # Non-prod, stateless, savings < $50/mo -> Tier 1 (Batched review eligible)
        res = self.engine.classify(
            resource_name="dev-analytics-runner",
            resource_type="compute/instance",
            tags={"env": "dev"},
            estimated_monthly_savings_usd=28.50,
        )
        self.assertEqual(res.tier, AutonomyTier.TIER_1)
        self.assertTrue(res.can_be_batched)
        self.assertFalse(res.requires_individual_signoff)
        self.assertFalse(res.is_production)
        self.assertFalse(res.is_stateful)
        self.assertFalse(res.is_high_spend)
        self.assertIn("eligible for batched", res.reasons[0].lower())

    def test_classify_candidate_helper(self) -> None:
        candidate = RecommendationCandidate(
            provider="GCP",
            resource_type="compute/instance",
            resource_name="sandbox-vm-01",
            action_summary="Downsize to e2-micro",
            rationale="Idle resource in sandbox",
            estimated_monthly_savings_usd=14.50,
        )
        res = self.engine.classify_candidate(candidate)
        self.assertEqual(res.tier, AutonomyTier.TIER_1)
        self.assertTrue(res.can_be_batched)

    def test_flow_integration_attaches_tier_and_batch_flags(self) -> None:
        mock_repo = MagicMock()
        mock_repo.get_interaction_memory.return_value = []
        mock_repo.get_optimization_history.return_value = []

        def mock_finops_exec(prompt: str) -> tuple[str, list[dict]]:
            return (
                "Verified team dev-analytics spend. Proposing rightsize dev-worker-01 with estimated savings of $22.00.",
                [{"tool_name": "propose_recommendation", "estimated_monthly_savings": 22.0}],
            )

        def mock_sre_exec(prompt: str) -> tuple[str, list[dict]]:
            return (
                "Assessment for dev-worker-01: Peak P95 CPU is 12%. Safe to downsize with 60% headroom.",
                [{"tool_name": "get_utilization_summaries", "p95_utilization": 12.0}],
            )

        flow = FinOpsFlow(
            memory_repo=mock_repo,
            mock_finops_executor=mock_finops_exec,
            mock_sre_executor=mock_sre_exec,
        )

        result = flow.execute_flow(
            query="Analyze dev-worker-01 in sandbox environment",
            team_scope="dev-analytics",
        )

        self.assertEqual(result.status, FlowStatus.COMPLETED)
        self.assertEqual(result.autonomy_tier, AutonomyTier.TIER_1.value)
        self.assertTrue(result.can_be_batched)
        self.assertIsNotNone(result.blast_radius_classification)
        self.assertFalse(result.blast_radius_classification["is_production"])


if __name__ == "__main__":
    unittest.main()
