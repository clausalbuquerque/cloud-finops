from __future__ import annotations

from datetime import datetime, timedelta, timezone
import unittest

from finops_ai.agents import RecommendationCandidate, RecommendationRenderer, RecommendationRendererConfig
from finops_ai.embedding.contracts import BatchEmbeddingMetrics, EmbeddingBatchResult, EmbeddingMode
from finops_ai.observability import (
    AlertThresholds,
    InMemoryObservabilitySink,
    compute_dashboard_metrics,
    evaluate_alerts,
    redact_text,
)
from finops_ai.retrieval import (
    ProviderContextRetrievalService,
    RetrievalMetadata,
    RetrievalServiceConfig,
    RetrieveProviderContextInput,
    RetrieveProviderContextOutput,
    RetrievedChunk,
)


class FakeEmbeddingService:
    def embed_texts(self, texts: list[str], mode: EmbeddingMode) -> EmbeddingBatchResult:
        vectors = [[0.1, 0.2, 0.3] for _ in texts]
        metrics = BatchEmbeddingMetrics(total_texts=len(texts), total_batches=1, retries=0, latency_ms=1.0)
        return EmbeddingBatchResult(vectors=vectors, metrics=metrics)


class FakeRetrievalRepository:
    def count_candidates(self, provider: str, resource_type: str, category: str | None, fresh_after: datetime) -> int:
        return 1

    def search_chunks(
        self,
        query_vector: list[float],
        provider: str,
        resource_type: str,
        category: str | None,
        fresh_after: datetime,
        top_k: int,
    ) -> list[RetrievedChunk]:
        return [
            RetrievedChunk(
                chunk_id="kb-1",
                content="Sample pricing guidance",
                score=0.91,
                source_url="https://cloud.google.com/compute/all-pricing",
                last_verified=datetime.now(timezone.utc) - timedelta(days=20),
                category="pricing",
                provider="GCP",
                resource_type="compute/instance",
            )
        ]


class FakeRetrievalService:
    def __init__(self, sink: InMemoryObservabilitySink) -> None:
        self.sink = sink

    def retrieve_provider_context(self, request: RetrieveProviderContextInput) -> RetrieveProviderContextOutput:
        self.sink.emit(
            "retrieval.complete",
            {
                "trace_id": request.trace_id,
                "latency_ms": 50.0,
                "returned_chunks": 1,
                "stale_hit_count": 0,
                "selected_source_urls": ["https://cloud.google.com/compute/all-pricing"],
            },
        )
        return RetrieveProviderContextOutput(
            chunks=[
                RetrievedChunk(
                    chunk_id="kb-2",
                    content="Use machine type guidance.",
                    score=0.88,
                    source_url="https://cloud.google.com/compute/docs/machine-types",
                    last_verified=datetime.now(timezone.utc),
                    category="rightsizing",
                    provider="GCP",
                    resource_type="compute/instance",
                )
            ],
            metadata=RetrievalMetadata(
                total_candidates=1,
                search_latency_ms=50.0,
                freshest_verified=datetime.now(timezone.utc),
            ),
        )


class ObservabilityTests(unittest.TestCase):
    def test_redaction_masks_pii_and_token_shapes(self) -> None:
        text = "contact me at dev@example.com with bearer hf_123456789abcdef and acct 123456789012"
        redacted = redact_text(text)
        self.assertNotIn("dev@example.com", redacted)
        self.assertNotIn("hf_123456789abcdef", redacted)
        self.assertNotIn("123456789012", redacted)
        self.assertIn("<email>", redacted)

    def test_retrieval_service_emits_structured_events_with_trace(self) -> None:
        sink = InMemoryObservabilitySink()
        service = ProviderContextRetrievalService(
            repository=FakeRetrievalRepository(),
            embedding_service=FakeEmbeddingService(),
            config=RetrievalServiceConfig(observability_sink=sink),
        )

        service.retrieve_provider_context(
            RetrieveProviderContextInput(
                provider="GCP",
                resource_type="compute/instance",
                query="send to dev@example.com token hf_123456789abcdef",
                category="pricing",
                top_k=5,
                trace_id="trace-123",
            )
        )

        event_names = [event["event_name"] for event in sink.events]
        self.assertIn("retrieval.start", event_names)
        self.assertIn("retrieval.complete", event_names)
        start = next(event for event in sink.events if event["event_name"] == "retrieval.start")
        complete = next(event for event in sink.events if event["event_name"] == "retrieval.complete")
        self.assertEqual("trace-123", start["trace_id"])
        self.assertEqual("trace-123", complete["trace_id"])
        self.assertNotIn("dev@example.com", start["query_redacted"])

    def test_recommendation_trace_links_to_retrieval(self) -> None:
        sink = InMemoryObservabilitySink()
        renderer = RecommendationRenderer(
            retrieval_service=FakeRetrievalService(sink),
            config=RecommendationRendererConfig(observability_sink=sink),
        )

        renderer.render(
            RecommendationCandidate(
                provider="GCP",
                resource_type="compute/instance",
                resource_name="orders-vm",
                action_summary="Downsize",
                rationale="CPU low",
                estimated_monthly_savings_usd=120.0,
            )
        )

        rec_start = next(event for event in sink.events if event["event_name"] == "recommendation.start")
        rec_done = next(event for event in sink.events if event["event_name"] == "recommendation.complete")
        retr_done = next(event for event in sink.events if event["event_name"] == "retrieval.complete")
        self.assertEqual(rec_start["trace_id"], rec_done["trace_id"])
        self.assertEqual(rec_start["trace_id"], retr_done["trace_id"])

    def test_dashboard_metrics_and_alerts(self) -> None:
        events = [
            {"event_name": "retrieval.complete", "latency_ms": 40.0, "returned_chunks": 0, "stale_hit_count": 0},
            {"event_name": "retrieval.complete", "latency_ms": 80.0, "returned_chunks": 2, "stale_hit_count": 1},
            {"event_name": "retrieval.failure", "error": "timeout"},
            {"event_name": "recommendation.complete", "used_retrieval": True, "source_count": 2},
        ]

        metrics = compute_dashboard_metrics(events)
        self.assertGreaterEqual(metrics.retrieval_latency_p95_ms, 40.0)
        self.assertGreater(metrics.empty_result_rate, 0.0)
        self.assertGreater(metrics.stale_result_rate, 0.0)
        self.assertGreater(metrics.citation_coverage, 0.0)

        alerts = evaluate_alerts(events, AlertThresholds(max_retrieval_failures=0, max_stale_result_rate=0.1))
        self.assertIn("retrieval_failure_threshold_exceeded", alerts)
        self.assertIn("stale_result_rate_threshold_exceeded", alerts)


if __name__ == "__main__":
    unittest.main()
