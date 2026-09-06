"""Tiered Autonomy & Blast-Radius Policy Engine.

Categorizes cloud resource recommendations into:
- Tier 1 (Low Risk / Non-Production): Dev/sandbox environments, stateless, impact < $50/mo.
  Permits batched or asynchronous review to prevent engineer approval fatigue.
- Tier 2 (High Risk / Production): Production environments, shared clusters, stateful databases,
  or high-spend infrastructure (>= $50/mo). Mandates explicit, individualized human review and sign-off.
"""

from __future__ import annotations

from enum import Enum
from typing import Any, Sequence
from pydantic import BaseModel, Field


class AutonomyTier(str, Enum):
    """Autonomy classification for infrastructure actions."""

    TIER_1 = "tier_1"
    TIER_2 = "tier_2"

    # Convenient semantic aliases
    TIER_1_AUTONOMOUS = "tier_1"
    TIER_2_HUMAN_APPROVAL = "tier_2"


class BlastRadiusClassification(BaseModel):
    """Detailed blast-radius and autonomy classification result."""

    tier: AutonomyTier
    tier_name: str = Field(
        description="Human-readable tier name (e.g. 'Tier 1 (Autonomous / Batched Review)')"
    )
    can_be_batched: bool = Field(
        description="True if recommendation can be reviewed/executed in a batch"
    )
    requires_individual_signoff: bool = Field(
        description="True if recommendation mandates individualized human sign-off"
    )
    is_production: bool = Field(
        description="True if target resource is tagged or identified as production"
    )
    is_stateful: bool = Field(
        description="True if target resource persists state (database, storage, disk)"
    )
    is_shared_or_critical: bool = Field(
        description="True if target resource is a shared cluster or critical backend"
    )
    is_high_spend: bool = Field(
        description="True if estimated monthly financial impact meets or exceeds the threshold ($50/mo)"
    )
    financial_impact_usd: float = Field(
        ge=0.0, description="Estimated monthly financial impact or savings in USD"
    )
    reasons: list[str] = Field(
        default_factory=list, description="Audit trail justifying the blast radius classification"
    )


