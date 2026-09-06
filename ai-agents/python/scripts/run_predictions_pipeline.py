"""CLI runner for the predictions pipeline (spend forecasting + anomaly detection).

Usage:
    uv run --python .venv/bin/python python scripts/run_predictions_pipeline.py
"""

from __future__ import annotations

import argparse
import os
import sys

from finops_ai.llm import _load_env
from finops_ai.predictions import (
    CostAnomalyDetector,
    PredictionsPipeline,
    PredictionsRepository,
    SpendForecaster,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run spend forecasting and anomaly detection on consumption records"
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

    print(f"Connecting to database: {db_url.split('@')[-1]}...")
    repo = PredictionsRepository.from_url(db_url)
    pipeline = PredictionsPipeline(repository=repo)

    print("Running predictions pipeline...")
    result = pipeline.run()

    print("\n--- Predictions Pipeline Results ---")
    print(f"Dimensions Processed:     {result.dimensions_processed}")
    print(f"Forecasts Stored:         {result.forecasts_stored}")
    print(f"Anomalies Detected:       {result.anomalies_detected}")
    print(f"  - Critical:             {result.critical_anomalies_count}")
    print(f"  - High:                 {result.high_anomalies_count}")

    if result.top_anomalies:
        print("\nTop Detected Anomalies:")
        for a in result.top_anomalies:
            print(
                f"  [{a.severity.upper()}] {a.detected_date} | {a.dimension}:{a.dimension_value} | "
                f"Cost: ${a.actual_cost:,.2f} (Expected: ${a.expected_cost:,.2f}, Delta: +${a.cost_delta:,.2f} / +{a.percentage_delta:.1f}%)"
            )

    return 0


if __name__ == "__main__":
    sys.exit(main())
