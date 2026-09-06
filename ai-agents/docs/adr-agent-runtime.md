# ADR: Agent Runtime — Bounded ReAct on CrewAI with Gemini

**Status:** Accepted
**Date:** 2026-08-22
**Authors:** Claus Albuquerque
**Related docs:** [agent-design-document.md](../../docs/agent-design-document.md), [agent-persistance-tools.document.md](../../docs/agent-persistance-tools.document.md), [agent-retrieval-design.document.md](../../docs/agent-retrieval-design.document.md), [agent-tree-of-thought.md](../../docs/agent-tree-of-thought.md), [adr-retrieval-pipeline.md](adr-retrieval-pipeline.md)
**Supersedes:** the earlier LangGraph/Azure-OpenAI leaning captured in the Phase 2 plan (`.ai/TASKS.md`)

---

## Context

The design docs specify a **FinOps Agent** and an **SRE Agent** that reason with a **bounded ReAct loop** (Thought → Action → Observation) over FOCUS-normalized data, delegate to each other, gate all write actions behind human approval, and retrieve provider-specific context only at recommendation-render time. `agent-tree-of-thought.md` explicitly rejects Tree-of-Thought in favor of **bounded ReAct with policy-gated orchestration**, prioritizing auditability, low latency, and reproducibility.

This ADR fixes **how** that runtime is built:

- **Framework:** CrewAI (Flows for orchestration, Agents for the specialists).
- **LLM provider:** Google Gemini on GCP via Vertex AI.
- **Runtime home:** the existing `ai-agents/python/finops_ai` package.

## Decision

### 1. Framework — CrewAI

- **CrewAI Agents** implement each specialist's ReAct loop.
- **CrewAI Flows** (`@start` / `@listen` / `@router`, with state persistence) implement orchestration, policy gates, and HITL.
- **CrewAI Tools** (`@tool` / `BaseTool`) wrap our typed, deterministic functions.

### 2. LLM provider — Gemini via Vertex AI

- Install `crewai[google-genai]` (native Google Gen AI SDK integration — no LiteLLM needed).
- Model string: `gemini/<model>` (e.g. `gemini/gemini-2.5-pro`, `gemini/gemini-2.5-flash` — verify current IDs in the Vertex AI model catalog before pinning).
- GCP-native route: **Vertex AI** via Application Default Credentials — `GOOGLE_GENAI_USE_VERTEXAI=true`, `GOOGLE_CLOUD_PROJECT`, `GOOGLE_CLOUD_LOCATION`. AI Studio key (`GEMINI_API_KEY`) is the quick local-dev fallback.
- A single `build_llm(tier)` factory returns a configured `crewai.LLM`, so the model is swappable in one place (mirrors the embedding-service abstraction already used for `nomic-embed-text-v1.5`).

> **Confirmed (2026-08-22):** Gemini via **Vertex AI** is the path for **all environments**. A fully local OSS model (e.g. Ollama-hosted Llama/Qwen) was considered but **deferred** — there is currently no local compute capable of running a model robust enough for reliable tool-calling and structured outputs. The `build_llm()` abstraction keeps that door open (swap the model string, no agent-code changes) if local capacity becomes available. AI Studio key (`GEMINI_API_KEY`) remains a lightweight dev fallback for the same Gemini models.

