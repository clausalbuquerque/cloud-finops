from __future__ import annotations

import unittest

from finops_ai.ingestion.chunker import ChunkerConfig, SectionAwareChunker
from finops_ai.ingestion.contracts import ProviderDocSource, SourceFormat


class ChunkerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.source = ProviderDocSource(
            source_id="gcp-compute-pricing",
            provider="GCP",
            category="pricing",
            resource_type="compute/instance",
            source_url="https://cloud.google.com/compute/all-pricing",
            cadence_days=7,
            source_format=SourceFormat.HTML,
        )

    def test_tokenizer_splits_words_and_punctuation(self) -> None:
        tokens = SectionAwareChunker.tokenize("n2-standard-4 costs $0.123/hour.")
        self.assertIn("n2", tokens)
        self.assertIn("-", tokens)
        self.assertIn(".", tokens)

    def test_section_aware_chunking_and_metadata(self) -> None:
        text = "## Pricing\n" + "word " * 120 + "\n### CLI\n" + "cmd " * 120
        chunker = SectionAwareChunker(ChunkerConfig(max_tokens=60, overlap_tokens=10, min_chunk_tokens=20))

        chunks = chunker.chunk(text, self.source)

        self.assertGreaterEqual(len(chunks), 4)
        self.assertTrue(all(chunk.token_count <= 60 for chunk in chunks))
        self.assertTrue(all(chunk.metadata["provider"] == "GCP" for chunk in chunks))
        self.assertTrue(all(chunk.metadata["source_id"] == self.source.source_id for chunk in chunks))

    def test_small_chunk_merge_and_dedup(self) -> None:
        text = "## Section\n" + ("alpha " * 40) + "\n" + ("beta " * 4) + "\n" + ("beta " * 4)
        chunker = SectionAwareChunker(ChunkerConfig(max_tokens=80, overlap_tokens=10, min_chunk_tokens=15))

        chunks = chunker.chunk(text, self.source)

        self.assertGreaterEqual(len(chunks), 1)
        hashes = [chunk.content_hash for chunk in chunks]
        self.assertEqual(len(hashes), len(set(hashes)))
        self.assertTrue(all(chunk.token_count <= 80 for chunk in chunks))


if __name__ == "__main__":
    unittest.main()
