from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeoutError
from dataclasses import dataclass
from time import sleep
from typing import Optional

from .backends import EmbeddingBackend, NomicEmbeddingBackend
from .config import EmbeddingServiceConfig
from .contracts import (
    BatchEmbeddingMetrics,
    EmbeddingBatchResult,
    EmbeddingMode,
    EmbeddingRuntimeError,
    EmbeddingTimeoutError,
    timed,
)


@dataclass
class _RetryState:
    attempts: int = 0
    retries: int = 0


class EmbeddingService:
    """
    Single abstraction for both index-time and query-time embeddings.

    Responsibilities:
    - batching
    - timeout control
    - retry with exponential backoff
    - output-shape validation
    """

    def __init__(
        self,
        config: Optional[EmbeddingServiceConfig] = None,
        backend: Optional[EmbeddingBackend] = None,
    ) -> None:
        self._config = config or EmbeddingServiceConfig.from_env()
        self._backend = backend or NomicEmbeddingBackend(
            self._config.model_name,
            huggingface_token=self._config.huggingface_token,
            local_files_only=self._config.local_files_only,
        )

    @property
    def config(self) -> EmbeddingServiceConfig:
        return self._config

    def embed_for_indexing(self, texts: list[str]) -> EmbeddingBatchResult:
        return self.embed_texts(texts, EmbeddingMode.INDEX)

    def embed_for_query(self, query: str) -> list[float]:
        result = self.embed_texts([query], EmbeddingMode.QUERY)
        return result.vectors[0]

    def embed_texts(self, texts: list[str], mode: EmbeddingMode) -> EmbeddingBatchResult:
        if not texts:
            metrics = BatchEmbeddingMetrics(0, 0, 0, 0.0)
            return EmbeddingBatchResult(vectors=[], metrics=metrics)

        cleaned = [text.strip() for text in texts]
        if any(not text for text in cleaned):
            raise ValueError("All texts must be non-empty after trimming.")

        retry_state = _RetryState()
        vectors: list[list[float]] = []
        total_latency_ms = 0.0
        batches = self._chunk(cleaned, self._config.batch_size)

        for batch in batches:
            batch_vectors, batch_latency_ms = self._embed_with_retry(batch, mode, retry_state)
            self._validate_shape(batch, batch_vectors)
            vectors.extend(batch_vectors)
            total_latency_ms += batch_latency_ms

        metrics = BatchEmbeddingMetrics(
            total_texts=len(cleaned),
            total_batches=len(batches),
            retries=retry_state.retries,
            latency_ms=total_latency_ms,
        )
        return EmbeddingBatchResult(vectors=vectors, metrics=metrics)

    def _embed_with_retry(
        self,
        batch: list[str],
        mode: EmbeddingMode,
        retry_state: _RetryState,
    ) -> tuple[list[list[float]], float]:
        last_error: Exception | None = None

        for attempt in range(1, self._config.max_retries + 1):
            retry_state.attempts += 1
            try:
                vectors, latency_ms = timed(
                    lambda: self._call_with_timeout(batch, mode, self._config.timeout_seconds)
                )
                return vectors, latency_ms
            except (EmbeddingTimeoutError, RuntimeError, ValueError) as exc:
                last_error = exc
                if attempt == self._config.max_retries:
                    break
                retry_state.retries += 1
                backoff = self._config.retry_backoff_seconds * (2 ** (attempt - 1))
                sleep(backoff)

        raise EmbeddingRuntimeError(
            f"Failed to embed batch after {self._config.max_retries} attempts"
        ) from last_error

    def _call_with_timeout(
        self,
        batch: list[str],
        mode: EmbeddingMode,
        timeout_seconds: float,
    ) -> list[list[float]]:
        with ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(self._backend.embed_texts, batch, mode)
            try:
                return future.result(timeout=timeout_seconds)
            except FuturesTimeoutError as exc:
                future.cancel()
                raise EmbeddingTimeoutError(
                    f"Embedding request timed out after {timeout_seconds:.2f}s"
                ) from exc

    @staticmethod
    def _chunk(texts: list[str], batch_size: int) -> list[list[str]]:
        return [texts[idx : idx + batch_size] for idx in range(0, len(texts), batch_size)]

    @staticmethod
    def _validate_shape(batch: list[str], vectors: list[list[float]]) -> None:
        if len(batch) != len(vectors):
            raise RuntimeError(
                f"Expected {len(batch)} vectors, received {len(vectors)}"
            )

        if vectors:
            dims = len(vectors[0])
            if dims == 0:
                raise RuntimeError("Embedding vector dimension cannot be zero")

            mismatched = [vector for vector in vectors if len(vector) != dims]
            if mismatched:
                raise RuntimeError("Embedding backend returned inconsistent dimensions")


def main() -> None:
    config = EmbeddingServiceConfig.from_env()
    service = EmbeddingService(config=config)
    sample = service.embed_for_query("right-size gcp compute instance")
    print(f"model={config.model_name} dimensions={len(sample)}")


if __name__ == "__main__":
    main()
