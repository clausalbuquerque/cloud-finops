from __future__ import annotations

from datetime import datetime, timedelta, timezone
import unittest

from finops_ai.agents import RecommendationCandidate, RecommendationRenderer
from finops_ai.retrieval import RetrieveProviderContextOutput, RetrievalMetadata, RetrievedChunk


class FakeRetrievalService:
    def __init__(self, chunks: list[RetrievedChunk]) -> None:
        self._chunks = chunks

    def retrieve_provider_context(self, request):  # noqa: ANN001
        return RetrieveProviderContextOutput(
            chunks=self._chunks,
            metadata=RetrievalMetadata(
                total_candidates=len(self._chunks),
                search_latency_ms=4.2,
                freshest_verified=datetime.now(timezone.utc),
            ),
        )


class RecommendationRendererTests(unittest.TestCase):
    def test_uses_retrieval_context_for_rendering(self) -> None:
        chunk = RetrievedChunk(
            chunk_id="kb1",
            content="For N2 workloads, downgrade to n2-standard-4 when avg CPU < 30%.",
            score=0.88,
            source_url="https://cloud.google.com/compute/docs/machine-types",
            last_verified=datetime.now(timezone.utc),
            category="rightsizing",
            provider="GCP",
            resource_type="compute/instance",
        )
        renderer = RecommendationRenderer(retrieval_service=FakeRetrievalService([chunk]))

        output = renderer.render(
            RecommendationCandidate(
                provider="GCP",
                resource_type="compute/instance",
                resource_name="orders-vm-1",
                action_summary="Downsize machine type",
                rationale="CPU under-utilized for 14 days",
                estimated_monthly_savings_usd=73.42,
            )
        )

        self.assertTrue(output.used_retrieval)
        self.assertIn("Provider context", output.body)
        self.assertIn("cloud.google.com", output.body)

    def test_fallback_when_no_confident_context(self) -> None:
        low_score_chunk = RetrievedChunk(
            chunk_id="kb2",
            content="Generic suggestion",
            score=0.10,
            source_url="https://example.com",
            last_verified=datetime.now(timezone.utc),
            category="general",
            provider="GCP",
            resource_type="compute/instance",
        )
        renderer = RecommendationRenderer(retrieval_service=FakeRetrievalService([low_score_chunk]))

        output = renderer.render(
            RecommendationCandidate(
                provider="GCP",
                resource_type="compute/instance",
                resource_name="orders-vm-2",
                action_summary="Downsize machine type",
                rationale="CPU under-utilized for 14 days",
                estimated_monthly_savings_usd=55.0,
            )
        )

        self.assertFalse(output.used_retrieval)
        self.assertIsNotNone(output.fallback_note)
        self.assertIn("Provider-specific details unavailable", output.body)

    def test_adds_warning_for_high_savings_with_aging_pricing_context(self) -> None:
        stale_pricing_chunk = RetrievedChunk(
            chunk_id="kb3",
            content="Pricing signal from cached catalog.",
            score=0.87,
            source_url="https://cloud.google.com/pricing/list",
            last_verified=datetime.now(timezone.utc) - timedelta(days=24),
            category="pricing",
            provider="GCP",
            resource_type="compute/instance",
        )
        renderer = RecommendationRenderer(retrieval_service=FakeRetrievalService([stale_pricing_chunk]))

        output = renderer.render(
            RecommendationCandidate(
                provider="GCP",
                resource_type="compute/instance",
                resource_name="orders-vm-3",
                action_summary="Downsize machine type",
                rationale="CPU under-utilized for 30 days",
                estimated_monthly_savings_usd=250.0,
            )
        )

        self.assertTrue(output.used_retrieval)
        self.assertIsNotNone(output.fallback_note)
        self.assertIn("Warning: Pricing evidence is aging", output.body)


if __name__ == "__main__":
    unittest.main()
