"""State and contracts for the CrewAI FinOps Orchestration Flow."""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field

from finops_ai.judges.contracts import JudgeEvaluationReport


class TriggerType(str, Enum):
    INTERACTIVE = "interactive"
    SCHEDULED_DIGEST = "scheduled_digest"
    ANOMALY_WEBHOOK = "anomaly_webhook"


class FlowStatus(str, Enum):
    INITIALIZED = "initialized"
    FINOPS_ANALYSIS = "finops_analysis"
    SRE_ASSESSMENT = "sre_assessment"
    POLICY_GATING = "policy_gating"
    COMPLETED = "completed"
    FAILED_CLOSED = "failed_closed"
    ESCALATED = "escalated"


class PolicyGateResult(BaseModel):
    """Result of an individual policy gate evaluation."""

    gate_name: str
    passed: bool
    reason: str
    fail_closed: bool = False
    details: dict[str, Any] = Field(default_factory=dict)


class FinOpsOrchestrationState(BaseModel):
    """Persisted state maintained throughout the FinOps Flow execution."""

    session_id: str = Field(default_factory=lambda: str(uuid4()))
    trace_id: str = Field(default_factory=lambda: str(uuid4()))
    user_id: str = "default_user"
    team_scope: str | None = None
    query: str = ""
    trigger_type: TriggerType = TriggerType.INTERACTIVE

    # Memory & Context
    cross_turn_context: dict[str, Any] = Field(default_factory=dict)
    short_term_memory: list[dict[str, Any]] = Field(default_factory=list)
    compressed_context: str | None = None

    # Specialist outputs & Judge reports
    finops_output: str | None = None
    finops_report: JudgeEvaluationReport | None = None
    needs_infra_assessment: bool = False
    target_resource_ids: list[str] = Field(default_factory=list)

    sre_output: str | None = None
    sre_report: JudgeEvaluationReport | None = None

    # Deterministic Confidence
    calibrated_confidence_report: Any | None = None

    # Policy Gates
    policy_gates: list[PolicyGateResult] = Field(default_factory=list)
    policy_passed: bool = True
    policy_violations: list[str] = Field(default_factory=list)

    # Output assembly & HITL
    rendered_recommendations: list[dict[str, Any]] = Field(default_factory=list)
    autonomy_tier: str | None = None
    blast_radius_classification: dict[str, Any] | None = None
    can_be_batched: bool = False
    final_response: str | None = None
    status: FlowStatus = FlowStatus.INITIALIZED
    started_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    completed_at: datetime | None = None


class FlowExecutionResult(BaseModel):
    """Final output emitted by the FinOps Orchestration Flow."""

    session_id: str
    trace_id: str
    status: FlowStatus
    final_response: str
    policy_passed: bool
    policy_violations: list[str] = Field(default_factory=list)
    finops_score: int | None = None
    sre_score: int | None = None
    calibrated_confidence_report: Any | None = None
    autonomy_tier: str | None = None
    blast_radius_classification: dict[str, Any] | None = None
    can_be_batched: bool = False
    recommendations_count: int = 0
    needs_human_review: bool = False