> **Credential wiring (2026-08-22):** The dev/test key lives in the **root `.env`** as `GCP_AGENTS_API_KEY` (a Vertex AI **Express-mode** API key, `AQ.`-prefixed, for the Gemini Enterprise Agent Platform). Per [Google's auth guidance](https://docs.cloud.google.com/gemini-enterprise-agent-platform/models/start/gcp-auth): **API key for testing, Application Default Credentials for production**. `build_llm()` therefore: (dev/test) reads `GCP_AGENTS_API_KEY`, sets `GOOGLE_GENAI_USE_VERTEXAI=true` and passes it as `GOOGLE_API_KEY`; (prod) uses ADC via an attached service account (`gcloud auth application-default login` locally) with `GOOGLE_CLOUD_PROJECT` + `GOOGLE_CLOUD_LOCATION` and no key. The key is gitignored and must never be committed; rotate if exposed.

### 3. Runtime layout (inside `ai-agents/python/finops_ai`)

```
finops_ai/
  agents/          # CrewAI Agents (FinOps, SRE) + RecommendationRenderer (exists)
  orchestration/   # CrewAI Flows + policy gates (the "orchestrator" — code, not an agent)
  tools/           # typed CrewAI tools (cost, infra, delegation, memory, forecast)
  llm.py           # build_llm() Gemini/Vertex factory
  retrieval/       # exists (RAG)
  observability/   # exists (trace sink)
```

The empty `ai-agents/agents/` TypeScript folder is superseded by this Python runtime.

## How the ReAct loop works in CrewAI

We do **not** hand-write the ReAct loop. The **Agent executor** runs it when it executes a **Task**:

1. CrewAI sends the task + tool schemas to Gemini.
2. Gemini emits a **Thought** and either a **tool call** (Action + typed input, via function calling) or a final answer.
3. CrewAI executes the tool; the return value becomes the **Observation** appended to the scratchpad.
4. The loop repeats until the model returns a final answer or a **bound** trips.

Our "bounded ReAct" maps directly onto CrewAI knobs:

| Design requirement | CrewAI mechanism |
|---|---|
| Step budget | `Agent(max_iter=…)` |
| Wall-clock bound | `Agent(max_execution_time=…)` |
| Auditable trace (shared `trace_id`) | `Agent(step_callback=…)` → `finops_ai.observability` sink |
| Structured verdicts | `Task(output_pydantic=…)` |
| Deterministic tool boundary | typed `@tool` functions resolving to FOCUS-normalized SQL |
| Optional explicit planning | `Agent(reasoning=True)` (evaluate; adds a planning pass) |

### Illustrative trace (FinOps anomaly investigation)

```
Thought:  "34% WoW jump in Compute. Which resources drive it?"
Action:   query_cost_by_service(service_category="Compute", date_range="last_14d", group_by="resource_id")
Observation: 3 VMs in prod-analytics = 78% of increase; effective_cost doubled 8d ago
Thought:  "Concentrated on 3 VMs. Justified by utilization? Need SRE."
Action:   delegate_to_sre(resource_ids=[...], question="Right-sized for workload?")
Observation: {avg CPU 12%, mem 18%, SKU D4s_v3→E16s_v3, no LB/AV-set}
Thought:  "Unnecessary upsize. Quantify savings, propose revert."
Action:   forecast_spend(...) → propose_recommendation(...)
Final:    recommendation candidate
```

## The two-agent model: orchestration without a third agent

**There are exactly two LLM agents** (FinOps, SRE). The "orchestrator" from the design docs is **not** a third agent — it is a **CrewAI Flow** (deterministic Python). This is a deliberate change from any reading that implied a separate orchestrator agent or a `hierarchical` manager-LLM.

Responsibilities that live in the **Flow (code)**, not in an LLM:

- Entry points (interactive query, scheduled digest).
- Short-term memory management (append observations; compress long traces while preserving resource IDs, dollar amounts, dates).
- Cross-turn context resolution via `agent_interaction_memory`.
- Policy gates before output: freshness, confidence threshold, prior-rejection check, dependency safety, fail-closed default.
- HITL approval and final response assembly.

## Domain-Specialist Judge Agents (Evaluator-Optimizer Reflection Loop)

**Decision: Domain-Specialist Judge Agents evaluate specialist outputs and drive reflection loops before state moves forward.**

To guarantee evidence grounding, mathematical accuracy, and operational safety:
- **FinOps Judge (`FinOpsJudgeAgent` / `FinOpsJudgeEvaluator`):** Evaluates financial reasoning against four dimensions:
  1. *Evidence Grounding (40%):* Zero-tolerance for unverified or hallucinated dollar amounts, dates, or resource IDs.
  2. *Mathematical Consistency (25%):* Validates cost deltas and projected savings calculations.
  3. *Long-Term Memory Compliance (20%):* Verifies that `get_optimization_history` was consulted before proposing actions.
  4. *Scope Integrity (15%):* Enforces team-level data isolation.
- **SRE Judge (`SREJudgeAgent` / `SREJudgeEvaluator`):** Evaluates infrastructure safety against four dimensions:
  1. *Operational Headroom (35%):* Verifies peak P95 CPU < 75% and peak Memory < 80% buffers.
  2. *Workload Baseline Awareness (25%):* Verifies `get_infrastructure_baselines` to protect batch/scheduled workloads from false positives.
  3. *Dependency Safety (20%):* Assesses blast radius and downstream dependencies.
  4. *Action Viability (20%):* Validates technical migration feasibility.
- **Flow Reflection Control:** The CrewAI Flow runs the `EvaluatorOptimizer` loop with a deterministic retry bound (`max_iterations = 2`). If an evaluation returns `verdict = REVISE`, structured critique and actionable steps are injected into the next iteration prompt. If an output repeatedly fails, it is escalated for human review with the judge's audit report attached.

```mermaid
flowchart TD
    S["@start: query / trigger"] --> M["load memory (short-term + interaction)"]
    M --> F["FinOps Agent — ReAct (SQL tools)"]
    F --> FJ["FinOps Domain Judge (Evidence, Math, Memory)"]
    FJ -->|REVISE (retries < 2)| F
    FJ -->|PASS| R{"needs infra context?"}
    R -- yes --> SRE["SRE Agent — ReAct (Infra tools)"]
    SRE --> SJ["SRE Domain Judge (Headroom, Baselines, Risk)"]
    SJ -->|REVISE (retries < 2)| SRE
    SJ -->|PASS| F
    R -- no --> G["policy gates: freshness · confidence · prior-rejection · dependency safety"]
    G --> RAG["retrieve_provider_context (render step ONLY)"]
    RAG --> H["@human_feedback gate (propose→approve→execute)"]
    H -->|approved| X["execute_recommendation (mocked in dev)"]
    H -->|needs_revision| F
    H -->|rejected| L["log rejection_reason to memory"]
```


## Inter-agent delegation

**Decision: explicit typed delegation tool, not implicit CrewAI delegation.**

- Do **not** rely on `allow_delegation=True` (CrewAI's built-in natural-language "Delegate work / Ask question to coworker" tools) or a `hierarchical` crew with a manager LLM.
- Instead, expose `delegate_to_sre(resource_ids, question)` and `delegate_to_finops(resource_ids, utilization_summary, question)` as typed tools that internally run the target agent (e.g. `sre_crew.kickoff(...)`) and return a **Pydantic verdict**.

Rationale: deterministic, schema-validated exchanges; explicit loop protection (max delegation depth, cycle detection); every delegation appears in the trace attributed to the caller. A manager LLM would add nondeterminism, latency, and cost on the control path for no benefit here (candidate actions are already bounded by inventory, thresholds, and policy).

## Human-in-the-loop (write actions)

**Decision: CrewAI Flow `@human_feedback`, async provider — no CrewAI Enterprise dependency.**

- Gate the approval step with `@human_feedback(emit=["approved","rejected","needs_revision"], llm=…, default_outcome="rejected")`. The LLM collapses free-form reviewer feedback into one outcome.
- Use a custom async `HumanFeedbackProvider`: it persists the pending recommendation and notifies the dashboard/Slack, then the flow pauses with `HumanFeedbackPending` (state auto-persisted). Resume via `Flow.from_pending(flow_id).resume(feedback)` when the human responds.
- `needs_revision` self-loops back to regeneration via `@listen(or_(...))`; `rejected` records `rejection_reason` to memory so the agent will not re-propose without new evidence.
- Audit trail from `human_feedback_history`. `execute_recommendation` is callable only when the outcome is `approved`. Provider mutations route through the provider abstraction layer and are mocked in dev.

## Retrieval boundary (unchanged)

Per [adr-retrieval-pipeline.md](adr-retrieval-pipeline.md): core analytical reasoning uses structured SQL tools only. `retrieve_provider_context` is invoked **only** at the recommendation-render node (before the HITL gate). Retrieval enriches; it never gates. A guardrail test asserts the anomaly/forecast path makes no retrieval call.

## Illustrative skeleton

```python
from crewai import Agent, Task, Crew
from crewai.flow.flow import Flow, start, listen, or_
from crewai.flow.human_feedback import human_feedback
from finops_ai.llm import build_llm
from finops_ai.tools import (query_cost_by_service, forecast_spend,
                             get_optimization_history, delegate_to_sre)

finops_agent = Agent(
    role="FinOps Analyst",
    goal="Explain cost movements and propose grounded, non-duplicate savings",
    backstory="Reasons in FOCUS-normalized cost vocabulary.",
    llm=build_llm("pro"),
    tools=[query_cost_by_service, forecast_spend, get_optimization_history, delegate_to_sre],
    max_iter=8,                        # bounded ReAct
    allow_delegation=False,            # delegation is an explicit typed tool
    step_callback=trace_sink.on_step,  # → observability, shared trace_id
    verbose=True,
)

class FinOpsFlow(Flow):
    @start()
    def analyze(self):
        task = Task(description="Investigate {trigger}", expected_output="candidate",
                    agent=finops_agent, output_pydantic=RecommendationCandidate)
        return Crew(agents=[finops_agent], tasks=[task]).kickoff(inputs=self.state.inputs)

    @human_feedback(message="Approve this action?",
                    emit=["approved", "rejected", "needs_revision"],
                    llm="gemini/gemini-2.5-flash", default_outcome="rejected")
    @listen(or_("analyze", "needs_revision"))
    def review(self, candidate):
        return render_with_rag(candidate)   # RAG only here

    @listen("approved")
    def execute(self, result): ...
```

## Consequences

**Positive**

- Two LLM agents + deterministic Flow → fewer moving parts on the control path; predictable latency/cost.
- Native, auditable HITL without Enterprise licensing.
- Native Gemini/Vertex integration keeps data in GCP and avoids extra dependencies.
- Bounds (`max_iter`, `max_execution_time`) and `step_callback` satisfy the auditability/replayability requirements directly.

**Negative / risks**

- CrewAI abstracts the ReAct loop; deep customization means working within its executor. Mitigation: keep logic in typed tools and the Flow, not in prompt hacks.
- Gemini model IDs and Vertex regional availability change; pin with a caveat and verify against the catalog.
- Structured-output support varies by model; validate `output_pydantic` on the chosen Gemini tier before relying on it.

## Alternatives considered

| Option | Why not |
|---|---|
| **LangGraph + Azure OpenAI** (earlier lean) | User selected Gemini/GCP and CrewAI; CrewAI gives native Gemini + HITL out of the box. |
| **CrewAI `hierarchical` crew (manager LLM)** | Nondeterministic routing, added latency/cost on the control path; conflicts with the auditability goal. |
| **Implicit `allow_delegation=True`** | Free-form NL delegation is not schema-validated or reliably loop-protected; explicit typed delegation tool is auditable. |
| **Separate orchestrator LLM agent** | Unnecessary third reasoning entity; a code Flow is deterministic and cheaper (this ADR's core clarification). |
| **CrewAI Enterprise webhook HITL** | Adds a licensing dependency; the async `HumanFeedbackProvider` covers our needs. |
| **Local OSS model via Ollama (Llama/Qwen)** | No local compute currently capable of a robust-enough model for reliable tool-calling/structured output; deferred. Kept reachable via `build_llm()` if capacity appears. |

## Follow-ups

- Pin Gemini model tier per role and Vertex auth per environment (TASK-035).
- Reframe TASK-041 as the **orchestration Flow** (not an agent).
- Decide predictions stack (Prophet vs. alternatives) — orthogonal to this ADR (TASK-045).
