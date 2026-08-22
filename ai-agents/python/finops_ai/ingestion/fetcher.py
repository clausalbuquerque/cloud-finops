from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from hashlib import sha256
from time import sleep

import requests

from .contracts import FetchedDocument, ProviderDocSource

try:
    import truststore

    truststore.inject_into_ssl()
except Exception:  # pragma: no cover
    # Fallback to default SSL behavior when truststore is unavailable.
    pass


@dataclass(frozen=True)
class FetcherConfig:
    timeout_seconds: float = 20.0
    max_retries: int = 3
    retry_backoff_seconds: float = 0.5


class DocumentFetcher:
    def __init__(self, config: FetcherConfig | None = None) -> None:
        self._config = config or FetcherConfig()

    def fetch(self, source: ProviderDocSource) -> FetchedDocument:
        last_error: Exception | None = None

        for attempt in range(1, self._config.max_retries + 1):
            try:
                response = requests.get(source.source_url, timeout=self._config.timeout_seconds)
                response.raise_for_status()
                response_headers = {k.lower(): v for k, v in response.headers.items()}
                raw_content_sha256 = sha256(response.content).hexdigest()
                return FetchedDocument(
                    source_url=source.source_url,
                    raw_content=response.content,
                    fetched_at=datetime.now(timezone.utc),
                    source_format=source.source_format,
                    status_code=response.status_code,
                    response_headers=response_headers,
                    raw_content_sha256=raw_content_sha256,
                    signature_header_value=(
                        response_headers.get((source.signature_header_name or "").lower())
                        if source.signature_header_name
                        else None
                    ),
                )
            except Exception as exc:
                last_error = exc
                if attempt == self._config.max_retries:
                    break
                backoff = self._config.retry_backoff_seconds * (2 ** (attempt - 1))
                sleep(backoff)

        raise RuntimeError(f"Failed to fetch {source.source_url}") from last_error
