"""Predictions pipeline orchestrator for batch forecasting and anomaly detection."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Any

from finops_ai.predictions.anomaly_detector import CostAnomalyDetector
from finops_ai.predictions.contracts import CostAnomaly, ForecastHorizon, SpendForecast
from finops_ai.predictions.forecaster import SpendForecaster
from finops_ai.predictions.repository import PredictionsRepository


@dataclass
class PipelineRunResult:
    """Summary of a predictions pipeline execution run."""

    dimensions_processed: int = 0
    forecasts_stored: int = 0
    anomalies_detected: int = 0
    critical_anomalies_count: int = 0
    high_anomalies_count: int = 0
    top_anomalies: list[CostAnomaly] = field(default_factory=list)


class PredictionsPipeline:
    """Orchestrates end-to-end forecasting and anomaly detection over consumption data."""

    def __init__(
        self,
        repository: PredictionsRepository,
        forecaster: SpendForecaster | None = None,
        anomaly_detector: CostAnomalyDetector | None = None,
    ) -> None:
        self.repository = repository
        self.forecaster = forecaster or SpendForecaster()
        self.anomaly_detector = anomaly_detector or CostAnomalyDetector()

    def run(self) -> PipelineRunResult:
        """Run forecasting and anomaly detection across services, teams, and top resources."""
        result = PipelineRunResult()
        all_detected_anomalies: list[CostAnomaly] = []

        dimensions_to_process = [
            ("service_category", "service:"),
            ("sub_account_name", "team:"),
            ("resource_id", "resource:"),
        ]

        for dim_col, dim_prefix in dimensions_to_process:
            series_map = self.repository.get_aggregated_cost_series(group_by_col=dim_col)

            for dim_val, (prov, points) in series_map.items():
                if len(points) < 4:
                    continue

                dates = [p[0] for p in points]
                costs = [p[1] for p in points]
                dim_key = f"{dim_prefix}{dim_val}"

                result.dimensions_processed += 1

                # 1. Anomaly Detection
                res_id = dim_val if dim_col == "resource_id" else None
                anomalies = self.anomaly_detector.detect_anomalies_for_series(
                    dimension=dim_col,
                    dimension_value=dim_val,
                    provider_name=prov,
                    dates=dates,
                    costs=costs,
                    resource_id=res_id,
                )
                if anomalies:
                    all_detected_anomalies.extend(anomalies)

                # 2. Time-series Forecasting
                try:
                    f = SpendForecaster()
                    f.fit(dates, costs)
                    forecast = f.generate_spend_forecast(
                        dimension=dim_key,
                        provider_name=prov,
                        horizon=ForecastHorizon.END_OF_MONTH,
                    )
                    self.repository.store_forecast(forecast)
                    result.forecasts_stored += 1
                except Exception:
                    pass

        # Persist all anomalies
        if all_detected_anomalies:
            self.repository.store_anomalies(all_detected_anomalies)
            result.anomalies_detected = len(all_detected_anomalies)

            for a in all_detected_anomalies:
                if str(a.severity) == "critical":
                    result.critical_anomalies_count += 1
                elif str(a.severity) == "high":
                    result.high_anomalies_count += 1

            # Top 5 by cost delta
            sorted_anom = sorted(all_detected_anomalies, key=lambda a: a.cost_delta, reverse=True)
            result.top_anomalies = sorted_anom[:5]

        return result
