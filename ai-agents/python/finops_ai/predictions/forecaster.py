"""Time-series statistical spend forecaster with prediction intervals."""

from __future__ import annotations

from datetime import date, timedelta
import math
from typing import Sequence

import numpy as np
from sklearn.linear_model import Ridge

from finops_ai.predictions.contracts import (
    BacktestMetrics,
    ForecastHorizon,
    ForecastPoint,
    SpendForecast,
)


class SpendForecaster:
    """Statistical & ML time-series forecaster for cloud spend."""

    def __init__(self, model_name: str = "ridge_seasonal") -> None:
        self.model_name = model_name
        self._model = Ridge(alpha=1.0)
        self._is_fitted = False
        self._base_date: date | None = None
        self._residual_std: float = 0.0
        self._mape: float | None = None
        self._last_date: date | None = None
        self._mean_cost: float = 0.0

    def _build_features(self, dates: Sequence[date]) -> np.ndarray:
        """Create feature matrix: trend index, day-of-week sine/cosine, weekend indicator."""
        if not dates or self._base_date is None:
            return np.empty((0, 4))

        features = []
        for d in dates:
            day_idx = (d - self._base_date).days
            dow = d.weekday()
            dow_sin = math.sin(2.0 * math.pi * dow / 7.0)
            dow_cos = math.cos(2.0 * math.pi * dow / 7.0)
            is_weekend = 1.0 if dow >= 5 else 0.0
            features.append([day_idx, dow_sin, dow_cos, is_weekend])

        return np.array(features, dtype=float)

    def fit(self, dates: Sequence[date], costs: Sequence[float]) -> BacktestMetrics:
        """Fit model on historical cost series and compute backtest evaluation metrics."""
        if len(dates) < 3 or len(costs) < 3:
            raise ValueError("At least 3 historical data points are required to fit forecaster")

        # Sort chronologically
        paired = sorted(zip(dates, costs), key=lambda p: p[0])
        sorted_dates = [p[0] for p in paired]
        sorted_costs = np.array([p[1] for p in paired], dtype=float)

        self._base_date = sorted_dates[0]
        self._last_date = sorted_dates[-1]
        self._mean_cost = float(np.mean(sorted_costs))

        X = self._build_features(sorted_dates)
        y = sorted_costs

        # Train on first 80%, validate on holdout (last 20%) if sufficient data
        n_samples = len(sorted_dates)
        if n_samples >= 7:
            split_idx = max(3, int(n_samples * 0.8))
            X_train, y_train = X[:split_idx], y[:split_idx]
            X_val, y_val = X[split_idx:], y[split_idx:]

            self._model.fit(X_train, y_train)
            y_pred_val = np.maximum(0.0, self._model.predict(X_val))

            # Compute MAPE on validation holdout
            non_zero_mask = y_val > 0.01
            if np.any(non_zero_mask):
                val_mape = float(
                    np.mean(np.abs((y_val[non_zero_mask] - y_pred_val[non_zero_mask]) / y_val[non_zero_mask]))
                )
            else:
                val_mape = 0.0
            val_rmse = float(np.sqrt(np.mean((y_val - y_pred_val) ** 2)))
        else:
            val_mape = 0.05
            val_rmse = 1.0

        # Refit on all available data
        self._model.fit(X, y)
        y_pred_all = np.maximum(0.0, self._model.predict(X))
        residuals = y - y_pred_all
        self._residual_std = float(np.std(residuals)) if len(residuals) > 1 else max(1.0, self._mean_cost * 0.05)
        self._mape = val_mape
        self._is_fitted = True

        return BacktestMetrics(
            dimension="total",
            mape=val_mape,
            rmse=val_rmse,
            sample_count=n_samples,
        )

    def forecast_days(
        self,
        horizon_days: int = 14,
        start_date: date | None = None,
        confidence_level: float = 0.95,
        scenario_multiplier: float = 1.0,
    ) -> list[ForecastPoint]:
        """Generate daily forecast points with upper and lower confidence bounds."""
        if not self._is_fitted or self._last_date is None:
            raise RuntimeError("Forecaster must be fitted before predicting")

        start = start_date or (self._last_date + timedelta(days=1))
        future_dates = [start + timedelta(days=i) for i in range(horizon_days)]

        X_future = self._build_features(future_dates)
        raw_preds = self._model.predict(X_future) * scenario_multiplier

        # Z-factor for confidence intervals (approx 1.96 for 95%)
        z_score = 1.96 if confidence_level >= 0.95 else 1.645

        points: list[ForecastPoint] = []
        for i, (f_date, raw_val) in enumerate(zip(future_dates, raw_preds)):
            expected = max(0.0, float(raw_val))
            # Uncertainty grows with horizon
            uncertainty = z_score * self._residual_std * math.sqrt(1.0 + (i + 1) / 14.0)
            lower = max(0.0, expected - uncertainty)
            upper = expected + uncertainty

            points.append(
                ForecastPoint(
                    forecast_date=f_date,
                    expected_cost=round(expected, 2),
                    lower_bound=round(lower, 2),
                    upper_bound=round(upper, 2),
                )
            )

        return points

    def generate_spend_forecast(
        self,
        dimension: str,
        provider_name: str,
        horizon: ForecastHorizon | str = ForecastHorizon.END_OF_MONTH,
        current_daily_rate: float | None = None,
        scenario_multiplier: float = 1.0,
    ) -> SpendForecast:
        """Produce a full SpendForecast object for the specified horizon."""
        if self._last_date is None:
            raise RuntimeError("Forecaster has no last_date")

        # Determine number of days to forecast based on horizon
        if str(horizon) == str(ForecastHorizon.NEXT_DAY) or horizon == "next_day":
            days = 1
        elif str(horizon) == str(ForecastHorizon.NEXT_7_DAYS) or horizon == "next_7_days":
            days = 7
        else:  # END_OF_MONTH default
            # Days remaining in the month of last_date
            curr_month = self._last_date.month
            next_month = (curr_month % 12) + 1
            next_year = self._last_date.year if curr_month < 12 else self._last_date.year + 1
            last_day_of_month = date(next_year, next_month, 1) - timedelta(days=1)
            days = max(1, (last_day_of_month - self._last_date).days)

        points = self.forecast_days(
            horizon_days=days,
            confidence_level=0.95,
            scenario_multiplier=scenario_multiplier,
        )

        projected_total = sum(p.expected_cost for p in points)
        run_rate = current_daily_rate if current_daily_rate is not None else self._mean_cost

        return SpendForecast(
            dimension=dimension,
            provider_name=provider_name,
            horizon=horizon,
            current_run_rate=run_rate,
            projected_total=projected_total,
            points=points,
            confidence_level=0.95,
            model_name=self.model_name,
            mape=self._mape,
        )
