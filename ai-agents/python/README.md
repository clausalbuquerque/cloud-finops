# AI Agents Python Runtime

Python runtime for AI-agent retrieval components, including the embedding service used for both indexing and query embeddings.

## Model

- Default model: `nomic-ai/nomic-embed-text-v1.5`
- Dimension: 768
- Token envs supported by the runtime: `HF_TOKEN`, `HUGGINGFACEHUB_API_TOKEN`, `HUGGINGFACE_API_TOKEN`, `hf_token`
- TLS trust: runtime uses `truststore` to inherit OS trust settings (helps enterprise/self-signed chain environments)

## Local setup

```bash
cd ai-agents/python
uv venv .venv
uv pip install --python .venv/bin/python -e .
```

## Run tests

```bash
cd ai-agents/python
uv run --python .venv/bin/python python -m unittest discover -s tests -p "test_*.py"
```

## Agent runtime (CrewAI + Gemini via Vertex AI)

The FinOps/SRE agents run on **CrewAI** with **Google Gemini via Vertex AI**. See
[ADR: Agent Runtime](docs/../../docs/adr-agent-runtime.md) for the design.

Install (after `./scripts/sync-env.sh` from the repo root has populated `.env`):

```bash
cd ai-agents/python
uv pip install --python .venv/bin/python -e .
```

Build an LLM in code via the single factory (model tier per role):

```python
from finops_ai.llm import build_llm

llm = build_llm("pro")     # gemini/gemini-2.5-pro   (deep reasoning)
llm = build_llm("flash")   # gemini/gemini-2.5-flash (cheap/fast)
```

`build_llm()` reads `GCP_AGENTS_API_KEY` (Vertex AI Express mode) from `.env`, sets
`GOOGLE_GENAI_USE_VERTEXAI=true`, and injects `truststore` so TLS works behind
enterprise CA chains. For production, leave the key empty and use ADC
(`gcloud auth application-default login`) with `GOOGLE_CLOUD_PROJECT` / `GOOGLE_CLOUD_LOCATION`.

Validate the runtime with the hello-flow smoke test (makes one live Gemini call):

```bash
uv run --python .venv/bin/python python scripts/run_hello_flow.py
# -> Flow result: 'FINOPS_OK'  /  Health check: PASS
```

## Containerized runtime

```bash
docker build -t cloud-finops-ai-embeddings -f Dockerfile .
```

## Benchmark

```bash
cd ai-agents/python
uv run --python .venv/bin/python python scripts/benchmark_embeddings.py --backend nomic --batch-size 16 --documents 256
```

If your environment cannot download models due to enterprise TLS interception, run:

```bash
uv run --python .venv/bin/python python scripts/benchmark_embeddings.py --backend stub --batch-size 16 --documents 256
```

Or run with local Hugging Face cache only:

```bash
EMBEDDING_LOCAL_FILES_ONLY=true uv run --python .venv/bin/python python scripts/benchmark_embeddings.py --backend nomic --batch-size 16 --documents 256
```

## Ingestion pipeline

Run provider documentation ingestion for a configured source:

```bash
cd ai-agents/python
set -a && source .env && set +a
export DATABASE_URL="postgresql+psycopg://postgres:postgres123@localhost:5432/cloud_finops"
uv run --python .venv/bin/python python scripts/run_ingestion.py --source-id gcp-compute-pricing
```

Force a full refresh for the selected source:

```bash
uv run --python .venv/bin/python python scripts/run_ingestion.py --source-id gcp-compute-pricing --force-full
```

Current source registry is restricted to official GCP and Azure documentation hosts (`cloud.google.com`, `docs.cloud.google.com`, `learn.microsoft.com`).

New source onboarding requires manual review metadata (`review_ticket`, `approved_by`) for non-default entries.
See [docs/source-governance-review-workflow.md](docs/source-governance-review-workflow.md).

Integrity checks run before persistence when configured (`expected_raw_content_sha256`, `signature_header_name`).

## Indexing pipeline

Build or refresh embeddings from chunked KB documents:

```bash
cd ai-agents/python
set -a && source .env && set +a
export DATABASE_URL="postgresql+psycopg://postgres:postgres123@localhost:5432/cloud_finops"
uv run --python .venv/bin/python python scripts/run_indexing.py --mode incremental --provider GCP
```

For a complete rebuild:

```bash
uv run --python .venv/bin/python python scripts/run_indexing.py --mode full
```

## Retrieval pipeline

Query provider-specific context at recommendation-render time:

```bash
cd ai-agents/python
set -a && source .env && set +a
export DATABASE_URL="postgresql+psycopg://postgres:postgres123@localhost:5432/cloud_finops"
uv run --python .venv/bin/python python scripts/run_retrieval.py \
	--provider GCP \
	--resource-type compute/instance \
	--query "right-size from n2-standard-8 to a smaller machine" \
	--category pricing \
	--top-k 5
```

Quick RAG smoke test utility (can start DB, show corpus stats, and run preset or ad-hoc queries):

```bash
cd ai-agents/python
set -a && source .env && set +a
export DATABASE_URL="postgresql+psycopg://postgres:postgres123@localhost:5432/cloud_finops"
uv run --python .venv/bin/python python scripts/run_rag_quick_test.py \
	--start-db \
	--provider AZURE \
	--resource-type organization \
	--preset sre \
	--show-stats
```

