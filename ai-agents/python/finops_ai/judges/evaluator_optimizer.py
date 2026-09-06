"""Evaluator-Optimizer reflection controller for agent task execution."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable

from crewai import Agent, Crew, Task

from finops_ai.judges.contracts import JudgeEvaluationReport, JudgeVerdict
from finops_ai.judges.finops_judge import FinOpsJudgeEvaluator
from finops_ai.judges.sre_judge import SREJudgeEvaluator


@dataclass
class EvaluatorOptimizerResult:
    """Final result of an evaluated task execution with audit trail."""

    final_output: str
    is_approved: bool
    iterations_run: int
    latest_report: JudgeEvaluationReport
    evaluation_history: list[JudgeEvaluationReport] = field(default_factory=list)
    needs_human_escalation: bool = False


class EvaluatorOptimizer:
    """Orchestrates the Evaluator-Optimizer reflection loop between specialist agents and domain judges."""

    def __init__(
        self,
        max_iterations: int = 2,
        min_passing_score: int = 85,
    ) -> None:
        self.max_iterations = max_iterations
        self.min_passing_score = min_passing_score
        self.finops_evaluator = FinOpsJudgeEvaluator()
        self.sre_evaluator = SREJudgeEvaluator()

    def run_with_finops_judge(
        self,
        agent: Agent,
        base_prompt: str,
        expected_output: str,
        team_scope: str | None = None,
        mock_executor: Callable[[str], tuple[str, list[dict[str, Any]]]] | None = None,
    ) -> EvaluatorOptimizerResult:
        """Run FinOps task with iterative FinOps Domain Judge evaluation."""
        eval_history: list[JudgeEvaluationReport] = []
        current_prompt = base_prompt
        final_output = ""
        latest_report: JudgeEvaluationReport | None = None

        for iter_num in range(1, self.max_iterations + 1):
            if mock_executor:
                output_text, observations = mock_executor(current_prompt)
            else:
                task = Task(
                    description=current_prompt,
                    expected_output=expected_output,
                    agent=agent,
                )
                crew = Crew(agents=[agent], tasks=[task], verbose=False)
                output_text = str(crew.kickoff())
                observations = []

            final_output = output_text

            # Evaluate with FinOps Judge
            report = self.finops_evaluator.evaluate(
                agent_output=output_text,
                tool_observations=observations,
                task_context=base_prompt,
                team_scope=team_scope,
                iteration=iter_num,
            )
            eval_history.append(report)
            latest_report = report

            if report.is_passing(min_score=self.min_passing_score):
                return EvaluatorOptimizerResult(
                    final_output=final_output,
                    is_approved=True,
                    iterations_run=iter_num,
                    latest_report=report,
                    evaluation_history=eval_history,
                    needs_human_escalation=False,
                )

            # If not passing and have remaining iterations, inject critique into prompt
            if iter_num < self.max_iterations:
                critique_block = (
                    f"\n\n--- PREVIOUS ATTEMPT REVIEW BY FINOPS JUDGE (Score: {report.overall_score}/100) ---\n"
                    f"Critique: {report.critique_summary}\n"
                    f"Actionable Fixes Required:\n"
                    + "\n".join(f"- {step}" for step in report.actionable_improvements)
                    + "\n\nPlease revise your output to resolve these specific deficiencies."
                )
                current_prompt = base_prompt + critique_block

        # Exceeded iterations without passing
        assert latest_report is not None
        return EvaluatorOptimizerResult(
            final_output=final_output,
            is_approved=False,
            iterations_run=self.max_iterations,
            latest_report=latest_report,
            evaluation_history=eval_history,
            needs_human_escalation=True,
        )

    def run_with_sre_judge(
        self,
        agent: Agent,
        base_prompt: str,
        expected_output: str,
        resource_id: str | None = None,
        mock_executor: Callable[[str], tuple[str, list[dict[str, Any]]]] | None = None,
    ) -> EvaluatorOptimizerResult:
        """Run SRE task with iterative SRE Domain Judge evaluation."""
        eval_history: list[JudgeEvaluationReport] = []
        current_prompt = base_prompt
        final_output = ""
        latest_report: JudgeEvaluationReport | None = None

        for iter_num in range(1, self.max_iterations + 1):
            if mock_executor:
                output_text, observations = mock_executor(current_prompt)
            else:
                task = Task(
                    description=current_prompt,
                    expected_output=expected_output,
                    agent=agent,
                )
                crew = Crew(agents=[agent], tasks=[task], verbose=False)
                output_text = str(crew.kickoff())
                observations = []

            final_output = output_text

            # Evaluate with SRE Judge
            report = self.sre_evaluator.evaluate(
                agent_output=output_text,
                tool_observations=observations,
                task_context=base_prompt,
                resource_id=resource_id,
                iteration=iter_num,
            )
            eval_history.append(report)
            latest_report = report

            if report.is_passing(min_score=self.min_passing_score):
                return EvaluatorOptimizerResult(
                    final_output=final_output,
                    is_approved=True,
                    iterations_run=iter_num,
                    latest_report=report,
                    evaluation_history=eval_history,
                    needs_human_escalation=False,
                )

            # Inject critique into prompt
            if iter_num < self.max_iterations:
                critique_block = (
                    f"\n\n--- PREVIOUS ATTEMPT REVIEW BY SRE SAFETY JUDGE (Score: {report.overall_score}/100) ---\n"
                    f"Critique: {report.critique_summary}\n"
                    f"Actionable Fixes Required:\n"
                    + "\n".join(f"- {step}" for step in report.actionable_improvements)
                    + "\n\nPlease revise your assessment to ensure full operational safety and headroom."
                )
                current_prompt = base_prompt + critique_block

        assert latest_report is not None
        return EvaluatorOptimizerResult(
            final_output=final_output,
            is_approved=False,
            iterations_run=self.max_iterations,
            latest_report=latest_report,
            evaluation_history=eval_history,
            needs_human_escalation=True,
        )

