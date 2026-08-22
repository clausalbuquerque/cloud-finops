from __future__ import annotations

from unittest.mock import Mock, patch
import unittest

import requests

from finops_ai.ingestion.fetcher import DocumentFetcher, FetcherConfig
from finops_ai.ingestion.registry import SourceRegistry


class FetcherTests(unittest.TestCase):
    def test_fetch_retries_then_succeeds(self) -> None:
        source = SourceRegistry().get_source("gcp-compute-pricing")

        success_response = Mock()
        success_response.status_code = 200
        success_response.content = b"ok"
        success_response.headers = {}
        success_response.raise_for_status = Mock()

        with patch("finops_ai.ingestion.fetcher.sleep", return_value=None), patch(
            "finops_ai.ingestion.fetcher.requests.get",
            side_effect=[requests.RequestException("boom"), success_response],
        ) as get_mock:
            fetcher = DocumentFetcher(FetcherConfig(max_retries=2, retry_backoff_seconds=0.0))
            result = fetcher.fetch(source)

        self.assertEqual(2, get_mock.call_count)
        self.assertEqual(200, result.status_code)
        self.assertEqual(b"ok", result.raw_content)

    def test_fetch_exhausts_retries(self) -> None:
        source = SourceRegistry().get_source("gcp-compute-pricing")

        with patch("finops_ai.ingestion.fetcher.sleep", return_value=None), patch(
            "finops_ai.ingestion.fetcher.requests.get",
            side_effect=requests.Timeout("timeout"),
        ):
            fetcher = DocumentFetcher(FetcherConfig(max_retries=2, retry_backoff_seconds=0.0))
            with self.assertRaises(RuntimeError):
                fetcher.fetch(source)


if __name__ == "__main__":
    unittest.main()
