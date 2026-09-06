from __future__ import annotations

import unittest
from unittest.mock import MagicMock

from finops_ai.memory.contracts import AgentInteractionMemory
from finops_ai.orchestration.memory_manager import (
    ConversationalContextResolver,
    TraceCompressor,
)


class TestMemoryManager(unittest.TestCase):
    def test_conversational_context_resolver_pronoun_resolution(self) -> None:
        mock_repo = MagicMock()
        resolver = ConversationalContextResolver(memory_repo=mock_repo)

        mock_memory = AgentInteractionMemory(
            id="mem-1",
            session_id="session-123",
            user_id="u1",
            agent_type="orchestration_flow",
            interaction_summary="Investigated analytics-worker-02",
            scope_context={
                "team_scope": "data-platform",
                "last_resource_id": "projects/p1/zones/z1/instances/analytics-worker-02",
            },
        )
        mock_repo.get_interaction_memory.return_value = [mock_memory]

        # Multi-turn query referring to "that VM"
        query = "How much did that VM cost last week?"
        resolved_query, context = resolver.resolve_context(
            query=query,
            session_id="session-123",
        )

        self.assertIn("projects/p1/zones/z1/instances/analytics-worker-02", resolved_query)
        self.assertEqual(context.get("inferred_team_scope"), "data-platform")

    def test_trace_compressor_entity_preservation(self) -> None:
        raw_observations = [
            {
                "tool_name": "query_cost_by_service",
                "total_spend": 284.50,
                "services": [
                    {"service_category": "Compute", "total_cost": 284.50, "provider": "Google"}
                ],
            },
            {
                "tool_name": "get_utilization_summaries",
                "avg_utilization": 8.5,
                "p95_utilization": 14.0,
            },
        ]

        compressed = TraceCompressor.compress_observations(raw_observations)
        self.assertIn("query_cost_by_service", compressed)
        self.assertIn("total_spend=284.5", compressed)
        self.assertIn("avg_utilization=8.5", compressed)
        self.assertIn("p95_utilization=14.0", compressed)

