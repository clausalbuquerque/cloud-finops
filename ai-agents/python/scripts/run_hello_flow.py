#!/usr/bin/env python
"""Run the hello-flow smoke test (validates CrewAI + Gemini/Vertex auth).

Usage:
    cd ai-agents/python
    uv run --python .venv/bin/python python scripts/run_hello_flow.py
"""

from __future__ import annotations

import sys

from finops_ai.llm import resolve_model
from finops_ai.orchestration import HelloFlow

HEALTH_TOKEN = "FINOPS_OK"


def main() -> int:
    print(f"Model (flash tier): {resolve_model('flash')}")
    flow = HelloFlow()
    result = flow.kickoff()
    text = str(result or "")
    ok = HEALTH_TOKEN in text
    print("\nFlow result:", repr(result))
    print("Health check:", "PASS ✅" if ok else "FAIL ❌")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
