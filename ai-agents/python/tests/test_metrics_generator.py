from __future__ import annotations

from datetime import date, datetime, timezone
import unittest
from unittest.mock import MagicMock

from finops_ai.loaders.metrics_generator import (
    MetricDefinitionRecord,
    ResourceGroupRecord,
    SubscriptionRecord,
    SyntheticMetricsGenerator,
    SyntheticResourceConfig,
    TRACKED_RESOURCE_SPECS,
    TrackedResourceRecord,
)


class TestSyntheticMetricsGenerator(unittest.TestCase):
    def setUp(self) -> None:
        self.mock_session = MagicMock()
        self.mock_session_factory = MagicMock()
        self.mock_session_factory.return_value.__enter__.return_value = self.mock_session
        self.generator = SyntheticMetricsGenerator(self.mock_session_factory, seed=42)

    def test_tracked_resource_specs_coverage(self) -> None:
        # Assert specs include key test resources from design doc
        resource_ids = [spec.resource_id for spec in TRACKED_RESOURCE_SPECS]
        self.assertIn(
            "projects/prod-analytics/zones/us-central1-a/instances/analytics-worker-01",
            resource_ids,
        )
        self.assertIn(
            "projects/prod-analytics/zones/us-central1-a/instances/analytics-worker-02",
            resource_ids,
        )
        self.assertIn(
            "projects/prod-analytics/zones/us-central1-b/instances/batch-worker-01",
            resource_ids,
        )
        self.assertIn(
            "projects/prod-analytics/instances/analytics-db-01",
            resource_ids,
        )

        # Ensure provisioned capacity is populated
        for spec in TRACKED_RESOURCE_SPECS:
            self.assertTrue(len(spec.provisioned_capacity) > 0)

    def test_generate_hourly_series_underused_vm(self) -> None:
        upsized_vm_spec = next(
            s for s in TRACKED_RESOURCE_SPECS if "analytics-worker-02" in s.resource_id
        )
        start_dt = datetime(2026, 8, 1, 0, 0, 0, tzinfo=timezone.utc)
        series = self.generator._generate_hourly_series(upsized_vm_spec, start_dt, hours=24 * 7)

        self.assertEqual(len(series), 24 * 7)
        avg_vals = [p[1] for p in series]
        mean_cpu = sum(avg_vals) / len(avg_vals)

        # Underused VM must average well below 10% threshold
        self.assertLess(mean_cpu, 10.0)
        self.assertGreater(mean_cpu, 2.0)

    def test_generate_hourly_series_nightly_batch_vm(self) -> None:
        batch_vm_spec = next(
            s for s in TRACKED_RESOURCE_SPECS if "batch-worker-01" in s.resource_id
        )
        start_dt = datetime(2026, 8, 1, 0, 0, 0, tzinfo=timezone.utc)
        series = self.generator._generate_hourly_series(batch_vm_spec, start_dt, hours=24)

        # Night hours (e.g. 23:00, 02:00) must have high CPU, daytime (12:00) must be low
        daytime_cpus = [p[1] for p in series if 8 <= p[0].hour <= 18]
        nighttime_cpus = [p[1] for p in series if p[0].hour in (23, 0, 1, 2, 3)]

        self.assertLess(sum(daytime_cpus) / len(daytime_cpus), 8.0)
        self.assertGreater(sum(nighttime_cpus) / len(nighttime_cpus), 50.0)

    def test_generate_hourly_series_healthy_vm(self) -> None:
        healthy_vm_spec = next(
            s for s in TRACKED_RESOURCE_SPECS if "analytics-worker-01" in s.resource_id
        )
        start_dt = datetime(2026, 8, 1, 0, 0, 0, tzinfo=timezone.utc)
        series = self.generator._generate_hourly_series(healthy_vm_spec, start_dt, hours=24 * 7)

        avg_vals = [p[1] for p in series]
        mean_cpu = sum(avg_vals) / len(avg_vals)

        # Healthy VM should average between 35% and 65%
        self.assertGreater(mean_cpu, 35.0)
        self.assertLess(mean_cpu, 65.0)

    def test_generate_pipeline_execution(self) -> None:
        # Mock database queries to return empty existing objects
        self.mock_session.scalars.return_value.first.return_value = None

        result = self.generator.generate(days=3, end_date=date(2026, 8, 22))

        self.assertEqual(result.tracked_resources_count, len(TRACKED_RESOURCE_SPECS))
        self.assertGreater(result.data_points_generated, 0)
        self.assertGreater(result.summaries_generated, 0)
        self.assertGreater(result.underused_summaries_count, 0)
        self.mock_session.commit.assert_called()

    def test_seed_determinism(self) -> None:
        spec = TRACKED_RESOURCE_SPECS[0]
        start_dt = datetime(2026, 8, 1, 0, 0, 0, tzinfo=timezone.utc)

        gen1 = SyntheticMetricsGenerator(self.mock_session_factory, seed=123)
        series1 = gen1._generate_hourly_series(spec, start_dt, hours=48)

        gen2 = SyntheticMetricsGenerator(self.mock_session_factory, seed=123)
        series2 = gen2._generate_hourly_series(spec, start_dt, hours=48)

        self.assertEqual([p[1] for p in series1], [p[1] for p in series2])

