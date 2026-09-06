"""FOCUS 1.0 Sample Data Loader.

Reads, normalizes, and idempotently persists multi-provider FOCUS 1.0 cost records
into the PostgreSQL `consumption_records` table, maintaining foreign key relations
with `subscriptions` and `resource_groups`.
"""

from __future__ import annotations

import csv
from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from decimal import Decimal
import gzip
import io
import json
from pathlib import Path
from typing import Any, Iterator
from uuid import uuid4

from sqlalchemy import Date, DateTime, Numeric, String, Text, create_engine, select, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, sessionmaker


class Base(DeclarativeBase):
    pass


class SubscriptionRecord(Base):
    __tablename__ = "subscriptions"
    __table_args__ = {"schema": "finops"}

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True)
    subscription_id: Mapped[str] = mapped_column(String, unique=True)
    display_name: Mapped[str] = mapped_column(String)
    state: Mapped[str | None] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )


class ResourceGroupRecord(Base):
    __tablename__ = "resource_groups"
    __table_args__ = {"schema": "finops"}

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True)
    name: Mapped[str] = mapped_column(String)
    location: Mapped[str | None] = mapped_column(String, nullable=True)
    subscription_id: Mapped[str] = mapped_column(UUID(as_uuid=False))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )


class ConsumptionRecord(Base):
    __tablename__ = "consumption_records"
    __table_args__ = {"schema": "finops"}

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True)
    billing_account_id: Mapped[str | None] = mapped_column(String, nullable=True)
    billing_account_name: Mapped[str | None] = mapped_column(String, nullable=True)
    billing_currency: Mapped[str] = mapped_column(String, default="USD")
    billing_period_end: Mapped[date | None] = mapped_column(Date, nullable=True)
    billing_period_start: Mapped[date | None] = mapped_column(Date, nullable=True)
    charge_type: Mapped[str | None] = mapped_column(String, nullable=True)
    effective_cost: Mapped[Decimal | None] = mapped_column(Numeric(18, 6), nullable=True)
    invoice_id: Mapped[str | None] = mapped_column(String, nullable=True)
    meter_category: Mapped[str | None] = mapped_column(String, nullable=True)
    meter_id: Mapped[str | None] = mapped_column(String, nullable=True)
    meter_name: Mapped[str | None] = mapped_column(String, nullable=True)
    meter_region: Mapped[str | None] = mapped_column(String, nullable=True)
    meter_subcategory: Mapped[str | None] = mapped_column(String, nullable=True)
    pricing_model: Mapped[str | None] = mapped_column(String, nullable=True)
    product_name: Mapped[str | None] = mapped_column(String, nullable=True)
    provider_name: Mapped[str] = mapped_column(String, default="GCP")
    publisher_name: Mapped[str | None] = mapped_column(String, nullable=True)
    quantity: Mapped[Decimal | None] = mapped_column(Numeric(18, 6), nullable=True)
    resource_id: Mapped[str | None] = mapped_column(String, nullable=True)
    resource_location: Mapped[str | None] = mapped_column(String, nullable=True)
    resource_name: Mapped[str | None] = mapped_column(String, nullable=True)
    resource_type: Mapped[str | None] = mapped_column(String, nullable=True)
    service_category: Mapped[str | None] = mapped_column(String, nullable=True)
    service_name: Mapped[str | None] = mapped_column(String, nullable=True)
    sku_id: Mapped[str | None] = mapped_column(String, nullable=True)
    sku_price_id: Mapped[str | None] = mapped_column(String, nullable=True)
    sub_account_id: Mapped[str | None] = mapped_column(String, nullable=True)
    sub_account_name: Mapped[str | None] = mapped_column(String, nullable=True)
    tags: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    unit_of_measure: Mapped[str | None] = mapped_column(String, nullable=True)
    unit_price: Mapped[Decimal | None] = mapped_column(Numeric(18, 6), nullable=True)
    usage_date: Mapped[date] = mapped_column(Date)
    usage_quantity: Mapped[Decimal | None] = mapped_column(Numeric(18, 6), nullable=True)
    usage_unit: Mapped[str | None] = mapped_column(String, nullable=True)
    subscription_id: Mapped[str] = mapped_column(UUID(as_uuid=False))
    resource_group_id: Mapped[str] = mapped_column(UUID(as_uuid=False))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )


