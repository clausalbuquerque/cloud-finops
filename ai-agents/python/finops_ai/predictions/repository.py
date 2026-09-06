"""SQLAlchemy repository for forecasts and cost anomalies."""

from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Any, Sequence
from uuid import uuid4

import numpy as np
from sqlalchemy import Date, DateTime, Float, Numeric, String, Text, create_engine, desc, func, select
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, sessionmaker

from finops_ai.predictions.contracts import (
    AnomalySeverity,
    AnomalyStatus,
    AnomalyType,
    CostAnomaly,
    ForecastHorizon,
    ForecastPoint,
    SpendForecast,
)


class Base(DeclarativeBase):
    pass


class CostForecastRecord(Base):
    __tablename__ = "cost_forecasts"
    __table_args__ = {"schema": "finops"}

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True)
    dimension: Mapped[str] = mapped_column(String(128))
    provider_name: Mapped[str] = mapped_column(String(64), default="GCP")
    forecast_date: Mapped[date] = mapped_column(Date)
    expected_cost: Mapped[Decimal] = mapped_column(Numeric(18, 6))
    lower_bound: Mapped[Decimal] = mapped_column(Numeric(18, 6))
    upper_bound: Mapped[Decimal] = mapped_column(Numeric(18, 6))
    confidence_level: Mapped[float] = mapped_column(Float, default=0.95)
    model_name: Mapped[str] = mapped_column(String(64), default="ridge_seasonal")
    mape: Mapped[float | None] = mapped_column(Float, nullable=True)
    generated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )


class CostAnomalyRecord(Base):
    __tablename__ = "cost_anomalies"
    __table_args__ = {"schema": "finops"}

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True)
    anomaly_id: Mapped[str] = mapped_column(String(128), unique=True)
    provider_name: Mapped[str] = mapped_column(String(64), default="GCP")
    resource_id: Mapped[str | None] = mapped_column(String(512), nullable=True)
    dimension: Mapped[str] = mapped_column(String(64))
    dimension_value: Mapped[str] = mapped_column(String(256))
    detected_date: Mapped[date] = mapped_column(Date)
    actual_cost: Mapped[Decimal] = mapped_column(Numeric(18, 6))
    expected_cost: Mapped[Decimal] = mapped_column(Numeric(18, 6))
    cost_delta: Mapped[Decimal] = mapped_column(Numeric(18, 6))
    percentage_delta: Mapped[float] = mapped_column(Float)
    z_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    severity: Mapped[str] = mapped_column(String(32), default="medium")
    anomaly_type: Mapped[str] = mapped_column(String(32), default="spike")
    status: Mapped[str] = mapped_column(String(32), default="detected")
    details: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    detected_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )


class ConsumptionRecord(Base):
    __tablename__ = "consumption_records"
    __table_args__ = {"schema": "finops"}

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True)
    provider_name: Mapped[str] = mapped_column(String)
    service_category: Mapped[str | None] = mapped_column(String, nullable=True)
    sub_account_name: Mapped[str | None] = mapped_column(String, nullable=True)
    resource_id: Mapped[str | None] = mapped_column(String, nullable=True)
    effective_cost: Mapped[Decimal | None] = mapped_column(Numeric(18, 6), nullable=True)
    usage_date: Mapped[date] = mapped_column(Date)


