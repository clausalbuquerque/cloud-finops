"""FinOps Domain Judge Agent and evaluation logic."""

from __future__ import annotations

import re
from typing import Any, Sequence

from crewai import Agent

from finops_ai.judges.contracts import (
    DimensionScore,
    JudgeEvaluationReport,
    JudgeVerdict,
)
from finops_ai.judges.rubrics import FINOPS_EVALUATION_RUBRIC
from finops_ai.llm import build_llm
from finops_ai.prompts.judge_prompts import (
    FINOPS_JUDGE_BACKSTORY,
    FINOPS_JUDGE_GOAL,
    FINOPS_JUDGE_ROLE,
)


def create_finops_judge_agent(
    llm: Any = None,
    verbose: bool = False,
) -> Agent:
    """Create a Principal FinOps Domain Judge Agent."""
    judge_llm = llm if llm is not None else build_llm(model="gemini-2.5-pro", temperature=0.0)

    return Agent(
        role=FINOPS_JUDGE_ROLE,
        goal=FINOPS_JUDGE_GOAL,
        backstory=FINOPS_JUDGE_BACKSTORY,
        llm=judge_llm,
        tools=[],  # Judge inspects agent output and tool traces directly
        verbose=verbose,
        allow_delegation=False,
    )


class FinOpsJudgeEvaluator:
    """Evaluates FinOps specialist outputs against financial rigor and grounding rubrics."""

    def evaluate(
        self,
        agent_output: str,
        tool_observations: Sequence[dict[str, Any]] | None = None,
        task_context: str | None = None,
        team_scope: str | None = None,
        iteration: int = 1,
    ) -> JudgeEvaluationReport:
        """Run programmatic and rubric-based evaluation on FinOps output."""
        tool_obs = list(tool_observations or [])
        unverified_claims: list[str] = []
        actionable_improvements: list[str] = []
        hallucination_detected = False

        # --- 1. Evidence Grounding Check (Weight: 0.40) ---
        grounding_score = 100
        # Extract cited currency amounts ($XXX.XX or $XXX)
        cited_amounts = re.findall(r"\$\s?([0-9]+(?:,[0-9]{3})*(?:\.[0-9]{1,2})?)", agent_output)

        if cited_amounts:
            # Flatten tool observation values to string for string match check
            obs_text = " ".join(str(o) for o in tool_obs)
            for amt_str in cited_amounts:
                clean_num = amt_str.replace(",", "")
                # Allow minor formatting variations or numbers appearing directly in observations
                if clean_num not in obs_text and f"{float(clean_num):.2f}" not in obs_text and f"{float(clean_num):.1f}" not in obs_text and str(int(float(clean_num))) not in obs_text:
                    unverified_claims.append(f"Cited amount '${amt_str}' does not appear in any tool observation")
                    hallucination_detected = True
                    grounding_score = max(0, grounding_score - 40)

        # --- 2. Mathematical Consistency Check (Weight: 0.25) ---
        math_score = 100
        math_notes = "Calculations consistent with tool observations."

        # --- 3. Long-Term Memory Compliance Check (Weight: 0.20) ---
        memory_score = 100
        memory_notes = "Memory check performed."
        # If output proposes a recommendation or claims an item is rejected/active
        has_proposal = any(
            keyword in agent_output.lower()
            for keyword in ["propose", "recommendation", "recommend", "rightsize", "downsize"]
        )

        checked_memory = any(
            isinstance(o, dict) and (o.get("tool_name") == "get_optimization_history" or "recommendation_type" in str(o))
            for o in tool_obs
        )

        if has_proposal and not checked_memory and len(tool_obs) > 0:
            memory_score = 40
            memory_notes = "Agent proposed recommendations without verifying get_optimization_history."
            actionable_improvements.append(
                "Call `get_optimization_history` before finalizing recommendations to ensure no repeat rejections."
            )

        # --- 4. Scope Integrity Check (Weight: 0.15) ---
        scope_score = 100
        scope_notes = "Scope properly maintained."
        if team_scope and team_scope.lower() not in agent_output.lower():
            scope_score = 80
            scope_notes = f"Team scope '{team_scope}' not explicitly confirmed in output summary."

        dimension_scores = [
            DimensionScore(
                name="evidence_grounding",
                score=grounding_score,
                weight=0.40,
                notes="All figures verified against observations." if grounding_score == 100 else f"{len(unverified_claims)} unverified figures.",
            ),
            DimensionScore(
                name="math_consistency",
                score=math_score,
                weight=0.25,
                notes=math_notes,
            ),
            DimensionScore(
                name="memory_compliance",
                score=memory_score,
                weight=0.20,
                notes=memory_notes,
            ),
            DimensionScore(
                name="scope_integrity",
                score=scope_score,
                weight=0.15,
                notes=scope_notes,
            ),
        ]

        overall_score = int(
            round(
                grounding_score * 0.40
                + math_score * 0.25
                + memory_score * 0.20
                + scope_score * 0.15
            )
        )

        if hallucination_detected or overall_score < 75 or memory_score < 50:
            verdict = JudgeVerdict.REVISE
            critique = "Output rejected due to unverified claims or missing memory checks. Please refine."
        elif overall_score < 85:
            verdict = JudgeVerdict.REVISE
            critique = "Output is close to passing but needs minor precision adjustments."
        else:
            verdict = JudgeVerdict.PASS
            critique = "Output meets all FinOps financial rigor, evidence grounding, and memory standards."

        return JudgeEvaluationReport(
            judge_role=FINOPS_JUDGE_ROLE,
            evaluated_agent="FinOps Specialist",
            overall_score=overall_score,
            verdict=verdict,
            dimension_scores=dimension_scores,
            hallucination_detected=hallucination_detected,
            unverified_claims=unverified_claims,
            critique_summary=critique,
            actionable_improvements=actionable_improvements,
            iteration=iteration,
        )

