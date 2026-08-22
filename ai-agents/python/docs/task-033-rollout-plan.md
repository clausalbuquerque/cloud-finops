# TASK-033 Rollout Plan

## Objective

Roll out retrieval-backed recommendation rendering safely across environments.

## Scope

- Provider corpus: GCP official documentation sources in the ingestion registry
- Path under validation: analysis -> retrieval -> recommendation rendering
- Controls under validation: stale safeguard, SLO checks, scheduler reliability, rollback path

## Dev Evidence Snapshot (2026-08-08)

- Full tests: `45 passed`
- E2E report: `docs/e2e-validation-report.json`
- Retrieval: `used=true`, `candidates=58`, `returned=5`, `latency_ms=42.78`
- Recommendation latency: `641.16ms`
- SLO evaluation: `passed=true`, `violations=[]`
- Stale safeguard: `passed=true`
- Citations: `5`
- Scheduler once run IDs:
	- ingest `98fba31a-5866-4b01-82e0-3d2c902eab81` (`gcp-compute-machine-types`)
	- ingest `8c833a90-c940-4677-a9eb-8ef10079694f` (`gcp-compute-pricing`)
	- ingest `d98a6533-0e51-4db1-ada0-9fa6c2f57f59` (`gcp-gcloud-compute-resize`)
	- ingest `dcf2cd9c-f812-4319-9021-95f2e5de0b9a` (`gcp-compute-rightsizing-recommendations`)
	- ingest `418a448d-b444-4aad-9bcf-bf31d26878b5` (`gcp-cud-pricing`)
	- index `96f0b147-69d4-4bda-a7ff-27fa66b1c7b4` (`GCP`)

## Phased Plan

1. Dev
- Execute and archive evidence commands:
	- `uv run --python .venv/bin/python python -m unittest discover -s tests -p "test_*.py"`
	- `uv run --python .venv/bin/python python scripts/run_e2e_validation.py --provider GCP --resource-type compute/instance --category pricing`
	- `uv run --python .venv/bin/python python scripts/run_ops_scheduler.py --once --provider GCP`
	- `uv run --python .venv/bin/python python scripts/list_ops_runs.py --limit 10`
- Verify E2E and SLO pass in `docs/e2e-validation-report.json`.
- Confirm operation statuses are `completed` for ingest and index runs.

2. Staging
- Deploy same code and environment settings.
- Re-run E2E validation with staging data.
- Verify stale-safeguard behavior with strict freshness test.
- Monitor p95 retrieval latency and empty-result/stale-result rates for 24h.
- Gate to proceed: no SLO violations, no retrieval failure burst, no contamination incidents.

3. Production
- Enable feature flag/canary for a subset of recommendation traffic.
- Track rollback triggers and quality guardrails.
- Increase traffic gradually after stability window.
- Gate to full rollout: manual sign-off complete and staging reliability window passed.

## Rollback Procedure

- Disable retrieval-backed rendering flag and return to deterministic recommendation template path.
- Keep ingestion/indexing jobs running but suppress retrieval context insertion.
- Investigate logs for retrieval failures, stale-hit spikes, and source contamination.
- Re-run E2E validation before re-enabling.

## Approval Gates

- Dev validation report is green.
- Staging validation and SLO checks are green.
- Manual verification checklist completed by FinOps/SRE reviewers.
- Final product/owner approval recorded.
