"""Minimal CrewAI Flow that validates the Gemini/Vertex runtime end to end.

Runs a single ``@start`` -> tool -> ``@listen`` cycle: the start step calls a
stub health-check tool, then makes a live Gemini call via ``build_llm``, and the
listener reports the result. This exercises the whole skeleton (Flow control,
tool invocation, LLM factory, auth) with an auditable ``trace_id``.

Run it with::

    uv run --python .venv/bin/python python scripts/run_hello_flow.py
"""

from __future__ import annotations

from uuid import uuid4

from crewai.flow.flow import Flow, listen, start
from crewai.tools import tool

from finops_ai.llm import build_llm

HEALTH_TOKEN = "FINOPS_OK"


@tool("health_probe")
def health_probe() -> str:
    """Return a deterministic health token (stands in for a real typed tool)."""
    return HEALTH_TOKEN


class HelloFlow(Flow):
    """Smoke-test flow: tool observation -> Gemini call -> report."""

    @start()
    def probe(self) -> str:
        trace_id = str(uuid4())
        self.state["trace_id"] = trace_id
        observation = health_probe.run()
        print(f"[{trace_id}] tool health_probe -> {observation}")
        return observation

    @listen(probe)
    def ask_gemini(self, observation: str) -> str:
        trace_id = self.state.get("trace_id", "-")
        llm = build_llm("flash")
        prompt = (
            "You are a deployment health check for a FinOps agent system. "
            f"The internal probe returned '{observation}'. "
            f"Reply with exactly this token and nothing else: {HEALTH_TOKEN}"
        )
        reply = llm.call(prompt)
        print(f"[{trace_id}] gemini({llm.model}) -> {reply!r}")
        return reply