@dataclass
class FocusLoadResult:
    """Summary of a FOCUS sample data load operation."""

    total_rows_read: int = 0
    inserted: int = 0
    updated: int = 0
    skipped: int = 0
    errors: list[str] = field(default_factory=list)
    total_effective_cost: float = 0.0
    cost_by_provider: dict[str, float] = field(default_factory=dict)
    cost_by_service: dict[str, float] = field(default_factory=dict)
    subscriptions_ensured: int = 0
    resource_groups_ensured: int = 0


class FocusDataLoader:
    """Streams and maps FOCUS 1.0 datasets into PostgreSQL consumption records."""

    def __init__(self, session_factory: sessionmaker[Session]) -> None:
        self._session_factory = session_factory
        self._sub_cache: dict[str, str] = {}  # subscription_id string -> DB UUID
        self._rg_cache: dict[tuple[str, str], str] = {}  # (sub_uuid, rg_name) -> DB UUID

    @classmethod
    def from_url(cls, db_url: str) -> "FocusDataLoader":
        engine = create_engine(db_url, future=True)
        return cls(session_factory=sessionmaker(bind=engine, future=True))

    @staticmethod
    def _parse_date(val: str | None) -> date | None:
        if not val or not val.strip():
            return None
        cleaned = val.strip().split(" ")[0].split("T")[0]
        try:
            return datetime.strptime(cleaned, "%Y-%m-%d").date()
        except ValueError:
            return None

    @staticmethod
    def _parse_decimal(val: str | None) -> Decimal | None:
        if not val or not val.strip():
            return None
        try:
            return Decimal(str(float(val.strip().replace("$", "").replace(",", ""))))
        except (ValueError, ArithmeticError):
            return None

    def map_focus_row(self, row: dict[str, str], source_provenance: str = "FOCUS-1.0-sample") -> dict[str, Any]:
        """Transform a raw FOCUS 1.0 CSV row dictionary into consumption record fields."""
        provider = (
            row.get("ProviderName")
            or row.get("PublisherName")
            or "GCP"
        ).strip()

        # Normalize known provider strings
        provider_lower = provider.lower()
        if "google" in provider_lower or "gcp" in provider_lower:
            provider = "Google"
        elif "microsoft" in provider_lower or "azure" in provider_lower:
            provider = "Microsoft"
        elif "amazon" in provider_lower or "aws" in provider_lower:
            provider = "AWS"
        elif "oracle" in provider_lower or "oci" in provider_lower:
            provider = "Oracle"

        effective_cost = self._parse_decimal(
            row.get("EffectiveCost") or row.get("BilledCost") or row.get("ContractedCost")
        ) or Decimal("0.0")

        usage_date = (
            self._parse_date(row.get("ChargePeriodStart"))
            or self._parse_date(row.get("BillingPeriodStart"))
            or date.today()
        )

        sub_acc_id = (
            row.get("SubAccountId")
            or row.get("BillingAccountId")
            or f"sub-{provider.lower()}-default"
        ).strip()

        sub_acc_name = (
            row.get("SubAccountName")
            or row.get("BillingAccountName")
            or sub_acc_id
        ).strip()

        rg_name = (
            row.get("x_ResourceGroupName")
            or row.get("ResourceGroupName")
            or f"rg-{sub_acc_name.lower().replace(' ', '-')}"
        ).strip()

        # Parse tags
        raw_tags = row.get("Tags") or ""
        tags_dict: dict[str, Any] = {}
        if raw_tags.strip().startswith("{") and raw_tags.strip().endswith("}"):
            try:
                tags_dict = json.loads(raw_tags)
            except json.JSONDecodeError:
                tags_dict = {"raw_tags": raw_tags}
        elif raw_tags.strip():
            tags_dict = {"raw_tags": raw_tags}

        # Preserve unmapped FOCUS attributes in tags
        unmapped_keys = [
            "AvailabilityZone",
            "ChargeClass",
            "ChargeFrequency",
            "CommitmentDiscountCategory",
            "CommitmentDiscountId",
            "CommitmentDiscountName",
            "CommitmentDiscountType",
            "ContractedCost",
            "ContractedUnitPrice",
            "ListCost",
            "ListUnitPrice",
        ]
        for k in unmapped_keys:
            v = row.get(k)
            if v and v.strip():
                tags_dict[f"focus_{k}"] = v.strip()

        # Add data provenance metadata
        tags_dict["_provenance"] = {
            "source": source_provenance,
            "license": "CC-BY-4.0",
            "loaded_at": datetime.now(timezone.utc).isoformat(),
        }

        return {
            "billing_account_id": row.get("BillingAccountId") or None,
            "billing_account_name": row.get("BillingAccountName") or None,
            "billing_currency": row.get("BillingCurrency") or "USD",
            "billing_period_start": self._parse_date(row.get("BillingPeriodStart")),
            "billing_period_end": self._parse_date(row.get("BillingPeriodEnd")),
            "charge_type": row.get("ChargeCategory") or row.get("ChargeType") or "Usage",
            "effective_cost": effective_cost,
            "invoice_id": row.get("InvoiceId") or None,
            "meter_category": row.get("ServiceCategory") or None,
            "meter_id": row.get("SkuId") or None,
            "meter_name": row.get("ServiceName") or None,
            "meter_region": row.get("RegionId") or row.get("RegionName") or None,
            "meter_subcategory": row.get("ResourceType") or None,
            "pricing_model": row.get("PricingCategory") or row.get("PricingModel") or "OnDemand",
            "product_name": row.get("ChargeDescription") or row.get("ServiceName") or None,
            "provider_name": provider,
            "publisher_name": row.get("PublisherName") or provider,
            "quantity": self._parse_decimal(row.get("ConsumedQuantity") or row.get("PricingQuantity")),
            "resource_id": row.get("ResourceId") or None,
            "resource_location": row.get("RegionName") or row.get("RegionId") or None,
            "resource_name": row.get("ResourceName") or None,
            "resource_type": row.get("ResourceType") or None,
            "service_category": row.get("ServiceCategory") or "Other",
            "service_name": row.get("ServiceName") or None,
            "sku_id": row.get("SkuId") or None,
            "sku_price_id": row.get("SkuPriceId") or None,
            "sub_account_id": sub_acc_id,
            "sub_account_name": sub_acc_name,
            "tags": tags_dict,
            "unit_of_measure": row.get("ConsumedUnit") or row.get("PricingUnit") or None,
            "unit_price": self._parse_decimal(row.get("ContractedUnitPrice") or row.get("ListUnitPrice")),
            "usage_date": usage_date,
            "usage_quantity": self._parse_decimal(row.get("ConsumedQuantity")),
            "usage_unit": row.get("ConsumedUnit") or None,
            "raw_sub_id": sub_acc_id,
            "raw_sub_name": sub_acc_name,
            "raw_rg_name": rg_name,
        }

    def _ensure_subscription(self, session: Session, sub_id_str: str, display_name: str) -> str:
        """Get or create subscription entity, caching by external subscription_id."""
        if sub_id_str in self._sub_cache:
            return self._sub_cache[sub_id_str]

        stmt = select(SubscriptionRecord).where(SubscriptionRecord.subscription_id == sub_id_str)
        existing = session.scalars(stmt).first()
        if existing:
            self._sub_cache[sub_id_str] = str(existing.id)
            return str(existing.id)

        new_id = str(uuid4())
        record = SubscriptionRecord(
            id=new_id,
            subscription_id=sub_id_str,
            display_name=display_name,
            state="active",
        )
        session.add(record)
        session.flush()
        self._sub_cache[sub_id_str] = new_id
        return new_id

    def _ensure_resource_group(
        self, session: Session, subscription_uuid: str, rg_name: str, location: str | None
    ) -> str:
        """Get or create resource group entity, caching by (sub_uuid, rg_name)."""
        cache_key = (subscription_uuid, rg_name)
        if cache_key in self._rg_cache:
            return self._rg_cache[cache_key]

        stmt = select(ResourceGroupRecord).where(
            ResourceGroupRecord.subscription_id == subscription_uuid,
            ResourceGroupRecord.name == rg_name,
        )
        existing = session.scalars(stmt).first()
        if existing:
            self._rg_cache[cache_key] = str(existing.id)
            return str(existing.id)

        new_id = str(uuid4())
        record = ResourceGroupRecord(
            id=new_id,
            name=rg_name,
            location=location or "global",
            subscription_id=subscription_uuid,
        )
        session.add(record)
        session.flush()
        self._rg_cache[cache_key] = new_id
        return new_id

    def load_stream(
        self,
        row_iterator: Iterator[dict[str, str]],
        batch_size: int = 500,
        source_provenance: str = "FOCUS-1.0-sample",
    ) -> FocusLoadResult:
        """Stream and persist rows from a CSV DictReader iterator in batches.
        Automatically shifts and expands the sample data backwards month-by-month to 2025-01.
        """
        result = FocusLoadResult()
        batch: list[dict[str, Any]] = []
        target_start = date(2025, 1, 1)

        with self._session_factory() as session:
            for row in row_iterator:
                result.total_rows_read += 1
                try:
                    base_mapped = self.map_focus_row(row, source_provenance=source_provenance)
                    orig_usage_date = base_mapped["usage_date"]
                    
                    # Calculate how many months to shift backwards from the CSV date to 2025-01
                    months_diff = (orig_usage_date.year - target_start.year) * 12 + (orig_usage_date.month - target_start.month)
                    months_diff = max(0, months_diff)
                    
                    # Duplicate the row for every month between the original date and 2025-01
                    for month_offset in range(months_diff + 1):
                        mapped = dict(base_mapped)
                        
                        # Shift dates backwards by month_offset
                        if month_offset > 0:
                            new_month = orig_usage_date.month - month_offset
                            new_year = orig_usage_date.year
                            while new_month < 1:
                                new_month += 12
                                new_year -= 1
                            
                            # Safely handle end-of-month days
                            try:
                                mapped["usage_date"] = orig_usage_date.replace(year=new_year, month=new_month)
                            except ValueError:
                                # if day is 31 but month is 30 days, clamp to 28 for simplicity
                                mapped["usage_date"] = orig_usage_date.replace(year=new_year, month=new_month, day=28)
                                
                            if mapped["billing_period_start"]:
                                try:
                                    mapped["billing_period_start"] = mapped["billing_period_start"].replace(year=new_year, month=new_month)
                                except ValueError:
                                    mapped["billing_period_start"] = mapped["billing_period_start"].replace(year=new_year, month=new_month, day=28)
                            if mapped["billing_period_end"]:
                                try:
                                    mapped["billing_period_end"] = mapped["billing_period_end"].replace(year=new_year, month=new_month)
                                except ValueError:
                                    mapped["billing_period_end"] = mapped["billing_period_end"].replace(year=new_year, month=new_month, day=28)

                        batch.append(mapped)

                        cost = float(mapped["effective_cost"] or Decimal("0.0"))
                        result.total_effective_cost += cost
                        prov = mapped["provider_name"]
                        result.cost_by_provider[prov] = result.cost_by_provider.get(prov, 0.0) + cost
                        svc = mapped["service_category"]
                        result.cost_by_service[svc] = result.cost_by_service.get(svc, 0.0) + cost

                        if len(batch) >= batch_size:
                            self._persist_batch(session, batch, result)
                            batch.clear()
                except Exception as ex:
                    result.errors.append(f"Row {result.total_rows_read} failed: {ex}")

            if batch:
                self._persist_batch(session, batch, result)

        result.subscriptions_ensured = len(self._sub_cache)
        result.resource_groups_ensured = len(self._rg_cache)
        return result

    def _persist_batch(
        self, session: Session, batch: list[dict[str, Any]], result: FocusLoadResult
    ) -> None:
        """Persist a single batch of mapped rows."""
        for item in batch:
            sub_uuid = self._ensure_subscription(session, item["raw_sub_id"], item["raw_sub_name"])
            rg_uuid = self._ensure_resource_group(
                session, sub_uuid, item["raw_rg_name"], item["meter_region"]
            )

            # Idempotent match: check if a record exists for same sub, rg, date, resource, charge_type
            res_id = item["resource_id"]
            usage_dt = item["usage_date"]
            charge_tp = item["charge_type"]

            existing_stmt = select(ConsumptionRecord).where(
                ConsumptionRecord.subscription_id == sub_uuid,
                ConsumptionRecord.resource_group_id == rg_uuid,
                ConsumptionRecord.usage_date == usage_dt,
                ConsumptionRecord.resource_id == res_id,
                ConsumptionRecord.charge_type == charge_tp,
            )
            existing = session.scalars(existing_stmt).first()

            if existing:
                existing.effective_cost = item["effective_cost"]
                existing.billing_currency = item["billing_currency"]
                existing.service_category = item["service_category"]
                existing.service_name = item["service_name"]
                existing.resource_type = item["resource_type"]
                existing.provider_name = item["provider_name"]
                existing.pricing_model = item["pricing_model"]
                existing.tags = item["tags"]
                existing.updated_at = datetime.now(timezone.utc)
                result.updated += 1
            else:
                record = ConsumptionRecord(
                    id=str(uuid4()),
                    billing_account_id=item["billing_account_id"],
                    billing_account_name=item["billing_account_name"],
                    billing_currency=item["billing_currency"],
                    billing_period_start=item["billing_period_start"],
                    billing_period_end=item["billing_period_end"],
                    charge_type=item["charge_type"],
                    effective_cost=item["effective_cost"],
                    invoice_id=item["invoice_id"],
                    meter_category=item["meter_category"],
                    meter_id=item["meter_id"],
                    meter_name=item["meter_name"],
                    meter_region=item["meter_region"],
                    meter_subcategory=item["meter_subcategory"],
                    pricing_model=item["pricing_model"],
                    product_name=item["product_name"],
                    provider_name=item["provider_name"],
                    publisher_name=item["publisher_name"],
                    quantity=item["quantity"],
                    resource_id=item["resource_id"],
                    resource_location=item["resource_location"],
                    resource_name=item["resource_name"],
                    resource_type=item["resource_type"],
                    service_category=item["service_category"],
                    service_name=item["service_name"],
                    sku_id=item["sku_id"],
                    sku_price_id=item["sku_price_id"],
                    sub_account_id=item["sub_account_id"],
                    sub_account_name=item["sub_account_name"],
                    tags=item["tags"],
                    unit_of_measure=item["unit_of_measure"],
                    unit_price=item["unit_price"],
                    usage_date=item["usage_date"],
                    usage_quantity=item["usage_quantity"],
                    usage_unit=item["usage_unit"],
                    subscription_id=sub_uuid,
                    resource_group_id=rg_uuid,
                )
                session.add(record)
                result.inserted += 1

        session.commit()

    def load_file(
        self, file_path: str | Path, batch_size: int = 500
    ) -> FocusLoadResult:
        """Load FOCUS data from a local .csv or .csv.gz file."""
        path = Path(file_path)
        if not path.is_file():
            raise FileNotFoundError(f"FOCUS sample file not found: {file_path}")

        source_provenance = f"file://{path.name}"
        if path.suffix == ".gz" or str(path).endswith(".csv.gz"):
            with gzip.open(path, mode="rt", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                return self.load_stream(reader, batch_size=batch_size, source_provenance=source_provenance)
        else:
            with open(path, mode="r", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                return self.load_stream(reader, batch_size=batch_size, source_provenance=source_provenance)

