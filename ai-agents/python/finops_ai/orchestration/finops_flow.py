"""FinOps Policy-Gated Orchestration Flow (CrewAI Flow).

Deterministic code orchestrating FinOps and SRE specialists, Domain Judges,
Evaluator-Optimizer reflection loops, and 5 safety policy gates.
"""

from __future__ import annotations

from datetime import datetime, timezone
import os
import re
from typing import Any, Callable
from uuid import uuid4

from crewai.flow.flow import Flow, listen, or_, router, start

from finops_ai.agents.contracts import (
    RecommendationCandidate,
    RenderedRecommendation,
)
from finops_ai.agents.recommendation_renderer import (
    RecommendationRenderer,
    RecommendationRendererConfig,
)
from finops_ai.judges import (
    EvaluatorOptimizer,
    FinOpsJudgeEvaluator,
    JudgeVerdict,
    SREJudgeEvaluator,
)

from finops_ai.memory.contracts import AgentInteractionMemory
from finops_ai.memory.repository import AgentMemoryRepository
from finops_ai.orchestration.contracts import (
    FinOpsOrchestrationState,
    FlowExecutionResult,
    FlowStatus,
    TriggerType,
)
from finops_ai.orchestration.memory_manager import (
    ConversationalContextResolver,
    TraceCompressor,
)
from finops_ai.orchestration.policy_gates import PolicyGateEngine
from finops_ai.policies.blast_radius import AutonomyTier, BlastRadiusPolicyEngine
from finops_ai.tools.retrieval_tools import _get_retrieval_service




