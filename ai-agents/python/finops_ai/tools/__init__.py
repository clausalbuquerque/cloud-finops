"""Typed CrewAI tools for the FinOps and SRE agents.

Tools resolve to deterministic functions (SQL over the FOCUS-normalized schema,
predictions models, agent memory DAO) and are logged via ``finops_ai.observability``.
See ``ai-agents/docs/adr-agent-runtime.md``.
"""

from .cost_tools import (
    get_commitment_coverage,
    get_top_cost_drivers,
    query_cost_by_service,
    query_cost_trend,
)
from .delegation_tools import delegate_to_finops, delegate_to_sre
from .infra_tools import (
    get_infrastructure_baselines,
    get_metric_definitions,
    get_tracked_resources,
    get_utilization_summaries,
    query_resource_dependencies,
    store_infrastructure_baseline,
    update_underuse_threshold,
)
from .memory_tools import (
    get_optimization_history,
    propose_recommendation,
    store_anomaly_resolution,
)
from .mutation_tools import (
    deallocate_resource,
    delete_resource,
    downgrade_resource_sku,
    execute_recommendation,
)
from .prediction_tools import forecast_spend, get_anomalies
from .retrieval_tools import retrieve_provider_context, lookup_cloud_catalog_skus

__all__: list[str] = [
    # Cost tools
    "query_cost_by_service",
    "query_cost_trend",
    "get_top_cost_drivers",
    "get_commitment_coverage",
    # Prediction tools
    "forecast_spend",
    "get_anomalies",
    # Infra tools
    "get_tracked_resources",
    "get_utilization_summaries",
    "get_metric_definitions",
    "query_resource_dependencies",
    "get_infrastructure_baselines",
    "store_infrastructure_baseline",
    "update_underuse_threshold",
    # Retrieval tools (render-step only)
    "retrieve_provider_context",
    "lookup_cloud_catalog_skus",
    # Memory tools
    "get_optimization_history",
    "propose_recommendation",
    "store_anomaly_resolution",
    # Delegation tools
    "delegate_to_sre",
    "delegate_to_finops",
    # Action execution / mutation tools (HITL gated)
    "execute_recommendation",
    "downgrade_resource_sku",
    "deallocate_resource",
    "delete_resource",
]



