from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Protocol

from .contracts import RetrievedChunk


@dataclass(frozen=True)
class ReverificationRequest:
    chunk_id: str
    source_url: str
    provider: str
    resource_type: str
    reason: str
    observed_drift_pct: float
    estimated_monthly_savings_usd: float
    actual_monthly_savings_usd: float
    requested_at: datetime


class ReverificationQueueProtocol(Protocol):
    def enqueue(self, request: ReverificationRequest) -> None: ...


def estimate_drift_pct(estimated_monthly_savings_usd: float, actual_monthly_savings_usd: float) -> float:
    denominator = max(abs(estimated_monthly_savings_usd), 1e-6)
    return abs(actual_monthly_savings_usd - estimated_monthly_savings_usd) / denominator * 100.0


def trigger_reverification_on_drift(
    chunks: list[RetrievedChunk],
    estimated_monthly_savings_usd: float,
    actual_monthly_savings_usd: float,
    queue: ReverificationQueueProtocol,
    drift_threshold_pct: float = 10.0,
    now: datetime | None = None,
) -> int:
    drift_pct = estimate_drift_pct(
        estimated_monthly_savings_usd=estimated_monthly_savings_usd,
        actual_monthly_savings_usd=actual_monthly_savings_usd,
    )
    if drift_pct <= drift_threshold_pct:
        return 0

    effective_now = now or datetime.now(timezone.utc)
    enqueue_count = 0
    for chunk in chunks:
        queue.enqueue(
            ReverificationRequest(
                chunk_id=chunk.chunk_id,
                source_url=chunk.source_url,
                provider=chunk.provider,
                resource_type=chunk.resource_type,
                reason="post_execution_drift_exceeded",
                observed_drift_pct=drift_pct,
                estimated_monthly_savings_usd=estimated_monthly_savings_usd,
                actual_monthly_savings_usd=actual_monthly_savings_usd,
                requested_at=effective_now,
            )
        )
        enqueue_count += 1

    return enqueue_count