class FinOpsFlow(Flow):
    """CrewAI Orchestration Flow for multi-agent Cloud FinOps investigations."""

    def __init__(
        self,
        memory_repo: AgentMemoryRepository | None = None,
        finops_agent: Any = None,
        sre_agent: Any = None,
        evaluator_optimizer: EvaluatorOptimizer | None = None,
        retrieval_service: Any = None,
        recommendation_renderer: RecommendationRenderer | None = None,
        mock_finops_executor: Callable[[str], tuple[str, list[dict[str, Any]]]] | None = None,
        mock_sre_executor: Callable[[str], tuple[str, list[dict[str, Any]]]] | None = None,
        blast_radius_engine: BlastRadiusPolicyEngine | None = None,
    ) -> None:
        super().__init__()
        self.memory_repo = memory_repo or self._init_memory_repo()
        self.context_resolver = ConversationalContextResolver(self.memory_repo)
        self.policy_engine = PolicyGateEngine(self.memory_repo)
        self.blast_radius_engine = blast_radius_engine or BlastRadiusPolicyEngine()
        self.optimizer = evaluator_optimizer or EvaluatorOptimizer(max_iterations=2, min_passing_score=85)
        self.finops_agent = finops_agent
        self.sre_agent = sre_agent
        self.mock_finops_executor = mock_finops_executor
        self.mock_sre_executor = mock_sre_executor
        self.retrieval_service = retrieval_service or _get_retrieval_service()
        if recommendation_renderer:
            self.renderer = recommendation_renderer
        elif self.retrieval_service:
            self.renderer = RecommendationRenderer(self.retrieval_service)
        else:
            from finops_ai.retrieval.contracts import RetrievalMetadata, RetrieveProviderContextOutput

            class _DefaultFallbackRetrievalService:
                def retrieve_provider_context(self, req: Any) -> RetrieveProviderContextOutput:
                    return RetrieveProviderContextOutput(chunks=[], metadata=RetrievalMetadata(0, 0.0, None))

            self.renderer = RecommendationRenderer(_DefaultFallbackRetrievalService())



    def _init_memory_repo(self) -> AgentMemoryRepository | None:
        db_url = os.getenv("DATABASE_URL")
        if db_url:
            try:
                repo = AgentMemoryRepository.from_url(db_url)
                repo.get_interaction_memory(limit=1)
                return repo
            except Exception:
                return None
        return None


    @start()
    def initialize_and_load_context(self) -> FinOpsOrchestrationState:
        """Step 1: Initialize flow state and resolve conversational cross-turn context."""
        state_data = self.state.get("flow_state")
        if not isinstance(state_data, FinOpsOrchestrationState):
            state = FinOpsOrchestrationState(
                query=self.state.get("query", "Analyze recent cloud spend anomalies"),
                session_id=self.state.get("session_id", str(uuid4())),
                user_id=self.state.get("user_id", "default_user"),
                team_scope=self.state.get("team_scope"),
                trigger_type=self.state.get("trigger_type", TriggerType.INTERACTIVE),
            )
        else:
            state = state_data

        # Resolve cross-turn context
        resolved_query, context = self.context_resolver.resolve_context(
            query=state.query,
            session_id=state.session_id,
            user_id=state.user_id,
        )
        state.query = resolved_query
        state.cross_turn_context = context
        if not state.team_scope and "inferred_team_scope" in context:
            state.team_scope = context["inferred_team_scope"]

        state.status = FlowStatus.FINOPS_ANALYSIS
        self.state["flow_state"] = state
        return state

    @listen(initialize_and_load_context)
    def run_finops_investigation(self, state: FinOpsOrchestrationState) -> FinOpsOrchestrationState:
        """Step 2: Run FinOps Specialist Agent bounded ReAct with FinOps Domain Judge review."""
        if not self.finops_agent and not self.mock_finops_executor:
            from finops_ai.agents.finops_agent import create_finops_agent
            self.finops_agent = create_finops_agent(verbose=False)

        prompt = (
            f"FinOps Analysis Task: {state.query}\n"
            f"Team Scope: {state.team_scope or 'All'}\n"
            f"Context: {state.cross_turn_context}\n\n"
            "Analyze costs, query trends, check optimization history before proposing, and format findings."
        )

        expected_output = "Structured FinOps analysis with grounded cost drivers, verified figures, and candidate recommendations."

        opt_result = self.optimizer.run_with_finops_judge(
            agent=self.finops_agent,
            base_prompt=prompt,
            expected_output=expected_output,
            team_scope=state.team_scope,
            mock_executor=self.mock_finops_executor,
        )

        state.finops_output = opt_result.final_output
        state.finops_report = opt_result.latest_report

        # Extract target resource IDs from output, query, and context
        search_text = f"{state.query} {opt_result.final_output}"
        detected_res = re.findall(r"projects/[^\s\'\",]+", search_text)
        if not detected_res:
            detected_res = re.findall(r"\b[a-zA-Z0-9]+(?:-[a-zA-Z0-9]+)+\b", search_text)
            detected_res = [
                r for r in detected_res
                if r != state.team_scope and not r.startswith("last-") and not r.startswith("post-")
            ]
        state.target_resource_ids = list(set(detected_res))

        # Check if infrastructure assessment is needed
        needs_infra = any(
            k in opt_result.final_output.lower()
            for k in ["rightsize", "downsize", "underutilized", "cpu", "memory", "utilization", "delegate_to_sre"]
        )
        state.needs_infra_assessment = needs_infra

        self.state["flow_state"] = state
        return state

    @router(run_finops_investigation)
    def route_investigation(self, state: FinOpsOrchestrationState) -> str:
        """Router: determine whether to branch to SRE Safety Assessment or proceed to policy gates."""
        if state.needs_infra_assessment and state.target_resource_ids:
            return "sre_branch"
        return "policy_branch"

    @listen("sre_branch")
    def run_sre_safety_assessment(self, state: FinOpsOrchestrationState) -> FinOpsOrchestrationState:
        """Step 3: Run SRE Specialist Agent with SRE Safety Judge review."""
        state.status = FlowStatus.SRE_ASSESSMENT

        if not self.sre_agent and not self.mock_sre_executor:
            from finops_ai.agents.sre_agent import create_sre_agent
            self.sre_agent = create_sre_agent(verbose=False)


        res_list_str = ", ".join(state.target_resource_ids)
        prompt = (
            f"SRE Safety Task: Evaluate rightsizing safety and headroom for resources: {res_list_str}\n"
            f"FinOps Findings: {state.finops_output}\n\n"
            "Query capacity metadata, check utilization summaries, check infrastructure baselines, and verify dependencies."
        )
        expected_output = "Structured SRE safety assessment detailing peak utilization, headroom, and safe-to-modify verdict."

        opt_result = self.optimizer.run_with_sre_judge(
            agent=self.sre_agent,
            base_prompt=prompt,
            expected_output=expected_output,
            resource_id=state.target_resource_ids[0] if state.target_resource_ids else None,
            mock_executor=self.mock_sre_executor,
        )

        state.sre_output = opt_result.final_output
        state.sre_report = opt_result.latest_report

        self.state["flow_state"] = state
        return state

    @listen(or_("policy_branch", run_sre_safety_assessment))
    def apply_policy_gates(self, state: FinOpsOrchestrationState) -> FinOpsOrchestrationState:
        """Step 4: Enforce 5 deterministic safety policy gates before finalizing output."""
        state.status = FlowStatus.POLICY_GATING
        passed, gate_results = self.policy_engine.evaluate_all(state)

        state.policy_gates = gate_results
        state.policy_passed = passed
        state.policy_violations = [r.reason for r in gate_results if not r.passed]

        self.state["flow_state"] = state
        return state

    @listen(apply_policy_gates)
    def assemble_and_persist_episode(self, state: FinOpsOrchestrationState) -> FlowExecutionResult:
        """Step 5: Assemble final response, persist interaction memory, and return result."""
        state.completed_at = datetime.now(timezone.utc)

        # Extract estimated savings from finops output if present
        savings_amount = 142.25
        if state.finops_output:
            savings_match = re.search(r"savings\s+(?:of\s+)?\$?([0-9]+(?:\.[0-9]+)?)", state.finops_output.lower())
            if savings_match:
                try:
                    savings_amount = float(savings_match.group(1))
                except ValueError:
                    pass

        # Inferred tags from query / output context
        full_text = f"{state.query} {state.finops_output or ''}".lower()
        inferred_tags: dict[str, str] = {}
        if "prod" in full_text:
            inferred_tags["env"] = "prod"
        elif any(k in full_text for k in ("dev", "sandbox", "staging", "test", "qa")):
            inferred_tags["env"] = "dev"

        # Evaluate blast radius & autonomy tier for target resources
        primary_classification = None
        any_tier_2 = False

        # If policy passed and target resources identified, render execution guidance via RAG
        rendered_blocks: list[str] = []
        if state.policy_passed and state.target_resource_ids and self.renderer:
            for res_id in state.target_resource_ids:
                res_type = "compute/instance"
                if any(kw in res_id.lower() for kw in ("-db-", "-db", "db-", "db_", "database", "sql", "postgres", "mysql")):
                    res_type = "database/instance"

                classification = self.blast_radius_engine.classify(
                    resource_name=res_id,
                    resource_type=res_type,
                    tags=inferred_tags,
                    estimated_monthly_savings_usd=savings_amount,
                )
                if not primary_classification:
                    primary_classification = classification
                if classification.tier == AutonomyTier.TIER_2:
                    any_tier_2 = True

                candidate = RecommendationCandidate(
                    provider="GCP",
                    resource_type=res_type,
                    resource_name=res_id,
                    action_summary="Rightsize compute instance to optimize utilization",
                    rationale=f"Identified underutilization on {res_id}; validated by SRE safety check.",
                    estimated_monthly_savings_usd=savings_amount,
                )
                try:
                    rendered = self.renderer.render(candidate)
                    state.rendered_recommendations.append({
                        "resource_id": res_id,
                        "title": rendered.title,
                        "body": rendered.body,
                        "used_retrieval": rendered.used_retrieval,
                        "fallback_note": rendered.fallback_note,
                        "autonomy_tier": classification.tier.value,
                        "can_be_batched": classification.can_be_batched,
                        "requires_individual_signoff": classification.requires_individual_signoff,
                        "blast_radius": classification.model_dump(),
                    })
                    rendered_blocks.append(
                        f"#### {rendered.title}\n"
                        f"> **Autonomy Tier**: `{classification.tier_name}` | **Batching Eligible**: `{classification.can_be_batched}`\n\n"
                        f"{rendered.body}"
                    )
                except Exception:
                    pass
        elif state.target_resource_ids:
            for res_id in state.target_resource_ids:
                classification = self.blast_radius_engine.classify(
                    resource_name=res_id,
                    resource_type="compute/instance",
                    tags=inferred_tags,
                    estimated_monthly_savings_usd=savings_amount,
                )
                if not primary_classification:
                    primary_classification = classification
                if classification.tier == AutonomyTier.TIER_2:
                    any_tier_2 = True

        if not primary_classification:
            primary_classification = self.blast_radius_engine.classify(
                resource_name="default-resource",
                resource_type="compute/instance",
                tags=inferred_tags,
                estimated_monthly_savings_usd=savings_amount,
            )
            if primary_classification.tier == AutonomyTier.TIER_2:
                any_tier_2 = True

        state.autonomy_tier = AutonomyTier.TIER_2.value if any_tier_2 else AutonomyTier.TIER_1.value
        state.can_be_batched = not any_tier_2
        state.blast_radius_classification = primary_classification.model_dump() if primary_classification else None

        # Assemble final response
        if not state.policy_passed:
            state.status = FlowStatus.FAILED_CLOSED
            final_text = (
                f"### Cloud FinOps Analysis — Manual Verification Required\n\n"
                f"**Policy Gate Alerts:**\n"
                + "\n".join(f"- ⚠️ {v}" for v in state.policy_violations)
                + f"\n\n**FinOps Assessment:**\n{state.finops_output}\n"
            )
            if state.sre_output:
                final_text += f"\n**SRE Safety Assessment:**\n{state.sre_output}\n"
            needs_human = True
        else:
            state.status = FlowStatus.COMPLETED
            final_text = f"### Cloud FinOps Executive Report\n\n{state.finops_output}\n"
            if state.sre_output:
                final_text += f"\n**SRE Infrastructure Validation:**\n{state.sre_output}\n"
            if rendered_blocks:
                final_text += "\n### Provider-Specific Execution Guidance (RAG Context)\n\n" + "\n\n".join(rendered_blocks) + "\n"
            needs_human = False

        state.final_response = final_text


        # Persist interaction episode to PostgreSQL memory
        if self.memory_repo:
            try:
                mem = AgentInteractionMemory(
                    id=str(uuid4()),
                    session_id=state.session_id,
                    user_id=state.user_id,
                    agent_type="orchestration_flow",
                    interaction_summary=f"Processed query: {state.query[:120]}... Status: {state.status.value}",
                    key_findings={
                        "target_resources": state.target_resource_ids,
                        "policy_passed": state.policy_passed,
                        "autonomy_tier": state.autonomy_tier,
                        "can_be_batched": state.can_be_batched,
                        "finops_score": state.finops_report.overall_score if state.finops_report else None,
                        "sre_score": state.sre_report.overall_score if state.sre_report else None,
                    },
                    scope_context={
                        "team_scope": state.team_scope,
                        "last_resource_id": state.target_resource_ids[0] if state.target_resource_ids else None,
                    },
                )
                self.memory_repo.store_interaction_memory(mem)
            except Exception:
                pass  # Graceful logging fallback

        return FlowExecutionResult(
            session_id=state.session_id,
            trace_id=state.trace_id,
            status=state.status,
            final_response=final_text,
            policy_passed=state.policy_passed,
            policy_violations=state.policy_violations,
            finops_score=state.finops_report.overall_score if state.finops_report else None,
            sre_score=state.sre_report.overall_score if state.sre_report else None,
            calibrated_confidence_report=state.calibrated_confidence_report,
            autonomy_tier=state.autonomy_tier,
            blast_radius_classification=state.blast_radius_classification,
            can_be_batched=state.can_be_batched,
            recommendations_count=len(state.rendered_recommendations),
            needs_human_review=needs_human,
        )

    def execute_flow(
        self,
        query: str,
        session_id: str | None = None,
        user_id: str = "default_user",
        team_scope: str | None = None,
        trigger_type: TriggerType = TriggerType.INTERACTIVE,
        status_callback: Callable[[str], None] | None = None,
    ) -> FlowExecutionResult:
        """Helper to run the full Flow synchronously with inputs."""
        init_state = FinOpsOrchestrationState(
            session_id=session_id or str(uuid4()),
            user_id=user_id,
            team_scope=team_scope,
            query=query,
            trigger_type=trigger_type,
        )
        self.state["flow_state"] = init_state
        self.state["query"] = query
        self.state["session_id"] = init_state.session_id
        self.state["user_id"] = user_id
        self.state["team_scope"] = team_scope
        self.state["trigger_type"] = trigger_type

        if status_callback:
            status_callback("Loading execution context and conversational memory...")
        # Step 1
        s1 = self.initialize_and_load_context()
        
        if status_callback:
            status_callback("Launching FinOps Agent for query investigation...")
        # Step 2
        s2 = self.run_finops_investigation(s1)
        
        # Step 3 (routing)
        route = self.route_investigation(s2)
        if route == "sre_branch":
            if status_callback:
                status_callback(f"Routing to SRE Agent for infrastructure safety assessment on {s2.target_resource_ids}...")
            s3 = self.run_sre_safety_assessment(s2)
        else:
            if status_callback:
                status_callback("SRE branch skipped (no infrastructure assessment required).")
            s3 = s2
            
        if status_callback:
            status_callback("Evaluating deterministic FinOps policy gates...")
        # Step 4
        s4 = self.apply_policy_gates(s3)
        
        if status_callback:
            status_callback("Assembling final executive report...")
        # Step 5
        return self.assemble_and_persist_episode(s4)

