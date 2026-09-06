from __future__ import annotations

from datetime import date
from decimal import Decimal
import unittest
from unittest.mock import MagicMock, patch

from finops_ai.tools.cost_tools import (
    _parse_date_range,
    get_commitment_coverage,
    get_top_cost_drivers,
    query_cost_by_service,
    query_cost_trend,
)


class TestCostTools(unittest.TestCase):
    def test_parse_date_range(self) -> None:
        start_30, end_30 = _parse_date_range("last_30d")
        self.assertIsNotNone(start_30)
        self.assertIsNotNone(end_30)
        self.assertEqual((end_30 - start_30).days, 30)

        start_custom, end_custom = _parse_date_range("2026-08-01:2026-08-15")
        self.assertEqual(start_custom, date(2026, 8, 1))
        self.assertEqual(end_custom, date(2026, 8, 15))

    @patch("finops_ai.tools.cost_tools._get_session")
    def test_query_cost_by_service(self, mock_get_session: MagicMock) -> None:
        mock_session = MagicMock()
        mock_get_session.return_value.__enter__.return_value = mock_session

        mock_row1 = MagicMock()
        mock_row1.service_category = "Compute"
        mock_row1.provider_name = "Google"
        mock_row1.total_cost = Decimal("4500.00")
        mock_row1.record_count = 120

        mock_row2 = MagicMock()
        mock_row2.service_category = "Storage"
        mock_row2.provider_name = "Google"
        mock_row2.total_cost = Decimal("1200.00")
        mock_row2.record_count = 45

        mock_session.execute.return_value.all.return_value = [mock_row1, mock_row2]

        result = query_cost_by_service._run(
            service_category="Compute",
            date_range="last_30d",
            provider="Google",
            team_scope="data-platform",
        )

        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["total_spend"], 5700.0)
        self.assertEqual(len(result["services"]), 2)
        self.assertEqual(result["team_scope"], "data-platform")

    @patch("finops_ai.tools.cost_tools._get_session")
    def test_query_cost_trend(self, mock_get_session: MagicMock) -> None:
        mock_session = MagicMock()
        mock_get_session.return_value.__enter__.return_value = mock_session

        mock_point1 = MagicMock()
        mock_point1.usage_date = date(2026, 8, 1)
        mock_point1.daily_cost = Decimal("150.00")

        mock_point2 = MagicMock()
        mock_point2.usage_date = date(2026, 8, 2)
        mock_point2.daily_cost = Decimal("180.00")

        mock_session.execute.return_value.all.return_value = [mock_point1, mock_point2]

        result = query_cost_trend._run(
            dimension="service_category",
            dimension_value="Compute",
            date_range="last_30d",
            team_scope="data-platform",
        )

        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["total_period_cost"], 330.0)
        self.assertEqual(result["average_daily_cost"], 165.0)
        self.assertEqual(len(result["trend"]), 2)

    @patch("finops_ai.tools.cost_tools._get_session")
    def test_get_top_cost_drivers(self, mock_get_session: MagicMock) -> None:
        mock_session = MagicMock()
        mock_get_session.return_value.__enter__.return_value = mock_session

        mock_driver = MagicMock()
        mock_driver.resource_id = "projects/p1/zones/z1/instances/w1"
        mock_driver.resource_name = "w1"
        mock_driver.resource_type = "compute/instance"
        mock_driver.service_category = "Compute"
        mock_driver.provider_name = "Google"
        mock_driver.sub_account_name = "data-platform"
        mock_driver.total_cost = Decimal("284.50")

        mock_session.execute.return_value.all.return_value = [mock_driver]

        result = get_top_cost_drivers._run(
            date_range="last_30d",
            limit=5,
            team_scope="data-platform",
        )

        self.assertEqual(result["status"], "ok")
        self.assertEqual(len(result["drivers"]), 1)
        self.assertEqual(result["drivers"][0]["total_cost"], 284.5)

    @patch("finops_ai.tools.cost_tools._get_session")
    def test_get_commitment_coverage(self, mock_get_session: MagicMock) -> None:
        mock_session = MagicMock()
        mock_get_session.return_value.__enter__.return_value = mock_session

        mock_row1 = MagicMock()
        mock_row1.pricing_model = "OnDemand"
        mock_row1.total_cost = Decimal("600.00")

        mock_row2 = MagicMock()
        mock_row2.pricing_model = "CommitmentDiscount"
        mock_row2.total_cost = Decimal("400.00")

        mock_session.execute.return_value.all.return_value = [mock_row1, mock_row2]

        result = get_commitment_coverage._run(
            provider="Google",
            team_scope="data-platform",
        )

        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["total_spend"], 1000.0)
        self.assertEqual(result["committed_spend"], 400.0)
        self.assertEqual(result["coverage_percentage"], 40.0)

