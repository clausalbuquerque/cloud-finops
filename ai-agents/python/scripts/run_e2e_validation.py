#!/usr/bin/env python3
"""Run comprehensive End-to-End validation scenarios for the Cloud FinOps AI platform.

Executes:
- Scenario 1: Compute cost spike root-cause investigation & attribution.
- Scenario 2: Underused VM rightsizing with SRE safety validation and HITL approval/execution.
- Scenario 3: Multi-tool end-of-month spend forecast & commitment discount coverage.
"""

from __future__ import annotations

import argparse
from dataclasses import asdict
import json
import os
from pathlib import Path
import sys

from finops_ai.embedding import EmbeddingService, EmbeddingServiceConfig
from finops_ai.memory import AgentMemoryRepository
from finops_ai.operations import E2EScenarioRunner, SLOThresholds
from finops_ai.retrieval import (
    ProviderContextRetrievalService,
    RetrievalRepository,
    RetrievalServiceConfig,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run complete FinOps multi-agent E2E validation scenarios.")
    parser.add_argument("--output-json", default="docs/e2e-validation-report.json")
    parser.add_argument("--scenario", choices=["all", "1", "2", "3"], default="all")
    return parser.parse_args()


def main() -> int:
    args = parse_args()

    db_url = os.getenv("DATABASE_URL")
    memory_repo = None
    retrieval_service = None

    if db_url:
        try:
            repo = AgentMemoryRepository.from_url(db_url)
            # Test connection
            repo.get_interaction_memory(limit=1)
            memory_repo = repo
            retrieval_service = ProviderContextRetrievalService(
                repository=RetrievalRepository.from_url(db_url),
                embedding_service=EmbeddingService(config=EmbeddingServiceConfig.from_env()),
                config=RetrievalServiceConfig(),
            )
            print("Connected to PostgreSQL live memory and knowledge base.")
        except Exception as e:
            print(f"Notice: PostgreSQL connection unavailable ({type(e).__name__}). Using deterministic fixtures.")
            memory_repo = None
            retrieval_service = None


    runner = E2EScenarioRunner(
        memory_repo=memory_repo,
        retrieval_service=retrieval_service,
    )

    print("\n" + "=" * 75)
    print(" 🚀 RUNNING CLOUD FINOPS MULTI-AGENT E2E SCENARIO VALIDATION")
    print("=" * 75)

    report = runner.run_all(
        thresholds=SLOThresholds(
            max_retrieval_latency_ms=1500.0,
            max_recommendation_latency_ms=3000.0,
        )
    )

    # Output details
    for sc in report.scenarios:
        status_symbol = "✅" if sc["passed"] else "❌"
        print(f"\n[{sc['scenario_id'].upper()}] {sc['name']}: {status_symbol} ({sc['latency_ms']:.2f}ms)")
        print(f" -> Summary: {sc['summary']}")
        for check, val in sc["verifications"].items():
            check_sym = "✓" if val else "✗"
            print(f"    {check_sym} {check}: {val}")

    print("\n" + "=" * 75)
    print(" 📊 E2E SCENARIO EXECUTION SUMMARY")
    print("=" * 75)
    print(f" -> Total Scenarios: {report.total_scenarios}")
    print(f" -> Passed: {report.passed_scenarios}")
    print(f" -> Failed: {report.failed_scenarios}")
    print(f" -> SLO Status: {'PASSED' if report.slo_evaluation['passed'] else 'FAILED'}")
    print(f" -> Average Flow Latency: {report.slo_evaluation['average_flow_latency_ms']}ms")

    output_path = Path(args.output_json)
    if not output_path.is_absolute():
        # Relative to ai-agents/python
        base_dir = Path(__file__).resolve().parent.parent
        output_path = base_dir / args.output_json

    output_path.parent.mkdir(parents=True, exist_ok=True)
    report_dict = asdict(report)
    output_path.write_text(json.dumps(report_dict, indent=2), encoding="utf-8")
    print(f"\n 📝 Detailed validation report saved to: {output_path}")

    if report.all_passed and report.slo_evaluation["passed"]:
        print("\n ✅ ALL E2E SCENARIOS & SLO CHECKS PASSED (100% SUCCESS RATE)")
        print("=" * 75 + "\n")
        return 0
    else:
        print("\n ❌ E2E SCENARIO VALIDATION ENCOUNTERED FAILURES")
        print("=" * 75 + "\n")
        return 1


if __name__ == "__main__":
    sys.exit(main())
