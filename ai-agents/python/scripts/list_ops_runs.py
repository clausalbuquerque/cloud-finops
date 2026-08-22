from __future__ import annotations

import argparse
import os

from finops_ai.operations import RunsStatusRepository


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="List recent ingestion/index operation runs")
    parser.add_argument("--limit", type=int, default=20)
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    db_url = os.getenv("DATABASE_URL")
    if not db_url:
        raise RuntimeError("DATABASE_URL is required")

    repo = RunsStatusRepository.from_url(db_url)
    runs = repo.list_recent_runs(limit=args.limit)

    print("Recent operation runs")
    for run in runs:
        print(
            f"run_id={run.id} type={run.run_type} source={run.source_id} status={run.status} "
            f"docs={run.documents_processed} chunks_created={run.chunks_created} "
            f"chunks_updated={run.chunks_updated} chunks_deprecated={run.chunks_deprecated} "
            f"started_at={run.started_at} completed_at={run.completed_at}"
        )


if __name__ == "__main__":
    main()
