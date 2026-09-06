"""FinOps Specialist CrewAI Agent Definition."""

from __future__ import annotations

from typing import Any, Sequence

from crewai import Agent

from finops_ai.llm import build_llm
from finops_ai.prompts.finops_prompts import (
    FINOPS_AGENT_BACKSTORY,
    FINOPS_AGENT_GOAL,
    FINOPS_AGENT_ROLE,
)
from finops_ai.tools import (
    delegate_to_sre,
    forecast_spend,
    get_anomalies,
    get_commitment_coverage,
    get_optimization_history,
    get_top_cost_drivers,
    propose_recommendation,
    query_cost_by_service,
    query_cost_trend,
    store_anomaly_resolution,
    lookup_cloud_catalog_skus,
)

DEFAULT_FINOPS_TOOLS = [
    query_cost_by_service,
    query_cost_trend,
    get_top_cost_drivers,
    get_anomalies,
    forecast_spend,
    get_commitment_coverage,
    get_optimization_history,
    propose_recommendation,
    store_anomaly_resolution,
    lookup_cloud_catalog_skus,
    delegate_to_sre,
]


def create_finops_agent(
    llm: Any = None,
    tools: Sequence[Any] | None = None,
    max_iter: int = 10,
    verbose: bool = True,
    step_callback: Any = None,
) -> Agent:
    """Create and configure the FinOps Specialist CrewAI Agent.

    Configured with bounded ReAct reasoning (max_iter=10) and full FOCUS/predictions/memory toolset.
    """
    agent_llm = llm if llm is not None else build_llm(model="gemini-2.5-pro", temperature=0.1)
    agent_tools = list(tools) if tools is not None else DEFAULT_FINOPS_TOOLS

    return Agent(
        role=FINOPS_AGENT_ROLE,
        goal=FINOPS_AGENT_GOAL,
        backstory=FINOPS_AGENT_BACKSTORY,
        llm=agent_llm,
        tools=agent_tools,
        max_iter=max_iter,
        verbose=verbose,
        step_callback=step_callback,
        allow_delegation=False,  # Use explicit typed delegation tool delegate_to_sre
    )

