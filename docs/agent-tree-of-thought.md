# Capstone Project: FinOps Forecasting Agent

Author: Claus Albuquerque

Course: Agentic AI Program: Building Autonomous Systems for Real-World Applications

Checkpoint: 4.1

## Capstone Checkpoint 4.1: Tree-of-Thought Integration Plan

### Project objective
The core objective of this project is to run a FinOps + SRE multi-agent system that detects cloud cost anomalies, validates operational safety, and proposes actionable optimization recommendations with measurable savings. The agent must produce decisions that are grounded in real telemetry and cost data, auditable for governance, and efficient enough for low-latency operational use.

### 1. Required decision: Is Tree-of-Thought (ToT) appropriate?
**Decision: ToT is not appropriate as the primary runtime reasoning strategy for this agentic use case.**

ToT could marginally help in a narrow subproblem (for example, exploring multiple recommendation phrasings), but for the core workflow it is more likely to **hinder** than improve outcomes.

Why it hinders this design:

1. The highest-value steps are deterministic and tool-grounded, not open-ended reasoning.
2. Core tasks already map well to structured actions: query normalized cost data, fetch utilization summaries, check dependency safety, quantify savings, apply approval gates.
3. ToT adds branching overhead where you already have strong external signals (SQL outputs, metrics, dependency graphs, policy constraints).
4. Branching increases latency and compute cost without proportional accuracy gains in this domain.
5. Safety and trust depend on reproducibility and auditability; multi-branch hidden exploration makes explanations and replay harder.
6. The architecture already separates responsibilities with two specialist agents and explicit delegation, which captures most benefits ToT tries to provide (multiple perspectives) without branch explosion.

As the objective is: produce reliable, auditable, low-latency decisions from governed operational data; ToT’s multi-branch search is not a good fit.

---

### 3. If ToT is not appropriate, what should be used instead?

#### 3.1 Why ToT is not appropriate (intentional design choice)
This is an intentional decision based on the capstone’s constraints:

1. **Premature commitment risk is low** in core analysis because tool calls provide hard observations that immediately constrain reasoning.
2. **High branching is unnecessary** because candidate actions are already naturally bounded by resource inventory, utilization thresholds, and policy rules.
3. **Constraint complexity is handled externally** by typed tool contracts, schema normalization (FOCUS), and human approval for write actions.
4. **Operational priorities** favor predictable latency and low cost; ToT’s multi-branch search conflicts with this.
5. **Evaluation signals are strong and objective** (cost deltas, utilization percentiles, dependency checks, prior rejection history), so heavy speculative search adds little value.

#### 3.2 Better-fit reasoning approach
Use a **bounded ReAct loop with policy-gated orchestration**, specialist delegation, and memory checks. Each element below intentionally substitutes for a capability ToT would otherwise provide — recovering its benefits (multiple perspectives, evidence-weighed choices) without paying its branch-explosion cost in latency, spend, and **auditability**.

1. **ReAct loop as the primary controller** — substitutes a single, linear evidence chain for tree search. Each cost/telemetry tool call returns a hard observation that immediately narrows the decision space, so exploring parallel branches adds cost without adding information.
   - *Thought:* decide the single next data need.
   - *Action:* call exactly one relevant tool.
   - *Observation:* fold the structured result into state.
   - *Stop:* halt when a confidence threshold, policy gate, or step budget is reached.
2. **Dual-agent specialization** — substitutes a bounded, role-separated "second opinion" for speculative branching. Cross-domain disagreement (cost vs. operational risk) is surfaced through delegation rather than by enumerating hypothetical paths.
   - *FinOps agent:* anomaly detection, cost attribution, savings quantification.
   - *SRE agent:* operational safety, utilization interpretation, dependency risk.
   - *Contract:* delegation returns a structured verdict, keeping the exchange auditable and cheap.
3. **Deterministic guardrails** — substitute objective, reproducible checks for subjective branch scoring and pruning. Because the pass/fail criteria are explicit, every decision is replayable for governance review.
   - *Pre-output checks:* data freshness, confidence thresholds, prior-rejection memory, dependency safety.
   - *Approval gate:* human-in-the-loop sign-off for any destructive or write action.
   - *Fail-closed default:* when evidence is insufficient, recommend manual verification instead of speculating.
4. **Retrieval only where needed** — substitutes grounded lookup for speculative reasoning. Provider-specific detail is fetched on demand, so the agent never "reasons its way" to SKU or pricing facts it can retrieve deterministically.
   - Retrieve provider-specific SKU/CLI context at the recommendation-rendering stage.
   - Keep core analytical reasoning on structured, FOCUS-normalized data tools.

#### Why this supports your goal better than ToT
1. **Higher trust:** easier to audit and explain every step to FinOps and finance stakeholders.
2. **Lower latency/cost:** one-step tool acquisition beats multi-branch exploration for most queries.
3. **Better governance:** clean separation between analysis, safety validation, and action approval.
4. **More robust in production:** fewer moving parts in runtime reasoning; easier SLO management and incident debugging.
5. **Aligned with your existing architecture:** it leverages what your docs already establish (ReAct, specialist agents, memory, retrieval boundary, HITL controls) instead of introducing unnecessary search complexity.
