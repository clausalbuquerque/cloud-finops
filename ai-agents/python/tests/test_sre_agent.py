from __future__ import annotations

import unittest
from unittest.mock import MagicMock

from crewai import LLM

from finops_ai.agents.sre_agent import DEFAULT_SRE_TOOLS, create_sre_agent
from finops_ai.prompts.sre_prompts import (
    SRE_AGENT_BACKSTORY,
    SRE_AGENT_GOAL,
    SRE_AGENT_ROLE,
)
from finops_ai.tools.delegation_tools import delegate_to_finops


class TestSREAgent(unittest.TestCase):
    def test_create_sre_agent_structure(self) -> None:
        test_llm = LLM(model="gemini/gemini-2.5-flash", api_key="test-api-key")
        agent = create_sre_agent(llm=test_llm, verbose=False)

        self.assertEqual(agent.role, SRE_AGENT_ROLE)
        self.assertEqual(agent.goal, SRE_AGENT_GOAL)
        self.assertEqual(agent.backstory, SRE_AGENT_BACKSTORY)
        self.assertEqual(agent.max_iter, 10)
        self.assertFalse(agent.allow_delegation)
        self.assertEqual(len(agent.tools), len(DEFAULT_SRE_TOOLS))

    def test_delegate_to_finops_tool(self) -> None:
        result = delegate_to_finops._run(
            resource_ids=["projects/p1/zones/z1/instances/analytics-worker-02"],
            utilization_summary="CPU avg 8.5%, P95 14%, safe to downsize to n2-standard-8 with 44% projected peak CPU",
            question="What are the estimated monthly cost savings for this rightsizing action?",
        )

        self.assertEqual(result["status"], "delegated")
        self.assertEqual(result["target_agent"], "FinOps Specialist")
        self.assertEqual(len(result["resource_ids"]), 1)
        self.assertIn("estimated monthly cost savings", result["question"])

