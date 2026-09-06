"""CLI tool to execute the FinOps Policy-Gated Orchestration Flow.

Usage:
    uv run --python .venv/bin/python python scripts/run_finops_flow.py [--query "..."] [--team-scope "..."]
    uv run --python .venv/bin/python python scripts/run_finops_flow.py --scheduled-digest
"""

from __future__ import annotations

import argparse
import sys

from finops_ai.llm import _load_env
from finops_ai.orchestration import FinOpsFlow, TriggerType


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the FinOps Policy-Gated Orchestration Flow")
    parser.add_argument(
        "--query",
        type=str,
        default="Investigate high cost anomalies in team data-platform and evaluate rightsizing for analytics-worker-02.",
        help="Investigation prompt or question for the Flow",
    )
    parser.add_argument(
        "--team-scope",
        type=str,
        default="data-platform",
        help="Team scope for RBAC filtering",
    )
    parser.add_argument(
        "--scheduled-digest",
        action="store_true",
        help="Run as a scheduled daily cost & anomaly digest trigger",
    )
    return parser.parse_args()


def main() -> int:
    _load_env()
    args = parse_args()

    trigger_type = TriggerType.SCHEDULED_DIGEST if args.scheduled_digest else TriggerType.INTERACTIVE
    query = (
        "Run daily FinOps digest: identify top cost drivers, check recent anomalies, and propose safe optimizations."
        if args.scheduled_digest
        else args.query
    )

    print(f"\n=======================================================")
    print(f"🚀 Launching FinOps Policy-Gated Flow ({trigger_type.value})")
    print(f"Query: {query}")
    print(f"Team Scope: {args.team_scope}")
    print(f"=======================================================\n")

    flow = FinOpsFlow()
    result = flow.execute_flow(
        query=query,
        team_scope=args.team_scope,
        trigger_type=trigger_type,
    )

    print("\n--- Flow Execution Result ---")
    print(f"Session ID: {result.session_id}")
    print(f"Trace ID:   {result.trace_id}")
    print(f"Status:     {result.status.value}")
    print(f"Policy Passed: {result.policy_passed}")
    if result.policy_violations:
        print(f"Violations: {result.policy_violations}")
    if result.finops_score:
        print(f"FinOps Judge Score: {result.finops_score}/100")
    if result.sre_score:
        print(f"SRE Judge Score:    {result.sre_score}/100")

    print(f"\n--- Final Response ---\n{result.final_response}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

