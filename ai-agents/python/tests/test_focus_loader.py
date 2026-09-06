from __future__ import annotations

from datetime import date
from decimal import Decimal
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import MagicMock

from finops_ai.loaders.focus_loader import (
    ConsumptionRecord,
    FocusDataLoader,
    FocusLoadResult,
    ResourceGroupRecord,
    SubscriptionRecord,
)


class TestFocusDataLoader(unittest.TestCase):
    def setUp(self) -> None:
        self.mock_session = MagicMock()
        self.mock_session_factory = MagicMock()
        self.mock_session_factory.return_value.__enter__.return_value = self.mock_session
        self.loader = FocusDataLoader(self.mock_session_factory)

    def test_map_focus_row_gcp(self) -> None:
        raw_row = {
            "ProviderName": "Google",
            "BillingAccountId": "BA-001",
            "BillingAccountName": "Main Billing",
            "BillingCurrency": "USD",
            "BillingPeriodStart": "2026-08-01",
            "BillingPeriodEnd": "2026-08-31",
            "ChargePeriodStart": "2026-08-15 00:00:00",
            "ChargeCategory": "Usage",
            "EffectiveCost": "142.25",
            "InvoiceId": "INV-123",
            "PricingCategory": "OnDemand",
            "PublisherName": "Google",
            "ConsumedQuantity": "24",
            "ConsumedUnit": "Hours",
            "ResourceId": "projects/p1/zones/z1/instances/w1",
            "ResourceName": "w1",
            "ResourceType": "compute/instance",
            "ServiceCategory": "Compute",
            "ServiceName": "Compute Engine",
            "SkuId": "SKU-N2-01",
            "SubAccountId": "sub-data-platform",
            "SubAccountName": "data-platform",
            "RegionId": "us-central1",
            "Tags": json.dumps({"team": "data-platform", "env": "prod"}),
            "x_ResourceGroupName": "prod-analytics",
            "AvailabilityZone": "us-central1-a",
            "CommitmentDiscountCategory": "None",
        }

        mapped = self.loader.map_focus_row(raw_row, source_provenance="test-run")

        self.assertEqual(mapped["provider_name"], "Google")
        self.assertEqual(mapped["effective_cost"], Decimal("142.25"))
        self.assertEqual(mapped["usage_date"], date(2026, 8, 15))
        self.assertEqual(mapped["service_category"], "Compute")
        self.assertEqual(mapped["service_name"], "Compute Engine")
        self.assertEqual(mapped["resource_id"], "projects/p1/zones/z1/instances/w1")
        self.assertEqual(mapped["sub_account_name"], "data-platform")
        self.assertEqual(mapped["raw_rg_name"], "prod-analytics")

        # Check tags and provenance
        tags = mapped["tags"]
        self.assertEqual(tags.get("team"), "data-platform")
        self.assertEqual(tags.get("focus_AvailabilityZone"), "us-central1-a")
        self.assertEqual(tags.get("focus_CommitmentDiscountCategory"), "None")
        self.assertIn("_provenance", tags)
        self.assertEqual(tags["_provenance"]["source"], "test-run")
        self.assertEqual(tags["_provenance"]["license"], "CC-BY-4.0")

    def test_map_focus_row_provider_normalization(self) -> None:
        cases = [
            ("GCP Cloud", "Google"),
            ("Microsoft Azure", "Microsoft"),
            ("Amazon Web Services", "AWS"),
            ("Oracle Cloud", "Oracle"),
        ]
        for input_prov, expected_prov in cases:
            row = {"ProviderName": input_prov, "EffectiveCost": "10.0"}
            mapped = self.loader.map_focus_row(row)
            self.assertEqual(mapped["provider_name"], expected_prov)

    def test_load_stream_insert_and_aggregate(self) -> None:
        rows = [
            {
                "ProviderName": "Google",
                "SubAccountId": "sub-1",
                "SubAccountName": "data-platform",
                "ServiceCategory": "Compute",
                "EffectiveCost": "100.00",
                "ChargePeriodStart": "2026-08-15",
                "ResourceId": "res-gcp-1",
                "x_ResourceGroupName": "rg-1",
            },
            {
                "ProviderName": "Microsoft",
                "SubAccountId": "sub-2",
                "SubAccountName": "core-services",
                "ServiceCategory": "Storage",
                "EffectiveCost": "50.00",
                "ChargePeriodStart": "2026-08-15",
                "ResourceId": "res-az-1",
                "x_ResourceGroupName": "rg-2",
            },
        ]

        # Mock scalar returns None for existing records so all rows are inserted
        self.mock_session.scalars.return_value.first.return_value = None

        result = self.loader.load_stream(iter(rows), batch_size=10)

        self.assertEqual(result.total_rows_read, 2)
        self.assertEqual(result.inserted, 2)
        self.assertEqual(result.updated, 0)
        self.assertEqual(result.total_effective_cost, 150.0)
        self.assertEqual(result.cost_by_provider["Google"], 100.0)
        self.assertEqual(result.cost_by_provider["Microsoft"], 50.0)
        self.assertEqual(result.cost_by_service["Compute"], 100.0)
        self.assertEqual(result.cost_by_service["Storage"], 50.0)
        self.mock_session.commit.assert_called()

    def test_load_stream_idempotent_update(self) -> None:
        rows = [
            {
                "ProviderName": "Google",
                "SubAccountId": "sub-1",
                "SubAccountName": "data-platform",
                "ServiceCategory": "Compute",
                "EffectiveCost": "120.00",
                "ChargePeriodStart": "2026-08-15",
                "ResourceId": "res-gcp-1",
                "x_ResourceGroupName": "rg-1",
            }
        ]

        # Existing record found
        existing_rec = MagicMock(spec=ConsumptionRecord)
        self.mock_session.scalars.return_value.first.return_value = existing_rec

        result = self.loader.load_stream(iter(rows), batch_size=10)

        self.assertEqual(result.total_rows_read, 1)
        self.assertEqual(result.inserted, 0)
        self.assertEqual(result.updated, 1)
        self.assertEqual(result.total_effective_cost, 120.0)

    def test_load_file_from_disk(self) -> None:
        with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".csv") as tmp:
            tmp.write(
                "ProviderName,SubAccountId,SubAccountName,ServiceCategory,EffectiveCost,ChargePeriodStart,ResourceId,x_ResourceGroupName\n"
                "Google,sub-gcp,analytics,Compute,250.00,2026-08-15,res-1,rg-analytics\n"
            )
            tmp_path = tmp.name

        try:
            self.mock_session.scalars.return_value.first.return_value = None
            result = self.loader.load_file(tmp_path)
            self.assertEqual(result.total_rows_read, 1)
            self.assertEqual(result.total_effective_cost, 250.0)
        finally:
            Path(tmp_path).unlink(missing_ok=True)

