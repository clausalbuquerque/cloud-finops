from __future__ import annotations

from dataclasses import dataclass
from statistics import mean
from typing import Any


@dataclass(frozen=True)
class DashboardMetrics:
    retrieval_latency_p95_ms: float
    empty_result_rate: float
    stale_result_rate: float
    citation_coverage: float


@dataclass(frozen=True)
class AlertThresholds:
    max_retrieval_failures: int = 0
    max_stale_result_rate: float = 0.25


def compute_dashboard_metrics(events: list[dict[str, Any]]) -> DashboardMetrics:
    retrieval_done = [event for event in events if event.get("event_name") == "retrieval.complete"]
    recommendation_done = [
        event for event in events if event.get("event_name") == "recommendation.complete"
    ]

    latencies = [float(event.get("latency_ms", 0.0)) for event in retrieval_done]
    sorted_latencies = sorted(latencies)
    p95_index = max(0, int(round(0.95 * len(sorted_latencies))) - 1) if sorted_latencies else 0
    p95 = sorted_latencies[p95_index] if sorted_latencies else 0.0

    empty_rate = (
        mean([1.0 if int(event.get("returned_chunks", 0)) == 0 else 0.0 for event in retrieval_done])
        if retrieval_done
        else 0.0
    )

    stale_rate = (
        mean([
            float(event.get("stale_hit_count", 0)) / max(int(event.get("returned_chunks", 0)), 1)
            for event in retrieval_done
        ])
        if retrieval_done
        else 0.0
    )

    citation_coverage = (
        mean([
            1.0 if bool(event.get("used_retrieval", False)) and int(event.get("source_count", 0)) > 0 else 0.0
            for event in recommendation_done
        ])
        if recommendation_done
        else 0.0
    )

    return DashboardMetrics(
        retrieval_latency_p95_ms=float(p95),
        empty_result_rate=float(empty_rate),
        stale_result_rate=float(stale_rate),
        citation_coverage=float(citation_coverage),
    )


def evaluate_alerts(events: list[dict[str, Any]], thresholds: AlertThresholds) -> list[str]:
    alerts: list[str] = []
    retrieval_failures = len([event for event in events if event.get("event_name") == "retrieval.failure"])
    if retrieval_failures > thresholds.max_retrieval_failures:
        alerts.append("retrieval_failure_threshold_exceeded")

    metrics = compute_dashboard_metrics(events)
    if metrics.stale_result_rate > thresholds.max_stale_result_rate:
        alerts.append("stale_result_rate_threshold_exceeded")

    return alerts
