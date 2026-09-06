from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal
import unittest
from unittest.mock import MagicMock

from finops_ai.predictions import (
    AnomalySeverity,
    AnomalyStatus,
    AnomalyType,
    CostAnomaly,
    CostAnomalyDetector,
    ForecastHorizon,
    ForecastPoint,
    PredictionsPipeline,
    PredictionsRepository,
    SpendForecast,
    SpendForecaster,
)
from finops_ai.predictions.repository import (
    ConsumptionRecord,
    CostAnomalyRecord,
    CostForecastRecord,
)


class TestPredictionsPipeline(unittest.TestCase):
    def setUp(self) -> None:
        self.mock_session = MagicMock()
        self.mock_session_factory = MagicMock()
        self.mock_session_factory.return_value.__enter__.return_value = self.mock_session
        self.repo = PredictionsRepository(self.mock_session_factory)

    def test_forecaster_fit_and_predict(self) -> None:
        start_date = date(2026, 8, 1)
        dates = [start_date + timedelta(days=i) for i in range(20)]
        costs = [100.0 + (i % 7) * 5.0 for i in range(20)]

        forecaster = SpendForecaster()
        metrics = forecaster.fit(dates, costs)

        self.assertIsNotNone(metrics.mape)
        self.assertLess(metrics.mape, 0.20)  # MAPE within reasonable tolerance
        self.assertEqual(metrics.sample_count, 20)

        # Predict next 7 days
        points = forecaster.forecast_days(horizon_days=7)
        self.assertEqual(len(points), 7)

        for pt in points:
            self.assertGreater(pt.expected_cost, 80.0)
            self.assertLess(pt.expected_cost, 150.0)
            self.assertGreaterEqual(pt.upper_bound, pt.expected_cost)
            self.assertLessEqual(pt.lower_bound, pt.expected_cost)

    def test_forecaster_scenario_multiplier(self) -> None:
        start_date = date(2026, 8, 1)
        dates = [start_date + timedelta(days=i) for i in range(15)]
        costs = [100.0 for _ in range(15)]

        forecaster = SpendForecaster()
        forecaster.fit(dates, costs)

        baseline_points = forecaster.forecast_days(horizon_days=5, scenario_multiplier=1.0)
        reduced_points = forecaster.forecast_days(horizon_days=5, scenario_multiplier=0.5)

        for b, r in zip(baseline_points, reduced_points):
            self.assertAlmostEqual(r.expected_cost, b.expected_cost * 0.5, places=1)

    def test_anomaly_detector_injected_spike(self) -> None:
        start_date = date(2026, 8, 1)
        dates = [start_date + timedelta(days=i) for i in range(25)]
        # Normal cost: $142.25/day for days 0-19; Spike: $284.50 on day 20+
        costs = [142.25] * 20 + [284.50] * 5

        detector = CostAnomalyDetector(z_threshold=2.5, min_cost_delta=10.0)
        anomalies = detector.detect_anomalies_for_series(
            dimension="resourceId",
            dimension_value="analytics-worker-02",
            provider_name="Google",
            dates=dates,
            costs=costs,
            resource_id="projects/prod-analytics/zones/us-central1-a/instances/analytics-worker-02",
        )

        self.assertGreater(len(anomalies), 0)
        spike = anomalies[0]
        self.assertEqual(spike.anomaly_type, AnomalyType.SPIKE)
        self.assertIn(spike.severity, [AnomalySeverity.CRITICAL, AnomalySeverity.HIGH])
        self.assertGreater(spike.cost_delta, 100.0)
        self.assertAlmostEqual(spike.percentage_delta, 100.0, delta=5.0)

    def test_anomaly_detector_injected_drop(self) -> None:
        start_date = date(2026, 8, 1)
        dates = [start_date + timedelta(days=i) for i in range(20)]
        costs = [200.0] * 15 + [20.0] * 5

        detector = CostAnomalyDetector(z_threshold=2.5, min_cost_delta=10.0)
        anomalies = detector.detect_anomalies_for_series(
            dimension="service_category",
            dimension_value="Compute",
            provider_name="Azure",
            dates=dates,
            costs=costs,
        )

        self.assertGreater(len(anomalies), 0)
        drop = anomalies[0]
        self.assertEqual(drop.anomaly_type, AnomalyType.DROP)
        self.assertLess(drop.cost_delta, -100.0)

    def test_repository_store_and_get_forecast(self) -> None:
        # Mock scalar query returning mock record
        mock_rec = MagicMock(spec=CostForecastRecord)
        mock_rec.dimension = "service:Compute"
        mock_rec.provider_name = "Google"
        mock_rec.forecast_date = date(2026, 8, 31)
        mock_rec.expected_cost = Decimal("1500.00")
        mock_rec.lower_bound = Decimal("1400.00")
        mock_rec.upper_bound = Decimal("1600.00")
        mock_rec.confidence_level = 0.95
        mock_rec.model_name = "ridge_seasonal"
        mock_rec.mape = 0.03
        mock_rec.generated_at = None

        self.mock_session.scalars.return_value.all.return_value = [mock_rec]

        forecast = self.repo.get_forecast("service:Compute")
        self.assertIsNotNone(forecast)
        self.assertEqual(forecast.dimension, "service:Compute")
        self.assertEqual(forecast.projected_total, 1500.0)

    def test_pipeline_orchestration(self) -> None:
        mock_series = {
            "Compute": (
                "Google",
                [(date(2026, 8, 1) + timedelta(days=i), 150.0 + i) for i in range(15)],
            )
        }
        self.repo.get_aggregated_cost_series = MagicMock(return_value=mock_series)

        pipeline = PredictionsPipeline(repository=self.repo)
        result = pipeline.run()

        self.assertGreater(result.dimensions_processed, 0)
        self.assertGreater(result.forecasts_stored, 0)
