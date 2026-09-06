"""Domain evaluation rubrics for FinOps and SRE specialist reviews."""

from __future__ import annotations

from typing import Any

FINOPS_EVALUATION_RUBRIC: list[dict[str, Any]] = [
    {
        "name": "evidence_grounding",
        "weight": 0.40,
        "description": (
            "Every dollar figure, date, percentage, and resource ID mentioned in the output must be "
            "directly supported by an explicit tool observation. Any invented or unverified numbers "
            "trigger an immediate failure (score 0) on this dimension."
        ),
    },
    {
        "name": "math_consistency",
        "weight": 0.25,
        "description": (
            "Calculations of cost deltas, percentage changes, and projected monthly/annual savings "
            "must be mathematically sound and match the tool results without calculation errors."
        ),
    },
    {
        "name": "memory_compliance",
        "weight": 0.20,
        "description": (
            "If the agent proposes an optimization recommendation or resolves an anomaly, it must have "
            "queried long-term memory (e.g. get_optimization_history) to ensure this action was not "
            "previously rejected or flagged as inappropriate for this team/resource."
        ),
    },
    {
        "name": "scope_integrity",
        "weight": 0.15,
        "description": (
            "The analysis and recommendations must strictly adhere to the requested team, account, or "
            "subscription scope, without leaking or mixing data from unauthorized scopes."
        ),
    },
]

SRE_EVALUATION_RUBRIC: list[dict[str, Any]] = [
    {
        "name": "operational_headroom",
        "weight": 0.35,
        "description": (
            "The sizing analysis or recommendation must guarantee adequate performance headroom. "
            "Target machine types must not cause projected peak CPU to exceed 75% or peak memory to exceed 80%."
        ),
    },
    {
        "name": "workload_baseline_awareness",
        "weight": 0.25,
        "description": (
            "The analysis must verify workload schedules and agent memory (get_infrastructure_baselines) "
            "to prevent false-positive alarms on expected nightly batch jobs or planned idle intervals."
        ),
    },
    {
        "name": "dependency_safety",
        "weight": 0.20,
        "description": (
            "Downstream dependencies, database connections, and storage attachments must be assessed "
            "to ensure the proposed change does not introduce cascade latency or outages."
        ),
    },
    {
        "name": "action_viability",
        "weight": 0.20,
        "description": (
            "The proposed execution step (e.g. SKU change, scale-in, migration) must be technically "
            "viable on the target cloud provider without unmanaged downtime."
        ),
    },
]

