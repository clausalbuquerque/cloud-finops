#!/usr/bin/env python3
"""Interactive Multi-Turn Conversational Console for Cloud FinOps Agents.

Allows real-time interactive pair-programming / chatting with the multi-agent system:
- FinOps Specialist Agent (Cost intelligence, FOCUS data, Spend Forecasting, Anomalies)
- SRE Specialist Agent (Resource utilization, CPU/Memory headroom, Workload baselines)
- Domain Judge Evaluators (4-dimension evaluation & reflection loop)
- Policy Gates (Data freshness, confidence >= 70%, prior rejection check, dependency safety, fail-closed)
- RAG Recommendation Renderer (Provider-specific CLI and rollback plans)
- Human-in-the-Loop Approval (Inline approval/rejection of proposed write actions)
"""

from __future__ import annotations

import os
import sys
from uuid import uuid4

from finops_ai.hitl import ApprovalEngine
from finops_ai.llm import _load_env
from finops_ai.memory import AgentMemoryRepository
from finops_ai.orchestration import FinOpsFlow, TriggerType


def print_banner() -> None:
    print("\n" + "=" * 78)
    print(" 🤖 CLOUD FINOPS & SRE MULTI-AGENT CONVERSATIONAL CONSOLE")
    print("=" * 78)
    print(" Commands:")
    print("   /team <name>     Switch active team scope (default: data-platform)")
    print("   /history         View current session memory & recommendations")
    print("   /clear           Start a new session")
    print("   /exit or /quit   Exit the console")
    print("=" * 78 + "\n")


def main() -> int:
    _load_env()

    db_url = os.getenv("DATABASE_URL") or "postgresql+psycopg://postgres:postgres123@localhost:5433/cloud_finops"
    memory_repo = None
    if db_url:
        try:
            repo = AgentMemoryRepository.from_url(db_url)
            repo.get_interaction_memory(limit=1)
            memory_repo = repo
        except Exception:
            memory_repo = None

    flow = FinOpsFlow(memory_repo=memory_repo)
    session_id = str(uuid4())
    team_scope = "data-platform"

    print_banner()
    print(f"🔹 Session Initialized: {session_id[:8]}...")
    print(f"🔹 Active Team Scope:   {team_scope}")
    if memory_repo:
        print("🔹 PostgreSQL Memory:   CONNECTED (localhost:5433)")
    else:
        print("🔹 PostgreSQL Memory:   IN-MEMORY / STANDALONE")
    print("\nAsk any FinOps or SRE question (e.g. 'What are our top cost drivers?').\n")

    while True:
        try:
            user_input = input(f"[{team_scope}] 👤 You: ").strip()
        except (KeyboardInterrupt, EOFError):
            print("\nExiting console. Goodbye!")
            break

        if not user_input:
            continue

        if user_input.lower() in ("/exit", "/quit", "exit", "quit"):
            print("\nExiting console. Goodbye!")
            break

        if user_input.startswith("/team"):
            parts = user_input.split(maxsplit=1)
            if len(parts) > 1 and parts[1].strip():
                team_scope = parts[1].strip()
                print(f" -> Switched team scope to: {team_scope}\n")
            else:
                print(f" -> Current team scope: {team_scope}\n")
            continue

        if user_input == "/clear":
            session_id = str(uuid4())
            print(f" -> Started new session: {session_id[:8]}...\n")
            continue

        if user_input == "/history":
            if memory_repo:
                try:
                    recs = memory_repo.get_optimization_history(limit=5)
                    print(f"\n--- Recent Optimization History ({len(recs)} records) ---")
                    for r in recs:
                        status_str = r.status if isinstance(r.status, str) else r.status.value
                        print(f" • [{status_str.upper()}] {r.resource_id} ({r.recommendation_type}): ${r.estimated_monthly_savings:.2f}/mo")
                    print()
                except Exception as e:
                    print(f"Error fetching history: {e}\n")
            else:
                print(" -> Long-term memory repository is currently in-memory for this session.\n")
            continue

        print("\nThinking and querying multi-agent system...\n")
        try:
            result = flow.execute_flow(
                query=user_input,
                session_id=session_id,
                team_scope=team_scope,
                trigger_type=TriggerType.INTERACTIVE,
            )

            print("=" * 78)
            print(" 🤖 AGENT RESPONSE")
            print("=" * 78)
            print(result.final_response)
            print("\n" + "-" * 78)
            status_symbol = "✅ PASSED" if result.policy_passed else f"⚠️ POLICY VIOLATION ({result.status.value})"
            print(f" 📊 Policy Gate: {status_symbol} | Trace ID: {result.trace_id[:8]}...")
            if result.finops_score:
                print(f" 🎯 FinOps Judge Score: {result.finops_score}/100 | SRE Judge Score: {result.sre_score or 'N/A'}/100")
            print("=" * 78 + "\n")

        except Exception as e:
            print(f"❌ Error during execution: {e}\n")

    return 0


if __name__ == "__main__":
    sys.exit(main())

