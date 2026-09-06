from __future__ import annotations

import unittest
from unittest.mock import MagicMock

from finops_ai.memory.contracts import OptimizationRecommendation, RecommendationStatus
from finops_ai.orchestration import FinOpsFlow, FlowStatus, TriggerType


class TestFinOpsFlow(unittest.TestCase):
    def setUp(self) -> None:
        self.mock_repo = MagicMock()
        self.mock_repo.get_interaction_memory.return_value = []
        self.mock_repo.get_optimization_history.return_value = []

    def test_flow_complete_success_path(self) -> None:
        # Mock FinOps output proposing rightsizing for analytics-worker-02
        def mock_finops_exec(prompt: str) -> tuple[str, list[dict]]:
            return (
                "Verified team data-platform spend. The cost of analytics-worker-02 is $284.50. "
                "Confirmed with get_optimization_history that no previous rejections exist. "
                "Proposing rightsize to n2-standard-8 with estimated savings of $142.25.",
                [
                    {"tool_name": "query_cost_trend", "total_period_cost": 284.50},
                    {"tool_name": "get_optimization_history", "recommendation_type": "rightsize"},
                    {"tool_name": "propose_recommendation", "estimated_monthly_savings": 142.25},
                ],
            )

        # Mock SRE output validating headroom
        def mock_sre_exec(prompt: str) -> tuple[str, list[dict]]:
            return (
                "Assessment for analytics-worker-02: Peak P95 CPU is 22%, memory is 18%. "
                "Downsizing to n2-standard-8 provides 44% projected peak CPU, leaving a 56% safe operational headroom buffer. "
                "Checked get_infrastructure_baselines and confirmed no batch workload conflicts.",
                [
                    {"tool_name": "get_utilization_summaries", "p95_utilization": 22.0},
                    {"tool_name": "get_infrastructure_baselines", "expected_pattern": {}},
                ],
            )

        flow = FinOpsFlow(
            memory_repo=self.mock_repo,
            mock_finops_executor=mock_finops_exec,
            mock_sre_executor=mock_sre_exec,
        )

        result = flow.execute_flow(
            query="Analyze analytics-worker-02 in team data-platform",
            team_scope="data-platform",
        )

        self.assertEqual(result.status, FlowStatus.COMPLETED)
        self.assertTrue(result.policy_passed)
        self.assertFalse(result.needs_human_review)
        self.assertIn("Cloud FinOps Executive Report", result.final_response)
        self.assertIn("SRE Infrastructure Validation", result.final_response)
        self.mock_repo.store_interaction_memory.assert_called_once()

    def test_flow_prior_rejection_fail_closed(self) -> None:
        target_res = "analytics-worker-02"

        # Mock FinOps output proposing rightsizing for a previously rejected resource
        def mock_finops_exec(prompt: str) -> tuple[str, list[dict]]:
            return (
                "Verified team data-platform spend. The cost of analytics-worker-02 is $284.50. "
                "Proposing rightsize to n2-standard-8 with estimated savings of $142.25.",
                [
                    {"tool_name": "query_cost_trend", "total_period_cost": 284.50},
                    {"tool_name": "get_optimization_history", "recommendation_type": "rightsize"},
                ],
            )

        # Mock SRE output
        def mock_sre_exec(prompt: str) -> tuple[str, list[dict]]:
            return (
                "Assessment for analytics-worker-02: Peak P95 CPU is 22%. Downsizing leaves 56% headroom buffer.",
                [{"tool_name": "get_utilization_summaries", "p95_utilization": 22.0}],
            )

        # Configure memory repo to return an existing rejection for this resource
        mock_rejection = OptimizationRecommendation(
            id="rec-rejected",
            resource_id=target_res,
            resource_type="compute/instance",
            recommendation_type="rightsize",
            current_state={},
            proposed_state={},
            estimated_monthly_savings=142.25,
            confidence_score=0.9,
            status=RecommendationStatus.REJECTED,
            rejection_reason="Batch job spikes unpredictably on month-end close",
        )
        self.mock_repo.get_optimization_history.return_value = [mock_rejection]

        flow = FinOpsFlow(
            memory_repo=self.mock_repo,
            mock_finops_executor=mock_finops_exec,
            mock_sre_executor=mock_sre_exec,
        )

        result = flow.execute_flow(
            query="Analyze analytics-worker-02 in team data-platform",
            team_scope="data-platform",
        )

        self.assertEqual(result.status, FlowStatus.FAILED_CLOSED)
        self.assertFalse(result.policy_passed)
        self.assertTrue(result.needs_human_review)
        self.assertTrue(any("previously rejected" in v for v in result.policy_violations))
        self.assertIn("Manual Verification Required", result.final_response)

    def test_flow_direct_finops_without_sre(self) -> None:
        # Financial breakdown query without rightsizing/downsizing
        def mock_finops_exec(prompt: str) -> tuple[str, list[dict]]:
            return (
                "Total spend across Google Cloud is $5700.00. Compute accounts for $4500.00 and Storage accounts for $1200.00.",
                [
                    {
                        "tool_name": "query_cost_by_service",
                        "total_spend": 5700.00,
                        "services": [
                            {"service_category": "Compute", "total_cost": 4500.00},
                            {"service_category": "Storage", "total_cost": 1200.00},
                        ],
                    }
                ],
            )

        flow = FinOpsFlow(
            memory_repo=self.mock_repo,
            mock_finops_executor=mock_finops_exec,
        )

        result = flow.execute_flow(
            query="What is our total GCP spend this month?",
            team_scope="data-platform",
            trigger_type=TriggerType.SCHEDULED_DIGEST,
        )

        self.assertEqual(result.status, FlowStatus.COMPLETED)
        self.assertTrue(result.policy_passed)
        self.assertFalse(result.needs_human_review)
        self.assertIn("Total spend across Google Cloud is $5700.00", result.final_response)

