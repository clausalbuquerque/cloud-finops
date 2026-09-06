"""Generates a 1,000-row FOCUS 1.0 sample CSV fixture covering multi-provider resources over 30 days."""

import csv
from datetime import date, timedelta
from pathlib import Path
import random

RESOURCES = [
    # GCP Resources (data-platform, prod-analytics)
    {
        "provider": "Google",
        "billing_account": "BA-GCP-001",
        "sub_account_id": "sub-gcp-data-platform",
        "sub_account_name": "data-platform",
        "rg_name": "prod-analytics",
        "resource_id": "projects/prod-analytics/zones/us-central1-a/instances/analytics-worker-01",
        "resource_name": "analytics-worker-01",
        "resource_type": "compute/instance",
        "service_category": "Compute",
        "service_name": "Compute Engine",
        "sku_id": "SKU-GCP-N2-01",
        "region": "us-central1",
        "pricing_category": "OnDemand",
        "unit_price": 5.927,
        "quantity": 24,
        "unit": "Hours",
        "daily_base_cost": 142.25,
        "spike_multiplier": 1.0,
    },
    {
        "provider": "Google",
        "billing_account": "BA-GCP-001",
        "sub_account_id": "sub-gcp-data-platform",
        "sub_account_name": "data-platform",
        "rg_name": "prod-analytics",
        "resource_id": "projects/prod-analytics/zones/us-central1-a/instances/analytics-worker-02",
        "resource_name": "analytics-worker-02",
        "resource_type": "compute/instance",
        "service_category": "Compute",
        "service_name": "Compute Engine",
        "sku_id": "SKU-GCP-E16-01",
        "region": "us-central1",
        "pricing_category": "OnDemand",
        "unit_price": 11.854,
        "quantity": 24,
        "unit": "Hours",
        "daily_base_cost": 142.25,
        "spike_after_day": 20,  # Accidental upsize 10 days ago (spike to 284.50)
        "spike_multiplier": 2.0,
    },
    {
        "provider": "Google",
        "billing_account": "BA-GCP-001",
        "sub_account_id": "sub-gcp-data-platform",
        "sub_account_name": "data-platform",
        "rg_name": "prod-analytics",
        "resource_id": "projects/prod-analytics/zones/us-central1-b/instances/batch-worker-01",
        "resource_name": "batch-worker-01",
        "resource_type": "compute/instance",
        "service_category": "Compute",
        "service_name": "Compute Engine",
        "sku_id": "SKU-GCP-D2-01",
        "region": "us-central1",
        "pricing_category": "OnDemand",
        "unit_price": 1.479,
        "quantity": 24,
        "unit": "Hours",
        "daily_base_cost": 35.50,
        "spike_multiplier": 1.0,
    },
    {
        "provider": "Google",
        "billing_account": "BA-GCP-001",
        "sub_account_id": "sub-gcp-data-platform",
        "sub_account_name": "data-platform",
        "rg_name": "prod-analytics",
        "resource_id": "projects/prod-analytics/buckets/analytics-lakehouse",
        "resource_name": "analytics-lakehouse",
        "resource_type": "storage/bucket",
        "service_category": "Storage",
        "service_name": "Cloud Storage",
        "sku_id": "SKU-GCP-GCS-01",
        "region": "us-central1",
        "pricing_category": "OnDemand",
        "unit_price": 0.02,
        "quantity": 2300,
        "unit": "GB-Mo",
        "daily_base_cost": 46.00,
        "spike_multiplier": 1.0,
    },
    {
        "provider": "Google",
        "billing_account": "BA-GCP-001",
        "sub_account_id": "sub-gcp-data-platform",
        "sub_account_name": "data-platform",
        "rg_name": "prod-analytics",
        "resource_id": "projects/prod-analytics/instances/analytics-db-01",
        "resource_name": "analytics-db-01",
        "resource_type": "sql/database",
        "service_category": "Database",
        "service_name": "Cloud SQL",
        "sku_id": "SKU-GCP-SQL-01",
        "region": "us-central1",
        "pricing_category": "OnDemand",
        "unit_price": 3.958,
        "quantity": 24,
        "unit": "Hours",
        "daily_base_cost": 95.00,
        "spike_multiplier": 1.0,
    },

    # Azure Resources (core-services, rg-core-services)
    {
        "provider": "Microsoft",
        "billing_account": "BA-AZ-002",
        "sub_account_id": "sub-az-core-services",
        "sub_account_name": "core-services",
        "rg_name": "rg-core-services",
        "resource_id": "/subscriptions/sub-az-core-services/resourceGroups/rg-core-services/providers/Microsoft.Compute/virtualMachines/core-app-vm1",
        "resource_name": "core-app-vm1",
        "resource_type": "Microsoft.Compute/virtualMachines",
        "service_category": "Compute",
        "service_name": "Virtual Machines",
        "sku_id": "SKU-AZ-D4S",
        "region": "eastus",
        "pricing_category": "OnDemand",
        "unit_price": 7.50,
        "quantity": 24,
        "unit": "Hours",
        "daily_base_cost": 180.00,
        "spike_multiplier": 1.0,
    },
    {
        "provider": "Microsoft",
        "billing_account": "BA-AZ-002",
        "sub_account_id": "sub-az-core-services",
        "sub_account_name": "core-services",
        "rg_name": "rg-core-services",
        "resource_id": "/subscriptions/sub-az-core-services/resourceGroups/rg-core-services/providers/Microsoft.Compute/virtualMachines/core-app-vm2",
        "resource_name": "core-app-vm2",
        "resource_type": "Microsoft.Compute/virtualMachines",
        "service_category": "Compute",
        "service_name": "Virtual Machines",
        "sku_id": "SKU-AZ-E8S",
        "region": "eastus",
        "pricing_category": "OnDemand",
        "unit_price": 15.00,
        "quantity": 24,
        "unit": "Hours",
        "daily_base_cost": 360.00,
        "spike_multiplier": 1.0,
    },
    {
        "provider": "Microsoft",
        "billing_account": "BA-AZ-002",
        "sub_account_id": "sub-az-core-services",
        "sub_account_name": "core-services",
        "rg_name": "rg-core-services",
        "resource_id": "/subscriptions/sub-az-core-services/resourceGroups/rg-core-services/providers/Microsoft.Sql/servers/sql-core/databases/db-core",
        "resource_name": "db-core",
        "resource_type": "Microsoft.Sql/servers/databases",
        "service_category": "Database",
        "service_name": "SQL Database",
        "sku_id": "SKU-AZ-SQL-GP",
        "region": "eastus",
        "pricing_category": "OnDemand",
        "unit_price": 2.292,
        "quantity": 24,
        "unit": "Hours",
        "daily_base_cost": 55.00,
        "spike_multiplier": 1.0,
    },

    # AWS Resources (marketing-ai, rg-marketing-prod)
    {
        "provider": "AWS",
        "billing_account": "BA-AWS-003",
        "sub_account_id": "sub-aws-marketing",
        "sub_account_name": "marketing-ai",
        "rg_name": "rg-marketing-prod",
        "resource_id": "arn:aws:ec2:us-east-1:123456789012:instance/i-0a1b2c3d4e5f6g7h8",
        "resource_name": "marketing-worker-01",
        "resource_type": "AWS::EC2::Instance",
        "service_category": "Compute",
        "service_name": "Amazon Elastic Compute Cloud",
        "sku_id": "SKU-AWS-M5-2XL",
        "region": "us-east-1",
        "pricing_category": "OnDemand",
        "unit_price": 8.75,
        "quantity": 24,
        "unit": "Hours",
        "daily_base_cost": 210.00,
        "spike_multiplier": 1.0,
    },
    {
        "provider": "AWS",
        "billing_account": "BA-AWS-003",
        "sub_account_id": "sub-aws-marketing",
        "sub_account_name": "marketing-ai",
        "rg_name": "rg-marketing-prod",
        "resource_id": "arn:aws:s3:::marketing-assets-prod",
        "resource_name": "marketing-assets-prod",
        "resource_type": "AWS::S3::Bucket",
        "service_category": "Storage",
        "service_name": "Amazon Simple Storage Service",
        "sku_id": "SKU-AWS-S3-STD",
        "region": "us-east-1",
        "pricing_category": "OnDemand",
        "unit_price": 0.023,
        "quantity": 2826,
        "unit": "GB-Mo",
        "daily_base_cost": 65.00,
        "spike_multiplier": 1.0,
    },
    {
        "provider": "AWS",
        "billing_account": "BA-AWS-003",
        "sub_account_id": "sub-aws-marketing",
        "sub_account_name": "marketing-ai",
        "rg_name": "rg-marketing-prod",
        "resource_id": "arn:aws:rds:us-east-1:123456789012:db:marketing-db",
        "resource_name": "marketing-db",
        "resource_type": "AWS::RDS::DBInstance",
        "service_category": "Database",
        "service_name": "Amazon Relational Database Service",
        "sku_id": "SKU-AWS-RDS-M5L",
        "region": "us-east-1",
        "pricing_category": "OnDemand",
        "unit_price": 5.00,
        "quantity": 24,
        "unit": "Hours",
        "daily_base_cost": 120.00,
        "spike_multiplier": 1.0,
    },

    # Oracle Resources (data-platform, rg-oci-dw)
    {
        "provider": "Oracle",
        "billing_account": "BA-OCI-004",
        "sub_account_id": "sub-oci-dw",
        "sub_account_name": "data-platform",
        "rg_name": "rg-oci-dw",
        "resource_id": "ocid1.instance.oc1.iad.anuwcljrn7x01",
        "resource_name": "oci-worker-01",
        "resource_type": "oci:compute:instance",
        "service_category": "Compute",
        "service_name": "OCI Compute",
        "sku_id": "SKU-OCI-E4-FLEX",
        "region": "us-ashburn-1",
        "pricing_category": "OnDemand",
        "unit_price": 3.542,
        "quantity": 24,
        "unit": "Hours",
        "daily_base_cost": 85.00,
        "spike_multiplier": 1.0,
    },
]

