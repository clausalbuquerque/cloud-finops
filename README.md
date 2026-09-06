# Cloud FinOps AI Agent Platform

An autonomous, multi-agent cloud financial operations and infrastructure reliability platform. Built around the **FinOps Open Cost and Usage Specification (FOCUS 1.0)**, the platform coordinates specialized AI agents (FinOps Specialist and SRE Specialist) with dual Evaluator-Optimizer feedback loops, defense-in-depth safety guardrails, tiered autonomy, and post-execution canary telemetry monitoring.

---

## 🔒 Data Provenance & Synthetic Privacy Notice

> [!IMPORTANT]
> **No proprietary, customer, or enterprise production data is stored or processed in this repository.**
> 
> - **Public Foundation**: All cloud billing records originate exclusively from the publicly available **FinOps Open Cost and Usage Specification (FOCUS 1.0)** sample dataset published by the FinOps Foundation.
> - **Synthetic Generation**: Historical billing rows, time-series usage trends, and infrastructure utilization metrics (CPU, Memory, IOPS, network) are synthetically generated and backfilled using statistical workload profiles (steady-state, spiky batch, warm standby, in-memory cache).
> - **Anonymized Metadata**: All resource IDs, subscription UUIDs, project identifiers, and resource tags are synthetic mock values designed strictly to demonstrate multi-agent reasoning, policy gating, and blast-radius isolation without exposing real infrastructure assets.

---

## 🎯 Problem Statement

Modern cloud financial operations face a critical tension between **cost reduction** and **infrastructure reliability**:
- **Engineering Friction & SRE Distrust**: Automated FinOps scripts frequently recommend downsizing instances based solely on average CPU, ignoring memory pressure, spiky batch jobs, or disaster recovery standbys. This risks severe production outages and degrades engineering trust.
- **Alert Fatigue & Inaction**: Operations teams are inundated with hundreds of unvetted, context-free cost recommendations, leading to decision paralysis and unaddressed cloud waste.
- **Ungrounded AI Hallucinations**: Standard LLM assistants lack deterministic telemetry grounding, invent inaccurate pricing calculations, and risk executing dangerous production modifications without safety gates or rollback mechanisms.

**Our Solution**: An autonomous multi-agent platform combining a **FinOps Specialist** and an **SRE Specialist** with independent veto authority, deterministic confidence calibration ($\ge 0.85$), tiered blast-radius isolation, and automated post-execution canary rollbacks.

---

## 🏗️ Architecture & Agentic Capabilities

The platform implements a collaborative, multi-agent pattern with separation of concerns:

```
┌─────────────────────────────────────────────────────────────────────────────────────────┐
│                                    Cloud FinOps Core                                    │
└─────────────────────────────────────────────────────────────────────────────────────────┘
                                             │
                       ┌─────────────────────┴─────────────────────┐
                       ▼                                           ▼
          ┌─────────────────────────┐                 ┌─────────────────────────┐
          │  FinOps Specialist Agent│                 │   SRE Specialist Agent  │
          │  (Cost, Billing & FOCUS)│                 │   (Telemetry & Safety)  │
          └─────────────────────────┘                 └─────────────────────────┘
                       │                                           │
                       ▼                                           ▼
          ┌─────────────────────────┐                 ┌─────────────────────────┐
          │   FinOps Safety Judge   │                 │     SRE Safety Judge    │
          │   (Evaluator-Optimizer) │                 │   (Evaluator-Optimizer) │
          └─────────────────────────┘                 └─────────────────────────┘
                       │                                           │
                       └─────────────────────┬─────────────────────┘
                                             ▼
                              ┌─────────────────────────────┐
                              │  Deterministic Policy Gates │
                              │  (Sanitization & Headroom)  │
                              └─────────────────────────────┘
                                             │
                       ┌─────────────────────┴─────────────────────┐
                       ▼                                           ▼
          ┌─────────────────────────┐                 ┌─────────────────────────┐
          │ Tier 1: Low Risk (Dev)  │                 │ Tier 2: High Risk (Prod)│
          │ Autonomous/Batch Review │                 │ Mandatory Human Sign-Off│
          └─────────────────────────┘                 └─────────────────────────┘
                                             │
                                             ▼
                              ┌─────────────────────────────┐
                              │    Canary Telemetry Watcher │
                              │    & 1-Click Rollback Engine│
                              └─────────────────────────────┘
```

