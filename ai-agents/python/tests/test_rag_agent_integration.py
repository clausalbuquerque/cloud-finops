from __future__ import annotations

from datetime import datetime, timedelta, timezone
import unittest
from unittest.mock import MagicMock

from finops_ai.agents import (
    RecommendationCandidate,
    RecommendationRenderer,
    RecommendationRendererConfig,
    summarize_analysis_without_retrieval,
)
from finops_ai.orchestration import FinOpsFlow, FlowStatus
from finops_ai.retrieval import (
    RetrieveProviderContextInput,
    RetrieveProviderContextOutput,
    RetrievedChunk,
)
from finops_ai.tools.retrieval_tools import retrieve_provider_context


class TestRAGAgentIntegration(unittest.TestCase):
    def test_retrieve_provider_context_tool(self) -> None:
        result = retrieve_provider_context._run(
            provider="Google",
            resource_type="compute/instance",
            query="Change machine type of VM",
        )

        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["provider"], "Google")
        self.assertGreater(len(result["chunks"]), 0)
        chunk = result["chunks"][0]
        self.assertIn("gcloud compute instances set-machine-type", chunk["content"])

    def test_rag_enriched_recommendation_rendering(self) -> None:
        mock_retrieval = MagicMock()
        mock_chunk = RetrievedChunk(
            chunk_id="c-001",
            category="architecture",
            provider="Google",
            resource_type="compute/instance",
            content="Run `gcloud compute instances set-machine-type my-vm --machine-type=n2-standard-8` to resize.",
            source_url="https://cloud.google.com/compute/docs",
            last_verified=datetime.now(timezone.utc),
            score=0.92,
        )
        mock_retrieval.retrieve_provider_context.return_value = RetrieveProviderContextOutput(
            chunks=[mock_chunk],
            metadata=MagicMock(),
        )

        renderer = RecommendationRenderer(retrieval_service=mock_retrieval)
        candidate = RecommendationCandidate(
            provider="Google",
            resource_type="compute/instance",
            resource_name="projects/p1/zones/z1/instances/analytics-worker-02",
            action_summary="Downsize to n2-standard-8",
            rationale="Average CPU 8.5% with safe 56% headroom",
            estimated_monthly_savings_usd=142.25,
        )

        rendered = renderer.render(candidate)
        self.assertTrue(rendered.used_retrieval)
        self.assertIn("gcloud compute instances set-machine-type", rendered.body)
        self.assertIn("$142.25", rendered.body)

    def test_rag_fallback_when_no_chunks(self) -> None:
        mock_retrieval = MagicMock()
        mock_retrieval.retrieve_provider_context.return_value = RetrieveProviderContextOutput(
            chunks=[],
            metadata=MagicMock(),
        )

        renderer = RecommendationRenderer(retrieval_service=mock_retrieval)
        candidate = RecommendationCandidate(
            provider="Oracle",
            resource_type="compute/instance",
            resource_name="oci-worker-01",
            action_summary="Downsize shape",
            rationale="Underused instance",
            estimated_monthly_savings_usd=50.00,
        )

        rendered = renderer.render(candidate)
        self.assertFalse(rendered.used_retrieval)
        self.assertIn("Provider-specific details unavailable", rendered.body)

    def test_pricing_staleness_warning(self) -> None:
        mock_retrieval = MagicMock()
        # Pricing chunk verified 25 days ago (> 21 days threshold)
        stale_date = datetime.now(timezone.utc) - timedelta(days=25)
        mock_pricing_chunk = RetrievedChunk(
            chunk_id="c-pricing",
            category="pricing",
            provider="Google",
            resource_type="compute/instance",
            content="n2-standard-8 list price is $142.25/month.",
            source_url="https://cloud.google.com/pricing",
            last_verified=stale_date,
            score=0.88,
        )
        mock_retrieval.retrieve_provider_context.return_value = RetrieveProviderContextOutput(
            chunks=[mock_pricing_chunk],
            metadata=MagicMock(),
        )

        config = RecommendationRendererConfig(
            high_savings_warning_threshold_usd=100.0,
            pricing_low_freshness_days=21,
        )
        renderer = RecommendationRenderer(retrieval_service=mock_retrieval, config=config)

        candidate = RecommendationCandidate(
            provider="Google",
            resource_type="compute/instance",
            resource_name="analytics-worker-02",
            action_summary="Downsize to n2-standard-8",
            rationale="High savings opportunity",
            estimated_monthly_savings_usd=142.25,
        )

        rendered = renderer.render(candidate)
        self.assertIn("Pricing evidence is aging", rendered.body)

    def test_guardrail_core_reasoning_no_retrieval(self) -> None:
        """Confirm core analytical summaries operate without calling retrieval."""
        summary = summarize_analysis_without_retrieval(
            anomaly_summary="Compute spend increased 34% WoW on analytics-worker-02",
            forecast_summary="Projected next month spend is $4,200 (Ridge seasonal MAPE: 4.8%)",
        )

        self.assertIn("Anomaly: Compute spend increased 34%", summary)
        self.assertIn("Forecast: Projected next month spend", summary)

    def test_flow_with_rag_rendering(self) -> None:
        mock_repo = MagicMock()
        mock_repo.get_interaction_memory.return_value = []
        mock_repo.get_optimization_history.return_value = []

        mock_retrieval = MagicMock()
        mock_chunk = RetrievedChunk(
            chunk_id="c-001",
            category="architecture",
            provider="Google",
            resource_type="compute/instance",
            content="Execute `gcloud compute instances set-machine-type analytics-worker-02 --machine-type=n2-standard-8`.",
            source_url="https://cloud.google.com",
            last_verified=datetime.now(timezone.utc),
            score=0.95,
        )
        mock_retrieval.retrieve_provider_context.return_value = RetrieveProviderContextOutput(
            chunks=[mock_chunk],
            metadata=MagicMock(),
        )


        renderer = RecommendationRenderer(retrieval_service=mock_retrieval)

        def mock_finops_exec(prompt: str) -> tuple[str, list[dict]]:
            return (
                "Verified spend on analytics-worker-02 is $284.50. Checked get_optimization_history. "
                "Propose rightsize to n2-standard-8 saving $142.25.",
                [
                    {"tool_name": "query_cost_trend", "cost": 284.50},
                    {"tool_name": "get_optimization_history", "recommendation_type": "rightsize"},
                ],
            )

        def mock_sre_exec(prompt: str) -> tuple[str, list[dict]]:
            return (
                "Assessment: Peak P95 CPU is 22%. Downsizing to n2-standard-8 leaves 56% headroom buffer.",
                [{"tool_name": "get_utilization_summaries", "p95_utilization": 22.0}],
            )

        flow = FinOpsFlow(
            memory_repo=mock_repo,
            recommendation_renderer=renderer,
            mock_finops_executor=mock_finops_exec,
            mock_sre_executor=mock_sre_exec,
        )

        result = flow.execute_flow(
            query="Analyze analytics-worker-02 for data-platform",
            team_scope="data-platform",
        )

        self.assertEqual(result.status, FlowStatus.COMPLETED)
        self.assertTrue(result.policy_passed)
        self.assertGreater(result.recommendations_count, 0)
        self.assertIn("Provider-Specific Execution Guidance (RAG Context)", result.final_response)
        self.assertIn("gcloud compute instances set-machine-type", result.final_response)
