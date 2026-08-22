from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class SLOThresholds:
    max_retrieval_latency_ms: float = 1500.0
    max_recommendation_latency_ms: float = 2000.0


@dataclass(frozen=True)
class SLOEvaluation:
    passed: bool
    violations: list[str]


def evaluate_slos(
    retrieval_latency_ms: float,
    recommendation_latency_ms: float,
    thresholds: SLOThresholds,
) -> SLOEvaluation:
    violations: list[str] = []

    if retrieval_latency_ms > thresholds.max_retrieval_latency_ms:
        violations.append(
            f"retrieval_latency_exceeded:{retrieval_latency_ms:.2f}>{thresholds.max_retrieval_latency_ms:.2f}"
        )

    if recommendation_latency_ms > thresholds.max_recommendation_latency_ms:
        violations.append(
            "recommendation_latency_exceeded:"
            f"{recommendation_latency_ms:.2f}>{thresholds.max_recommendation_latency_ms:.2f}"
        )

    return SLOEvaluation(passed=not violations, violations=violations)
