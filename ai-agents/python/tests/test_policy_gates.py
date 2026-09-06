from __future__ import annotations

import unittest
from unittest.mock import MagicMock

from finops_ai.judges.contracts import JudgeEvaluationReport, JudgeVerdict
from finops_ai.memory.contracts import OptimizationRecommendation, RecommendationStatus
from finops_ai.orchestration.contracts import FinOpsOrchestrationState
from finops_ai.orchestration.policy_gates import PolicyGateEngine


class TestPolicyGates(unittest.TestCase):
    def setUp(self) -> None:
        self.mock_repo = MagicMock()
        self.engine = PolicyGateEngine(memory_repo=self.mock_repo)

    def test_data_freshness_gate(self) -> None:
        fresh_state = FinOpsOrchestrationState(finops_output="Recent 30-day spend is $500.")
        res = self.engine.check_data_freshness(fresh_state)
        self.assertTrue(res.passed)

        stale_state = FinOpsOrchestrationState(finops_output="Using stale data from 6 months ago.")
        stale_res = self.engine.check_data_freshness(stale_state)
        self.assertFalse(stale_res.passed)
        self.assertTrue(stale_res.fail_closed)

    def test_confidence_threshold_gate(self) -> None:
        # High confidence passes
        passing_report = JudgeEvaluationReport(
            judge_role="FinOps Judge",
            evaluated_agent="FinOps Specialist",
            overall_score=88,
            verdict=JudgeVerdict.PASS,
            critique_summary="Excellent",
        )
        state_pass = FinOpsOrchestrationState(finops_report=passing_report)
        res_pass = self.engine.check_confidence_threshold(state_pass)
        self.assertTrue(res_pass.passed)

        # Low confidence (< 70%) fails closed
        low_report = JudgeEvaluationReport(
            judge_role="FinOps Judge",
            evaluated_agent="FinOps Specialist",
            overall_score=62,
            verdict=JudgeVerdict.REVISE,
            critique_summary="Low confidence",
        )
        state_fail = FinOpsOrchestrationState(finops_report=low_report)
        res_fail = self.engine.check_confidence_threshold(state_fail)
        self.assertFalse(res_fail.passed)
        self.assertTrue(res_fail.fail_closed)

    def test_prior_rejections_gate(self) -> None:
        target_res = "projects/p1/zones/z1/instances/analytics-worker-02"
        mock_rec = OptimizationRecommendation(
            id="rec-001",
            resource_id=target_res,
            resource_type="compute/instance",
            recommendation_type="rightsize",
            current_state={},
            proposed_state={},
            estimated_monthly_savings=142.25,
            confidence_score=0.9,
            status=RecommendationStatus.REJECTED,
            rejection_reason="Batch peaks unpredictably",
        )

        # 1. Has prior rejection
        self.mock_repo.get_optimization_history.return_value = [mock_rec]
        state = FinOpsOrchestrationState(target_resource_ids=[target_res])
        res = self.engine.check_prior_rejections(state)
        self.assertFalse(res.passed)
        self.assertIn("previously rejected", res.reason)

        # 2. No prior rejection
        self.mock_repo.get_optimization_history.return_value = []
        res_clean = self.engine.check_prior_rejections(state)
        self.assertTrue(res_clean.passed)

    def test_dependency_safety_gate(self) -> None:
        safe_state = FinOpsOrchestrationState(sre_output="Risk level: LOW. Dependencies safe.")
        self.assertTrue(self.engine.check_dependency_safety(safe_state).passed)

        unsafe_state = FinOpsOrchestrationState(sre_output="Risk_level: HIGH. Critical dependency on shared DB.")
        self.assertFalse(self.engine.check_dependency_safety(unsafe_state).passed)

    def test_fail_closed_default_gate(self) -> None:
        clean_state = FinOpsOrchestrationState(finops_output="Analysis completed successfully.")
        self.assertTrue(self.engine.check_fail_closed_default(clean_state).passed)

        ambiguous_state = FinOpsOrchestrationState(finops_output="Unknown error during pipeline run.")
        self.assertFalse(self.engine.check_fail_closed_default(ambiguous_state).passed)

