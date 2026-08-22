from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum


class SourceFormat(str, Enum):
    MARKDOWN = "markdown"
    HTML = "html"
    PDF = "pdf"


@dataclass(frozen=True)
class ProviderDocSource:
    source_id: str
    provider: str
    category: str
    resource_type: str
    source_url: str
    cadence_days: int
    source_format: SourceFormat
    # Manual governance controls for non-default source onboarding.
    review_ticket: str | None = None
    approved_by: str | None = None
    # Optional integrity expectations when publisher hashes/signatures are available.
    expected_raw_content_sha256: str | None = None
    signature_header_name: str | None = None


@dataclass(frozen=True)
class IngestProviderDocsInput:
    source_id: str
    force_full: bool = False


@dataclass(frozen=True)
class IngestError:
    source_url: str
    error: str
    stage: str


@dataclass(frozen=True)
class IngestProviderDocsOutput:
    run_id: str
    documents_fetched: int
    documents_changed: int
    chunks_created: int
    chunks_updated: int
    chunks_deprecated: int
    errors: list[IngestError]


@dataclass(frozen=True)
class FetchedDocument:
    source_url: str
    raw_content: bytes
    fetched_at: datetime
    source_format: SourceFormat
    status_code: int
    response_headers: dict[str, str]
    raw_content_sha256: str
    signature_header_value: str | None


@dataclass(frozen=True)
class NormalizedDocument:
    normalized_text: str
    content_hash: str
    fetched_at: datetime


@dataclass(frozen=True)
class ChunkedDocument:
    chunk_index: int
    content: str
    token_count: int
    content_hash: str
    metadata: dict[str, str]


@dataclass(frozen=True)
class ChunkUpsertResult:
    created: int
    updated: int
    deprecated: int


@dataclass(frozen=True)
class UpsertDocumentResult:
    changed: bool
    document_id: str
