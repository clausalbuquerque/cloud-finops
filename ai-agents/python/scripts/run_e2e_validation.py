from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from time import perf_counter

from finops_ai.agents import (
    RecommendationCandidate,
    RecommendationRenderer,
    RecommendationRendererConfig,
    summarize_analysis_without_retrieval,
)
from finops_ai.embedding import EmbeddingService, EmbeddingServiceConfig
from finops_ai.operations import SLOThresholds, evaluate_slos
from finops_ai.retrieval import (
    ProviderContextRetrievalService,
    RetrieveProviderContextInput,
    RetrievalRepository,
    RetrievalServiceConfig,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run end-to-end validation for retrieval-backed recommendations")
    parser.add_argument("--provider", default="GCP")
    parser.add_argument("--resource-type", default="compute/instance")
    parser.add_argument("--query", default="right-size from n2-standard-8 to n2-standard-4")
    parser.add_argument("--category", default="pricing")
    parser.add_argument("--top-k", type=int, default=5)
    parser.add_argument("--max-age-days", type=int, default=30)
    parser.add_argument("--output-json", default="docs/e2e-validation-report.json")
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    db_url = os.getenv("DATABASE_URL")
    if not db_url:
        raise RuntimeError("DATABASE_URL is required")

    retrieval_service = ProviderContextRetrievalService(
        repository=RetrievalRepository.from_url(db_url),
        embedding_service=EmbeddingService(config=EmbeddingServiceConfig.from_env()),
        config=RetrievalServiceConfig(),
    )

    renderer = RecommendationRenderer(
        retrieval_service=retrieval_service,
        config=RecommendationRendererConfig(
            retrieval_top_k=args.top_k,
            retrieval_max_age_days=args.max_age_days,
        ),
    )

    analysis_summary = summarize_analysis_without_retrieval(
        anomaly_summary="CPU utilization below 30% for 14 days",
        forecast_summary="Projected steady usage over next 30 days",
    )

    candidate = RecommendationCandidate(
        provider=args.provider,
        resource_type=args.resource_type,
        resource_name="orders-vm-1",
        action_summary="Downsize machine type",
        rationale="Sustained under-utilization suggests lower tier is sufficient",
        estimated_monthly_savings_usd=120.0,
    )

    start = perf_counter()
    rendered = renderer.render(candidate)
    recommendation_latency_ms = (perf_counter() - start) * 1000

    retrieval_latency_ms = 0.0
    source_count = 0
    if rendered.used_retrieval:
        source_count = rendered.body.count("(source:")

    # Run controlled stale-safeguard check by forcing strict freshness window.
    stale_guard_renderer = RecommendationRenderer(
        retrieval_service=retrieval_service,
        config=RecommendationRendererConfig(
            retrieval_top_k=args.top_k,
            retrieval_max_age_days=0,
        ),
    )
    stale_guard_output = stale_guard_renderer.render(candidate)
    stale_guard_passed = (
        (not stale_guard_output.used_retrieval)
        or ("Warning: Pricing evidence is aging" in stale_guard_output.body)
    )

    # Collect one direct retrieval call latency for SLO check.
    retrieval_start = perf_counter()
    retrieval_result = retrieval_service.retrieve_provider_context(
        request=RetrieveProviderContextInput(
            provider=args.provider,
            resource_type=args.resource_type,
            query=args.query,
            category=args.category,
            top_k=args.top_k,
            max_age_days=args.max_age_days,
        ),
    )
    retrieval_latency_ms = (perf_counter() - retrieval_start) * 1000

    slo = evaluate_slos(
        retrieval_latency_ms=retrieval_latency_ms,
        recommendation_latency_ms=recommendation_latency_ms,
        thresholds=SLOThresholds(),
    )

    report = {
        "analysis_summary": analysis_summary,
        "e2e_actionable_recommendation": rendered.used_retrieval or rendered.fallback_note is not None,
        "retrieval_used": rendered.used_retrieval,
        "retrieval_candidates": retrieval_result.metadata.total_candidates,
        "retrieval_returned": len(retrieval_result.chunks),
        "retrieval_latency_ms": round(retrieval_latency_ms, 2),
        "recommendation_latency_ms": round(recommendation_latency_ms, 2),
        "slo_passed": slo.passed,
        "slo_violations": slo.violations,
        "stale_safeguard_passed": stale_guard_passed,
        "source_citation_count": source_count,
    }

    output_path = Path(args.output_json)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report, indent=2), encoding="utf-8")

    print("E2E validation summary")
    print(f"retrieval_used={report['retrieval_used']}")
    print(f"retrieval_candidates={report['retrieval_candidates']}")
    print(f"retrieval_returned={report['retrieval_returned']}")
    print(f"retrieval_latency_ms={report['retrieval_latency_ms']}")
    print(f"recommendation_latency_ms={report['recommendation_latency_ms']}")
    print(f"slo_passed={report['slo_passed']}")
    print(f"stale_safeguard_passed={report['stale_safeguard_passed']}")
    print(f"output_json={output_path}")


if __name__ == "__main__":
    main()
