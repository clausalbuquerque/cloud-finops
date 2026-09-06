"""Data contracts for inter-agent delegation protocols."""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field


class DependencyRisk(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"


class DelegationRequest(BaseModel):
    """Structured inter-agent delegation request payload."""

    caller_agent: str = Field(description="Name/Role of the calling agent")
    target_agent: str = Field(description="Name/Role of the target delegate agent")
    resource_ids: list[str] = Field(description="Target cloud resource IDs to assess")
    question: str = Field(description="Specific analytical question or assessment task")
    context: dict[str, Any] = Field(default_factory=dict, description="Contextual evidence or findings")
    delegation_depth: int = Field(default=1, ge=1, le=5, description="Current delegation call depth")
    call_stack: list[str] = Field(default_factory=list, description="Stack of agents in delegation chain")
    parent_trace_id: str = Field(default_factory=lambda: str(uuid4()))
    delegation_id: str = Field(default_factory=lambda: str(uuid4()))
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class SREDelegationVerdict(BaseModel):
    """Structured operational safety assessment returned by the SRE Agent."""

    safe_to_modify: bool = Field(description="Whether the target resources are safe for modification")
    target_resources: list[str] = Field(description="Resources analyzed")
    projected_peak_cpu_pct: float | None = Field(default=None, description="Projected peak P95 CPU on target SKU")
    headroom_buffer_pct: float | None = Field(default=None, description="Safe operational headroom percentage")
    dependency_risk: DependencyRisk = Field(default=DependencyRisk.LOW, description="Assessed dependency risk level")
    baseline_suppressed: bool = Field(default=False, description="Whether alert was suppressed by workload baseline")
    recommended_sku: str | None = Field(default=None, description="Recommended target SKU if right-sizing")
    assessment_summary: str = Field(description="Detailed SRE findings and justification")
    delegation_id: str
    trace_id: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class FinOpsDelegationVerdict(BaseModel):
    """Structured financial quantification returned by the FinOps Agent."""

    quantified_savings_monthly: float = Field(description="Estimated monthly net cost savings in USD")
    current_monthly_cost: float = Field(description="Current monthly baseline spend in USD")
    projected_monthly_cost: float = Field(description="Projected monthly spend after modification in USD")
    pricing_model: str = Field(default="OnDemand", description="Target pricing model")
    commitment_impact: str = Field(default="None", description="Impact on active commitment discounts")
    candidate_action: str = Field(description="Summary of proposed financial action")
    delegation_id: str
    trace_id: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

