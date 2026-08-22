from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from time import perf_counter
from typing import Callable


class EmbeddingMode(str, Enum):
    INDEX = "index"
    QUERY = "query"


@dataclass(frozen=True)
class BatchEmbeddingMetrics:
    total_texts: int
    total_batches: int
    retries: int
    latency_ms: float


@dataclass(frozen=True)
class EmbeddingBatchResult:
    vectors: list[list[float]]
    metrics: BatchEmbeddingMetrics


class EmbeddingRuntimeError(RuntimeError):
    """Raised when embedding generation fails after retries."""


class EmbeddingTimeoutError(TimeoutError):
    """Raised when a backend call exceeds configured timeout."""


def timed(callable_fn: Callable[[], list[list[float]]]) -> tuple[list[list[float]], float]:
    start = perf_counter()
    result = callable_fn()
    latency_ms = (perf_counter() - start) * 1000
    return result, latency_ms
