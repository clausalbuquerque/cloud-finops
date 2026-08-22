from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone


def chunk_age_days(last_verified: datetime, now: datetime | None = None) -> float:
    effective_now = now or datetime.now(timezone.utc)
    return max(0.0, (effective_now - last_verified).total_seconds() / 86400.0)


@dataclass(frozen=True)
class FreshnessPenaltyConfig:
    max_age_days: int = 30
    penalty_start_ratio: float = 0.5
    max_penalty: float = 0.35


def freshness_penalty(age_days: float, config: FreshnessPenaltyConfig) -> float:
    start_days = config.max_age_days * config.penalty_start_ratio
    if age_days <= start_days:
        return 0.0
    if age_days >= config.max_age_days:
        return config.max_penalty

    span = max(config.max_age_days - start_days, 1e-6)
    progress = (age_days - start_days) / span
    return min(config.max_penalty, max(0.0, progress * config.max_penalty))


def penalized_score(base_score: float, age_days: float, config: FreshnessPenaltyConfig) -> float:
    penalty = freshness_penalty(age_days, config)
    return base_score * (1.0 - penalty)
