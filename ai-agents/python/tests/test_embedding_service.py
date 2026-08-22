from __future__ import annotations

import time
import unittest

from finops_ai.embedding.config import EmbeddingServiceConfig
from finops_ai.embedding.contracts import EmbeddingMode, EmbeddingRuntimeError
from finops_ai.embedding.service import EmbeddingService


class StubBackend:
    def __init__(self, dims: int = 4) -> None:
        self.dims = dims
        self.calls = 0

    def embed_texts(self, texts: list[str], mode: EmbeddingMode) -> list[list[float]]:
        self.calls += 1
        base = 1.0 if mode is EmbeddingMode.INDEX else 2.0
        return [[base + float(idx)] * self.dims for idx, _ in enumerate(texts)]


class FailingBackend:
    def __init__(self, failures_before_success: int) -> None:
        self.failures_before_success = failures_before_success
        self.calls = 0

    def embed_texts(self, texts: list[str], mode: EmbeddingMode) -> list[list[float]]:
        self.calls += 1
        if self.calls <= self.failures_before_success:
            raise RuntimeError("transient backend error")
        return [[1.0, 2.0, 3.0] for _ in texts]


class ShapeMismatchBackend:
    def embed_texts(self, texts: list[str], mode: EmbeddingMode) -> list[list[float]]:
        return [[1.0], [1.0, 2.0]]


class SlowBackend:
    def embed_texts(self, texts: list[str], mode: EmbeddingMode) -> list[list[float]]:
        time.sleep(0.05)
        return [[1.0, 2.0] for _ in texts]


class EmbeddingServiceTests(unittest.TestCase):
    def test_embed_for_indexing_returns_deterministic_shape(self) -> None:
        service = EmbeddingService(
            config=EmbeddingServiceConfig(batch_size=2, max_retries=1),
            backend=StubBackend(dims=4),
        )

        result = service.embed_for_indexing(["alpha", "beta", "gamma"])

        self.assertEqual(3, len(result.vectors))
        self.assertTrue(all(len(vector) == 4 for vector in result.vectors))
        self.assertEqual(2, result.metrics.total_batches)

    def test_embed_for_query_uses_same_abstraction(self) -> None:
        backend = StubBackend(dims=6)
        service = EmbeddingService(
            config=EmbeddingServiceConfig(batch_size=4, max_retries=1),
            backend=backend,
        )

        vector = service.embed_for_query("resize vm")

        self.assertEqual(6, len(vector))
        self.assertEqual(1, backend.calls)

    def test_retry_succeeds_before_exhaustion(self) -> None:
        backend = FailingBackend(failures_before_success=2)
        service = EmbeddingService(
            config=EmbeddingServiceConfig(
                batch_size=10,
                max_retries=3,
                retry_backoff_seconds=0.0,
            ),
            backend=backend,
        )

        result = service.embed_for_indexing(["one", "two"])

        self.assertEqual(2, len(result.vectors))
        self.assertEqual(2, result.metrics.retries)
        self.assertEqual(3, backend.calls)

    def test_retry_exhaustion_raises_runtime_error(self) -> None:
        backend = FailingBackend(failures_before_success=99)
        service = EmbeddingService(
            config=EmbeddingServiceConfig(
                batch_size=10,
                max_retries=2,
                retry_backoff_seconds=0.0,
            ),
            backend=backend,
        )

        with self.assertRaises(EmbeddingRuntimeError):
            service.embed_for_indexing(["will", "fail"])

    def test_shape_mismatch_raises_error(self) -> None:
        service = EmbeddingService(
            config=EmbeddingServiceConfig(batch_size=2, max_retries=1),
            backend=ShapeMismatchBackend(),
        )

        with self.assertRaises(RuntimeError):
            service.embed_for_indexing(["a", "b"])

    def test_timeout_retries_then_fails(self) -> None:
        service = EmbeddingService(
            config=EmbeddingServiceConfig(
                batch_size=2,
                timeout_seconds=0.01,
                max_retries=2,
                retry_backoff_seconds=0.0,
            ),
            backend=SlowBackend(),
        )

        with self.assertRaises(EmbeddingRuntimeError):
            service.embed_for_indexing(["slow", "backend"])


if __name__ == "__main__":
    unittest.main()
