from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
import unittest
from unittest.mock import MagicMock, patch

from finops_ai.agents.finops_agent import DEFAULT_FINOPS_TOOLS, create_finops_agent
from finops_ai.memory.contracts import (
    AnomalyResolution,
    OptimizationRecommendation,
    RecommendationStatus,
)
from finops_ai.prompts.finops_prompts import (
    FINOPS_AGENT_BACKSTORY,
    FINOPS_AGENT_GOAL,
    FINOPS_AGENT_ROLE,
)
from finops_ai.tools.delegation_tools import delegate_to_sre
from finops_ai.tools.memory_tools import (
    get_optimization_history,
    propose_recommendation,
    store_anomaly_resolution,
)


class TestFinOpsAgent(unittest.TestCase):
    def test_create_finops_agent_structure(self) -> None:
        from crewai import LLM
        test_llm = LLM(model="gemini/gemini-2.5-pro", api_key="test-mock-api-key")
        agent = create_finops_agent(llm=test_llm, verbose=False)

        self.assertEqual(agent.role, FINOPS_AGENT_ROLE)
        self.assertEqual(agent.goal, FINOPS_AGENT_GOAL)
        self.assertEqual(agent.backstory, FINOPS_AGENT_BACKSTORY)
        self.assertEqual(agent.max_iter, 10)
        self.assertFalse(agent.allow_delegation)
        self.assertEqual(len(agent.tools), len(DEFAULT_FINOPS_TOOLS))



    @patch("finops_ai.tools.memory_tools._get_memory_repo")
    def test_get_optimization_history_tool(self, mock_get_repo: MagicMock) -> None:
        mock_repo = MagicMock()
        mock_get_repo.return_value = mock_repo

        mock_rec = OptimizationRecommendation(
            id="rec-001",
            provider_name="Google",
            resource_id="projects/p1/zones/z1/instances/w1",
            resource_type="compute/instance",
            recommendation_type="rightsize",
            current_state={"sku": "n2-standard-16"},
            proposed_state={"sku": "n2-standard-8"},
            estimated_monthly_savings=Decimal("142.25"),
            confidence_score=0.92,
            status=RecommendationStatus.REJECTED,
            rejection_reason="Batch workloads spike unpredictably",
            scope_team="data-platform",
            proposed_at=datetime.now(timezone.utc),
        )
        mock_repo.get_optimization_history.return_value = [mock_rec]

        result = get_optimization_history._run(
            scope="data-platform",
            status="rejected",
        )

        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["id"], "rec-001")
        self.assertEqual(result[0]["status"], "rejected")
        self.assertEqual(result[0]["rejection_reason"], "Batch workloads spike unpredictably")
        self.assertEqual(result[0]["estimated_monthly_savings"], 142.25)

    @patch("finops_ai.tools.memory_tools._get_memory_repo")
    def test_propose_recommendation_tool(self, mock_get_repo: MagicMock) -> None:
        mock_repo = MagicMock()
        mock_get_repo.return_value = mock_repo
        mock_repo.store_recommendation.return_value = "new-rec-uuid"

        result = propose_recommendation._run(
            recommendation_type="rightsize",
            resource_id="projects/p1/zones/z1/instances/w2",
            current_state={"sku": "n2-standard-16", "monthly_cost": 284.50},
            proposed_state={"sku": "n2-standard-8", "estimated_monthly_cost": 142.25},
            estimated_monthly_savings=142.25,
            scope_team="data-platform",
        )

        self.assertEqual(result["status"], "proposed")
        self.assertEqual(result["recommendation_id"], "new-rec-uuid")
        self.assertEqual(result["estimated_monthly_savings"], 142.25)
        mock_repo.store_recommendation.assert_called_once()

    @patch("finops_ai.tools.memory_tools._get_memory_repo")
    def test_store_anomaly_resolution_tool(self, mock_get_repo: MagicMock) -> None:
        mock_repo = MagicMock()
        mock_get_repo.return_value = mock_repo
        mock_repo.store_anomaly_resolution.return_value = "res-uuid"

        result = store_anomaly_resolution._run(
            anomaly_id="anom-001",
            root_cause="Upsized instance during incident investigation was not reverted",
            resolution_action="Rightsize back to n2-standard-8",
        )

        self.assertEqual(result["status"], "recorded")
        self.assertEqual(result["resolution_id"], "res-uuid")
        mock_repo.store_anomaly_resolution.assert_called_once()

    def test_delegate_to_sre_tool(self) -> None:
        result = delegate_to_sre._run(
            resource_ids=["projects/p1/zones/z1/instances/w2"],
            question="Can we safely downsize analytics-worker-02 without risking OOM or latency regressions?",
        )

        self.assertEqual(result["status"], "delegated")
        self.assertEqual(result["target_agent"], "SRE Specialist")
        self.assertEqual(len(result["resource_ids"]), 1)
        self.assertIn("safely downsize", result["question"])
