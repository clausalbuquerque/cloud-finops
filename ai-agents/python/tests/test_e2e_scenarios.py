from __future__ import annotations

import unittest
from unittest.mock import MagicMock

from finops_ai.operations.e2e_scenarios import E2EScenarioRunner
from finops_ai.operations.e2e_validation import SLOThresholds


class TestE2EScenarios(unittest.TestCase):
    def setUp(self) -> None:
        self.mock_memory = MagicMock()
        self.mock_memory.get_interaction_memory.return_value = []
        self.mock_memory.get_optimization_history.return_value = []
        self.runner = E2EScenarioRunner(memory_repo=self.mock_memory)

    def test_scenario_1_cost_spike_attribution(self) -> None:
        """Scenario 1: Compute cost spike root-cause investigation & attribution."""
        res = self.runner.run_scenario_1_cost_spike()
        self.assertTrue(res.passed, f"Scenario 1 failed with verifications: {res.verifications}")
        self.assertEqual(res.scenario_id, "scenario_1")
        self.assertTrue(res.verifications["resource_attributed"])
        self.assertTrue(res.verifications["spike_identified"])
        self.assertLess(res.latency_ms, 5000.0)

    def test_scenario_2_rightsizing_hitl(self) -> None:
        """Scenario 2: Underused VM rightsizing with SRE safety validation and HITL approval/execution."""
        res = self.runner.run_scenario_2_rightsizing_hitl()
        self.assertTrue(res.passed, f"Scenario 2 failed with verifications: {res.verifications}")
        self.assertEqual(res.scenario_id, "scenario_2")
        self.assertTrue(res.verifications["sre_headroom_validated"])
        self.assertTrue(res.verifications["rag_cli_rendered"])
        self.assertTrue(res.verifications["hitl_approved"])
        self.assertTrue(res.verifications["hitl_executed"])
        self.assertTrue(res.verifications["rollback_plan_generated"])

    def test_scenario_3_team_forecast(self) -> None:
        """Scenario 3: Multi-tool end-of-month spend forecast & commitment discount coverage."""
        res = self.runner.run_scenario_3_team_forecast()
        self.assertTrue(res.passed, f"Scenario 3 failed with verifications: {res.verifications}")
        self.assertEqual(res.scenario_id, "scenario_3")
        self.assertTrue(res.verifications["forecast_projected"])
        self.assertTrue(res.verifications["commitment_coverage_analyzed"])
        self.assertTrue(res.verifications["budget_margin_evaluated"])

    def test_run_all_and_slo_compliance(self) -> None:
        """Verify full runner executes all scenarios and meets latency SLO budgets."""
        report = self.runner.run_all(
            thresholds=SLOThresholds(
                max_retrieval_latency_ms=1500.0,
                max_recommendation_latency_ms=3000.0,
            )
        )
        self.assertTrue(report.all_passed)
        self.assertEqual(report.total_scenarios, 3)
        self.assertEqual(report.passed_scenarios, 3)
        self.assertEqual(report.failed_scenarios, 0)
        self.assertTrue(report.slo_evaluation["passed"])
        self.assertLess(report.slo_evaluation["average_flow_latency_ms"], 3000.0)

