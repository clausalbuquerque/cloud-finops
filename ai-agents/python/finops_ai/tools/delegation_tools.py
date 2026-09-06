"""Typed Delegation Tools for Inter-Agent Communication.

Enables explicit, structured delegation between the FinOps and SRE specialists
in accordance with ai-agents/docs/adr-agent-runtime.md.
"""

from __future__ import annotations

from typing import Any
from uuid import uuid4

from crewai.tools import tool

_default_controller = None


def _get_controller():
    global _default_controller
    if _default_controller is None:
        from finops_ai.orchestration.delegation_protocol import DelegationController
        _default_controller = DelegationController()
    return _default_controller


@tool("delegate_to_sre")
def delegate_to_sre(
    resource_ids: list[str],
    question: str,
    context: dict[str, Any] | None = None,
    delegation_depth: int = 1,
) -> dict[str, Any]:
    """Request infrastructure utilization and operational risk assessment from the SRE Specialist.

    Use when: You identify a cost anomaly or candidate rightsizing opportunity on specific
    resources and need the SRE agent to check CPU/Memory utilization trends, dependencies,
    or expected batch schedules before proposing changes.
    """
    from finops_ai.orchestration.delegation_contracts import DelegationRequest

    req = DelegationRequest(
        caller_agent="FinOps Specialist",
        target_agent="SRE Specialist",
        resource_ids=resource_ids,
        question=question,
        context=context or {},
        delegation_depth=delegation_depth,
        call_stack=["FinOps Specialist"],
    )

    verdict = _get_controller().delegate_to_sre(req)
    res = verdict.model_dump()
    res["status"] = "delegated"
    res["target_agent"] = "SRE Specialist"
    res["resource_ids"] = resource_ids
    res["question"] = question
    return res


@tool("delegate_to_finops")
def delegate_to_finops(
    resource_ids: list[str],
    utilization_summary: str,
    question: str,
    delegation_depth: int = 1,
) -> dict[str, Any]:
    """Request financial quantification and cost analysis from the FinOps Specialist.

    Use when: The SRE Agent discovers underutilized or idle infrastructure and needs
    the FinOps agent to calculate dollar-denominated waste and potential monthly savings.
    """
    from finops_ai.orchestration.delegation_contracts import DelegationRequest

    req = DelegationRequest(
        caller_agent="SRE Specialist",
        target_agent="FinOps Specialist",
        resource_ids=resource_ids,
        question=question,
        context={"utilization_summary": utilization_summary},
        delegation_depth=delegation_depth,
        call_stack=["SRE Specialist"],
    )

    verdict = _get_controller().delegate_to_finops(req)
    res = verdict.model_dump()
    res["status"] = "delegated"
    res["target_agent"] = "FinOps Specialist"
    res["resource_ids"] = resource_ids
    res["question"] = question
    return res






