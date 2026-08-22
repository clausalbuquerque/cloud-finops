from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class RetrieveProviderContextInput:
    provider: str
    resource_type: str
    query: str
    top_k: int = 5
    category: str | None = None
    max_age_days: int = 30
    trace_id: str | None = None
    parent_step: str = "agent.recommendation"


@dataclass(frozen=True)
class RetrievedChunk:
    content: str
    score: float
    source_url: str
    last_verified: datetime
    category: str
    provider: str
    resource_type: str
    chunk_id: str


@dataclass(frozen=True)
class RetrievalMetadata:
    total_candidates: int
    search_latency_ms: float
    freshest_verified: datetime | None


@dataclass(frozen=True)
class RetrieveProviderContextOutput:
    chunks: list[RetrievedChunk]
    metadata: RetrievalMetadata