class PredictionsRepository:
    """DAO for storing forecasts, anomalies, and aggregating consumption history."""

    def __init__(self, session_factory: sessionmaker[Session]) -> None:
        self._session_factory = session_factory

    @classmethod
    def from_url(cls, db_url: str) -> "PredictionsRepository":
        engine = create_engine(db_url, future=True)
        return cls(session_factory=sessionmaker(bind=engine, future=True))

    def store_forecast(self, forecast: SpendForecast) -> None:
        """Store or update forecast points in finops.cost_forecasts."""
        with self._session_factory() as session:
            for pt in forecast.points:
                existing = session.scalars(
                    select(CostForecastRecord).where(
                        CostForecastRecord.dimension == forecast.dimension,
                        CostForecastRecord.forecast_date == pt.forecast_date,
                    )
                ).first()

                if existing:
                    existing.expected_cost = Decimal(str(pt.expected_cost))
                    existing.lower_bound = Decimal(str(pt.lower_bound))
                    existing.upper_bound = Decimal(str(pt.upper_bound))
                    existing.confidence_level = forecast.confidence_level
                    existing.model_name = forecast.model_name
                    existing.mape = forecast.mape
                    existing.generated_at = datetime.now(timezone.utc)
                else:
                    rec = CostForecastRecord(
                        id=str(uuid4()),
                        dimension=forecast.dimension,
                        provider_name=forecast.provider_name,
                        forecast_date=pt.forecast_date,
                        expected_cost=Decimal(str(pt.expected_cost)),
                        lower_bound=Decimal(str(pt.lower_bound)),
                        upper_bound=Decimal(str(pt.upper_bound)),
                        confidence_level=forecast.confidence_level,
                        model_name=forecast.model_name,
                        mape=forecast.mape,
                    )
                    session.add(rec)

            session.commit()

    def get_forecast(self, dimension: str, horizon: str = "end_of_month") -> SpendForecast | None:
        """Retrieve stored forecast for a dimension."""
        with self._session_factory() as session:
            stmt = (
                select(CostForecastRecord)
                .where(CostForecastRecord.dimension == dimension)
                .order_by(CostForecastRecord.forecast_date.asc())
            )
            records = list(session.scalars(stmt).all())
            if not records:
                return None

            points = [
                ForecastPoint(
                    forecast_date=r.forecast_date,
                    expected_cost=float(r.expected_cost),
                    lower_bound=float(r.lower_bound),
                    upper_bound=float(r.upper_bound),
                )
                for r in records
            ]

            first = records[0]
            projected_total = sum(p.expected_cost for p in points)
            run_rate = float(np.mean([p.expected_cost for p in points])) if points else 0.0

            return SpendForecast(
                dimension=dimension,
                provider_name=first.provider_name,
                horizon=horizon,
                current_run_rate=run_rate,
                projected_total=projected_total,
                points=points,
                confidence_level=first.confidence_level,
                model_name=first.model_name,
                mape=first.mape,
                generated_at=first.generated_at,
            )

    def store_anomalies(self, anomalies: Sequence[CostAnomaly]) -> int:
        """Upsert detected cost anomalies."""
        count = 0
        with self._session_factory() as session:
            for anom in anomalies:
                existing = session.scalars(
                    select(CostAnomalyRecord).where(CostAnomalyRecord.anomaly_id == anom.anomaly_id)
                ).first()

                if existing:
                    existing.actual_cost = Decimal(str(anom.actual_cost))
                    existing.expected_cost = Decimal(str(anom.expected_cost))
                    existing.cost_delta = Decimal(str(anom.cost_delta))
                    existing.percentage_delta = anom.percentage_delta
                    existing.z_score = anom.z_score
                    existing.severity = str(anom.severity)
                    existing.status = str(anom.status)
                    existing.details = anom.details
                else:
                    rec = CostAnomalyRecord(
                        id=str(uuid4()),
                        anomaly_id=anom.anomaly_id,
                        provider_name=anom.provider_name,
                        resource_id=anom.resource_id,
                        dimension=anom.dimension,
                        dimension_value=anom.dimension_value,
                        detected_date=anom.detected_date,
                        actual_cost=Decimal(str(anom.actual_cost)),
                        expected_cost=Decimal(str(anom.expected_cost)),
                        cost_delta=Decimal(str(anom.cost_delta)),
                        percentage_delta=anom.percentage_delta,
                        z_score=anom.z_score,
                        severity=str(anom.severity),
                        anomaly_type=str(anom.anomaly_type),
                        status=str(anom.status),
                        details=anom.details,
                    )
                    session.add(rec)
                    count += 1

            session.commit()
        return count

    def get_anomalies(
        self,
        severity: str | None = None,
        status: str | None = None,
        dimension: str | None = None,
        min_date: date | None = None,
    ) -> list[CostAnomaly]:
        """Query detected cost anomalies with optional filtering."""
        with self._session_factory() as session:
            stmt = select(CostAnomalyRecord)
            if severity:
                stmt = stmt.where(CostAnomalyRecord.severity == severity.lower())
            if status:
                stmt = stmt.where(CostAnomalyRecord.status == status.lower())
            if dimension:
                stmt = stmt.where(CostAnomalyRecord.dimension == dimension)
            if min_date:
                stmt = stmt.where(CostAnomalyRecord.detected_date >= min_date)

            stmt = stmt.order_by(desc(CostAnomalyRecord.detected_date), desc(CostAnomalyRecord.cost_delta))
            records = list(session.scalars(stmt).all())

            return [
                CostAnomaly(
                    anomaly_id=r.anomaly_id,
                    provider_name=r.provider_name,
                    resource_id=r.resource_id,
                    dimension=r.dimension,
                    dimension_value=r.dimension_value,
                    detected_date=r.detected_date,
                    actual_cost=float(r.actual_cost),
                    expected_cost=float(r.expected_cost),
                    cost_delta=float(r.cost_delta),
                    percentage_delta=r.percentage_delta,
                    z_score=r.z_score,
                    severity=AnomalySeverity(r.severity) if r.severity in AnomalySeverity._value2member_map_ else r.severity,
                    anomaly_type=AnomalyType(r.anomaly_type) if r.anomaly_type in AnomalyType._value2member_map_ else r.anomaly_type,
                    status=AnomalyStatus(r.status) if r.status in AnomalyStatus._value2member_map_ else r.status,
                    details=r.details or {},
                    detected_at=r.detected_at,
                )
                for r in records
            ]

    def get_aggregated_cost_series(
        self, group_by_col: str = "service_category"
    ) -> dict[str, tuple[str, list[tuple[date, float]]]]:
        """Fetch historical cost series aggregated by the specified dimension column."""
        # Supported column mappings
        col_attr = {
            "service_category": ConsumptionRecord.service_category,
            "sub_account_name": ConsumptionRecord.sub_account_name,
            "resource_id": ConsumptionRecord.resource_id,
        }.get(group_by_col, ConsumptionRecord.service_category)

        with self._session_factory() as session:
            stmt = (
                select(
                    col_attr.label("dim_val"),
                    ConsumptionRecord.provider_name,
                    ConsumptionRecord.usage_date,
                    func.sum(ConsumptionRecord.effective_cost).label("total_cost"),
                )
                .where(col_attr.is_not(None))
                .group_by(col_attr, ConsumptionRecord.provider_name, ConsumptionRecord.usage_date)
                .order_by(ConsumptionRecord.usage_date.asc())
            )

            rows = session.execute(stmt).all()
            series_map: dict[str, tuple[str, list[tuple[date, float]]]] = {}

            for dim_val, prov, dt, cost in rows:
                if not dim_val:
                    continue
                if dim_val not in series_map:
                    series_map[dim_val] = (prov, [])
                series_map[dim_val][1].append((dt, float(cost or Decimal("0.0"))))

            return series_map
