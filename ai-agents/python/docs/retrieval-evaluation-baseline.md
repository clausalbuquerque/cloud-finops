# Retrieval Evaluation Baseline

Date: 2026-08-08
Dataset: `docs/retrieval-golden-queries.json`
Mode: fixture-ranked benchmark
k: 5

## Metrics

- Recall@5: 1.0000
- MRR@5: 1.0000
- Source citation coverage: 1.0000
- Cross-provider contamination rate: 0.0000
- Pass thresholds: true

## Production Readiness Thresholds

Defined in dataset:

- `min_recall_at_k`: 0.75
- `min_mrr_at_k`: 0.65
- `min_source_citation_coverage`: 0.75
- `max_cross_provider_contamination_rate`: 0.0

## Notes

- This fixture baseline provides a deterministic regression gate for ranking/citation logic.
- Complement with live-corpus benchmarks once ingestion/indexing coverage expands.
