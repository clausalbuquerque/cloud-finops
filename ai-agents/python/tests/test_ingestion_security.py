from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
import unittest

from finops_ai.ingestion.contracts import FetchedDocument, ProviderDocSource, SourceFormat
from finops_ai.ingestion.security import verify_document_integrity


class IngestionSecurityTests(unittest.TestCase):
    def test_integrity_hash_match_passes(self) -> None:
        raw = b"trusted-content"
        document = FetchedDocument(
            source_url="https://cloud.google.com/doc",
            raw_content=raw,
            fetched_at=datetime.now(timezone.utc),
            source_format=SourceFormat.HTML,
            status_code=200,
            response_headers={},
            raw_content_sha256=sha256(raw).hexdigest(),
            signature_header_value=None,
        )
        source = ProviderDocSource(
            source_id="gcp-reviewed",
            provider="GCP",
            category="pricing",
            resource_type="compute/instance",
            source_url="https://cloud.google.com/doc",
            cadence_days=7,
            source_format=SourceFormat.HTML,
            review_ticket="SEC-100",
            approved_by="reviewer@example.com",
            expected_raw_content_sha256=sha256(raw).hexdigest(),
        )

        result = verify_document_integrity(source, document)
        self.assertTrue(result.passed)

    def test_integrity_missing_required_signature_fails(self) -> None:
        raw = b"trusted-content"
        document = FetchedDocument(
            source_url="https://cloud.google.com/doc",
            raw_content=raw,
            fetched_at=datetime.now(timezone.utc),
            source_format=SourceFormat.HTML,
            status_code=200,
            response_headers={},
            raw_content_sha256=sha256(raw).hexdigest(),
            signature_header_value=None,
        )
        source = ProviderDocSource(
            source_id="gcp-reviewed",
            provider="GCP",
            category="pricing",
            resource_type="compute/instance",
            source_url="https://cloud.google.com/doc",
            cadence_days=7,
            source_format=SourceFormat.HTML,
            review_ticket="SEC-100",
            approved_by="reviewer@example.com",
            signature_header_name="x-content-signature",
        )

        result = verify_document_integrity(source, document)
        self.assertFalse(result.passed)
        self.assertEqual("missing_signature_header", result.details["reason"])


if __name__ == "__main__":
    unittest.main()
