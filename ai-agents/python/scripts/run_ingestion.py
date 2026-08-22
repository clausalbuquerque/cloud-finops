from __future__ import annotations

import argparse
import os

from finops_ai.ingestion import IngestProviderDocsInput, ProviderDocsIngestionService, SourceRegistry
from finops_ai.ingestion.repository import IngestionRepository


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Ingest provider docs into kb_documents")
    parser.add_argument("--source-id", required=True)
    parser.add_argument("--force-full", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    db_url = os.getenv("DATABASE_URL")
    if not db_url:
        raise RuntimeError("DATABASE_URL is required")

    service = ProviderDocsIngestionService(
        registry=SourceRegistry(),
        repository=IngestionRepository.from_url(db_url),
    )

    result = service.ingest_provider_docs(
        IngestProviderDocsInput(source_id=args.source_id, force_full=args.force_full)
    )

    print("Ingestion run summary")
    print(f"run_id={result.run_id}")
    print(f"documents_fetched={result.documents_fetched}")
    print(f"documents_changed={result.documents_changed}")
    print(f"errors={len(result.errors)}")


if __name__ == "__main__":
    main()
