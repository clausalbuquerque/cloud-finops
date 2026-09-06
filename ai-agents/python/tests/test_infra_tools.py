from __future__ import annotations

from datetime import date, datetime, timezone
import unittest
from unittest.mock import MagicMock, patch

from finops_ai.memory.contracts import InfrastructureBaseline
from finops_ai.tools.infra_tools import (
    get_infrastructure_baselines,
    get_metric_definitions,
    get_tracked_resources,
    get_utilization_summaries,
    query_resource_dependencies,
    store_infrastructure_baseline,
    update_underuse_threshold,
)


class TestInfraTools(unittest.TestCase):
    @patch("finops_ai.tools.infra_tools._get_session")
    def test_get_tracked_resources(self, mock_get_session: MagicMock) -> None:
        mock_session = MagicMock()
        mock_get_session.return_value.__enter__.return_value = mock_session

        mock_res = MagicMock()
        mock_res.id = "uuid-res-1"
        mock_res.azure_resource_id = "projects/p1/zones/z1/instances/w1"
        mock_res.resource_name = "w1"
        mock_res.resource_type = "compute/instance"
        mock_res.region = "us-central1"
        mock_res.sku = "n2-standard-16"
        mock_res.provisioned_capacity = {"vCPUs": 16, "memoryGB": 64}
        mock_res.is_active = True

        mock_session.scalars.return_value.all.return_value = [mock_res]

        result = get_tracked_resources._run(
            resource_type="compute/instance",
            region="us-central1",
        )

        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["resource_name"], "w1")
        self.assertEqual(result[0]["sku"], "n2-standard-16")
        self.assertEqual(result[0]["provisioned_capacity"]["vCPUs"], 16)

    @patch("finops_ai.tools.infra_tools._get_session")
    def test_get_utilization_summaries(self, mock_get_session: MagicMock) -> None:
        mock_session = MagicMock()
        mock_get_session.return_value.__enter__.return_value = mock_session

        mock_res = MagicMock()
        mock_res.id = "uuid-res-1"
        mock_res.azure_resource_id = "projects/p1/zones/z1/instances/w1"

        mock_sum = MagicMock()
        mock_sum.tracked_resource_id = "uuid-res-1"
        mock_sum.summary_date = date(2026, 8, 20)
        mock_sum.metric_name = "Percentage CPU"
        mock_sum.avg_utilization = 8.5
        mock_sum.max_utilization = 18.2
        mock_sum.min_utilization = 2.1
        mock_sum.p95_utilization = 14.0
        mock_sum.sample_count = 24
        mock_sum.underuse_threshold = 15.0
        mock_sum.is_underused = True

        # First call gets resources, second call gets summaries
        mock_session.scalars.return_value.all.side_effect = [
            [mock_res],
            [mock_sum],
        ]

        result = get_utilization_summaries._run(
            resource_ids=["projects/p1/zones/z1/instances/w1"],
            date_range="last_30d",
        )

        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["resource_id"], "projects/p1/zones/z1/instances/w1")
        self.assertEqual(result[0]["avg_utilization"], 8.5)
        self.assertEqual(result[0]["p95_utilization"], 14.0)
        self.assertTrue(result[0]["is_underused"])

    @patch("finops_ai.tools.infra_tools._get_session")
    def test_get_metric_definitions(self, mock_get_session: MagicMock) -> None:
        mock_session = MagicMock()
        mock_get_session.return_value.__enter__.return_value = mock_session

        mock_def = MagicMock()
        mock_def.resource_type = "compute/instance"
        mock_def.metric_name = "Percentage CPU"
        mock_def.display_name = "CPU Utilization"
        mock_def.unit = "Percent"
        mock_def.primary_aggregation = "Average"
        mock_def.underuse_threshold = 15.0

        mock_session.scalars.return_value.all.return_value = [mock_def]

        result = get_metric_definitions._run(resource_type="compute/instance")
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["metric_name"], "Percentage CPU")
        self.assertEqual(result[0]["underuse_threshold"], 15.0)

    def test_query_resource_dependencies(self) -> None:
        result = query_resource_dependencies._run(
            resource_ids=["projects/p1/zones/z1/instances/analytics-worker-02"]
        )

        self.assertEqual(result["status"], "ok")
        self.assertIn("projects/p1/zones/z1/instances/analytics-worker-02", result["dependencies"])
        dep = result["dependencies"]["projects/p1/zones/z1/instances/analytics-worker-02"]
        self.assertEqual(dep["risk_level"], "LOW")
        self.assertGreater(len(dep["attached_disks"]), 0)

    @patch("finops_ai.tools.infra_tools._get_memory_repo")
    def test_infrastructure_baselines_tools(self, mock_get_repo: MagicMock) -> None:
        mock_repo = MagicMock()
        mock_get_repo.return_value = mock_repo

        mock_baseline = InfrastructureBaseline(
            id="base-001",
            resource_id="projects/p1/zones/z1/instances/batch-worker-01",
            metric_name="Percentage CPU",
            baseline_type="nightly_batch",
            expected_pattern={"peak_hours": "00:00-06:00", "daytime_avg": 4.0},
            suppress_underuse_alerts=True,
            confidence_score=0.98,
        )
        mock_repo.get_infrastructure_baselines.return_value = [mock_baseline]
        mock_repo.store_infrastructure_baseline.return_value = "new-base-uuid"

        # Test querying baseline
        queried = get_infrastructure_baselines._run(
            resource_ids=["projects/p1/zones/z1/instances/batch-worker-01"]
        )
        self.assertEqual(len(queried), 1)
        self.assertEqual(queried[0]["baseline_type"], "nightly_batch")
        self.assertTrue(queried[0]["suppress_underuse_alerts"])

        # Test storing baseline
        stored = store_infrastructure_baseline._run(
            resource_id="projects/p1/zones/z1/instances/batch-worker-01",
            metric_name="Percentage CPU",
            baseline_type="nightly_batch",
            expected_pattern={"peak_hours": "00:00-06:00"},
            suppress_underuse_alerts=True,
        )
        self.assertEqual(stored["status"], "stored")
        self.assertEqual(stored["baseline_id"], "new-base-uuid")
        self.assertTrue(stored["suppress_underuse_alerts"])

    @patch("finops_ai.tools.infra_tools._get_session")
    def test_update_underuse_threshold(self, mock_get_session: MagicMock) -> None:
        mock_session = MagicMock()
        mock_get_session.return_value.__enter__.return_value = mock_session

        mock_def = MagicMock()
        mock_def.underuse_threshold = 15.0

        mock_session.scalars.return_value.first.return_value = mock_def

        result = update_underuse_threshold._run(
            resource_type="compute/instance",
            metric_name="Percentage CPU",
            new_threshold=10.0,
            justification="Lowered threshold for high-density cluster",
        )

        self.assertEqual(result["status"], "updated")
        self.assertEqual(result["previous_threshold"], 15.0)
        self.assertEqual(result["new_threshold"], 10.0)
        self.assertEqual(mock_def.underuse_threshold, 10.0)
        mock_session.commit.assert_called_once()

