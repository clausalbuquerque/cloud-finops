"""CLI tool to execute a FinOps investigation task with the FinOps Agent.

Usage:
    uv run --python .venv/bin/python python scripts/run_finops_agent.py [--query "..."]
"""

from __future__ import annotations

import argparse
import sys

from crewai import Crew, Task

from finops_ai.agents import create_finops_agent
from finops_ai.llm import _load_env, build_llm


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run an investigation task with the FinOps Agent")
    parser.add_argument(
        "--query",
        type=str,
        default="Investigate recent high and critical cost anomalies in the 'data-platform' team and propose optimization actions.",
        help="Investigation prompt or question for the FinOps Agent",
    )
    return parser.parse_args()


def main() -> int:
    _load_env()
    args = parse_args()

    print("Initializing FinOps Specialist Agent with Gemini LLM...")
    llm = build_llm(model="gemini-2.5-pro", temperature=0.1)
    agent = create_finops_agent(llm=llm, verbose=True)

    task = Task(
        description=f"FinOps Analysis Task: {args.query}\n\n"
        "Guidelines:\n"
        "1. Check anomalies using get_anomalies.\n"
        "2. Query cost trends and service breakdowns.\n"
        "3. Check optimization history using get_optimization_history before proposing anything.\n"
        "4. If rightsizing is warranted, propose recommendation or delegate to SRE.\n",
        expected_output="A structured FinOps report identifying cost drivers, root cause analysis of anomalies, and concrete optimization candidates.",
        agent=agent,
    )

    crew = Crew(
        agents=[agent],
        tasks=[task],
        verbose=True,
    )

    print(f"\nExecuting query: {args.query}\n")
    result = crew.kickoff()

    print("\n--- Final Agent Output ---")
    print(result)
    return 0


if __name__ == "__main__":
    sys.exit(main())