### 1. Dual Specialist Agents with Evaluator-Optimizer Loops
- **FinOps Specialist Agent**: Analyzes FOCUS 1.0 billing data, identifies top spenders, detects cost anomalies, looks up official cloud catalog SKUs, and calculates rightsizing/cleanup proposals. Uses read-only analysis tools.
- **SRE Specialist Agent**: Independent validation gate. Inspects multi-day utilization telemetry (CPU/Memory P95), evaluates workload baselines (e.g. batch spikes, disaster recovery standbys), and checks service dependencies.
- **Domain Judges & Rubrics**: Specialized LLM judges score recommendations against rubrics for cost math accuracy, source attribution, and operational headroom, triggering iterative refinement before proposals progress.

### 2. Defense-in-Depth Safety Guardrails
- **Input Metadata Sanitization & Structural Isolation**: Neutralizes indirect prompt injection attacks embedded within cloud metadata tags, resource names, and billing descriptions by stripping control characters, escaping prompt delimiters, and isolating untrusted fields in `<untrusted_metadata>` tags.
- **Deterministic Confidence Calibration**: Computes an objective evidence score:
  $$\text{Confidence} = (0.35 \times \text{Telemetry Completeness}) + (0.40 \times \text{Headroom Margin}) + (0.25 \times \text{Catalog Match})$$
  Fails closed to human review with an **Ambiguity Warning** if confidence $< 0.85$ or if critical telemetry (e.g. memory) is missing.
- **5 Deterministic Policy Gates**: Enforces data freshness, calibrated confidence thresholds, memory of prior user rejections, dependency safety, and headroom limits before any action is approved.

### 3. Tiered Autonomy & Blast-Radius Engine
- **Tier 1 (Low Risk / Non-Production)**: Dev and sandbox environments with estimated monthly impact under \$50 allow batched or asynchronous review to prevent engineer alert fatigue.
- **Tier 2 (High Risk / Production)**: Any optimization targeting production environments (`env: prod`), stateful databases, storage volumes, or shared clusters requires explicit, individualized human sign-off.

### 4. Post-Execution Canary Telemetry Monitor & Rollback Engine
- Following approved execution, the system initiates a **60-minute canary observation window**.
- If CPU/Memory utilization exceeds 90% or application error rate spikes occur, a high-priority alert is emitted and a **1-click rollback action** reverts the resource to its pre-execution baseline SKU.

### 5. Golden Benchmark Test Suite & Automated Evaluator Pipeline
- Versioned dataset of **52 historical cloud optimization scenarios** across 8 categories (steady-state underused, spiky batch, warm standby, memory-bound, stateful production, missing telemetry, prompt injection attempts, canary spikes).
- Automated evaluator pipeline measuring Groundedness ($100\%$), SRE Veto Recall ($100\%$), Expected Calibration Error ($\text{ECE} = 0.0389 \le 0.150$), and Tier 2 Isolation Precision ($100\%$).

---

## 💻 Tech Stack

- **AI Agent Engine**: Python 3.12, CrewAI, LangChain, Pydantic v2, `google-genai` (Gemini 2.5 Flash / Pro)
- **Frontend Dashboard**: React 18, Vite, Tailwind CSS, Lucide Icons, Server-Sent Events (SSE)
- **Backend-For-Frontend (BFF)**: Node.js, Express, TypeScript
- **Database & Storage**: PostgreSQL 16 with `pgvector` extension, TypeORM (migrations & entities)
- **Package & Dependency Management**: `uv` (Python), `npm` (Node.js), Docker & Docker Compose

---

## 🚀 Quick Start: Running Locally

### Prerequisites
- **Docker & Docker Compose** (Docker Desktop recommended)
- **Node.js** >= 20 LTS & **npm** >= 10
- **Python** >= 3.11 with **`uv`** installed (`curl -LsSf https://astral.sh/uv/install.sh | sh`)
- **Google Gemini API Key** (`GEMINI_API_KEY` or `GCP_AGENTS_API_KEY`)

---

### Step 1: Clone and Configure Environment

```bash
# Clone the repository
git clone https://github.com/clausalbuquerque/cloud-finops.git
cd cloud-finops

# Create the root .env configuration
cp .env.example .env

# Edit .env and supply your Gemini API key:
# GEMINI_API_KEY="your-api-key-here"
# GCP_AGENTS_API_KEY="your-api-key-here"

# Distribute the environment configuration to all sub-projects
./scripts/sync-env.sh
```

---

### Step 2: Bootstrap the Local Environment

The bootstrap script automates container startup, database migrations, sample data seeding, and readiness checks:

```bash
./scripts/setup-local-env.sh
```

What this script executes:
1. Validates and distributes `.env` across services.
2. Starts the PostgreSQL 16 + `pgvector` container on port `5433` (Docker Compose).
3. Applies TypeORM migrations (Core schema, Metrics, Agent Memory, and Predictions).
4. Seeds the FOCUS 1.0 dataset, generates synthetic utilization metrics, and computes spend forecasts.
5. Verifies database connectivity and agent memory repository health.

---

