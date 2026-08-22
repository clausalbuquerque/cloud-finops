from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class RecommendationCandidate:
    provider: str
    resource_type: str
    resource_name: str
    action_summary: str
    rationale: str
    estimated_monthly_savings_usd: float


@dataclass(frozen=True)
class RenderedRecommendation:
    title: str
    body: str
    used_retrieval: bool
    fallback_note: str | None
