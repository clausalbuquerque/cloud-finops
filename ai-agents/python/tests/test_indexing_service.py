from __future__ import annotations

from dataclasses import dataclass
import unittest

from finops_ai.embedding.contracts import BatchEmbeddingMetrics, EmbeddingBatchResult, EmbeddingMode
from finops_ai.indexing import ChunkIndexerService, IndexChunksInput, IndexingPlan


class FakeEmbeddingService:
    def __init__(self) -> None:
        self.calls = 0

    def embed_texts(self, texts: list[str], mode: EmbeddingMode) -> EmbeddingBatchResult:
        self.calls += 1
        vectors = [[1.0, 2.0, 3.0] for _ in texts]
        metrics = BatchEmbeddingMetrics(
            total_texts=len(texts),
            total_batches=1,
            retries=0,
            latency_ms=1.0,
        )
        return EmbeddingBatchResult(vectors=vectors, metrics=metrics)


@dataclass(frozen=True)
class FakeChunk:
    chunk_id: str
    content: str


class FakeRepository:
    def __init__(self) -> None:
        self.upserted: list[str] = []
        self.deleted_inputs: list[str] = []
        self.completed: list[tuple[str, str, int, int, int, list[dict[str, str]]]] = []

    def create_run(self, source_id: str | None, run_type: str = "index") -> str:
        return "index-run-1"

    def complete_run(
        self,
        run_id: str,
        status: str,
        chunks_created: int,
        chunks_updated: int,
        chunks_deprecated: int,
        errors: list[dict[str, str]],
    ) -> None:
        self.completed.append((run_id, status, chunks_created, chunks_updated, chunks_deprecated, errors))

    def get_indexing_plan(self, mode: str, provider: str | None, model_version: str) -> IndexingPlan:
        return IndexingPlan(
            to_embed=[
                FakeChunk(chunk_id="c1", content="chunk one"),
                FakeChunk(chunk_id="c2", content="chunk two"),
            ],
            to_deprecate=["c9"],
            skipped=3,
        )

    def upsert_embedding(self, chunk_id: str, vector: list[float], model_version: str) -> None:
        self.upserted.append(chunk_id)

    def delete_embeddings_for_chunks(self, chunk_ids: list[str]) -> int:
        self.deleted_inputs.extend(chunk_ids)
        return len(chunk_ids)


class FailingEmbeddingService(FakeEmbeddingService):
    def embed_texts(self, texts: list[str], mode: EmbeddingMode) -> EmbeddingBatchResult:
        raise RuntimeError("embedding failed")


class IndexingServiceTests(unittest.TestCase):
    def test_incremental_indexing_embeds_skips_and_deprecates(self) -> None:
        repo = FakeRepository()
        service = ChunkIndexerService(repository=repo, embedding_service=FakeEmbeddingService())

        result = service.index_chunks(IndexChunksInput(mode="incremental", provider="GCP"))

        self.assertEqual("index-run-1", result.run_id)
        self.assertEqual(2, result.chunks_embedded)
        self.assertEqual(3, result.chunks_skipped)
        self.assertEqual(1, result.chunks_deprecated)
        self.assertEqual(0, len(result.errors))
        self.assertEqual(["c1", "c2"], repo.upserted)
        self.assertEqual(["c9"], repo.deleted_inputs)
        self.assertEqual("completed", repo.completed[0][1])

    def test_indexing_failure_collects_errors(self) -> None:
        repo = FakeRepository()
        service = ChunkIndexerService(repository=repo, embedding_service=FailingEmbeddingService())

        result = service.index_chunks(IndexChunksInput(mode="full", provider=None))

        self.assertEqual(0, result.chunks_embedded)
        self.assertEqual(2, len(result.errors))
        self.assertEqual("failed", repo.completed[0][1])


if __name__ == "__main__":
    unittest.main()
