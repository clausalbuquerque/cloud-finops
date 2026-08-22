from __future__ import annotations

import unittest

from finops_ai.ingestion.contracts import ProviderDocSource, SourceFormat
from finops_ai.ingestion.registry import SourceRegistry


class SourceRegistryTests(unittest.TestCase):
    def test_default_registry_has_expected_sources(self) -> None:
        registry = SourceRegistry()
        self.assertGreaterEqual(len(registry.list_sources()), 5)

    def test_untrusted_source_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            SourceRegistry(
                sources=(
                    ProviderDocSource(
                        source_id="bad-source",
                        provider="GCP",
                        category="pricing",
                        resource_type="compute/instance",
                        source_url="https://evil.example.com/malicious",
                        cadence_days=7,
                        source_format=SourceFormat.HTML,
                    ),
                )
            )

    def test_new_source_requires_manual_review_metadata(self) -> None:
        with self.assertRaises(ValueError):
            SourceRegistry(
                sources=(
                    ProviderDocSource(
                        source_id="gcp-new-cost-doc",
                        provider="GCP",
                        category="pricing",
                        resource_type="compute/instance",
                        source_url="https://cloud.google.com/new-doc",
                        cadence_days=7,
                        source_format=SourceFormat.HTML,
                    ),
                )
            )

    def test_new_source_with_manual_review_metadata_is_allowed(self) -> None:
        registry = SourceRegistry(
            sources=(
                ProviderDocSource(
                    source_id="gcp-new-reviewed-doc",
                    provider="GCP",
                    category="pricing",
                    resource_type="compute/instance",
                    source_url="https://cloud.google.com/new-reviewed-doc",
                    cadence_days=7,
                    source_format=SourceFormat.HTML,
                    review_ticket="SEC-1234",
                    approved_by="finops-security@example.com",
                ),
            )
        )

        self.assertEqual(1, len(registry.list_sources()))


if __name__ == "__main__":
    unittest.main()
