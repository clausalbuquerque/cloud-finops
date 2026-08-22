from __future__ import annotations

import json
from pathlib import Path
import unittest

from finops_ai.retrieval import (
    RetrievalEvalCase,
    RetrievalEvalHit,
    RetrievalEvalThresholds,
    evaluate_retrieval_results,
)


class RetrievalEvaluationTests(unittest.TestCase):
    def test_metrics_and_contamination(self) -> None:
        cases = [
            RetrievalEvalCase(
                case_id="c1",
                provider="GCP",
                resource_type="compute/instance",
                query="q1",
                category="pricing",
                expected_chunk_ids=["r1"],
                expected_source_domains=["cloud.google.com"],
                disallowed_providers=["AWS"],
            ),
            RetrievalEvalCase(
                case_id="c2",
                provider="GCP",
                resource_type="compute/instance",
                query="q2",
                category="cli",
                expected_chunk_ids=["r2"],
                expected_source_domains=["cloud.google.com"],
                disallowed_providers=["AWS"],
            ),
        ]

        ranked_hits_by_case = {
            "c1": [
                RetrievalEvalHit(
                    chunk_id="r1",
                    provider="GCP",
                    source_url="https://cloud.google.com/compute",
                    score=0.95,
                )
            ],
            "c2": [
                RetrievalEvalHit(
                    chunk_id="rX",
                    provider="AWS",
                    source_url="https://aws.amazon.com/ec2",
                    score=0.9,
                )
            ],
        }

        thresholds = RetrievalEvalThresholds(
            min_recall_at_k=0.5,
            min_mrr_at_k=0.5,
            min_source_citation_coverage=0.5,
            max_cross_provider_contamination_rate=0.0,
        )

        summary = evaluate_retrieval_results(cases, ranked_hits_by_case, k=5, thresholds=thresholds)

        self.assertAlmostEqual(0.5, summary.recall_at_k, places=6)
        self.assertAlmostEqual(0.5, summary.mrr_at_k, places=6)
        self.assertAlmostEqual(0.5, summary.source_citation_coverage, places=6)
        self.assertAlmostEqual(0.5, summary.cross_provider_contamination_rate, places=6)
        self.assertFalse(summary.passed)

    def test_golden_dataset_regression_thresholds(self) -> None:
        dataset_path = Path(__file__).resolve().parents[1] / "docs" / "retrieval-golden-queries.json"
        payload = json.loads(dataset_path.read_text(encoding="utf-8"))

        cases = [
            RetrievalEvalCase(
                case_id=item["case_id"],
                provider=item["provider"],
                resource_type=item["resource_type"],
                query=item["query"],
                category=item.get("category"),
                expected_chunk_ids=item["expected_chunk_ids"],
                expected_source_domains=item["expected_source_domains"],
                disallowed_providers=item.get("disallowed_providers", []),
            )
            for item in payload["queries"]
        ]

        ranked_hits_by_case = {
            case_id: [
                RetrievalEvalHit(
                    chunk_id=hit["chunk_id"],
                    provider=hit["provider"],
                    source_url=hit["source_url"],
                    score=float(hit["score"]),
                )
                for hit in hits
            ]
            for case_id, hits in payload["fixture_ranked_results"].items()
        }

        thresholds = RetrievalEvalThresholds(
            min_recall_at_k=float(payload["thresholds"]["min_recall_at_k"]),
            min_mrr_at_k=float(payload["thresholds"]["min_mrr_at_k"]),
            min_source_citation_coverage=float(payload["thresholds"]["min_source_citation_coverage"]),
            max_cross_provider_contamination_rate=float(payload["thresholds"]["max_cross_provider_contamination_rate"]),
        )

        summary = evaluate_retrieval_results(cases, ranked_hits_by_case, k=5, thresholds=thresholds)

        self.assertTrue(summary.passed)


if __name__ == "__main__":
    unittest.main()
