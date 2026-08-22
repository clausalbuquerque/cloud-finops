from __future__ import annotations

from datetime import datetime, timedelta, timezone
import unittest

from finops_ai.embedding.contracts import BatchEmbeddingMetrics, EmbeddingBatchResult, EmbeddingMode
from finops_ai.retrieval import (
    ProviderContextRetrievalService,
    RetrieveProviderContextInput,
    RetrievedChunk,
)


class FakeEmbeddingService:
    def embed_texts(self, texts: list[str], mode: EmbeddingMode) -> EmbeddingBatchResult:
        vectors = [[0.1, 0.2, 0.3] for _ in texts]
        metrics = BatchEmbeddingMetrics(total_texts=len(texts), total_batches=1, retries=0, latency_ms=1.0)
        return EmbeddingBatchResult(vectors=vectors, metrics=metrics)


class FakeRetrievalRepository:
    def __init__(self) -> None:
        now = datetime.now(timezone.utc)
        self._chunks = [
            RetrievedChunk(
                chunk_id="gcp-1",
                content="Use n2-standard-4 for moderate workloads",
                score=0.92,
                source_url="https://cloud.google.com/compute/all-pricing",
                last_verified=now - timedelta(days=3),
                category="pricing",
                provider="GCP",
                resource_type="compute/instance",
            ),
            RetrievedChunk(
                chunk_id="gcp-2",
                content="Use gcloud compute instances set-machine-type",
                score=0.81,
                source_url="https://cloud.google.com/sdk/gcloud/reference/compute/instances/set-machine-type",
                last_verified=now - timedelta(days=2),
                category="cli",
                provider="GCP",
                resource_type="compute/instance",
            ),
            RetrievedChunk(
                chunk_id="gcp-3",
                content="Older pricing guidance",
                score=0.95,
                source_url="https://cloud.google.com/compute/legacy-pricing",
                last_verified=now - timedelta(days=25),
                category="pricing",
                provider="GCP",
                resource_type="compute/instance",
            ),
            RetrievedChunk(
                chunk_id="gcp-4",
                content="Expired pricing guidance",
                score=0.99,
                source_url="https://cloud.google.com/compute/expired-pricing",
                last_verified=now - timedelta(days=45),
                category="pricing",
                provider="GCP",
                resource_type="compute/instance",
            ),
            RetrievedChunk(
                chunk_id="aws-1",
                content="AWS c6i pricing",
                score=0.99,
                source_url="https://aws.amazon.com/ec2/pricing/",
                last_verified=now - timedelta(days=1),
                category="pricing",
                provider="AWS",
                resource_type="compute/instance",
            ),
        ]

    def count_candidates(self, provider: str, resource_type: str, category: str | None, fresh_after: datetime) -> int:
        return len(
            [
                c
                for c in self._chunks
                if c.provider == provider
                and c.resource_type == resource_type
                and c.last_verified >= fresh_after
                and (category is None or c.category == category)
            ]
        )

    def search_chunks(
        self,
        query_vector: list[float],
        provider: str,
        resource_type: str,
        category: str | None,
        fresh_after: datetime,
        top_k: int,
    ) -> list[RetrievedChunk]:
        rows = [
            c
            for c in self._chunks
            if c.provider == provider
            and c.resource_type == resource_type
            and c.last_verified >= fresh_after
            and (category is None or c.category == category)
        ]
        return sorted(rows, key=lambda item: item.score, reverse=True)[:top_k]


class RetrievalServiceTests(unittest.TestCase):
    def test_cross_provider_isolation(self) -> None:
        service = ProviderContextRetrievalService(
            repository=FakeRetrievalRepository(),
            embedding_service=FakeEmbeddingService(),
        )

        result = service.retrieve_provider_context(
            RetrieveProviderContextInput(
                provider="GCP",
                resource_type="compute/instance",
                query="right size vm",
                top_k=5,
            )
        )

        self.assertEqual(3, len(result.chunks))
        self.assertTrue(all(chunk.provider == "GCP" for chunk in result.chunks))
        self.assertNotIn("gcp-4", [chunk.chunk_id for chunk in result.chunks])

    def test_expected_ranking_and_category_filter(self) -> None:
        service = ProviderContextRetrievalService(
            repository=FakeRetrievalRepository(),
            embedding_service=FakeEmbeddingService(),
        )

        result = service.retrieve_provider_context(
            RetrieveProviderContextInput(
                provider="GCP",
                resource_type="compute/instance",
                query="pricing",
                category="pricing",
                top_k=5,
            )
        )

        self.assertEqual(2, len(result.chunks))
        self.assertEqual("gcp-1", result.chunks[0].chunk_id)
        self.assertEqual(2, result.metadata.total_candidates)

    def test_freshness_penalty_demotes_aging_chunk(self) -> None:
        service = ProviderContextRetrievalService(
            repository=FakeRetrievalRepository(),
            embedding_service=FakeEmbeddingService(),
        )

        result = service.retrieve_provider_context(
            RetrieveProviderContextInput(
                provider="GCP",
                resource_type="compute/instance",
                query="pricing",
                top_k=5,
            )
        )

        self.assertEqual("gcp-1", result.chunks[0].chunk_id)
        gcp3 = next(chunk for chunk in result.chunks if chunk.chunk_id == "gcp-3")
        self.assertLess(gcp3.score, 0.95)


if __name__ == "__main__":
    unittest.main()
