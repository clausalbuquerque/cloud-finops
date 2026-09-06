from __future__ import annotations

import unittest
from unittest.mock import MagicMock

from crewai import LLM

from finops_ai.judges import (
    EvaluatorOptimizer,
    FinOpsJudgeEvaluator,
    JudgeVerdict,
    SREJudgeEvaluator,
    create_finops_judge_agent,
    create_sre_judge_agent,
)
from finops_ai.prompts.judge_prompts import FINOPS_JUDGE_ROLE, SRE_JUDGE_ROLE


class TestJudges(unittest.TestCase):
    def setUp(self) -> None:
        self.finops_evaluator = FinOpsJudgeEvaluator()
        self.sre_evaluator = SREJudgeEvaluator()

    def test_create_judge_agents(self) -> None:
        test_llm = LLM(model="gemini/gemini-2.5-pro", api_key="test-api-key")

        finops_judge = create_finops_judge_agent(llm=test_llm, verbose=False)
        self.assertEqual(finops_judge.role, FINOPS_JUDGE_ROLE)
        self.assertFalse(finops_judge.allow_delegation)

        sre_judge = create_sre_judge_agent(llm=test_llm, verbose=False)
        self.assertEqual(sre_judge.role, SRE_JUDGE_ROLE)
        self.assertFalse(sre_judge.allow_delegation)

    def test_finops_judge_catches_hallucinated_dollar_figures(self) -> None:
        # Agent cites $950.00 which does not appear in tool observations
        agent_output = (
            "Based on the analysis, analytics-worker-01 cost $950.00 last month. "
            "Downsizing will save $475.00 per month."
        )
        tool_observations = [
            {
                "tool_name": "query_cost_by_service",
                "total_spend": 142.25,
                "services": [{"service_category": "Compute", "total_cost": 142.25}],
            }
        ]

        report = self.finops_evaluator.evaluate(
            agent_output=agent_output,
            tool_observations=tool_observations,
            team_scope="data-platform",
        )

        self.assertTrue(report.hallucination_detected)
        self.assertEqual(report.verdict, JudgeVerdict.REVISE)
        self.assertLess(report.overall_score, 75)
        self.assertGreater(len(report.unverified_claims), 0)

    def test_finops_judge_catches_missing_memory_check(self) -> None:
        # Agent proposes a recommendation without checking get_optimization_history
        agent_output = (
            "We propose rightsizing analytics-worker-02 from n2-standard-16 to n2-standard-8, "
            "saving $142.25 per month."
        )
        tool_observations = [
            {
                "tool_name": "query_cost_trend",
                "total_period_cost": 284.50,
            }
        ]

        report = self.finops_evaluator.evaluate(
            agent_output=agent_output,
            tool_observations=tool_observations,
        )

        self.assertEqual(report.verdict, JudgeVerdict.REVISE)
        memory_dim = next(d for d in report.dimension_scores if d.name == "memory_compliance")
        self.assertEqual(memory_dim.score, 40)
        self.assertTrue(any("get_optimization_history" in step for step in report.actionable_improvements))

    def test_finops_judge_approves_grounded_response(self) -> None:
        agent_output = (
            "Verified team data-platform spend. The cost of analytics-worker-02 is $284.50. "
            "Confirmed with get_optimization_history that no previous rejections exist. "
            "Proposing rightsize to n2-standard-8 with estimated savings of $142.25."
        )
        tool_observations = [
            {
                "tool_name": "query_cost_trend",
                "total_period_cost": 284.50,
            },
            {
                "tool_name": "get_optimization_history",
                "history": [],
                "recommendation_type": "rightsize",
            },
            {
                "tool_name": "propose_recommendation",
                "estimated_monthly_savings": 142.25,
            },
        ]

        report = self.finops_evaluator.evaluate(
            agent_output=agent_output,
            tool_observations=tool_observations,
            team_scope="data-platform",
        )

        self.assertEqual(report.verdict, JudgeVerdict.PASS)
        self.assertFalse(report.hallucination_detected)
        self.assertGreaterEqual(report.overall_score, 85)
        self.assertTrue(report.is_passing())

    def test_sre_judge_catches_unverified_batch_workload(self) -> None:
        agent_output = (
            "Resource batch-worker-01 shows average CPU of 9.0%. "
            "Recommend rightsizing immediately."
        )
        tool_observations = [
            {"tool_name": "get_utilization_summaries", "avg_utilization": 9.0}
        ]

        report = self.sre_evaluator.evaluate(
            agent_output=agent_output,
            tool_observations=tool_observations,
            resource_id="projects/p1/zones/z1/instances/batch-worker-01",
        )

        self.assertEqual(report.verdict, JudgeVerdict.REVISE)
        baseline_dim = next(d for d in report.dimension_scores if d.name == "workload_baseline_awareness")
        self.assertEqual(baseline_dim.score, 40)
        self.assertTrue(any("get_infrastructure_baselines" in step for step in report.actionable_improvements))

    def test_sre_judge_approves_safe_assessment(self) -> None:
        agent_output = (
            "Assessment for analytics-worker-02: Peak P95 CPU is 22%, memory is 18%. "
            "Downsizing to n2-standard-8 provides 44% projected peak CPU, leaving a 56% safe operational headroom buffer. "
            "Checked get_infrastructure_baselines and confirmed no batch workload conflicts."
        )
        tool_observations = [
            {"tool_name": "get_utilization_summaries", "p95_utilization": 22.0},
            {"tool_name": "get_infrastructure_baselines", "expected_pattern": {}},
        ]

        report = self.sre_evaluator.evaluate(
            agent_output=agent_output,
            tool_observations=tool_observations,
            resource_id="projects/p1/zones/z1/instances/analytics-worker-02",
        )

        self.assertEqual(report.verdict, JudgeVerdict.PASS)
        self.assertGreaterEqual(report.overall_score, 85)

    def test_evaluator_optimizer_reflection_loop(self) -> None:
        optimizer = EvaluatorOptimizer(max_iterations=2, min_passing_score=85)
        mock_agent = MagicMock()

        # Step 1 fails (missing memory check), Step 2 passes (critique applied)
        call_count = 0

        def mock_executor(prompt: str) -> tuple[str, list[dict]]:
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return (
                    "Propose rightsize of analytics-worker-02 saving $142.25.",
                    [{"tool_name": "cost_trend", "cost": 142.25}],
                )
            else:
                return (
                    "Checked get_optimization_history. Verified team data-platform spend. "
                    "Propose rightsize of analytics-worker-02 saving $142.25.",
                    [
                        {"tool_name": "cost_trend", "cost": 142.25},
                        {"tool_name": "get_optimization_history", "recommendation_type": "rightsize"},
                    ],
                )

        result = optimizer.run_with_finops_judge(
            agent=mock_agent,
            base_prompt="Analyze analytics-worker-02 for data-platform",
            expected_output="Grounded recommendation",
            team_scope="data-platform",
            mock_executor=mock_executor,
        )

        self.assertTrue(result.is_approved)
        self.assertEqual(result.iterations_run, 2)
        self.assertEqual(len(result.evaluation_history), 2)
        self.assertFalse(result.needs_human_escalation)
        self.assertEqual(result.latest_report.verdict, JudgeVerdict.PASS)

    def test_evaluator_optimizer_escalates_on_repeated_failure(self) -> None:
        optimizer = EvaluatorOptimizer(max_iterations=2, min_passing_score=85)
        mock_agent = MagicMock()

        # Stubbornly produces hallucinated output on every iteration
        def mock_failing_executor(prompt: str) -> tuple[str, list[dict]]:
            return (
                "Invented cost is $9999.00 without tool observation.",
                [],
            )

        result = optimizer.run_with_finops_judge(
            agent=mock_agent,
            base_prompt="Analyze unverified cost",
            expected_output="Grounded report",
            mock_executor=mock_failing_executor,
        )

        self.assertFalse(result.is_approved)
        self.assertEqual(result.iterations_run, 2)
        self.assertTrue(result.needs_human_escalation)
        self.assertEqual(result.latest_report.verdict, JudgeVerdict.REVISE)

