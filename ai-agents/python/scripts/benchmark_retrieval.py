from __future__ import annotations

import argparse
import json
from pathlib import Path

from finops_ai.retrieval import (
    RetrievalEvalCase,
    RetrievalEvalHit,
    RetrievalEvalThresholds,
    evaluate_retrieval_results,
)


def _load_dataset(dataset_path: Path) -> tuple[list[RetrievalEvalCase], dict[str, list[RetrievalEvalHit]], RetrievalEvalThresholds]:
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

    threshold_payload = payload["thresholds"]
    thresholds = RetrievalEvalThresholds(
        min_recall_at_k=float(threshold_payload["min_recall_at_k"]),
        min_mrr_at_k=float(threshold_payload["min_mrr_at_k"]),
        min_source_citation_coverage=float(threshold_payload["min_source_citation_coverage"]),
        max_cross_provider_contamination_rate=float(threshold_payload["max_cross_provider_contamination_rate"]),
    )

    return cases, ranked_hits_by_case, thresholds


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Benchmark retrieval quality against golden query set")
    parser.add_argument(
        "--dataset",
        default="docs/retrieval-golden-queries.json",
        help="Path to golden retrieval dataset JSON",
    )
    parser.add_argument("--k", type=int, default=5)
    parser.add_argument(
        "--output-json",
        default=None,
        help="Optional output file for benchmark summary JSON",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    cases, ranked_hits_by_case, thresholds = _load_dataset(Path(args.dataset))

    summary = evaluate_retrieval_results(
        cases=cases,
        ranked_hits_by_case=ranked_hits_by_case,
        k=args.k,
        thresholds=thresholds,
    )

    print("Retrieval benchmark summary")
    print(f"Dataset: {args.dataset}")
    print(f"Queries: {summary.query_count}")
    print(f"k: {args.k}")
    print(f"Recall@{args.k}: {summary.recall_at_k:.4f}")
    print(f"MRR@{args.k}: {summary.mrr_at_k:.4f}")
    print(f"Source citation coverage: {summary.source_citation_coverage:.4f}")
    print(f"Cross-provider contamination rate: {summary.cross_provider_contamination_rate:.4f}")
    print(f"Pass thresholds: {summary.passed}")

    if args.output_json:
        output = {
            "query_count": summary.query_count,
            "k": args.k,
            "recall_at_k": summary.recall_at_k,
            "mrr_at_k": summary.mrr_at_k,
            "source_citation_coverage": summary.source_citation_coverage,
            "cross_provider_contamination_rate": summary.cross_provider_contamination_rate,
            "passed": summary.passed,
        }
        Path(args.output_json).write_text(json.dumps(output, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
