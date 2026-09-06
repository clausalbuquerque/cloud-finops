"""Data contracts for Human-in-the-Loop (HITL) approval workflows."""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field


class ApprovalStatus(str, Enum):
    PROPOSED = "proposed"
    APPROVED = "approved"
    REJECTED = "rejected"
    NEEDS_REVISION = "needs_revision"
    EXECUTED = "executed"
    ROLLED_BACK = "rolled_back"
    FAILED = "failed"
    EXPIRED = "expired"


class ApprovalOutcome(str, Enum):
    APPROVED = "approved"
    REJECTED = "rejected"
    NEEDS_REVISION = "needs_revision"


class HumanFeedbackDecision(BaseModel):
    """Payload representing a human reviewer's evaluation of a recommendation."""

    recommendation_id: str = Field(description="Unique ID of the optimization recommendation")
    reviewer_id: str = Field(description="Identifier or email of the human reviewer")
    reviewer_role: str = Field(default="finops_engineer", description="Role/authority of the reviewer")
    outcome: ApprovalOutcome = Field(description="Review outcome: approved, rejected, or needs_revision")
    feedback_notes: str | None = Field(default=None, description="Explanation, conditions, or revision instructions")
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class ExecutionResult(BaseModel):
    """Result of executing an approved cloud infrastructure optimization action."""

    recommendation_id: str
    resource_id: str
    status: ApprovalStatus
    execution_command: str
    rollback_command: str
    executed_by: str
    executed_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    projected_monthly_savings: float
    actual_monthly_savings: float | None = None
    drift_detected: bool = False
    drift_pct: float | None = None
    audit_trace_id: str = Field(default_factory=lambda: str(uuid4()))
    error_message: str | None = None


class RollbackResult(BaseModel):
    """Result of reverting an executed recommendation back to its baseline configuration."""

    recommendation_id: str
    resource_id: str
    status: ApprovalStatus = ApprovalStatus.ROLLED_BACK
    restored_sku: str
    rollback_command: str
    reason: str
    rolled_back_by: str
    rolled_back_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    audit_trace_id: str = Field(default_factory=lambda: str(uuid4()))
    success: bool = True
    error_message: str | None = None