Interactive mode example:

```bash
uv run --python .venv/bin/python python scripts/run_rag_quick_test.py \
	--provider GCP \
	--resource-type compute/instance \
	--interactive
```

## Recommendation rendering with retrieval

Retrieval augments recommendation phrasing only; it does not change anomaly/forecast calculations.

```python
from finops_ai.agents import RecommendationCandidate, RecommendationRenderer

renderer = RecommendationRenderer(retrieval_service=your_retrieval_service)
rendered = renderer.render(
		RecommendationCandidate(
				provider="GCP",
				resource_type="compute/instance",
				resource_name="orders-vm-1",
				action_summary="Downsize machine type",
				rationale="CPU under-utilized for 14 days",
				estimated_monthly_savings_usd=73.42,
		)
)
```

## Freshness and staleness controls

- Hard freshness filter: retrieval excludes chunks older than `max_age_days` (default `30`).
- Aging penalty: chunk score is reduced as `last_verified` approaches expiration.
- High-savings warning: renderer adds a warning when pricing evidence is old for high-impact actions.

Post-execution drift workflow helper:

```python
from finops_ai.retrieval import trigger_reverification_on_drift

enqueued = trigger_reverification_on_drift(
    chunks=retrieved_chunks,
    estimated_monthly_savings_usd=120.0,
    actual_monthly_savings_usd=95.0,
    queue=your_reverification_queue,
    drift_threshold_pct=10.0,
)
```

## Retrieval evaluation benchmark

Run golden-query retrieval quality benchmark:

```bash
cd ai-agents/python
uv run --python .venv/bin/python python scripts/benchmark_retrieval.py \
	--dataset docs/retrieval-golden-queries.json \
	--k 5 \
	--output-json docs/retrieval-evaluation-baseline.json
```

The benchmark computes `Recall@k`, `MRR@k`, source citation coverage, and cross-provider contamination rate.
Regression threshold checks are enforced by tests in `tests/test_retrieval_evaluation.py`.

## Scheduled operations (ingestion + indexing)

Run one scheduler cycle locally (all configured sources for provider + incremental indexing):

```bash
cd ai-agents/python
set -a && source .env && set +a
export DATABASE_URL="postgresql+psycopg://postgres:postgres123@localhost:5432/cloud_finops"
uv run --python .venv/bin/python python scripts/run_ops_scheduler.py --once --provider GCP
```

Run as a long-lived scheduler process (weekly ingestion and daily incremental indexing defaults):

```bash
uv run --python .venv/bin/python python scripts/run_ops_scheduler.py --provider GCP
```

List recent persisted run status for operations:

```bash
uv run --python .venv/bin/python python scripts/list_ops_runs.py --limit 20
```

Dead-letter failures are written to `docs/dead-letter-jobs.jsonl` after retries are exhausted.

## End-to-end validation and rollout

Run E2E validation (analysis -> retrieval -> recommendation + stale safeguard + SLO check):

```bash
cd ai-agents/python
set -a && source .env && set +a
export DATABASE_URL="postgresql+psycopg://postgres:postgres123@localhost:5432/cloud_finops"
uv run --python .venv/bin/python python scripts/run_e2e_validation.py --provider GCP --resource-type compute/instance --category pricing
```

Outputs JSON report to `docs/e2e-validation-report.json`.

Run full documentation evidence sequence (tests + E2E + scheduler + run status):

```bash
cd ai-agents/python
uv run --python .venv/bin/python python -m unittest discover -s tests -p "test_*.py"
set -a && source .env && set +a
export DATABASE_URL="postgresql+psycopg://postgres:postgres123@localhost:5432/cloud_finops"
uv run --python .venv/bin/python python scripts/run_e2e_validation.py --provider GCP --resource-type compute/instance --category pricing
uv run --python .venv/bin/python python scripts/run_ops_scheduler.py --once --provider GCP
uv run --python .venv/bin/python python scripts/list_ops_runs.py --limit 10
```

Latest validated dev snapshot (2026-08-08):

- tests: `45 passed`
- retrieval: `used=true`, `candidates=58`, `returned=5`, `latency_ms=42.78`
- recommendation latency: `641.16ms`
- SLO: `passed=true`
- stale safeguard: `passed=true`
- source citations: `5`

Primary evidence artifacts:

- `docs/e2e-validation-report.json`
- `docs/task-033-e2e-documentation-report.md`
- `docs/task-033-rollout-plan.md`
- `docs/task-033-manual-verification.md`

Rollout and manual verification docs:

- `docs/task-033-rollout-plan.md`
- `docs/task-033-manual-verification.md`

## Observability and tracing

Retrieval and recommendation flows emit structured events with shared `trace_id` values.

- `retrieval.start` / `retrieval.complete` / `retrieval.failure`
- `recommendation.start` / `recommendation.complete`

Use analytics helpers for dashboard and alert computations:

```python
from finops_ai.observability import AlertThresholds, compute_dashboard_metrics, evaluate_alerts

metrics = compute_dashboard_metrics(events)
alerts = evaluate_alerts(events, AlertThresholds(max_retrieval_failures=0, max_stale_result_rate=0.25))
```

Query logging uses redaction guards to mask common PII/token patterns.

See [docs/embedding-performance-baseline.md](docs/embedding-performance-baseline.md) for baseline methodology and initial results.
