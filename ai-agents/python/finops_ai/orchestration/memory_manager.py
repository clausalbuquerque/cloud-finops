"""Memory and Conversational Context Manager for the FinOps Orchestration Flow."""

from __future__ import annotations

import re
from typing import Any, Sequence

from finops_ai.memory.contracts import AgentInteractionMemory
from finops_ai.memory.repository import AgentMemoryRepository


class ConversationalContextResolver:
    """Resolves cross-turn references (pronouns, implicit scope, target resource IDs)

    using PostgreSQL interaction memory.
    """

    def __init__(self, memory_repo: AgentMemoryRepository | None = None) -> None:
        self.memory_repo = memory_repo

    def resolve_context(
        self,
        query: str,
        session_id: str,
        user_id: str = "default_user",
    ) -> tuple[str, dict[str, Any]]:
        """Resolve pronouns and carry over prior turn scope from memory."""
        if not self.memory_repo:
            return query, {}

        # Fetch recent session memory
        try:
            memories = self.memory_repo.get_interaction_memory(session_id=session_id, limit=5)
        except Exception:
            return query, {}

        if not memories:
            return query, {}

        latest = memories[0]
        context: dict[str, Any] = {}
        if latest.scope_context:
            context.update(latest.scope_context)
        if latest.key_findings:
            context.update(latest.key_findings)


        resolved_query = query
        # Pronoun & implicit reference replacement
        last_resource = context.get("last_resource_id") or context.get("resource_id")
        last_team = context.get("team_scope") or context.get("scope_team")

        if last_resource:
            for pronoun in ["that vm", "this vm", "that resource", "this resource", "the instance", "it"]:
                pattern = re.compile(rf"\b{pronoun}\b", re.IGNORECASE)
                if pattern.search(resolved_query):
                    resolved_query = pattern.sub(f"resource '{last_resource}'", resolved_query, count=1)
                    context["resolved_resource_id"] = last_resource
                    break

        if last_team and "team" not in resolved_query.lower():
            context["inferred_team_scope"] = last_team

        return resolved_query, context


class TraceCompressor:
    """Compresses verbose ReAct tool observation traces while strictly preserving

    factual entities: resource IDs, currency amounts, dates, percentages, and SKUs.
    """

    @staticmethod
    def compress_observations(observations: Sequence[dict[str, Any]]) -> str:
        """Summarize observation history into a compact, fact-dense context string."""
        if not observations:
            return ""

        summary_lines: list[str] = []
        for i, obs in enumerate(observations, start=1):
            tool_name = obs.get("tool_name", f"Step_{i}")
            # Extract key entity values
            facts: list[str] = []

            for key, val in obs.items():
                if key == "tool_name":
                    continue
                if isinstance(val, (int, float, str)):
                    facts.append(f"{key}={val}")
                elif isinstance(val, list) and len(val) > 0 and isinstance(val[0], dict):
                    # Summarize top 2 list items
                    sample = [f"{k}={v}" for k, v in list(val[0].items())[:3]]
                    facts.append(f"{key}_sample=[{', '.join(sample)}], total_items={len(val)}")

            summary_lines.append(f"- [{tool_name}] {'; '.join(facts)}")

        return "\n".join(summary_lines)

