"""CLI tool to execute an infrastructure safety assessment with the SRE Agent.

Usage:
    uv run --python .venv/bin/python python scripts/run_sre_agent.py [--query "..."]
"""

from __future__ import annotations

import argparse
import sys

from crewai import Crew, Task

from finops_ai.agents import create_sre_agent
from finops_ai.llm import _load_env, build_llm


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run an SRE infrastructure assessment task")
    parser.add_argument(
        "--query",
        type=str,
        default=(
            "Evaluate rightsizing feasibility and operational headroom for 'analytics-worker-02' and 'batch-worker-01'. "
            "Check utilization summaries and infrastructure baselines."
        ),
        help="Investigation prompt or question for the SRE Agent",
    )
    return parser.parse_args()


def main() -> int:
    _load_env()
    args = parse_args()

    print("Initializing SRE Specialist Agent with Gemini LLM (Flash tier)...")
    llm = build_llm(tier="flash", temperature=0.1)
    agent = create_sre_agent(llm=llm, verbose=True)

    task = Task(
        description=f"SRE Infrastructure Safety Task: {args.query}\n\n"
        "Guidelines:\n"
        "1. Check tracked resource capacity metadata using get_tracked_resources.\n"
        "2. Query utilization statistics and P95 peaks using get_utilization_summaries.\n"
        "3. Check for existing workload baselines using get_infrastructure_baselines (suppress false positives on batch jobs).\n"
        "4. Check dependency risks using query_resource_dependencies.\n"
        "5. Output a structured safety verdict with projected headroom.\n",
        expected_output="A structured SRE assessment detailing peak utilization, headroom calculation, dependency risks, and safe-to-modify verdict.",
        agent=agent,
    )

    crew = Crew(
        agents=[agent],
        tasks=[task],
        verbose=True,
    )

    print(f"\nExecuting SRE assessment query: {args.query}\n")
    result = crew.kickoff()

    print("\n--- Final SRE Agent Output ---")
    print(result)
    return 0


if __name__ == "__main__":
    sys.exit(main())

