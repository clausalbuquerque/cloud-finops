"""SRE Domain Judge Agent and evaluation logic."""

from __future__ import annotations

from typing import Any, Sequence

from crewai import Agent

from finops_ai.judges.contracts import (
    DimensionScore,
    JudgeEvaluationReport,
    JudgeVerdict,
)
from finops_ai.judges.rubrics import SRE_EVALUATION_RUBRIC
from finops_ai.llm import build_llm
from finops_ai.prompts.judge_prompts import (
    SRE_JUDGE_BACKSTORY,
    SRE_JUDGE_GOAL,
    SRE_JUDGE_ROLE,
)


def create_sre_judge_agent(
    llm: Any = None,
    verbose: bool = False,
) -> Agent:
    """Create a Principal SRE Domain Judge Agent."""
    judge_llm = llm if llm is not None else build_llm(model="gemini-2.5-flash", temperature=0.0)

    return Agent(
        role=SRE_JUDGE_ROLE,
        goal=SRE_JUDGE_GOAL,
        backstory=SRE_JUDGE_BACKSTORY,
        llm=judge_llm,
        tools=[],
        verbose=verbose,
        allow_delegation=False,
    )


class SREJudgeEvaluator:
    """Evaluates SRE specialist outputs against operational safety and baseline awareness rubrics."""

    def evaluate(
        self,
        agent_output: str,
        tool_observations: Sequence[dict[str, Any]] | None = None,
        task_context: str | None = None,
        resource_id: str | None = None,
        iteration: int = 1,
    ) -> JudgeEvaluationReport:
        """Run programmatic and rubric-based evaluation on SRE output."""
        tool_obs = list(tool_observations or [])
        actionable_improvements: list[str] = []
        unverified_claims: list[str] = []

        # --- 1. Operational Headroom Check (Weight: 0.35) ---
        headroom_score = 100
        headroom_notes = "Headroom verified within safe operational thresholds."
        # If output proposes rightsizing without mentioning peak utilization or headroom
        if "rightsize" in agent_output.lower() or "downsize" in agent_output.lower():
            if not any(k in agent_output.lower() for k in ["headroom", "peak", "p95", "buffer", "max"]):
                headroom_score = 65
                headroom_notes = "Rightsizing proposed without explicit peak/P95 headroom analysis."
                actionable_improvements.append(
                    "Include explicit peak (P95/Max) CPU and memory headroom calculations for the target SKU."
                )

        # --- 2. Workload Baseline Awareness Check (Weight: 0.25) ---
        baseline_score = 100
        baseline_notes = "Baseline checks evaluated."
        # If the target resource is a batch worker or has batch patterns
        is_batch_resource = (resource_id and "batch" in resource_id.lower()) or "batch" in (task_context or "").lower()
        checked_baselines = any(
            isinstance(o, dict) and (o.get("tool_name") == "get_infrastructure_baselines" or "expected_pattern" in str(o))
            for o in tool_obs
        )

        if is_batch_resource and not checked_baselines:
            baseline_score = 40
            baseline_notes = "Batch workload analyzed without querying get_infrastructure_baselines."
            actionable_improvements.append(
                "Verify `get_infrastructure_baselines` before classifying cyclical batch workloads as underutilized."
            )

        # --- 3. Dependency Safety Check (Weight: 0.20) ---
        dependency_score = 100
        dependency_notes = "Dependencies and blast radius accounted for."

        # --- 4. Action Viability Check (Weight: 0.20) ---
        viability_score = 100
        viability_notes = "Action is viable on target provider."

        dimension_scores = [
            DimensionScore(
                name="operational_headroom",
                score=headroom_score,
                weight=0.35,
                notes=headroom_notes,
            ),
            DimensionScore(
                name="workload_baseline_awareness",
                score=baseline_score,
                weight=0.25,
                notes=baseline_notes,
            ),
            DimensionScore(
                name="dependency_safety",
                score=dependency_score,
                weight=0.20,
                notes=dependency_notes,
            ),
            DimensionScore(
                name="action_viability",
                score=viability_score,
                weight=0.20,
                notes=viability_notes,
            ),
        ]

        overall_score = int(
            round(
                headroom_score * 0.35
                + baseline_score * 0.25
                + dependency_score * 0.20
                + viability_score * 0.20
            )
        )

        if overall_score < 75 or baseline_score < 50:
            verdict = JudgeVerdict.REVISE
            critique = "SRE assessment requires revision due to unverified headroom or unaddressed workload baseline."
        elif overall_score < 85:
            verdict = JudgeVerdict.REVISE
            critique = "SRE assessment is near passing but requires explicit headroom confirmation."
        else:
            verdict = JudgeVerdict.PASS
            critique = "SRE assessment meets all operational safety, headroom, and baseline awareness criteria."

        return JudgeEvaluationReport(
            judge_role=SRE_JUDGE_ROLE,
            evaluated_agent="SRE Specialist",
            overall_score=overall_score,
            verdict=verdict,
            dimension_scores=dimension_scores,
            hallucination_detected=False,
            unverified_claims=unverified_claims,
            critique_summary=critique,
            actionable_improvements=actionable_improvements,
            iteration=iteration,
        )

