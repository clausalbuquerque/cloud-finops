# Embedding Performance Baseline

## Scope

This baseline covers the TASK-022 embedding service abstraction used for:
- Index-time embedding (`EmbeddingMode.INDEX`)
- Query-time embedding (`EmbeddingMode.QUERY`)

Both paths use the same runtime and model (`nomic-ai/nomic-embed-text-v1.5`).

## Reproducible Environment

- Python: `3.12.12` (uv-managed)
- Package source: [pyproject.toml](../pyproject.toml)
- Container image build:

```bash
cd ai-agents/python
docker build -t cloud-finops-ai-embeddings -f Dockerfile .
```

## Benchmark Command

```bash
cd ai-agents/python
uv run --python .venv/bin/python python scripts/benchmark_embeddings.py --backend nomic --documents 128 --batch-size 16 --rounds 3
```

Offline benchmark (no external model download):

```bash
uv run --python .venv/bin/python python scripts/benchmark_embeddings.py --backend stub --documents 512 --batch-size 32 --rounds 5
```

## Baseline Template

Record and update measurements whenever model/runtime dependencies change.

| Date | Runtime | Model | Batch Size | Documents | p50 Latency (ms) | p95 Latency (ms) | Avg Throughput (docs/s) |
|------|---------|-------|------------|-----------|------------------|------------------|--------------------------|
| 2026-08-08 | local CPU (nomic backend) | nomic-ai/nomic-embed-text-v1.5 | 16 | 128 | 624.92 | 1068.67 | 181.02 |
| 2026-08-08 | local CPU (nomic backend) | nomic-ai/nomic-embed-text-v1.5 | 8 | 16 | 635.16 | 1180.69 | 96.03 |
| 2026-08-08 | local CPU (stub backend) | nomic-ai/nomic-embed-text-v1.5 | 32 | 512 | 2.75 | 3.95 | 173324.58 |

## Notes

- The benchmark script validates that vectors are produced and reports p50/p95 latency plus average throughput.
- For CI and unit tests, model calls should be mocked/stubbed to avoid network/download overhead.
- Runtime includes `truststore` injection so Python SSL uses OS trust settings in enterprise/self-signed chain environments.
- `nomic-ai/nomic-embed-text-v1.5` requires remote model code loading (`trust_remote_code=True`) and the `einops` dependency.
