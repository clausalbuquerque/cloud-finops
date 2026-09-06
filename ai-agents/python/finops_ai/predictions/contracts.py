"""Data contracts for forecasting and anomaly detection."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from enum import Enum
from typing import Any


class AnomalySeverity(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class AnomalyType(str, Enum):
    SPIKE = "spike"
    DRIFT = "drift"
    DROP = "drop"
    NEW_RESOURCE = "new_resource"


class AnomalyStatus(str, Enum):
    DETECTED = "detected"
    INVESTIGATING = "investigating"
    RESOLVED = "resolved"
    DISMISSED = "dismissed"


class ForecastHorizon(str, Enum):
    NEXT_DAY = "next_day"
    NEXT_7_DAYS = "next_7_days"
    END_OF_MONTH = "end_of_month"


@dataclass
class ForecastPoint:
    """A single daily forecast point."""

    forecast_date: date
    expected_cost: float
    lower_bound: float
    upper_bound: float


@dataclass
class SpendForecast:
    """Aggregated spend forecast for a given dimension and horizon."""

    dimension: str
    provider_name: str
    horizon: ForecastHorizon | str
    current_run_rate: float
    projected_total: float
    points: list[ForecastPoint] = field(default_factory=list)
    confidence_level: float = 0.95
    model_name: str = "ridge_seasonal"
    mape: float | None = None
    generated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> dict[str, Any]:
        return {
            "dimension": self.dimension,
            "provider_name": self.provider_name,
            "horizon": str(self.horizon),
            "current_run_rate": round(self.current_run_rate, 2),
            "projected_total": round(self.projected_total, 2),
            "confidence_level": self.confidence_level,
            "model_name": self.model_name,
            "mape": round(self.mape, 4) if self.mape is not None else None,
            "points_count": len(self.points),
            "generated_at": self.generated_at.isoformat(),
        }


@dataclass
class CostAnomaly:
    """Detected cost anomaly record."""

    anomaly_id: str
    provider_name: str
    dimension: str
    dimension_value: str
    detected_date: date
    actual_cost: float
    expected_cost: float
    cost_delta: float
    percentage_delta: float
    z_score: float | None = None
    severity: AnomalySeverity | str = AnomalySeverity.MEDIUM
    anomaly_type: AnomalyType | str = AnomalyType.SPIKE
    status: AnomalyStatus | str = AnomalyStatus.DETECTED
    resource_id: str | None = None
    details: dict[str, Any] = field(default_factory=dict)
    detected_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> dict[str, Any]:
        return {
            "anomaly_id": self.anomaly_id,
            "provider_name": self.provider_name,
            "resource_id": self.resource_id,
            "dimension": self.dimension,
            "dimension_value": self.dimension_value,
            "detected_date": self.detected_date.isoformat(),
            "actual_cost": round(self.actual_cost, 2),
            "expected_cost": round(self.expected_cost, 2),
            "cost_delta": round(self.cost_delta, 2),
            "percentage_delta": round(self.percentage_delta, 2),
            "z_score": round(self.z_score, 2) if self.z_score is not None else None,
            "severity": str(self.severity),
            "anomaly_type": str(self.anomaly_type),
            "status": str(self.status),
            "details": self.details,
            "detected_at": self.detected_at.isoformat(),
        }


@dataclass
class BacktestMetrics:
    """Evaluation metrics for time-series forecaster."""

    dimension: str
    mape: float
    rmse: float
    sample_count: int
