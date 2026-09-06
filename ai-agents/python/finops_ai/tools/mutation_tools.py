"""Provider Mutation Tools for Approved Action Execution.

All tools enforce strict Human-in-the-Loop approval verification before generating
or running infrastructure mutation commands.
"""

from __future__ import annotations

from typing import Any

from crewai.tools import tool

from finops_ai.hitl.approval_engine import ApprovalEngine

_default_engine: ApprovalEngine | None = None


def _get_engine() -> ApprovalEngine:
    global _default_engine
    if _default_engine is None:
        _default_engine = ApprovalEngine()
    return _default_engine


@tool("execute_recommendation")
def execute_recommendation(
    recommendation_id: str,
    executor_role: str = "platform_engineer",
    dry_run: bool = True,
) -> dict[str, Any]:
    """Execute an approved optimization recommendation.

    Fails closed if the recommendation has not received human authorization.
    """
    engine = _get_engine()
    try:
        res = engine.execute(
            recommendation_id=recommendation_id,
            executor_id=executor_role,
            dry_run=dry_run,
        )
        return {
            "status": "executed",
            "recommendation_id": res.recommendation_id,
            "resource_id": res.resource_id,
            "execution_command": res.execution_command,
            "rollback_command": res.rollback_command,
            "dry_run": dry_run,
            "projected_monthly_savings": res.projected_monthly_savings,
        }
    except Exception as e:
        return {
            "status": "error",
            "recommendation_id": recommendation_id,
            "error": str(e),
            "message": "Action execution blocked. Recommendation must be approved by a human reviewer first.",
        }


@tool("downgrade_resource_sku")
def downgrade_resource_sku(
    recommendation_id: str,
    target_sku: str,
    dry_run: bool = True,
) -> dict[str, Any]:
    """Modify resource machine type/size according to an approved rightsizing recommendation."""
    return execute_recommendation._run(recommendation_id=recommendation_id, dry_run=dry_run)


@tool("deallocate_resource")
def deallocate_resource(
    recommendation_id: str,
    dry_run: bool = True,
) -> dict[str, Any]:
    """Stop/deallocate an idle resource according to an approved optimization plan."""
    return execute_recommendation._run(recommendation_id=recommendation_id, dry_run=dry_run)


@tool("delete_resource")
def delete_resource(
    recommendation_id: str,
    dry_run: bool = True,
) -> dict[str, Any]:
    """Delete an unattached or orphaned resource according to an approved optimization plan."""
    return execute_recommendation._run(recommendation_id=recommendation_id, dry_run=dry_run)

