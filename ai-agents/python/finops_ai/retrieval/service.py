from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from time import perf_counter
from typing import Protocol
from uuid import uuid4

from finops_ai.embedding import EmbeddingMode, EmbeddingService
from finops_ai.observability import LoggingObservabilitySink, ObservabilitySink, redact_text

from .contracts import (
    RetrieveProviderContextInput,
    RetrieveProviderContextOutput,
    RetrievalMetadata,
    RetrievedChunk,
)
from .freshness import FreshnessPenaltyConfig, chunk_age_days, penalized_score


class RetrievalRepositoryProtocol(Protocol):
    def search_chunks(
        self,
        query_vector: list[float],
        provider: str,
        resource_type: str,
        category: str | None,
        fresh_after: datetime,
        top_k: int,
    ) -> list[RetrievedChunk]: ...

    def count_candidates(
        self,
        provider: str,
        resource_type: str,
        category: str | None,
        fresh_after: datetime,
    ) -> int: ...


@dataclass(frozen=True)
class RetrievalServiceConfig:
    min_score: float = 0.0
    freshness_penalty: FreshnessPenaltyConfig = FreshnessPenaltyConfig()
    observability_sink: ObservabilitySink | None = None


class ProviderContextRetrievalService:
    def __init__(
        self,
        repository: RetrievalRepositoryProtocol,
        embedding_service: EmbeddingService,
        config: RetrievalServiceConfig | None = None,
    ) -> None:
        self._repository = repository
        self._embedding_service = embedding_service
        self._config = config or RetrievalServiceConfig()
        self._sink = self._config.observability_sink or LoggingObservabilitySink()

    def retrieve_provider_context(
        self,
        request: RetrieveProviderContextInput,
    ) -> RetrieveProviderContextOutput:
        trace_id = request.trace_id or str(uuid4())
        fresh_after = datetime.now(timezone.utc) - timedelta(days=request.max_age_days)

        self._sink.emit(
            "retrieval.start",
            {
                "trace_id": trace_id,
                "parent_step": request.parent_step,
                "provider": request.provider,
                "resource_type": request.resource_type,
                "category": request.category,
                "top_k": request.top_k,
                "max_age_days": request.max_age_days,
                "query_redacted": redact_text(request.query),
            },
        )

        start = perf_counter()
        try:
            vector_result = self._embedding_service.embed_texts([request.query], EmbeddingMode.QUERY)
        except Exception as exc:
            self._sink.emit(
                "retrieval.failure",
                {
                    "trace_id": trace_id,
                    "provider": request.provider,
                    "resource_type": request.resource_type,
                    "error": str(exc),
                },
            )
            raise
        query_vector = vector_result.vectors[0]

        candidates = self._repository.count_candidates(
            provider=request.provider,
            resource_type=request.resource_type,
            category=request.category,
            fresh_after=fresh_after,
        )

        chunks = self._repository.search_chunks(
            query_vector=query_vector,
            provider=request.provider,
            resource_type=request.resource_type,
            category=request.category,
            fresh_after=fresh_after,
            top_k=request.top_k,
        )

        now = datetime.now(timezone.utc)
        scored_chunks = [
            RetrievedChunk(
                chunk_id=chunk.chunk_id,
                content=chunk.content,
                score=penalized_score(
                    base_score=chunk.score,
                    age_days=chunk_age_days(last_verified=chunk.last_verified, now=now),
                    config=self._config.freshness_penalty,
                ),
                source_url=chunk.source_url,
                last_verified=chunk.last_verified,
                category=chunk.category,
                provider=chunk.provider,
                resource_type=chunk.resource_type,
            )
            for chunk in chunks
        ]

        filtered = [chunk for chunk in scored_chunks if chunk.score >= self._config.min_score]
        filtered.sort(key=lambda chunk: chunk.score, reverse=True)
        freshest_verified = max((chunk.last_verified for chunk in filtered), default=None)
        stale_hit_count = len(
            [
                chunk
                for chunk in filtered
                if chunk_age_days(last_verified=chunk.last_verified, now=now)
                > (request.max_age_days * self._config.freshness_penalty.penalty_start_ratio)
            ]
        )
        latency_ms = (perf_counter() - start) * 1000

        self._sink.emit(
            "retrieval.complete",
            {
                "trace_id": trace_id,
                "provider": request.provider,
                "resource_type": request.resource_type,
                "category": request.category,
                "top_k": request.top_k,
                "candidate_count": candidates,
                "returned_chunks": len(filtered),
                "latency_ms": round(latency_ms, 2),
                "stale_hit_count": stale_hit_count,
                "selected_source_urls": [chunk.source_url for chunk in filtered],
            },
        )

        return RetrieveProviderContextOutput(
            chunks=filtered,
            metadata=RetrievalMetadata(
                total_candidates=candidates,
                search_latency_ms=latency_ms,
                freshest_verified=freshest_verified,
            ),
        )
