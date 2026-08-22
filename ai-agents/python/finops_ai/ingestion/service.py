from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from .contracts import IngestError, IngestProviderDocsInput, IngestProviderDocsOutput, ProviderDocSource
from .contracts import ChunkedDocument
from .chunker import SectionAwareChunker
from .fetcher import DocumentFetcher
from .normalizers import normalize_document
from .registry import SourceRegistry
from .repository import IngestionRepository
from .security import verify_document_integrity


class DocumentProcessor(Protocol):
    def fetch(self, source: ProviderDocSource): ...


@dataclass(frozen=True)
class IngestionServiceConfig:
    continue_on_error: bool = True


class ProviderDocsIngestionService:
    def __init__(
        self,
        registry: SourceRegistry,
        repository: IngestionRepository,
        fetcher: DocumentProcessor | None = None,
        chunker: SectionAwareChunker | None = None,
        config: IngestionServiceConfig | None = None,
    ) -> None:
        self._registry = registry
        self._repository = repository
        self._fetcher = fetcher or DocumentFetcher()
        self._chunker = chunker or SectionAwareChunker()
        self._config = config or IngestionServiceConfig()

    def ingest_provider_docs(self, request: IngestProviderDocsInput) -> IngestProviderDocsOutput:
        source = self._registry.get_source(request.source_id)
        run_id = self._repository.create_run(source_id=source.source_id, run_type="ingest")

        fetched = 0
        changed = 0
        chunks_created = 0
        chunks_updated = 0
        chunks_deprecated = 0
        errors: list[IngestError] = []

        try:
            doc = self._fetcher.fetch(source)
            fetched += 1

            integrity = verify_document_integrity(source=source, document=doc)
            if not integrity.passed:
                raise RuntimeError(f"Integrity check failed ({integrity.details.get('reason', 'unknown')})")

            normalized = normalize_document(doc)
            upsert = self._repository.upsert_document(
                source_id=source.source_id,
                source_url=source.source_url,
                provider=source.provider,
                category=source.category,
                content_hash=normalized.content_hash,
                fetched_at=normalized.fetched_at,
                force_full=request.force_full,
            )
            changed += int(upsert.changed)

            if upsert.changed or request.force_full:
                chunks = self._chunker.chunk(normalized.normalized_text, source)
                chunks = self._attach_integrity_metadata(chunks=chunks, integrity_details=integrity.details)
                chunk_result = self._repository.upsert_chunks(
                    document_id=upsert.document_id,
                    chunks=chunks,
                    fetched_at=normalized.fetched_at,
                    provider=source.provider,
                    resource_type=source.resource_type,
                    category=source.category,
                    source_url=source.source_url,
                )
                chunks_created += chunk_result.created
                chunks_updated += chunk_result.updated
                chunks_deprecated += chunk_result.deprecated
        except Exception as exc:
            errors.append(
                IngestError(
                    source_url=source.source_url,
                    error=str(exc),
                    stage="fetch_or_persist",
                )
            )
            if not self._config.continue_on_error:
                self._repository.complete_run(
                    run_id=run_id,
                    status="failed",
                    documents_processed=fetched,
                    chunks_created=chunks_created,
                    chunks_updated=chunks_updated,
                    chunks_deprecated=chunks_deprecated,
                    errors=[error.__dict__ for error in errors],
                )
                raise

        status = "completed" if not errors else "failed"
        self._repository.complete_run(
            run_id=run_id,
            status=status,
            documents_processed=fetched,
            chunks_created=chunks_created,
            chunks_updated=chunks_updated,
            chunks_deprecated=chunks_deprecated,
            errors=[error.__dict__ for error in errors],
        )

        return IngestProviderDocsOutput(
            run_id=run_id,
            documents_fetched=fetched,
            documents_changed=changed,
            chunks_created=chunks_created,
            chunks_updated=chunks_updated,
            chunks_deprecated=chunks_deprecated,
            errors=errors,
        )

    @staticmethod
    def _attach_integrity_metadata(
        chunks: list[ChunkedDocument],
        integrity_details: dict[str, str],
    ) -> list[ChunkedDocument]:
        decorated: list[ChunkedDocument] = []
        for chunk in chunks:
            metadata = {**chunk.metadata, **{f"integrity_{k}": v for k, v in integrity_details.items() if v}}
            decorated.append(
                ChunkedDocument(
                    chunk_index=chunk.chunk_index,
                    content=chunk.content,
                    token_count=chunk.token_count,
                    content_hash=chunk.content_hash,
                    metadata=metadata,
                )
            )
        return decorated
