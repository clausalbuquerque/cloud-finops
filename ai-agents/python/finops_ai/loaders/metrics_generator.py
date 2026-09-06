"""Synthetic Utilization Metrics Generator.

Generates realistic time-series metrics data points and daily utilization summaries
for tracked resources, aligned with FOCUS cost dataset identifiers.
Supports healthy, underused, idle, spiky, and nightly-batch workload scenarios.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
import math
import random
from typing import Any
from uuid import uuid4

import numpy as np
from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    Float,
    Integer,
    String,
    Text,
    create_engine,
    select,
)
from sqlalchemy.dialects.postgresql import ENUM, JSONB, UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, sessionmaker

MetricUnitEnum = ENUM(
    "Count",
    "Bytes",
    "Seconds",
    "CountPerSecond",
    "BytesPerSecond",
    "Percent",
    "MilliSeconds",
    "ByteSeconds",
    "Cores",
    "MilliCores",
    "NanoCores",
    "BitsPerSecond",
    "Unspecified",
    name="metric_unit_enum",
    schema="finops",
    create_type=False,
)

AggregationTypeEnum = ENUM(
    "Average",
    "Minimum",
    "Maximum",
    "Total",
    "Count",
    "None",
    name="aggregation_type_enum",
    schema="finops",
    create_type=False,
)

TimeGrainEnum = ENUM(
    "PT1M",
    "PT5M",
    "PT15M",
    "PT30M",
    "PT1H",
    "PT6H",
    "PT12H",
    "P1D",
    name="time_grain_enum",
    schema="finops",
    create_type=False,
)


class Base(DeclarativeBase):
    pass


class SubscriptionRecord(Base):
    __tablename__ = "subscriptions"
    __table_args__ = {"schema": "finops"}

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True)
    subscription_id: Mapped[str] = mapped_column(String, unique=True)
    display_name: Mapped[str] = mapped_column(String)
    state: Mapped[str | None] = mapped_column(String, nullable=True)


class ResourceGroupRecord(Base):
    __tablename__ = "resource_groups"
    __table_args__ = {"schema": "finops"}

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True)
    name: Mapped[str] = mapped_column(String)
    location: Mapped[str | None] = mapped_column(String, nullable=True)
    subscription_id: Mapped[str] = mapped_column(UUID(as_uuid=False))


class TrackedResourceRecord(Base):
    __tablename__ = "tracked_resources"
    __table_args__ = {"schema": "finops"}

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True)
    azure_resource_id: Mapped[str] = mapped_column(String, unique=True)
    resource_name: Mapped[str] = mapped_column(String)
    resource_type: Mapped[str] = mapped_column(String)
    region: Mapped[str | None] = mapped_column(String, nullable=True)
    sku: Mapped[str | None] = mapped_column(String, nullable=True)
    provisioned_capacity: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    subscription_id: Mapped[str] = mapped_column(UUID(as_uuid=False))
    resource_group_id: Mapped[str] = mapped_column(UUID(as_uuid=False))


class MetricDefinitionRecord(Base):
    __tablename__ = "metric_definitions"
    __table_args__ = {"schema": "finops"}

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True)
    resource_type: Mapped[str] = mapped_column(String)
    metric_namespace: Mapped[str] = mapped_column(String)
    metric_name: Mapped[str] = mapped_column(String)
    display_name: Mapped[str] = mapped_column(String)
    unit: Mapped[str] = mapped_column(MetricUnitEnum, default="Percent")
    primary_aggregation: Mapped[str] = mapped_column("primary_aggregation_type", AggregationTypeEnum, default="Average")
    is_utilization_metric: Mapped[bool] = mapped_column(Boolean, default=True)


class MetricDataPointRecord(Base):
    __tablename__ = "metric_data_points"
    __table_args__ = {"schema": "finops"}

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True)
    tracked_resource_id: Mapped[str] = mapped_column(UUID(as_uuid=False))
    metric_definition_id: Mapped[str] = mapped_column(UUID(as_uuid=False))
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    average: Mapped[float] = mapped_column(Float)
    maximum: Mapped[float] = mapped_column(Float)
    minimum: Mapped[float] = mapped_column(Float)
    total: Mapped[float] = mapped_column(Float)
    sample_count: Mapped[float] = mapped_column("count", Float, default=1.0)
    time_grain: Mapped[str] = mapped_column(TimeGrainEnum, default="PT1H")





class UtilizationSummaryRecord(Base):
    __tablename__ = "utilization_summaries"
    __table_args__ = {"schema": "finops"}

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True)
    tracked_resource_id: Mapped[str] = mapped_column(UUID(as_uuid=False))
    summary_date: Mapped[date] = mapped_column(Date)
    metric_name: Mapped[str] = mapped_column(String)
    avg_utilization: Mapped[float] = mapped_column(Float)
    max_utilization: Mapped[float] = mapped_column(Float)
    min_utilization: Mapped[float] = mapped_column(Float)
    p95_utilization: Mapped[float | None] = mapped_column(Float, nullable=True)
    sample_count: Mapped[int] = mapped_column(Integer)
    underuse_threshold: Mapped[float] = mapped_column(Float)
    is_underused: Mapped[bool] = mapped_column(Boolean, default=False)


@dataclass
class SyntheticResourceConfig:
    """Configuration definition for a synthetic tracked resource and its metric profile."""

    resource_id: str
    resource_name: str
    resource_type: str
    region: str
    sku: str
    provisioned_capacity: dict[str, Any]
    sub_account_id: str
    sub_account_name: str
    rg_name: str
    scenario: str  # 'healthy' | 'underused' | 'idle' | 'spiky' | 'nightly_batch'
    base_cpu_avg: float
    base_mem_avg: float
    cpu_threshold: float = 10.0
    mem_threshold: float = 20.0


# Standard test scenarios correlated with FOCUS sample dataset
TRACKED_RESOURCE_SPECS: list[SyntheticResourceConfig] = [
    # 1. GCP Healthy VM
    SyntheticResourceConfig(
        resource_id="projects/prod-analytics/zones/us-central1-a/instances/analytics-worker-01",
        resource_name="analytics-worker-01",
        resource_type="compute/instance",
        region="us-central1",
        sku="n2-standard-8",
        provisioned_capacity={"vCPUs": 8, "memoryGB": 32},
        sub_account_id="sub-gcp-data-platform",
        sub_account_name="data-platform",
        rg_name="prod-analytics",
        scenario="healthy",
        base_cpu_avg=52.0,
        base_mem_avg=58.0,
    ),
    # 2. GCP Upsized / Underused VM (Key scenario for FinOps+SRE investigation)
    SyntheticResourceConfig(
        resource_id="projects/prod-analytics/zones/us-central1-a/instances/analytics-worker-02",
        resource_name="analytics-worker-02",
        resource_type="compute/instance",
        region="us-central1",
        sku="n2-standard-16",
        provisioned_capacity={"vCPUs": 16, "memoryGB": 64},
        sub_account_id="sub-gcp-data-platform",
        sub_account_name="data-platform",
        rg_name="prod-analytics",
        scenario="underused",
        base_cpu_avg=8.5,
        base_mem_avg=14.0,
    ),
    # 3. GCP Nightly Batch VM (Low daytime, high nighttime -> tests baseline false-positive suppression)
    SyntheticResourceConfig(
        resource_id="projects/prod-analytics/zones/us-central1-b/instances/batch-worker-01",
        resource_name="batch-worker-01",
        resource_type="compute/instance",
        region="us-central1",
        sku="n2-standard-2",
        provisioned_capacity={"vCPUs": 2, "memoryGB": 8},
        sub_account_id="sub-gcp-data-platform",
        sub_account_name="data-platform",
        rg_name="prod-analytics",
        scenario="nightly_batch",
        base_cpu_avg=9.0,
        base_mem_avg=22.0,
    ),
    # 4. GCP Cloud SQL Database
    SyntheticResourceConfig(
        resource_id="projects/prod-analytics/instances/analytics-db-01",
        resource_name="analytics-db-01",
        resource_type="sql/database",
        region="us-central1",
        sku="db-custom-4-16",
        provisioned_capacity={"vCPUs": 4, "memoryGB": 16, "storageGB": 250},
        sub_account_id="sub-gcp-data-platform",
        sub_account_name="data-platform",
        rg_name="prod-analytics",
        scenario="healthy",
        base_cpu_avg=45.0,
        base_mem_avg=55.0,
    ),
    # 5. Azure Healthy VM
    SyntheticResourceConfig(
        resource_id="/subscriptions/sub-az-core-services/resourceGroups/rg-core-services/providers/Microsoft.Compute/virtualMachines/core-app-vm1",
        resource_name="core-app-vm1",
        resource_type="Microsoft.Compute/virtualMachines",
        region="eastus",
        sku="Standard_D4s_v3",
        provisioned_capacity={"vCPUs": 4, "memoryGB": 16},
        sub_account_id="sub-az-core-services",
        sub_account_name="core-services",
        rg_name="rg-core-services",
        scenario="healthy",
        base_cpu_avg=48.0,
        base_mem_avg=52.0,
    ),
    # 6. Azure Idle/Underused VM
    SyntheticResourceConfig(
        resource_id="/subscriptions/sub-az-core-services/resourceGroups/rg-core-services/providers/Microsoft.Compute/virtualMachines/core-app-vm2",
        resource_name="core-app-vm2",
        resource_type="Microsoft.Compute/virtualMachines",
        region="eastus",
        sku="Standard_E8s_v3",
        provisioned_capacity={"vCPUs": 8, "memoryGB": 64},
        sub_account_id="sub-az-core-services",
        sub_account_name="core-services",
        rg_name="rg-core-services",
        scenario="underused",
        base_cpu_avg=5.5,
        base_mem_avg=11.0,
    ),
    # 7. Azure SQL Database (DTU underused)
    SyntheticResourceConfig(
        resource_id="/subscriptions/sub-az-core-services/resourceGroups/rg-core-services/providers/Microsoft.Sql/servers/sql-core/databases/db-core",
        resource_name="db-core",
        resource_type="Microsoft.Sql/servers/databases",
        region="eastus",
        sku="GP_Gen5_4",
        provisioned_capacity={"vCores": 4, "maxStorageGB": 500},
        sub_account_id="sub-az-core-services",
        sub_account_name="core-services",
        rg_name="rg-core-services",
        scenario="underused",
        base_cpu_avg=11.0,
        base_mem_avg=25.0,
        cpu_threshold=15.0,
    ),
    # 8. AWS Spiky VM
    SyntheticResourceConfig(
        resource_id="arn:aws:ec2:us-east-1:123456789012:instance/i-0a1b2c3d4e5f6g7h8",
        resource_name="marketing-worker-01",
        resource_type="AWS::EC2::Instance",
        region="us-east-1",
        sku="m5.2xlarge",
        provisioned_capacity={"vCPUs": 8, "memoryGB": 32},
        sub_account_id="sub-aws-marketing",
        sub_account_name="marketing-ai",
        rg_name="rg-marketing-prod",
        scenario="spiky",
        base_cpu_avg=28.0,
        base_mem_avg=45.0,
    ),
    # 9. AWS RDS Database
    SyntheticResourceConfig(
        resource_id="arn:aws:rds:us-east-1:123456789012:db:marketing-db",
        resource_name="marketing-db",
        resource_type="AWS::RDS::DBInstance",
        region="us-east-1",
        sku="db.m5.large",
        provisioned_capacity={"vCPUs": 2, "memoryGB": 8},
        sub_account_id="sub-aws-marketing",
        sub_account_name="marketing-ai",
        rg_name="rg-marketing-prod",
        scenario="healthy",
        base_cpu_avg=35.0,
        base_mem_avg=42.0,
    ),
    # 10. Oracle VM Underused
    SyntheticResourceConfig(
        resource_id="ocid1.instance.oc1.iad.anuwcljrn7x01",
        resource_name="oci-worker-01",
        resource_type="oci:compute:instance",
        region="us-ashburn-1",
        sku="VM.Standard.E4.Flex",
        provisioned_capacity={"vCPUs": 4, "memoryGB": 16},
        sub_account_id="sub-oci-dw",
        sub_account_name="data-platform",
        rg_name="rg-oci-dw",
        scenario="underused",
        base_cpu_avg=7.5,
        base_mem_avg=16.0,
    ),
]


@dataclass
class MetricsGenerationResult:
    """Summary of the synthetic metrics generation run."""

    tracked_resources_count: int = 0
    metric_definitions_count: int = 0
    data_points_generated: int = 0
    summaries_generated: int = 0
    underused_summaries_count: int = 0
    start_date: date | None = None
    end_date: date | None = None


class SyntheticMetricsGenerator:
    """Generates synthetic time-series data points and daily utilization summaries."""

    def __init__(self, session_factory: sessionmaker[Session], seed: int = 42) -> None:
        self._session_factory = session_factory
        self.seed = seed
        random.seed(seed)
        np.random.seed(seed)

    @classmethod
    def from_url(cls, db_url: str, seed: int = 42) -> "SyntheticMetricsGenerator":
        engine = create_engine(db_url, future=True)
        return cls(session_factory=sessionmaker(bind=engine, future=True), seed=seed)

    def _ensure_subscription_and_rg(
        self, session: Session, sub_id_str: str, sub_name: str, rg_name: str, region: str
    ) -> tuple[str, str]:
        """Ensure subscription and resource group records exist in database."""
        sub = session.scalars(
            select(SubscriptionRecord).where(SubscriptionRecord.subscription_id == sub_id_str)
        ).first()
        if not sub:
            sub = SubscriptionRecord(
                id=str(uuid4()),
                subscription_id=sub_id_str,
                display_name=sub_name,
                state="active",
            )
            session.add(sub)
            session.flush()

        rg = session.scalars(
            select(ResourceGroupRecord).where(
                ResourceGroupRecord.subscription_id == str(sub.id),
                ResourceGroupRecord.name == rg_name,
            )
        ).first()
        if not rg:
            rg = ResourceGroupRecord(
                id=str(uuid4()),
                name=rg_name,
                location=region,
                subscription_id=str(sub.id),
            )
            session.add(rg)
            session.flush()

        return str(sub.id), str(rg.id)

    def _ensure_metric_definitions(self, session: Session) -> dict[str, str]:
        """Ensure standard metric definitions exist, returning metric_name -> definition_id."""
        metric_defs = [
            # Percentage CPU
            {
                "resource_type": "compute/instance",
                "metric_namespace": "compute.googleapis.com",
                "metric_name": "Percentage CPU",
                "display_name": "Percentage CPU",
                "unit": "Percent",
                "primary_aggregation": "Average",
                "underuse_threshold": 10.0,
            },
            {
                "resource_type": "Microsoft.Compute/virtualMachines",
                "metric_namespace": "Microsoft.Compute/virtualMachines",
                "metric_name": "Percentage CPU",
                "display_name": "Percentage CPU",
                "unit": "Percent",
                "primary_aggregation": "Average",
                "underuse_threshold": 10.0,
            },
            {
                "resource_type": "AWS::EC2::Instance",
                "metric_namespace": "AWS/EC2",
                "metric_name": "Percentage CPU",
                "display_name": "CPUUtilization",
                "unit": "Percent",
                "primary_aggregation": "Average",
                "underuse_threshold": 10.0,
            },
            {
                "resource_type": "oci:compute:instance",
                "metric_namespace": "oci_computeagent",
                "metric_name": "Percentage CPU",
                "display_name": "CpuUtilization",
                "unit": "Percent",
                "primary_aggregation": "Average",
                "underuse_threshold": 10.0,
            },
            # Memory Utilization
            {
                "resource_type": "compute/instance",
                "metric_namespace": "compute.googleapis.com",
                "metric_name": "Available Memory Bytes",
                "display_name": "Memory Utilization",
                "unit": "Percent",
                "primary_aggregation": "Average",
                "underuse_threshold": 20.0,
            },
            {
                "resource_type": "Microsoft.Compute/virtualMachines",
                "metric_namespace": "Microsoft.Compute/virtualMachines",
                "metric_name": "Available Memory Bytes",
                "display_name": "Memory Utilization",
                "unit": "Percent",
                "primary_aggregation": "Average",
                "underuse_threshold": 20.0,
            },
            # Database metrics
            {
                "resource_type": "sql/database",
                "metric_namespace": "cloudsql.googleapis.com",
                "metric_name": "Percentage CPU",
                "display_name": "CPU Utilization",
                "unit": "Percent",
                "primary_aggregation": "Average",
                "underuse_threshold": 15.0,
            },
            {
                "resource_type": "Microsoft.Sql/servers/databases",
                "metric_namespace": "Microsoft.Sql/servers/databases",
                "metric_name": "Percentage CPU",
                "display_name": "DTU Percentage",
                "unit": "Percent",
                "primary_aggregation": "Average",
                "underuse_threshold": 15.0,
            },
            {
                "resource_type": "AWS::RDS::DBInstance",
                "metric_namespace": "AWS/RDS",
                "metric_name": "Percentage CPU",
                "display_name": "CPUUtilization",
                "unit": "Percent",
                "primary_aggregation": "Average",
                "underuse_threshold": 15.0,
            },
        ]

        def_map: dict[str, str] = {}
        for m in metric_defs:
            key = f"{m['resource_type']}:{m['metric_name']}"
            stmt = select(MetricDefinitionRecord).where(
                MetricDefinitionRecord.resource_type == m["resource_type"],
                MetricDefinitionRecord.metric_name == m["metric_name"],
            )
            existing = session.scalars(stmt).first()
            if existing:
                def_map[key] = str(existing.id)
            else:
                row_id = str(uuid4())
                record = MetricDefinitionRecord(
                    id=row_id,
                    resource_type=m["resource_type"],
                    metric_namespace=m["metric_namespace"],
                    metric_name=m["metric_name"],
                    display_name=m["display_name"],
                    unit=m["unit"],
                    primary_aggregation=m["primary_aggregation"],
                    is_utilization_metric=True,
                )

                session.add(record)
                session.flush()
                def_map[key] = row_id

        return def_map

    def _generate_hourly_series(
        self,
        config: SyntheticResourceConfig,
        dt_start: datetime,
        hours: int,
        metric_name: str = "Percentage CPU"
    ) -> list[tuple[datetime, float, float, float]]:
        """Generate hourly timestamps and (avg, min, max) values based on scenario."""
        series: list[tuple[datetime, float, float, float]] = []

        base_avg = config.base_cpu_avg if metric_name == "Percentage CPU" else config.base_mem_avg

        for h in range(hours):
            ts = dt_start + timedelta(hours=h)
            hour_of_day = ts.hour
            is_weekend = ts.weekday() >= 5

            if config.scenario == "healthy":
                # Diurnal curve peaking in afternoon
                diurnal = 15.0 * math.sin((hour_of_day - 6) / 24.0 * 2.0 * math.pi)
                weekend_factor = 0.7 if is_weekend else 1.0
                mean_val = (base_avg + diurnal) * weekend_factor
                val = max(5.0, min(95.0, np.random.normal(mean_val, 4.0)))

            elif config.scenario == "underused":
                # Flat low utilization
                mean_val = base_avg
                val = max(1.0, min(25.0, np.random.normal(mean_val, 2.5)))

            elif config.scenario == "nightly_batch":
                # Very low daytime (4%), high nightly (75%)
                if 22 <= hour_of_day or hour_of_day <= 4:
                    mean_val = 75.0 if metric_name == "Percentage CPU" else 80.0
                    val = max(40.0, min(95.0, np.random.normal(mean_val, 8.0)))
                else:
                    mean_val = 4.0 if metric_name == "Percentage CPU" else 15.0
                    val = max(1.0, min(25.0, np.random.normal(mean_val, 2.0)))

            elif config.scenario == "spiky":
                # Low baseline with occasional spikes up to 90%
                if random.random() < 0.10:
                    val = random.uniform(70.0, 95.0)
                else:
                    val = max(5.0, min(40.0, np.random.normal(base_avg, 3.0)))

            else:  # idle
                val = max(0.1, min(5.0, np.random.normal(2.0, 1.0)))

            min_val = max(0.0, val - random.uniform(1.0, 4.0))
            max_val = min(100.0, val + random.uniform(2.0, 8.0))
            series.append((ts, float(val), float(min_val), float(max_val)))

        return series

    def generate(
        self,
        days: int = 30,
        end_date: date | None = None,
    ) -> MetricsGenerationResult:
        """Generate time-series metrics data points and daily utilization summaries."""
        if end_date is None:
            end_date = date(2026, 8, 22)
        start_date = end_date - timedelta(days=days)
        start_dt = datetime.combine(start_date, datetime.min.time(), tzinfo=timezone.utc)
        total_hours = days * 24

        result = MetricsGenerationResult(
            start_date=start_date,
            end_date=end_date,
        )

        with self._session_factory() as session:
            def_map = self._ensure_metric_definitions(session)
            result.metric_definitions_count = len(def_map)

            for config in TRACKED_RESOURCE_SPECS:
                sub_uuid, rg_uuid = self._ensure_subscription_and_rg(
                    session,
                    config.sub_account_id,
                    config.sub_account_name,
                    config.rg_name,
                    config.region,
                )

                # Ensure tracked resource
                tracked_res = session.scalars(
                    select(TrackedResourceRecord).where(
                        TrackedResourceRecord.azure_resource_id == config.resource_id
                    )
                ).first()

                if not tracked_res:
                    tracked_res_id = str(uuid4())
                    tracked_res = TrackedResourceRecord(
                        id=tracked_res_id,
                        azure_resource_id=config.resource_id,
                        resource_name=config.resource_name,
                        resource_type=config.resource_type,
                        region=config.region,
                        sku=config.sku,
                        provisioned_capacity=config.provisioned_capacity,
                        is_active=True,
                        subscription_id=sub_uuid,
                        resource_group_id=rg_uuid,
                    )
                    session.add(tracked_res)
                    session.flush()
                else:
                    tracked_res_id = str(tracked_res.id)

                result.tracked_resources_count += 1

                for metric_name, threshold in [("Percentage CPU", config.cpu_threshold), ("Available Memory Bytes", config.mem_threshold)]:
                    metric_key = f"{config.resource_type}:{metric_name}"
                    metric_def_id = def_map.get(metric_key)
                    if not metric_def_id:
                        continue

                    hourly_series = self._generate_hourly_series(config, start_dt, total_hours, metric_name=metric_name)

                    # Group by day to compute daily utilization summaries
                    daily_points: dict[date, list[float]] = {}

                    for ts, avg_v, min_v, max_v in hourly_series:
                        dp = MetricDataPointRecord(
                            id=str(uuid4()),
                            tracked_resource_id=tracked_res_id,
                            metric_definition_id=metric_def_id,
                            timestamp=ts,
                            average=avg_v,
                            minimum=min_v,
                            maximum=max_v,
                            total=avg_v,
                            sample_count=1,
                            time_grain="PT1H",
                        )
                        session.add(dp)
                        result.data_points_generated += 1

                        day = ts.date()
                        daily_points.setdefault(day, []).append(avg_v)

                    # Compute daily summaries
                    for day, vals in daily_points.items():
                        if not vals:
                            continue
                        day_avg = float(np.mean(vals))
                        day_min = float(np.min(vals))
                        day_max = float(np.max(vals))
                        day_p95 = float(np.percentile(vals, 95))
                        is_underused = day_avg < threshold

                        # Check existing summary
                        existing_sum = session.scalars(
                            select(UtilizationSummaryRecord).where(
                                UtilizationSummaryRecord.tracked_resource_id == tracked_res_id,
                                UtilizationSummaryRecord.summary_date == day,
                                UtilizationSummaryRecord.metric_name == metric_name,
                            )
                        ).first()

                        if existing_sum:
                            existing_sum.avg_utilization = day_avg
                            existing_sum.min_utilization = day_min
                            existing_sum.max_utilization = day_max
                            existing_sum.p95_utilization = day_p95
                            existing_sum.sample_count = len(vals)
                            existing_sum.underuse_threshold = threshold
                            existing_sum.is_underused = is_underused
                        else:
                            summary = UtilizationSummaryRecord(
                                id=str(uuid4()),
                                tracked_resource_id=tracked_res_id,
                                summary_date=day,
                                metric_name=metric_name,
                                avg_utilization=day_avg,
                                min_utilization=day_min,
                                max_utilization=day_max,
                                p95_utilization=day_p95,
                                sample_count=len(vals),
                                underuse_threshold=threshold,
                                is_underused=is_underused,
                            )
                            session.add(summary)

                        result.summaries_generated += 1
                        if is_underused:
                            result.underused_summaries_count += 1

            session.commit()

        return result

