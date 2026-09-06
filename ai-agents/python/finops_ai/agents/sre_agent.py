"""SRE Specialist CrewAI Agent Definition."""

from __future__ import annotations

from typing import Any, Sequence

from crewai import Agent

from finops_ai.llm import build_llm
from finops_ai.prompts.sre_prompts import (
    SRE_AGENT_BACKSTORY,
    SRE_AGENT_GOAL,
    SRE_AGENT_ROLE,
)
from finops_ai.tools import (
    delegate_to_finops,
    get_infrastructure_baselines,
    get_metric_definitions,
    get_tracked_resources,
    get_utilization_summaries,
    query_resource_dependencies,
    store_infrastructure_baseline,
    update_underuse_threshold,
    lookup_cloud_catalog_skus,
)

DEFAULT_SRE_TOOLS = [
    get_tracked_resources,
    get_utilization_summaries,
    get_metric_definitions,
    query_resource_dependencies,
    get_infrastructure_baselines,
    store_infrastructure_baseline,
    update_underuse_threshold,
    lookup_cloud_catalog_skus,
    delegate_to_finops,
]


def create_sre_agent(
    llm: Any = None,
    tools: Sequence[Any] | None = None,
    max_iter: int = 10,
    verbose: bool = True,
    step_callback: Any = None,
) -> Agent:
    """Create and configure the SRE Specialist CrewAI Agent.

    Configured with bounded ReAct reasoning (max_iter=10) and full infrastructure/metrics toolset.
    """
    agent_llm = llm if llm is not None else build_llm(tier="flash", temperature=0.1)
    agent_tools = list(tools) if tools is not None else DEFAULT_SRE_TOOLS

    return Agent(
        role=SRE_AGENT_ROLE,
        goal=SRE_AGENT_GOAL,
        backstory=SRE_AGENT_BACKSTORY,
        llm=agent_llm,
        tools=agent_tools,
        max_iter=max_iter,
        verbose=verbose,
        step_callback=step_callback,
        allow_delegation=False,  # Use explicit typed delegation tool delegate_to_finops
    )
