from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal
import unittest
from unittest.mock import MagicMock, patch
from uuid import uuid4



from finops_ai.hitl import (
    ApprovalEngine,
    ApprovalOutcome,
    ApprovalStatus,
    HumanFeedbackDecision,
)
from finops_ai.judges import (
    EvaluatorOptimizer,
    FinOpsJudgeEvaluator,
    JudgeVerdict,
    SREJudgeEvaluator,
)
from finops_ai.memory.contracts import (
    AgentInteractionMemory,
    AnomalyResolution,
    InfrastructureBaseline,
    OptimizationRecommendation,
)
from finops_ai.orchestration import (
    DelegationController,
    DelegationRequest,
    DependencyRisk,
    FinOpsFlow,
    FlowStatus,
    PolicyGateEngine,
)
from finops_ai.tools.cost_tools import (
    get_commitment_coverage,
    get_top_cost_drivers,
    query_cost_by_service,
    query_cost_trend,
)
from finops_ai.tools.infra_tools import (
    get_infrastructure_baselines,
    get_tracked_resources,
    get_utilization_summaries,
    query_resource_dependencies,
)
from finops_ai.tools.prediction_tools import forecast_spend, get_anomalies
from finops_ai.tools.retrieval_tools import retrieve_provider_context


class TestAgentEngineIntegration(unittest.TestCase):
    """Full integration test suite for the multi-agent FinOps & SRE runtime."""

    def setUp(self) -> None:
        self.mock_repo = MagicMock()
        self.mock_sink = MagicMock()

    @patch("finops_ai.tools.prediction_tools._get_repository")
    @patch("finops_ai.tools.infra_tools._get_session")
    @patch("finops_ai.tools.cost_tools._get_session")
    def test_full_tool_layer_integration(
        self,
        mock_cost_session: MagicMock,
        mock_infra_session: MagicMock,
        mock_pred_repo: MagicMock,
    ) -> None:
        """Verify all deterministic tool categories return structured results."""
        # 1. Mock Cost DB session
        cost_session = MagicMock()
        mock_cost_session.return_value.__enter__.return_value = cost_session

        mock_row = MagicMock()
        mock_row.service_category = "Compute"
        mock_row.provider_name = "Google"
        mock_row.total_cost = 284.50
        mock_row.daily_cost = Decimal("284.50")
        mock_row.record_count = 10
        mock_row.usage_date = date(2026, 8, 15)
        mock_row.resource_id = "projects/p1/zones/z1/instances/analytics-worker-02"
        mock_row.resource_name = "analytics-worker-02"
        mock_row.resource_type = "compute/instance"
        mock_row.sub_account_name = "data-platform"
        cost_session.execute.return_value.all.return_value = [mock_row]

        # 2. Mock Infra DB session
        infra_session = MagicMock()
        mock_infra_session.return_value.__enter__.return_value = infra_session

        mock_res = MagicMock()
        mock_res.id = "uuid-res-1"
        mock_res.azure_resource_id = "projects/p1/zones/z1/instances/analytics-worker-02"
        mock_res.resource_name = "analytics-worker-02"
        mock_res.resource_type = "compute/instance"
        mock_res.region = "us-central1"
        mock_res.sku = "n2-standard-16"
        mock_res.provisioned_capacity = {"vCPUs": 16, "memoryGB": 64}
        mock_res.is_active = True
        mock_sum = MagicMock()

        mock_sum.tracked_resource_id = "uuid-res-1"
        mock_sum.summary_date = date(2026, 8, 20)
        mock_sum.metric_name = "Percentage CPU"
        mock_sum.avg_utilization = 18.5
        mock_sum.max_utilization = 42.0
        mock_sum.p95_utilization = 22.0
        mock_sum.underuse_threshold = 30.0
        mock_sum.is_underused = True

        def mock_scalars(stmt: Any) -> MagicMock:
            scalar_res = MagicMock()
            stmt_str = str(stmt).lower()
            if "utilization_summaries" in stmt_str:
                scalar_res.all.return_value = [mock_sum]
                scalar_res.first.return_value = mock_sum
            else:
                scalar_res.all.return_value = [mock_res]
                scalar_res.first.return_value = mock_res
            return scalar_res

        infra_session.scalars.side_effect = mock_scalars

        # 3. Mock Predictions Repository
        pred_repo = MagicMock()
        mock_pred_repo.return_value = pred_repo

        mock_forecast = MagicMock()
        mock_forecast.to_dict.return_value = {
            "dimension": "service:Compute",
            "horizon": "end_of_month",
            "projected_cost": 4500.0,
        }
        pred_repo.get_forecast.return_value = mock_forecast

        mock_anomaly = MagicMock()
        mock_anomaly.to_dict.return_value = {
            "anomaly_id": "anom-1",
            "dimension": "service_category",
            "severity": "high",
            "actual_cost": 500.0,
            "expected_cost": 200.0,
        }
        pred_repo.get_anomalies.return_value = [mock_anomaly]

        # Cost tools verification
        cost_trend = query_cost_trend._run(
            dimension="service_category",
            date_range="last_30d",
            team_scope="data-platform",
        )
        self.assertEqual(cost_trend["status"], "ok")
        self.assertGreater(cost_trend["total_period_cost"], 0)

        top_drivers = get_top_cost_drivers._run(team_scope="data-platform", limit=3)
        self.assertEqual(top_drivers["status"], "ok")
        self.assertGreater(len(top_drivers["drivers"]), 0)

        # Infra tools verification
        resources = get_tracked_resources._run(resource_type="compute/instance")
        self.assertGreater(len(resources), 0)
        self.assertEqual(resources[0]["resource_name"], "analytics-worker-02")

        util_summaries = get_utilization_summaries._run(
            resource_ids=["projects/p1/zones/z1/instances/analytics-worker-02"]
        )
        self.assertGreater(len(util_summaries), 0)

        # Prediction tools verification
        anomalies = get_anomalies._run(severity="high")
        self.assertEqual(len(anomalies), 1)

        forecast = forecast_spend._run(dimension="service:Compute", horizon="end_of_month")
        self.assertEqual(forecast["status"], "ok")
        self.assertIn("forecast", forecast)

        # Retrieval tool verification
        rag_context = retrieve_provider_context._run(
            provider="Google",
            resource_type="compute/instance",
            query="Resize VM command",
        )
        self.assertEqual(rag_context["status"], "ok")
        self.assertGreater(len(rag_context["chunks"]), 0)



    def test_orchestration_flow_end_to_end(self) -> None:
        """Verify multi-agent flow: FinOps analysis -> SRE safety -> policy gates -> RAG rendering -> memory."""
        self.mock_repo.get_interaction_memory.return_value = []
        self.mock_repo.get_optimization_history.return_value = []

        mock_retrieval = MagicMock()
        from finops_ai.retrieval.contracts import RetrieveProviderContextOutput, RetrievedChunk
        mock_chunk = RetrievedChunk(
            chunk_id="c-001",
            category="architecture",
            provider="Google",
            resource_type="compute/instance",
            content="Run `gcloud compute instances set-machine-type analytics-worker-02 --machine-type=n2-standard-8` to resize.",
            source_url="https://cloud.google.com/compute/docs",
            last_verified=datetime.now(timezone.utc),
            score=0.95,
        )
        mock_retrieval.retrieve_provider_context.return_value = RetrieveProviderContextOutput(
            chunks=[mock_chunk],
            metadata=MagicMock(),
        )

        def mock_finops_exec(prompt: str) -> tuple[str, list[dict]]:
            return (
                "Verified team data-platform spend. The cost of analytics-worker-02 is $284.50. "
                "Checked get_optimization_history (no prior rejections). Proposing rightsize to n2-standard-8 "
                "saving $142.25.",
                [
                    {"tool_name": "query_cost_trend", "cost": 284.50},
                    {"tool_name": "get_optimization_history", "status": "none"},
                ],
            )

        def mock_sre_exec(prompt: str) -> tuple[str, list[dict]]:
            return (
                "SRE Safety Assessment for analytics-worker-02: Peak P95 CPU is 22%, leaving 56% operational headroom "
                "on target n2-standard-8. Safe to modify.",
                [{"tool_name": "get_utilization_summaries", "p95_utilization": 22.0}],
            )

        flow = FinOpsFlow(
            memory_repo=self.mock_repo,
            retrieval_service=mock_retrieval,
            mock_finops_executor=mock_finops_exec,
            mock_sre_executor=mock_sre_exec,
        )

        result = flow.execute_flow(
            query="Analyze analytics-worker-02 for team data-platform",
            team_scope="data-platform",
        )

        self.assertEqual(result.status, FlowStatus.COMPLETED)
        self.assertTrue(result.policy_passed)
        self.assertEqual(len(result.policy_violations), 0)
        self.assertIn("Cloud FinOps Executive Report", result.final_response)
        self.assertIn("SRE Infrastructure Validation", result.final_response)
        self.assertIn("Provider-Specific Execution Guidance", result.final_response)
        self.assertIn("gcloud compute instances set-machine-type", result.final_response)

        # Verify episode memory persistence call
        self.mock_repo.store_interaction_memory.assert_called_once()


    def test_prior_rejection_policy_gate_blocking(self) -> None:
        """Verify that a rejected recommendation in long-term memory blocks re-proposing the same action."""
        rejected_rec = OptimizationRecommendation(
            id=str(uuid4()),
            resource_id="projects/p1/zones/z1/instances/analytics-worker-02",
            resource_type="compute/instance",
            recommendation_type="rightsize",
            current_state={"machine_type": "n2-standard-16"},
            proposed_state={"target_sku": "n2-standard-8"},
            estimated_monthly_savings=142.25,
            confidence_score=90.0,
            status="rejected",
            rejection_reason="Workload scheduled for next quarter migration",
        )
        self.mock_repo.get_interaction_memory.return_value = []
        self.mock_repo.get_optimization_history.return_value = [rejected_rec]

        def mock_finops_exec(prompt: str) -> tuple[str, list[dict]]:
            return (
                "Verified cost on analytics-worker-02 is $284.50. Checked get_optimization_history. "
                "Propose rightsize to n2-standard-8.",
                [{"tool_name": "get_optimization_history", "status": "rejected"}],
            )

        flow = FinOpsFlow(
            memory_repo=self.mock_repo,
            mock_finops_executor=mock_finops_exec,
        )

        result = flow.execute_flow(
            query="Analyze analytics-worker-02 for team data-platform",
            team_scope="data-platform",
        )

        self.assertEqual(result.status, FlowStatus.FAILED_CLOSED)
        self.assertFalse(result.policy_passed)
        self.assertTrue(any("previously rejected" in v for v in result.policy_violations))
        self.assertTrue(result.needs_human_review)

    def test_hitl_approval_and_execution_lifecycle(self) -> None:
        """Verify complete HITL state machine with SRE safety gate and drift detection."""
        engine = ApprovalEngine(
            memory_repo=self.mock_repo,
            observability_sink=self.mock_sink,
            rbac_high_savings_threshold=500.0,
        )

        rec = OptimizationRecommendation(
            id=str(uuid4()),
            resource_id="projects/p1/zones/z1/instances/analytics-worker-02",
            resource_type="compute/instance",
            recommendation_type="rightsize",
            current_state={"machine_type": "n2-standard-16"},
            proposed_state={"target_sku": "n2-standard-8"},
            estimated_monthly_savings=142.25,
            confidence_score=92.0,
            provider_name="GCP",
            sre_assessment={"safe_to_modify": True, "headroom_pct": 56.0},
        )

        # 1. Propose
        proposed = engine.propose(rec, flow_id="flow-999")
        self.assertEqual(proposed.status, "proposed")

        # 2. Review and Approve
        decision = HumanFeedbackDecision(
            recommendation_id=proposed.id,
            reviewer_id="lead@company.com",
            reviewer_role="finops_lead",
            outcome=ApprovalOutcome.APPROVED,
            feedback_notes="Authorized for maintenance window.",
        )
        approved = engine.process_feedback(proposed.id, decision)
        self.assertEqual(approved.status, "approved")

        # 3. Execute with drift verification
        execution = engine.execute(
            recommendation_id=approved.id,
            executor_id="devops@company.com",
            actual_monthly_savings=142.25,
            dry_run=True,
        )
        self.assertEqual(execution.status, ApprovalStatus.EXECUTED)
        self.assertIn("gcloud compute instances set-machine-type", execution.execution_command)
        self.assertFalse(execution.drift_detected)

    def test_sre_baseline_workload_suppression(self) -> None:
        """Verify SRE Judge suppresses alerts on known batch workload spikes with registered baselines."""
        baseline = InfrastructureBaseline(
            resource_id="projects/p1/zones/z1/instances/etl-batch-worker-01",
            metric_name="cpu_utilization",
            baseline_type="batch_spiky",
            expected_pattern={"peak_cpu": 95.0, "active_hours": ["02:00-06:00"]},
            suppress_underuse_alerts=True,
            provider_name="GCP",
        )
        self.mock_repo.get_infrastructure_baseline.return_value = baseline

        evaluator = SREJudgeEvaluator()
        report = evaluator.evaluate(
            agent_output="Identified CPU peak of 92% on etl-batch-worker-01 during 03:00 UTC. Operational headroom is safe.",
            tool_observations=[{"tool_name": "get_infrastructure_baselines"}],
            resource_id="projects/p1/zones/z1/instances/etl-batch-worker-01",
        )

        self.assertEqual(report.verdict, JudgeVerdict.PASS)
        self.assertGreaterEqual(report.overall_score, 85)



