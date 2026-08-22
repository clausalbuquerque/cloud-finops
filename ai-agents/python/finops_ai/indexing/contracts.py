from __future__ import annotations

from dataclasses import dataclass
from typing import Literal


IndexMode = Literal["full", "incremental"]


@dataclass(frozen=True)
class IndexChunksInput:
    mode: IndexMode
    provider: str | None = None


@dataclass(frozen=True)
class IndexError:
    chunk_id: str
    error: str


@dataclass(frozen=True)
class IndexChunksOutput:
    run_id: str
    chunks_embedded: int
    chunks_skipped: int
    chunks_deprecated: int
    embedding_latency_ms: float
    errors: list[IndexError]


@dataclass(frozen=True)
class ChunkToIndex:
    chunk_id: str
    content: str


@dataclass(frozen=True)
class IndexingPlan:
    to_embed: list[ChunkToIndex]
    to_deprecate: list[str]
    skipped: int
