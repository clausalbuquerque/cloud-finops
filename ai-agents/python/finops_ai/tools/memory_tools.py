"""Agent Memory Tools for the FinOps Agent.

Reads and writes long-term agent memory in PostgreSQL (finops schema)
to prevent repeating rejected recommendations and store anomaly resolution findings.
"""

from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal
import os
from typing import Any, Sequence
from uuid import uuid4

from crewai.tools import tool

from finops_ai.memory.contracts import (
    AnomalyResolution,
    OptimizationRecommendation,
    RecommendationStatus,
)
from finops_ai.memory.repository import AgentMemoryRepository


def _get_memory_repo() -> AgentMemoryRepository:
    db_url = os.getenv("DATABASE_URL") or "postgresql+psycopg://postgres:postgres123@localhost:5432/cloud_finops"
    return AgentMemoryRepository.from_url(db_url)


_IN_MEMORY_RECOMMENDATIONS: list[dict[str, Any]] = []
_IN_MEMORY_RESOLUTIONS: list[dict[str, Any]] = []


@tool("get_optimization_history")
def get_optimization_history(
    scope: str = "all",
    status: str | None = None,
    resource_id: str | None = None,
) -> list[dict[str, Any]]:
    """Retrieve historical optimization recommendations, lifecycle status, and user rejection reasons.

    CRITICAL: Always invoke this tool before proposing a recommendation to verify that
    the candidate action has not already been rejected or proposed recently.
    """
    scope_team = None if scope == "all" else scope
    try:
        repo = _get_memory_repo()
        history = repo.get_optimization_history(
            scope_team=scope_team,
            status=status,
            resource_id=resource_id,
        )
        return [
            {
                "id": h.id,
                "provider_name": h.provider_name,
                "resource_id": h.resource_id,
                "recommendation_type": h.recommendation_type,
                "status": h.status if isinstance(h.status, str) else h.status.value,
                "rejection_reason": h.rejection_reason,
                "estimated_monthly_savings": float(h.estimated_monthly_savings),
                "confidence_score": h.confidence_score,
                "proposed_at": h.proposed_at.isoformat() if h.proposed_at else None,
                "current_state": h.current_state,
                "proposed_state": h.proposed_state,
            }
            for h in history
        ]
    except Exception:
        # Return in-memory recommendations
        filtered = _IN_MEMORY_RECOMMENDATIONS
        if resource_id:
            filtered = [r for r in filtered if r.get("resource_id") == resource_id]
        if status:
            filtered = [r for r in filtered if r.get("status") == status]
        return filtered


@tool("propose_recommendation")
def propose_recommendation(
    recommendation_type: str,
    resource_id: str,
    current_state: dict[str, Any],
    proposed_state: dict[str, Any],
    estimated_monthly_savings: float,
    scope_team: str | None = None,
    provider_name: str = "GCP",
    resource_type: str = "compute/instance",
    confidence_score: float = 0.90,
) -> dict[str, Any]:
    """Create a new optimization recommendation in 'proposed' status for user review.

    Requires explicit user approval before execution (HITL).
    """
    rec_id = str(uuid4())
    rec_dict = {
        "id": rec_id,
        "provider_name": provider_name,
        "resource_id": resource_id,
        "resource_type": resource_type,
        "recommendation_type": recommendation_type,
        "current_state": current_state,
        "proposed_state": proposed_state,
        "estimated_monthly_savings": round(estimated_monthly_savings, 2),
        "confidence_score": confidence_score,
        "status": "proposed",
        "scope_team": scope_team,
        "proposed_at": datetime.now(timezone.utc).isoformat(),
        "rejection_reason": None,
    }

    try:
        repo = _get_memory_repo()
        rec = OptimizationRecommendation(
            id=rec_id,
            provider_name=provider_name,
            resource_id=resource_id,
            resource_type=resource_type,
            recommendation_type=recommendation_type,
            current_state=current_state,
            proposed_state=proposed_state,
            estimated_monthly_savings=Decimal(str(round(estimated_monthly_savings, 2))),
            confidence_score=confidence_score,
            status=RecommendationStatus.PROPOSED,
            scope_team=scope_team,
            proposed_at=datetime.now(timezone.utc),
        )
        created_id = repo.store_recommendation(rec)
    except Exception:
        _IN_MEMORY_RECOMMENDATIONS.append(rec_dict)
        created_id = rec_id

    return {
        "status": "proposed",
        "recommendation_id": created_id,
        "resource_id": resource_id,
        "estimated_monthly_savings": round(estimated_monthly_savings, 2),
        "message": f"Recommendation '{recommendation_type}' on '{resource_id}' submitted for human review.",
    }


@tool("store_anomaly_resolution")
def store_anomaly_resolution(
    anomaly_id: str,
    root_cause: str,
    resolution_action: str,
    resource_id: str = "",
    dimension: str = "resource_id",
    root_cause_type: str = "misconfiguration",
    is_recurring: bool = False,
    investigation_trace: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Persist anomaly investigation findings and root cause classifications into long-term memory."""
    res_id = str(uuid4())
    try:
        repo = _get_memory_repo()
        res = AnomalyResolution(
            id=res_id,
            anomaly_id=anomaly_id,
            resource_id=resource_id or anomaly_id,
            dimension=dimension,
            root_cause_type=root_cause_type,
            root_cause_description=root_cause,
            resolution_action=resolution_action,
            is_recurring=is_recurring,
            investigation_trace=investigation_trace or {},
        )
        created_id = repo.store_anomaly_resolution(res)
    except Exception:
        _IN_MEMORY_RESOLUTIONS.append(
            {
                "id": res_id,
                "anomaly_id": anomaly_id,
                "root_cause": root_cause,
                "resolution_action": resolution_action,
            }
        )
        created_id = res_id

    return {
        "status": "recorded",
        "resolution_id": created_id,
        "anomaly_id": anomaly_id,
        "message": f"Anomaly resolution for '{anomaly_id}' successfully stored in memory.",
    }

