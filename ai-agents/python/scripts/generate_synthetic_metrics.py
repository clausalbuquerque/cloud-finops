"""CLI tool to generate synthetic utilization metrics and daily summaries.

Usage:
    uv run --python .venv/bin/python python scripts/generate_synthetic_metrics.py [--days 30] [--seed 42]
"""

from __future__ import annotations

import argparse
import os
import sys

from finops_ai.llm import _load_env
from finops_ai.loaders.metrics_generator import SyntheticMetricsGenerator


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate synthetic utilization metrics and summaries for tracked resources"
    )
    from datetime import date
    default_days = (date.today() - date(2025, 1, 1)).days

    parser.add_argument(
        "--days",
        type=int,
        default=default_days,
        help=f"Number of days of history to generate (default: {default_days} days since 2025-01-01)",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=42,
        help="Random seed for reproducible series generation (default: 42)",
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

    db_url = (
        args.db_url
        or os.getenv("DATABASE_URL")
        or "postgresql+psycopg://postgres:postgres123@localhost:5432/cloud_finops"
    )

    print(f"Generating {args.days} days of synthetic metrics into {db_url.split('@')[-1]} (seed={args.seed})...")
    generator = SyntheticMetricsGenerator.from_url(db_url, seed=args.seed)

    result = generator.generate(days=args.days)

    print("\n--- Metrics Generation Results ---")
    print(f"Tracked Resources:       {result.tracked_resources_count}")
    print(f"Metric Definitions:      {result.metric_definitions_count}")
    print(f"Hourly Data Points:      {result.data_points_generated:,}")
    print(f"Daily Summaries:         {result.summaries_generated:,}")
    print(f"Underused Summaries:     {result.underused_summaries_count:,}")
    print(f"Date Range:              {result.start_date} to {result.end_date}")

    return 0


if __name__ == "__main__":
    sys.exit(main())

