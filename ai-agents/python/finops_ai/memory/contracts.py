"""Data contracts for Agent Long-Term Memory (PostgreSQL).

Defines typed dataclasses for optimization history, anomaly resolutions,
infrastructure baselines, and interaction memory.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any
from uuid import uuid4


class RecommendationStatus(str, Enum):
    PROPOSED = "proposed"
    APPROVED = "approved"
    REJECTED = "rejected"
    EXECUTED = "executed"
    ROLLED_BACK = "rolled_back"
    EXPIRED = "expired"


@dataclass
class OptimizationRecommendation:
    """Represents an optimization recommendation in long-term memory."""

    resource_id: str
    resource_type: str
    recommendation_type: str
    current_state: dict[str, Any]
    proposed_state: dict[str, Any]
    estimated_monthly_savings: float
    confidence_score: float
    id: str = field(default_factory=lambda: str(uuid4()))
    provider_name: str = "GCP"
    actual_monthly_savings: float | None = None
    sre_assessment: dict[str, Any] | None = None
    status: RecommendationStatus | str = RecommendationStatus.PROPOSED

    rejection_reason: str | None = None
    scope_team: str | None = None
    flow_id: str | None = None
    proposed_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    resolved_at: datetime | None = None
    executed_at: datetime | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class AnomalyResolution:
    """Represents a root-cause investigation record for cost anomalies."""

    anomaly_id: str
    resource_id: str
    dimension: str
    root_cause_type: str
    root_cause_description: str
    id: str = field(default_factory=lambda: str(uuid4()))
    provider_name: str = "GCP"
    resolution_action: str | None = None
    is_recurring: bool = false if False else False
    recurrence_count: int = 1
    investigation_trace: dict[str, Any] | None = None
    resolved_by: str | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class InfrastructureBaseline:
    """Represents an interpreted workload baseline to prevent false-positive alerts."""

    resource_id: str
    metric_name: str
    baseline_type: str
    expected_pattern: dict[str, Any]
    id: str = field(default_factory=lambda: str(uuid4()))
    tracked_resource_id: str | None = None
    provider_name: str = "GCP"
    suppress_underuse_alerts: bool = False
    confidence_score: float = 1.0
    evidence: dict[str, Any] | None = None
    established_by: str = "agent_inferred"
    last_validated: datetime | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class AgentInteractionMemory:
    """Represents cross-session interaction context and key findings."""

    session_id: str
    user_id: str
    agent_type: str
    interaction_summary: str
    id: str = field(default_factory=lambda: str(uuid4()))
    key_findings: dict[str, Any] | None = None
    follow_up_items: list[dict[str, Any]] | dict[str, Any] | None = None
    scope_context: dict[str, Any] | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

