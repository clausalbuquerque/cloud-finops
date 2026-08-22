from __future__ import annotations

from dataclasses import dataclass

from .contracts import FetchedDocument, ProviderDocSource


@dataclass(frozen=True)
class IntegrityCheckResult:
    passed: bool
    details: dict[str, str]


def verify_document_integrity(source: ProviderDocSource, document: FetchedDocument) -> IntegrityCheckResult:
    details = {
        "raw_content_sha256": document.raw_content_sha256,
        "signature_header_name": source.signature_header_name or "",
        "signature_header_value": document.signature_header_value or "",
    }

    if source.expected_raw_content_sha256:
        if document.raw_content_sha256.lower() != source.expected_raw_content_sha256.lower():
            return IntegrityCheckResult(passed=False, details={**details, "reason": "hash_mismatch"})

    if source.signature_header_name:
        if not document.signature_header_value:
            return IntegrityCheckResult(passed=False, details={**details, "reason": "missing_signature_header"})

    return IntegrityCheckResult(passed=True, details=details)
