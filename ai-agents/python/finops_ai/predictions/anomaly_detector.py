"""Cost Anomaly Detector combining Z-score baseline evaluation and Isolation Forest."""

from __future__ import annotations

from datetime import date
from typing import Any, Sequence
from uuid import uuid4

import numpy as np
from sklearn.ensemble import IsolationForest

from finops_ai.predictions.contracts import (
    AnomalySeverity,
    AnomalyStatus,
    AnomalyType,
    CostAnomaly,
)


class CostAnomalyDetector:
    """Detects and classifies cost anomalies across multiple cloud dimensions."""

    def __init__(
        self,
        z_threshold: float = 2.5,
        min_cost_delta: float = 5.0,
        rolling_window: int = 14,
    ) -> None:
        self.z_threshold = z_threshold
        self.min_cost_delta = min_cost_delta
        self.rolling_window = rolling_window

    def detect_anomalies_for_series(
        self,
        dimension: str,
        dimension_value: str,
        provider_name: str,
        dates: Sequence[date],
        costs: Sequence[float],
        resource_id: str | None = None,
        extra_details: dict[str, Any] | None = None,
    ) -> list[CostAnomaly]:
        """Analyze a time series for spikes, drifts, and drops."""
        if len(dates) < 5 or len(costs) < 5:
            return []

        paired = sorted(zip(dates, costs), key=lambda p: p[0])
        sorted_dates = [p[0] for p in paired]
        sorted_costs = np.array([p[1] for p in paired], dtype=float)

        anomalies: list[CostAnomaly] = []
        n_points = len(sorted_costs)

        # Fit Isolation Forest on 2D cost values
        if n_points >= 10:
            iso_forest = IsolationForest(contamination=0.08, random_state=42)
            iso_preds = iso_forest.fit_predict(sorted_costs.reshape(-1, 1))
        else:
            iso_preds = np.ones(n_points)

        consecutive_positive_deviations = 0

        for i in range(3, n_points):
            curr_date = sorted_dates[i]
            curr_cost = sorted_costs[i]

            # Baseline window (up to rolling_window preceding days)
            window_start = max(0, i - self.rolling_window)
            baseline = sorted_costs[window_start:i]

            base_mean = float(np.mean(baseline))
            base_std = float(np.std(baseline)) if len(baseline) > 1 else max(1.0, base_mean * 0.1)
            effective_std = max(base_std, max(1.0, base_mean * 0.05))

            delta = curr_cost - base_mean
            pct_delta = (delta / base_mean * 100.0) if base_mean > 0.01 else 0.0
            z_val = delta / effective_std

            # Track consecutive drift
            if z_val > 1.5 and delta > 2.0:
                consecutive_positive_deviations += 1
            else:
                consecutive_positive_deviations = 0

            detected_type: AnomalyType | None = None
            if z_val >= self.z_threshold and delta >= self.min_cost_delta:
                detected_type = AnomalyType.SPIKE
            elif z_val <= -self.z_threshold and abs(delta) >= self.min_cost_delta:
                detected_type = AnomalyType.DROP
            elif consecutive_positive_deviations >= 3 and delta >= self.min_cost_delta:
                detected_type = AnomalyType.DRIFT
            elif iso_preds[i] == -1 and abs(delta) >= (self.min_cost_delta * 1.5):
                detected_type = AnomalyType.SPIKE if delta > 0 else AnomalyType.DROP

            if detected_type is not None:
                # Determine severity
                severity = self._compute_severity(delta, pct_delta)
                anom_id = f"anom-{curr_date.strftime('%Y%m%d')}-{dimension_value.lower().replace('/', '-').replace(':', '-')[:32]}-{uuid4().hex[:6]}"

                details = dict(extra_details or {})
                details.update(
                    {
                        "baseline_mean": round(base_mean, 2),
                        "baseline_std": round(base_std, 2),
                        "window_size": len(baseline),
                    }
                )

                anomalies.append(
                    CostAnomaly(
                        anomaly_id=anom_id,
                        provider_name=provider_name,
                        resource_id=resource_id,
                        dimension=dimension,
                        dimension_value=dimension_value,
                        detected_date=curr_date,
                        actual_cost=round(curr_cost, 2),
                        expected_cost=round(base_mean, 2),
                        cost_delta=round(delta, 2),
                        percentage_delta=round(pct_delta, 2),
                        z_score=round(z_val, 2),
                        severity=severity,
                        anomaly_type=detected_type,
                        status=AnomalyStatus.DETECTED,
                        details=details,
                    )
                )

        return anomalies

    def _compute_severity(self, delta: float, pct_delta: float) -> AnomalySeverity:
        """Assign severity level based on dollar magnitude and relative percentage increase."""
        abs_delta = abs(delta)
        if abs_delta >= 100.0 or (pct_delta >= 100.0 and abs_delta >= 25.0):
            return AnomalySeverity.CRITICAL
        elif abs_delta >= 50.0 or (pct_delta >= 50.0 and abs_delta >= 15.0):
            return AnomalySeverity.HIGH
        elif abs_delta >= 20.0 or pct_delta >= 25.0:
            return AnomalySeverity.MEDIUM
        return AnomalySeverity.LOW
