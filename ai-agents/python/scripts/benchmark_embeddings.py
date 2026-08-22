from __future__ import annotations

import argparse
import statistics
import time

from finops_ai.embedding.backends import EmbeddingBackend
from finops_ai.embedding.contracts import EmbeddingMode
from finops_ai.embedding import EmbeddingService, EmbeddingServiceConfig


class StubEmbeddingBackend(EmbeddingBackend):
    def __init__(self, dimensions: int = 768) -> None:
        self._dimensions = dimensions

    def embed_texts(self, texts: list[str], mode: EmbeddingMode) -> list[list[float]]:
        base = 1.0 if mode is EmbeddingMode.INDEX else 2.0
        return [[base + (idx * 0.001)] * self._dimensions for idx, _ in enumerate(texts)]


def _sample_documents(count: int) -> list[str]:
    return [
        f"gcp compute recommendation #{idx}: switch n2-standard-8 to n2-standard-4 when cpu utilization < 25%"
        for idx in range(count)
    ]


def run_benchmark(documents: int, batch_size: int, rounds: int, backend: str) -> None:
    config = EmbeddingServiceConfig.from_env()
    config = EmbeddingServiceConfig(
        model_name=config.model_name,
        dimensions=config.dimensions,
        batch_size=batch_size,
        timeout_seconds=config.timeout_seconds,
        max_retries=config.max_retries,
        retry_backoff_seconds=config.retry_backoff_seconds,
    )

    if backend == "stub":
        service = EmbeddingService(config=config, backend=StubEmbeddingBackend(config.dimensions))
    else:
        service = EmbeddingService(config=config)
    docs = _sample_documents(documents)

    latencies_ms: list[float] = []
    throughput_docs_per_sec: list[float] = []

    for _ in range(rounds):
        start = time.perf_counter()
        result = service.embed_for_indexing(docs)
        elapsed = (time.perf_counter() - start) * 1000
        latencies_ms.append(elapsed)
        throughput_docs_per_sec.append(documents / (elapsed / 1000.0))

        if not result.vectors:
            raise RuntimeError("Benchmark failed: no vectors produced")

    sorted_latencies = sorted(latencies_ms)
    p95_index = max(0, int(round(0.95 * len(sorted_latencies))) - 1)

    print("Embedding benchmark summary")
    print(f"Model: {config.model_name}")
    print(f"Backend: {backend}")
    print(f"Docs per run: {documents}")
    print(f"Batch size: {batch_size}")
    print(f"Rounds: {rounds}")
    print(f"Latency p50 (ms): {statistics.median(latencies_ms):.2f}")
    print(f"Latency p95 (ms): {sorted_latencies[p95_index]:.2f}")
    print(f"Throughput avg (docs/s): {statistics.mean(throughput_docs_per_sec):.2f}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Benchmark local embedding service")
    parser.add_argument("--documents", type=int, default=128)
    parser.add_argument("--batch-size", type=int, default=16)
    parser.add_argument("--rounds", type=int, default=3)
    parser.add_argument("--backend", choices=["nomic", "stub"], default="nomic")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    run_benchmark(args.documents, args.batch_size, args.rounds, args.backend)


if __name__ == "__main__":
    main()
