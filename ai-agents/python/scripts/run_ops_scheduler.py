from __future__ import annotations

import argparse
import os

from finops_ai.embedding import EmbeddingService, EmbeddingServiceConfig
from finops_ai.indexing import ChunkIndexerService, IndexChunksInput, IndexingRepository
from finops_ai.ingestion import IngestProviderDocsInput, ProviderDocsIngestionService, SourceRegistry
from finops_ai.ingestion.repository import IngestionRepository
from finops_ai.operations import OperationsScheduler, OperationsSchedulerConfig, RunsStatusRepository


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run scheduled ingestion + indexing operations")
    parser.add_argument("--once", action="store_true", help="Run jobs once and exit")
    parser.add_argument("--provider", default="GCP")
    parser.add_argument("--sources", default=None, help="Comma-separated source ids")
    parser.add_argument("--dead-letter-path", default="docs/dead-letter-jobs.jsonl")
    parser.add_argument("--max-retries", type=int, default=3)
    parser.add_argument("--retry-backoff-seconds", type=float, default=1.0)
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    db_url = os.getenv("DATABASE_URL")
    if not db_url:
        raise RuntimeError("DATABASE_URL is required")

    registry = SourceRegistry()
    source_ids = (
        [item.strip() for item in args.sources.split(",") if item.strip()]
        if args.sources
        else [source.source_id for source in registry.list_sources() if source.provider.upper() == args.provider.upper()]
    )

    ingestion_service = ProviderDocsIngestionService(
        registry=registry,
        repository=IngestionRepository.from_url(db_url),
    )
    indexing_service = ChunkIndexerService(
        repository=IndexingRepository.from_url(db_url),
        embedding_service=EmbeddingService(config=EmbeddingServiceConfig.from_env()),
    )

    scheduler = OperationsScheduler(
        OperationsSchedulerConfig(
            max_retries=args.max_retries,
            retry_backoff_seconds=args.retry_backoff_seconds,
            dead_letter_path=args.dead_letter_path,
        )
    )

    def make_ingest_job(source_id: str):
        def _action() -> dict[str, object]:
            result = ingestion_service.ingest_provider_docs(IngestProviderDocsInput(source_id=source_id))
            return {
                "run_id": result.run_id,
                "source_id": source_id,
                "documents_fetched": result.documents_fetched,
                "documents_changed": result.documents_changed,
                "errors": len(result.errors),
            }

        return _action

    def index_action() -> dict[str, object]:
        result = indexing_service.index_chunks(IndexChunksInput(mode="incremental", provider=args.provider))
        return {
            "run_id": result.run_id,
            "chunks_embedded": result.chunks_embedded,
            "chunks_skipped": result.chunks_skipped,
            "chunks_deprecated": result.chunks_deprecated,
            "errors": len(result.errors),
        }

    once_jobs = [(f"ingest:{source_id}", make_ingest_job(source_id)) for source_id in source_ids]
    once_jobs.append((f"index:{args.provider}", index_action))

    if args.once:
        results = scheduler.run_once(once_jobs)
        for item in results:
            print(
                f"job={item.job_name} success={item.success} attempts={item.attempts} payload={item.payload}"
            )

        status_repo = RunsStatusRepository.from_url(db_url)
        print("Recent operation runs")
        for run in status_repo.list_recent_runs(limit=10):
            print(
                f"run_id={run.id} type={run.run_type} source={run.source_id} status={run.status} "
                f"docs={run.documents_processed} chunks_created={run.chunks_created} started_at={run.started_at}"
            )
        return

    periodic_jobs: list[tuple[str, int, object]] = [
        (f"ingest:{source_id}", scheduler.config.weekly_ingestion_interval_seconds, make_ingest_job(source_id))
        for source_id in source_ids
    ]
    periodic_jobs.append(
        (f"index:{args.provider}", scheduler.config.incremental_indexing_interval_seconds, index_action)
    )

    scheduler.run_forever(periodic_jobs)


if __name__ == "__main__":
    main()
