from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from hashlib import sha256
import unittest

from finops_ai.ingestion.contracts import (
    FetchedDocument,
    IngestProviderDocsInput,
    ProviderDocSource,
    SourceFormat,
)
from finops_ai.ingestion.service import ProviderDocsIngestionService


@dataclass
class FakeUpsertResult:
    changed: bool
    document_id: str


@dataclass
class FakeChunkUpsertResult:
    created: int
    updated: int
    deprecated: int


class FakeRepository:
    def __init__(self) -> None:
        self.created_runs: list[tuple[str | None, str]] = []
        self.completed_runs: list[
            tuple[str, str, int, int, int, int, list[dict[str, str]]]
        ] = []
        self.upsert_calls: int = 0
        self.chunk_upsert_calls: int = 0

    def create_run(self, source_id: str | None, run_type: str = "ingest") -> str:
        self.created_runs.append((source_id, run_type))
        return "run-123"

    def complete_run(
        self,
        run_id: str,
        status: str,
        documents_processed: int,
        chunks_created: int,
        chunks_updated: int,
        chunks_deprecated: int,
        errors: list[dict[str, str]],
    ) -> None:
        self.completed_runs.append(
            (
                run_id,
                status,
                documents_processed,
                chunks_created,
                chunks_updated,
                chunks_deprecated,
                errors,
            )
        )

    def upsert_document(self, **kwargs):
        self.upsert_calls += 1
        return FakeUpsertResult(changed=True, document_id="doc-123")

    def upsert_chunks(self, **kwargs):
        self.chunk_upsert_calls += 1
        return FakeChunkUpsertResult(created=2, updated=1, deprecated=0)


class FakeRegistry:
    def __init__(self, source: ProviderDocSource) -> None:
        self._source = source

    def get_source(self, source_id: str) -> ProviderDocSource:
        if source_id != self._source.source_id:
            raise KeyError(source_id)
        return self._source


class SuccessfulFetcher:
    def fetch(self, source: ProviderDocSource) -> FetchedDocument:
        raw = b"<html><body><h1>Compute Pricing</h1></body></html>"
        return FetchedDocument(
            source_url=source.source_url,
            raw_content=raw,
            fetched_at=datetime.now(timezone.utc),
            source_format=SourceFormat.HTML,
            status_code=200,
            response_headers={},
            raw_content_sha256=sha256(raw).hexdigest(),
            signature_header_value=None,
        )


class FailingFetcher:
    def fetch(self, source: ProviderDocSource) -> FetchedDocument:
        raise RuntimeError("network down")


class IngestionServiceTests(unittest.TestCase):
    def test_ingestion_success_logs_completed_run(self) -> None:
        source = ProviderDocSource(
            source_id="gcp-compute-pricing",
            provider="GCP",
            category="pricing",
            resource_type="compute/instance",
            source_url="https://cloud.google.com/compute/all-pricing",
            cadence_days=7,
            source_format=SourceFormat.HTML,
        )
        repo = FakeRepository()

        service = ProviderDocsIngestionService(
            registry=FakeRegistry(source),
            repository=repo,
            fetcher=SuccessfulFetcher(),
        )

        result = service.ingest_provider_docs(IngestProviderDocsInput(source_id=source.source_id))

        self.assertEqual("run-123", result.run_id)
        self.assertEqual(1, result.documents_fetched)
        self.assertEqual(1, result.documents_changed)
        self.assertEqual(2, result.chunks_created)
        self.assertEqual(1, result.chunks_updated)
        self.assertEqual(0, result.chunks_deprecated)
        self.assertEqual(0, len(result.errors))
        self.assertEqual(1, repo.upsert_calls)
        self.assertEqual(1, repo.chunk_upsert_calls)
        self.assertEqual("completed", repo.completed_runs[0][1])

    def test_ingestion_failure_records_partial_failure(self) -> None:
        source = ProviderDocSource(
            source_id="gcp-compute-pricing",
            provider="GCP",
            category="pricing",
            resource_type="compute/instance",
            source_url="https://cloud.google.com/compute/all-pricing",
            cadence_days=7,
            source_format=SourceFormat.HTML,
        )
        repo = FakeRepository()

        service = ProviderDocsIngestionService(
            registry=FakeRegistry(source),
            repository=repo,
            fetcher=FailingFetcher(),
        )

        result = service.ingest_provider_docs(IngestProviderDocsInput(source_id=source.source_id))

        self.assertEqual(0, result.documents_fetched)
        self.assertEqual(0, result.chunks_created)
        self.assertEqual(0, result.chunks_updated)
        self.assertEqual(0, result.chunks_deprecated)
        self.assertEqual(1, len(result.errors))
        self.assertEqual("failed", repo.completed_runs[0][1])

    def test_ingestion_integrity_mismatch_fails_run(self) -> None:
        source = ProviderDocSource(
            source_id="gcp-compute-pricing",
            provider="GCP",
            category="pricing",
            resource_type="compute/instance",
            source_url="https://cloud.google.com/compute/all-pricing",
            cadence_days=7,
            source_format=SourceFormat.HTML,
            expected_raw_content_sha256="deadbeef",
        )
        repo = FakeRepository()

        service = ProviderDocsIngestionService(
            registry=FakeRegistry(source),
            repository=repo,
            fetcher=SuccessfulFetcher(),
        )

        result = service.ingest_provider_docs(IngestProviderDocsInput(source_id=source.source_id))

        self.assertEqual(1, result.documents_fetched)
        self.assertEqual(0, result.documents_changed)
        self.assertEqual(1, len(result.errors))
        self.assertIn("Integrity check failed", result.errors[0].error)
        self.assertEqual("failed", repo.completed_runs[0][1])


if __name__ == "__main__":
    unittest.main()