### Step 3: Launch the Fullstack Application

To launch the entire platform (FastAPI Agent Engine, BFF Express Server, and Vite React Dashboard) in a single command:

```bash
./scripts/start-dashboard.sh
```

Once started, the services are available at:

| Component | URL | Description |
|---|---|---|
| **Vite React Dashboard** | [http://localhost:5173](http://localhost:5173) | Interactive UI with real-time SSE chat, batch approvals & canary rollback |
| **BFF Express Server** | [http://localhost:3001](http://localhost:3001) | REST & SSE API bridging UI with PostgreSQL and Agent service |
| **FastAPI Agent Engine** | [http://localhost:8000](http://localhost:8000) | Python agent orchestration and streaming chat endpoint (`/api/chat`) |
| **PostgreSQL + pgvector** | `localhost:5433` | Database: `cloud_finops`, Schema: `finops` |

---

## 🤖 CLI & Standalone Agent Workflows

If you wish to interact with or evaluate the AI agents directly from the command line:

### 1. Interactive Terminal Chat
```bash
cd ai-agents/python
uv run python scripts/chat_finops_agent.py
```

### 2. Run the Golden Benchmark Evaluator Pipeline
Executes all 52 historical cloud optimization scenarios and generates a quantitative scorecard:
```bash
cd ai-agents/python
uv run python scripts/run_golden_evaluator.py
```
Output report is persisted to `ai-agents/python/docs/golden-benchmark-report.json`.

### 3. Run Headless Orchestration Flow
```bash
cd ai-agents/python
uv run python scripts/run_finops_flow.py
```

---

## 🧪 Testing & Verification

### Run Safety & Guardrails Test Suite
```bash
cd ai-agents/python
uv run python -m unittest tests/test_golden_evaluator.py tests/test_guardrails_calibration.py tests/test_guardrails_sanitizer.py tests/test_policy_gates.py tests/test_blast_radius.py tests/test_canary_monitor.py
```
- **44/44 unit and safety tests pass** covering input sanitization, deterministic calibration, blast-radius isolation, canary rollback, and golden benchmark execution.

### Run Database Entity & Migration Tests
```bash
cd database
npm test
```

### Verify Dashboard Build
```bash
cd dashboard
npm run build
cd server && npm run build
```

---

## 📊 Sample Inputs, Outputs & Evaluation Artifacts

To enable immediate review and verification without requiring live cloud connections or long evaluation runs, this repository includes complete input datasets, sample agent outputs, and benchmark artifacts:

### 1. Sample Inputs
- **FOCUS 1.0 Cloud Billing Dataset**: [`ai-agents/python/data/focus_sample_1k.csv`](ai-agents/python/data/focus_sample_1k.csv) contains 1,000 normalized FOCUS cost records used for local SQL analytics and anomaly detection.
- **Golden Evaluation Benchmark (52 Scenarios)**: [`ai-agents/python/tests/benchmarks/golden_dataset.json`](ai-agents/python/tests/benchmarks/golden_dataset.json) contains versioned test scenarios covering 8 failure modes (steady-state underused, spiky batch, warm standby, memory-bound, stateful production, missing telemetry, prompt injection, and canary regression).

### 2. Sample Agent Output
When evaluating a rightsizing candidate, the agent pipeline generates a deterministic, fully-grounded recommendation object:
```json
{
  "recommendation_id": "rec-2026-09-01",
  "resource_id": "gce-instance-dev-worker-01",
  "action_type": "rightsize",
  "current_sku": "e2-standard-4",
  "recommended_sku": "e2-standard-2",
  "estimated_monthly_savings_usd": 48.50,
  "confidence_score": 0.924,
  "sre_veto": false,
  "autonomy_tier": "Tier 1 (Non-Prod)",
  "evidence": {
    "p95_cpu_utilization": "18.2%",
    "p95_memory_utilization": "28.5%",
    "workload_profile": "steady_state_underused",
    "telemetry_freshness": "100%"
  }
}
```

### 3. Evaluation Artifacts & Verification Scorecard
- **Golden Benchmark Evaluation Report**: [`ai-agents/python/docs/golden-benchmark-report.json`](ai-agents/python/docs/golden-benchmark-report.json) stores quantitative evaluation results:
  | Metric | Result | Benchmark Target | Status |
  |---|---|---|---|
  | **Overall Scenario Pass Rate** | **100.0%** (52/52) | $\ge 95.0\%$ | ✅ PASSED |
  | **Groundedness Score** | **100.0%** | $\ge 90.0\%$ | ✅ PASSED |
  | **SRE Veto Precision** | **100.0%** | $\ge 90.0\%$ | ✅ PASSED |
  | **SRE Veto Recall** | **100.0%** | $\ge 95.0\%$ | ✅ PASSED |
  | **Expected Calibration Error (ECE)** | **0.0389** | $\le 0.150$ | ✅ PASSED |
  | **Tier 2 (Prod) Isolation Precision** | **100.0%** | $100.0\%$ | ✅ PASSED |
- **Catalog Semantic Retrieval Benchmark**: [`ai-agents/python/docs/retrieval-golden-queries.json`](ai-agents/python/docs/retrieval-golden-queries.json) benchmarks semantic similarity matching across cloud SKUs.

---

## 🔍 Reviewer Guide: Core Implementation Files

For evaluators and technical reviewers exploring the codebase, the core agentic logic is organized into clean, modular layers:

- **Agent Personas & Reasoning**:
  - FinOps Specialist: [`ai-agents/python/finops_ai/agents/finops_agent.py`](ai-agents/python/finops_ai/agents/finops_agent.py)
  - SRE Specialist: [`ai-agents/python/finops_ai/agents/sre_agent.py`](ai-agents/python/finops_ai/agents/sre_agent.py)
- **Safety, Calibration & Guardrails**:
  - Input Sanitizer & Injection Defense: [`ai-agents/python/finops_ai/guardrails/sanitizer.py`](ai-agents/python/finops_ai/guardrails/sanitizer.py)
  - Deterministic Confidence Scorer: [`ai-agents/python/finops_ai/guardrails/confidence_calibration.py`](ai-agents/python/finops_ai/guardrails/confidence_calibration.py)
  - Deterministic Policy Gates: [`ai-agents/python/finops_ai/orchestration/policy_gates.py`](ai-agents/python/finops_ai/orchestration/policy_gates.py)
  - Tiered Autonomy & Blast-Radius: [`ai-agents/python/finops_ai/policies/blast_radius.py`](ai-agents/python/finops_ai/policies/blast_radius.py)
- **Evaluator-Optimizer Feedback & Post-Execution**:
  - Domain Rubrics & LLM Judges: [`ai-agents/python/finops_ai/judges/domain_judges.py`](ai-agents/python/finops_ai/judges/domain_judges.py)
  - Canary Telemetry Monitor & Rollback: [`ai-agents/python/finops_ai/monitoring/canary_watcher.py`](ai-agents/python/finops_ai/monitoring/canary_watcher.py)
- **Benchmarking & Evaluation Harness**:
  - Evaluator Pipeline: [`ai-agents/python/scripts/run_golden_evaluator.py`](ai-agents/python/scripts/run_golden_evaluator.py)
  - Synthetic Scenario Generator: [`ai-agents/python/scripts/generate_golden_dataset.py`](ai-agents/python/scripts/generate_golden_dataset.py)

---

## 📁 Repository Structure

```
cloud-finops/
├── ai-agents/
│   └── python/
│       ├── finops_ai/
│       │   ├── agents/          # FinOps & SRE Specialist Agent definitions
│       │   ├── guardrails/      # Input sanitization & confidence calibration scorer
│       │   ├── hitl/            # Human-in-the-loop approval & rollback engine
│       │   ├── judges/          # Evaluator-Optimizer judges & domain rubrics
│       │   ├── memory/          # Episodic & semantic pgvector interaction repository
│       │   ├── monitoring/      # Post-execution canary watcher
│       │   ├── orchestration/   # FinOpsFlow state machine, policy gates & delegation
│       │   ├── policies/        # Tiered autonomy & blast-radius classifier
│       │   ├── predictions/     # Anomaly detector & Holt-Winters forecaster
│       │   └── tools/           # Cost querying, infra telemetry, and SKU retrieval tools
│       ├── scripts/             # CLI runners, dataset generator, benchmark evaluator
│       └── tests/               # Unit, integration, and golden benchmark test suites
├── dashboard/
│   ├── src/                     # React 18 frontend (Vite, Tailwind, SSE ChatPanel)
│   └── server/                  # Node.js Express BFF server (batch review, rollback API)
├── database/
│   ├── src/entities/            # TypeORM entities (FOCUS consumption, memory, metrics)
│   ├── migrations/              # Database migration definitions
│   └── tests/                   # Entity and migration unit tests
├── docs/
│   ├── multi-agent-architecture.md   # Architectural design specification
│   └── safety_and_intervention_plan.md # Safety, guardrails & HITL plan
├── scripts/
│   ├── setup-local-env.sh       # One-click environment bootstrap & health check
│   ├── start-dashboard.sh       # One-click runner for UI, BFF, and Agent FastAPI
│   └── sync-env.sh              # Single source of truth .env distribution
├── docker-compose.yml           # PostgreSQL 16 + pgvector container configuration
└── .env.example                 # Root environment variables template
```

---

## 📄 License

This project is licensed under the MIT License.