HEADERS = [
    "AvailabilityZone",
    "BilledCost",
    "BillingAccountId",
    "BillingAccountName",
    "BillingCurrency",
    "BillingPeriodEnd",
    "BillingPeriodStart",
    "ChargeCategory",
    "ChargeClass",
    "ChargeDescription",
    "ChargeFrequency",
    "ChargePeriodEnd",
    "ChargePeriodStart",
    "CommitmentDiscountCategory",
    "CommitmentDiscountId",
    "CommitmentDiscountName",
    "CommitmentDiscountType",
    "ConsumedQuantity",
    "ConsumedUnit",
    "ContractedCost",
    "ContractedUnitPrice",
    "EffectiveCost",
    "InvoiceId",
    "InvoiceIssuerName",
    "ListCost",
    "ListUnitPrice",
    "PricingCategory",
    "PricingQuantity",
    "PricingUnit",
    "ProviderName",
    "PublisherName",
    "RegionId",
    "RegionName",
    "ResourceId",
    "ResourceName",
    "ResourceType",
    "ServiceCategory",
    "ServiceName",
    "SkuId",
    "SkuPriceId",
    "SubAccountId",
    "SubAccountName",
    "Tags",
    "x_ResourceGroupName",
]


def generate_rows(target_count: int = 1000) -> list[dict[str, str]]:
    random.seed(42)
    start_date = date(2026, 7, 23)
    rows: list[dict[str, str]] = []

    day_offset = 0
    while len(rows) < target_count:
        curr_date = start_date + timedelta(days=(day_offset % 30))
        for res in RESOURCES:
            if len(rows) >= target_count:
                break

            day_in_window = day_offset % 30
            multiplier = res["spike_multiplier"]
            if "spike_after_day" in res and day_in_window >= res["spike_after_day"]:
                multiplier = 2.0

            # Small realistic variance (+/- 3%)
            variance = random.uniform(0.97, 1.03)
            effective_cost = round(res["daily_base_cost"] * multiplier * variance, 2)
            billed_cost = effective_cost

            charge_start = f"{curr_date.isoformat()} 00:00:00"
            charge_end = f"{curr_date.isoformat()} 23:59:59"

            tags_json = (
                f'{{"team": "{res["sub_account_name"]}", '
                f'"provider": "{res["provider"]}", '
                f'"env": "prod"}}'
            )

            row = {
                "AvailabilityZone": f"{res['region']}-a",
                "BilledCost": f"{billed_cost:.2f}",
                "BillingAccountId": res["billing_account"],
                "BillingAccountName": f"Enterprise {res['provider']}",
                "BillingCurrency": "USD",
                "BillingPeriodEnd": "2026-08-31",
                "BillingPeriodStart": "2026-08-01",
                "ChargeCategory": "Usage",
                "ChargeClass": "",
                "ChargeDescription": f"{res['service_name']} usage",
                "ChargeFrequency": "Usage",
                "ChargePeriodEnd": charge_end,
                "ChargePeriodStart": charge_start,
                "CommitmentDiscountCategory": "",
                "CommitmentDiscountId": "",
                "CommitmentDiscountName": "",
                "CommitmentDiscountType": "",
                "ConsumedQuantity": str(res["quantity"]),
                "ConsumedUnit": res["unit"],
                "ContractedCost": f"{effective_cost:.2f}",
                "ContractedUnitPrice": f"{res['unit_price']:.6f}",
                "EffectiveCost": f"{effective_cost:.2f}",
                "InvoiceId": f"INV-{res['provider'].upper()[:3]}-202608",
                "InvoiceIssuerName": res["provider"],
                "ListCost": f"{effective_cost:.2f}",
                "ListUnitPrice": f"{res['unit_price']:.6f}",
                "PricingCategory": res["pricing_category"],
                "PricingQuantity": str(res["quantity"]),
                "PricingUnit": res["unit"],
                "ProviderName": res["provider"],
                "PublisherName": res["provider"],
                "RegionId": res["region"],
                "RegionName": res["region"],
                "ResourceId": res["resource_id"],
                "ResourceName": res["resource_name"],
                "ResourceType": res["resource_type"],
                "ServiceCategory": res["service_category"],
                "ServiceName": res["service_name"],
                "SkuId": res["sku_id"],
                "SkuPriceId": f"SKUP-{res['sku_id']}",
                "SubAccountId": res["sub_account_id"],
                "SubAccountName": res["sub_account_name"],
                "Tags": tags_json,
                "x_ResourceGroupName": res["rg_name"],
            }
            rows.append(row)
        day_offset += 1

    return rows


def write_sample_csv(output_path: Path, count: int = 1000) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    rows = generate_rows(count)
    with open(output_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=HEADERS)
        writer.writeheader()
        writer.writerows(rows)
    print(f"Generated {len(rows)} FOCUS 1.0 sample rows at {output_path}")


if __name__ == "__main__":
    out = Path(__file__).resolve().parents[1] / "data" / "focus_sample_1k.csv"
    write_sample_csv(out, 1000)