class BlastRadiusPolicyEngine:
    """Evaluates resource attributes and financial impact against blast-radius safety policies."""

    DEFAULT_HIGH_SPEND_THRESHOLD: float = 50.0

    STATEFUL_KEYWORDS: tuple[str, ...] = (
        "sql",
        "database",
        "cosmos",
        "spanner",
        "bigtable",
        "redis",
        "storage",
        "disk",
        "db",
        "postgres",
        "mysql",
        "mongodb",
        "filestore",
    )

    SHARED_CRITICAL_KEYWORDS: tuple[str, ...] = (
        "cluster",
        "k8s",
        "kubernetes",
        "gke",
        "aks",
        "loadbalancer",
        "ingress",
        "gateway",
        "backend",
        "router",
    )

    PROD_TAG_KEYS: tuple[str, ...] = ("env", "environment", "tier", "stage", "lifecycle")
    PROD_TAG_VALUES: tuple[str, ...] = ("prod", "production", "live")
    NON_PROD_VALUES: tuple[str, ...] = (
        "dev",
        "development",
        "stage",
        "staging",
        "test",
        "sandbox",
        "qa",
        "uat",
    )

    def __init__(self, high_spend_threshold_usd: float = DEFAULT_HIGH_SPEND_THRESHOLD) -> None:
        self.high_spend_threshold_usd = high_spend_threshold_usd

    def classify(
        self,
        resource_name: str,
        resource_type: str = "compute/instance",
        tags: dict[str, Any] | None = None,
        estimated_monthly_savings_usd: float = 0.0,
        is_load_balanced: bool = False,
        is_stateful: bool | None = None,
        is_production: bool | None = None,
    ) -> BlastRadiusClassification:
        """Evaluate a target resource and classify it into Tier 1 or Tier 2."""
        reasons: list[str] = []
        name_lower = (resource_name or "").lower()
        type_lower = (resource_type or "").lower()
        tags_map = {str(k).lower(): str(v).lower() for k, v in (tags or {}).items()}

        # 1. Production Detection
        detected_prod = False
        prod_source = None
        if is_production is not None:
            detected_prod = is_production
            if detected_prod:
                prod_source = "explicit flag"
        else:
            # Check tags
            for pkey in self.PROD_TAG_KEYS:
                if pkey in tags_map:
                    val = tags_map[pkey]
                    if any(pval in val for pval in self.PROD_TAG_VALUES):
                        detected_prod = True
                        prod_source = f"tag '{pkey}: {val}'"
                        break
            # Check resource name indicators if tags did not explicitly flag as non-prod
            if not detected_prod:
                has_explicit_non_prod = False
                for pkey in self.PROD_TAG_KEYS:
                    if pkey in tags_map:
                        val = tags_map[pkey]
                        if any(npval in val for npval in self.NON_PROD_VALUES):
                            has_explicit_non_prod = True
                            break

                if not has_explicit_non_prod:
                    if any(sub in name_lower for sub in ("-prod-", "-prod", "prod-", "prod_", "_prod")):
                        detected_prod = True
                        prod_source = f"resource name '{resource_name}'"

        if detected_prod:
            reasons.append(
                f"Target resource '{resource_name}' belongs to production environment ({prod_source or 'production'})."
            )

        # 2. Stateful Detection
        detected_stateful = False
        if is_stateful is not None:
            detected_stateful = is_stateful
        else:
            if any(kw in type_lower for kw in self.STATEFUL_KEYWORDS) or any(
                kw in name_lower for kw in ("-db-", "-db", "db-", "db_", "_db", "-database-", "postgres", "mysql", "redis")
            ):
                detected_stateful = True

        if detected_stateful:
            reasons.append(
                f"Target resource '{resource_name}' is stateful or data-bearing ({resource_type})."
            )

        # 3. Shared Cluster or Critical Networking Detection
        detected_shared_critical = False
        if is_load_balanced:
            detected_shared_critical = True
        elif any(kw in type_lower for kw in self.SHARED_CRITICAL_KEYWORDS) or any(
            kw in name_lower for kw in ("-lb-", "-lb", "lb-", "cluster-", "-cluster-")
        ):
            detected_shared_critical = True

        if detected_shared_critical:
            reasons.append(
                f"Target resource '{resource_name}' is a shared cluster, load-balancer, or critical backend."
            )

        # 4. Financial Impact Check
        savings_amount = max(0.0, float(estimated_monthly_savings_usd or 0.0))
        is_high_spend = savings_amount >= self.high_spend_threshold_usd
        if is_high_spend:
            reasons.append(
                f"Estimated monthly financial impact of ${savings_amount:.2f} meets or exceeds the threshold (${self.high_spend_threshold_usd:.2f}/mo)."
            )

        # Overall Tier Assignment
        if detected_prod or detected_stateful or detected_shared_critical or is_high_spend:
            tier = AutonomyTier.TIER_2
            tier_name = "Tier 2 (Mandatory Individual Sign-off)"
            can_be_batched = False
            requires_individual_signoff = True
        else:
            tier = AutonomyTier.TIER_1
            tier_name = "Tier 1 (Autonomous / Batched Review)"
            can_be_batched = True
            requires_individual_signoff = False
            reasons.append(
                f"Target resource '{resource_name}' is non-production, stateless, and low-spend (< ${self.high_spend_threshold_usd:.2f}/mo); eligible for batched or automated review."
            )

        return BlastRadiusClassification(
            tier=tier,
            tier_name=tier_name,
            can_be_batched=can_be_batched,
            requires_individual_signoff=requires_individual_signoff,
            is_production=detected_prod,
            is_stateful=detected_stateful,
            is_shared_or_critical=detected_shared_critical,
            is_high_spend=is_high_spend,
            financial_impact_usd=round(savings_amount, 2),
            reasons=reasons,
        )

    def classify_candidate(self, candidate: Any) -> BlastRadiusClassification:
        """Classify a RecommendationCandidate dataclass or object."""
        resource_name = getattr(candidate, "resource_name", "") or getattr(candidate, "resource_id", "")
        resource_type = getattr(candidate, "resource_type", "compute/instance")
        savings = getattr(candidate, "estimated_monthly_savings_usd", 0.0) or getattr(
            candidate, "estimated_monthly_savings", 0.0
        )
        tags = getattr(candidate, "tags", None) or {}
        return self.classify(
            resource_name=resource_name,
            resource_type=resource_type,
            tags=tags,
            estimated_monthly_savings_usd=float(savings),
        )

    def classify_recommendation(self, rec: Any) -> BlastRadiusClassification:
        """Classify an OptimizationRecommendation dataclass or dict."""
        if isinstance(rec, dict):
            return self.classify(
                resource_name=rec.get("resource_id", "") or rec.get("resource_name", ""),
                resource_type=rec.get("resource_type", "compute/instance"),
                tags=rec.get("tags", {}),
                estimated_monthly_savings_usd=float(rec.get("estimated_monthly_savings", 0.0) or 0.0),
            )
        return self.classify_candidate(rec)
