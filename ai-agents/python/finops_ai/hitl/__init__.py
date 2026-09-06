"""Human-in-the-Loop (HITL) approval and action execution module."""

from .approval_engine import ApprovalEngine
from .contracts import (
    ApprovalOutcome,
    ApprovalStatus,
    ExecutionResult,
    HumanFeedbackDecision,
)

__all__ = [
    "ApprovalEngine",
    "ApprovalStatus",
    "ApprovalOutcome",
    "HumanFeedbackDecision",
    "ExecutionResult",
]

