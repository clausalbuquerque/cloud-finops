from __future__ import annotations

from dataclasses import dataclass
from time import perf_counter
from typing import Protocol

from finops_ai.embedding import EmbeddingMode, EmbeddingService

from .contracts import IndexChunksInput, IndexChunksOutput, IndexError


class IndexingRepositoryProtocol(Protocol):
    def create_run(self, source_id: str | None, run_type: str = "index") -> str: ...

    def complete_run(
        self,
        run_id: str,
        status: str,
        chunks_created: int,
        chunks_updated: int,
        chunks_deprecated: int,
        errors: list[dict[str, str]],
    ) -> None: ...

    def get_indexing_plan(self, mode: str, provider: str | None, model_version: str): ...

    def upsert_embedding(self, chunk_id: str, vector: list[float], model_version: str) -> None: ...

    def delete_embeddings_for_chunks(self, chunk_ids: list[str]) -> int: ...


@dataclass(frozen=True)
class IndexingServiceConfig:
    model_version: str = "nomic-ai/nomic-embed-text-v1.5"


class ChunkIndexerService:
    def __init__(
        self,
        repository: IndexingRepositoryProtocol,
        embedding_service: EmbeddingService,
        config: IndexingServiceConfig | None = None,
    ) -> None:
        self._repository = repository
        self._embedding_service = embedding_service
        self._config = config or IndexingServiceConfig()

    def index_chunks(self, request: IndexChunksInput) -> IndexChunksOutput:
        run_id = self._repository.create_run(source_id=request.provider, run_type="index")
        errors: list[IndexError] = []

        plan = self._repository.get_indexing_plan(
            mode=request.mode,
            provider=request.provider,
            model_version=self._config.model_version,
        )

        start = perf_counter()
        embedded = 0
        for chunk in plan.to_embed:
            try:
                result = self._embedding_service.embed_texts([chunk.content], EmbeddingMode.INDEX)
                self._repository.upsert_embedding(
                    chunk_id=chunk.chunk_id,
                    vector=result.vectors[0],
                    model_version=self._config.model_version,
                )
                embedded += 1
            except Exception as exc:
                errors.append(IndexError(chunk_id=chunk.chunk_id, error=str(exc)))

        deprecated = self._repository.delete_embeddings_for_chunks(plan.to_deprecate)
        latency_ms = (perf_counter() - start) * 1000

        status = "completed" if not errors else "failed"
        self._repository.complete_run(
            run_id=run_id,
            status=status,
            chunks_created=embedded,
            chunks_updated=0,
            chunks_deprecated=deprecated,
            errors=[error.__dict__ for error in errors],
        )

        return IndexChunksOutput(
            run_id=run_id,
            chunks_embedded=embedded,
            chunks_skipped=plan.skipped,
            chunks_deprecated=deprecated,
            embedding_latency_ms=latency_ms,
            errors=errors,
        )
