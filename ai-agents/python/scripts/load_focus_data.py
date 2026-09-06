"""CLI tool to load FOCUS 1.0 sample data into PostgreSQL consumption_records.

Usage:
    uv run --python .venv/bin/python python scripts/load_focus_data.py [--file <path>] [--batch-size 500]
"""

from __future__ import annotations

import argparse
import os
from pathlib import Path
import sys

from finops_ai.llm import _load_env
from finops_ai.loaders.focus_loader import FocusDataLoader


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Load FOCUS 1.0 dataset into PostgreSQL consumption_records table"
    )
    default_csv = Path(__file__).resolve().parents[1] / "data" / "focus_sample_1k.csv"
    parser.add_argument(
        "--file",
        type=str,
        default=str(default_csv),
        help="Path to FOCUS 1.0 CSV or CSV.GZ file (default: data/focus_sample_1k.csv)",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=500,
        help="Batch size for database operations (default: 500)",
    )
    parser.add_argument(
        "--db-url",
        type=str,
        default=None,
        help="PostgreSQL connection string (defaults to DATABASE_URL in environment)",
    )
    return parser.parse_args()


def main() -> int:
    _load_env()
    args = parse_args()

    file_path = Path(args.file)
    if not file_path.is_file():
        print(f"Error: File not found at {file_path}", file=sys.stderr)
        return 1

    db_url = (
        args.db_url
        or os.getenv("DATABASE_URL")
        or "postgresql+psycopg://postgres:postgres123@localhost:5432/cloud_finops"
    )

    print(f"Loading FOCUS data from {file_path} into {db_url.split('@')[-1]}...")
    loader = FocusDataLoader.from_url(db_url)

    result = loader.load_file(file_path, batch_size=args.batch_size, backfill_history=True)

    print("\n--- FOCUS Load Results ---")
    print(f"Total Rows Read:        {result.total_rows_read}")
    print(f"Inserted Records:       {result.inserted}")
    print(f"Updated Records:        {result.updated}")
    print(f"Errors:                 {len(result.errors)}")
    print(f"Subscriptions Ensured:  {result.subscriptions_ensured}")
    print(f"Resource Groups Ensured:{result.resource_groups_ensured}")
    print(f"Total Effective Cost:   ${result.total_effective_cost:,.2f}")
    print("\nCost by Provider:")
    for prov, cost in sorted(result.cost_by_provider.items()):
        print(f"  - {prov:<12}: ${cost:>12,.2f}")
    print("\nCost by Service Category:")
    for svc, cost in sorted(result.cost_by_service.items()):
        print(f"  - {svc:<12}: ${cost:>12,.2f}")

    if result.errors:
        print("\nSample Errors:")
        for err in result.errors[:5]:
            print(f"  ! {err}")

    return 0 if not result.errors else 1


if __name__ == "__main__":
    sys.exit(main())

