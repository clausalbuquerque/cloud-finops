# Agent Persistence, Tools, and Cloud-Agnostic Architecture

**Companion document to:** [agent-design-document.md](agent-design-document.md)

Author: Claus Albuquerque

Course: Agentic AI Program: Building Autonomous Systems for Real-World Applications

Date: August 2, 2026.

---

This document expands on the agent design document with concrete definitions for the tool interfaces, the persistence layer that serves as long-term memory, and the architectural decisions that enable the system to operate across cloud providers. The design document establishes *what* the FinOps and SRE agents reason about and *why*; this document specifies *how* they interact with external systems and *how* the architecture accommodates multi-cloud environments.

## Cloud-Agnostic Design with Provider-Specific Execution

### Current State and Target State

The current codebase implements Azure-specific extractors — `azure-consumption-extractor` and `azure-metrics-extractor` — with configuration tied to Azure credentials (`AZURE_TENANT_ID`, `AZURE_CLIENT_ID`, `AZURE_CLIENT_SECRET`, `AZURE_SUBSCRIPTION_ID`). These extractors ingest cost and metrics data from Azure APIs and persist it into the shared PostgreSQL database.

The immediate target is **Google Cloud Platform (GCP)**. The long-term objective is that neither the FinOps Agent nor the SRE Agent is aware of which cloud provider produced the data they reason over. The agents reason in cloud-agnostic terms — FOCUS-normalized cost dimensions and provider-neutral utilization metrics — while a **provider abstraction layer** handles the translation between cloud-specific APIs and the normalized data model.

### Why FOCUS Makes Cloud Agnosticism Tractable

The FinOps Open Cost and Usage Specification (FOCUS) is not merely a naming convention — it is the architectural seam that decouples the agents from cloud providers. The `ConsumptionRecordEntity` already stores cost data using FOCUS column definitions: `effectiveCost`, `chargeType`, `pricingModel`, `serviceCategory`, `billingCurrency`, `providerName`. The `providerName` field is a string (not an enum) with a current default of `'Azure'` — it already supports values like `'GCP'` or `'AWS'` without schema changes.

This means the FinOps Agent's ReAct loop — as described in the design document — works identically regardless of provider. When the agent executes `query_cost_by_service(service_category='Compute', date_range='last_14d')`, it queries `consumption_records` filtered on FOCUS-aligned `service_category`. Whether the underlying record came from Azure Cost Management API or GCP Cloud Billing Export is irrelevant to the reasoning chain. The agent reasons over `effectiveCost`, `chargeType`, and `pricingModel` — FOCUS terms that map to both providers.

### Provider Abstraction Layer

The architecture separates concerns into three layers:

```
┌─────────────────────────────────────────────────────────┐
│                    Agent Layer                          │
│   FinOps Agent (ReAct)  ←→  SRE Agent (ReAct)         │
│   Reasons in FOCUS terms and provider-neutral metrics   │
├─────────────────────────────────────────────────────────┤
│                 Tool Interface Layer                    │
│   Cloud-agnostic tool signatures                        │
│   query_cost_by_service()  get_utilization_summaries() │
│   get_tracked_resources()  forecast_spend()            │
├─────────────────────────────────────────────────────────┤
│              Provider Abstraction Layer                 │
│   ┌──────────────┐  ┌──────────────┐  ┌─────────────┐ │
│   │ Azure        │  │ GCP          │  │ AWS         │ │
│   │ Extractor    │  │ Extractor    │  │ Extractor   │ │
│   │ (exists)     │  │ (target)     │  │ (future)    │ │
│   └──────┬───────┘  └──────┬───────┘  └──────┬──────┘ │
│          │                 │                 │         │
│          ▼                 ▼                 ▼         │
│   ┌─────────────────────────────────────────────────┐  │
│   │       PostgreSQL (FOCUS-normalized schema)      │  │
│   │   consumption_records · tracked_resources       │  │
│   │   utilization_summaries · metric_definitions    │  │
│   │   + agent memory tables (see below)             │  │
│   └─────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────┘
```

Each provider extractor is responsible for:

1. **Authentication:** Managing provider-specific credentials (Azure service principal, GCP service account key, AWS IAM role).
2. **API invocation:** Calling the provider's billing and monitoring APIs (Azure Cost Management → GCP Cloud Billing Export; Azure Monitor Metrics → GCP Cloud Monitoring).
3. **FOCUS normalization:** Mapping provider-specific billing fields to FOCUS columns before writing to `consumption_records`. For example, GCP's `cost` field maps to FOCUS `effectiveCost`; GCP's `service.description` maps to `serviceCategory`; `providerName` is set to `'GCP'`.
4. **Metric normalization:** Mapping provider-specific metric names to a normalized vocabulary before writing to `utilization_summaries`. GCP's `compute.googleapis.com/instance/cpu/utilization` (reported as 0.0–1.0 ratio) maps to the same conceptual metric as Azure's `Percentage CPU` (reported as 0–100%), with unit conversion handled at the extractor level.

The agents never call cloud provider APIs directly. Every tool call resolves to a database query against the FOCUS-normalized schema. The extractors run on a schedule (or are triggered by events) and populate the database asynchronously. This separation means adding a new cloud provider requires writing a new extractor — not modifying any agent logic, tool definition, or reasoning prompt.

### GCP-Specific Considerations

The GCP extractor will interface with:

- **Cloud Billing Export to BigQuery:** GCP does not expose a real-time billing query API equivalent to Azure Cost Management. Instead, billing data is exported to a BigQuery dataset. The GCP extractor queries BigQuery on a schedule, maps the `gcp_billing_export` table columns to FOCUS fields, and inserts records into `consumption_records` with `providerName = 'GCP'`.
- **Cloud Monitoring API:** Provides time-series metrics for GCE instances, Cloud SQL, GKE nodes, and other resources. The extractor maps GCP metric descriptors (e.g., `compute.googleapis.com/instance/cpu/utilization`, `compute.googleapis.com/instance/memory/balloon/ram_used`) to normalized metric names and writes to `metric_data_points` and `utilization_summaries`.
- **Cloud Asset Inventory:** GCP's equivalent to Azure Resource Graph. Provides resource metadata, relationships, labels (GCP's term for tags), and organizational hierarchy. The SRE Agent's `query_resource_dependencies()` tool resolves to this API through the extractor.

The key structural difference from Azure is the billing data path — BigQuery export versus real-time API. This does not affect the agent layer because the extractors normalize the data before it reaches the database. The agents see FOCUS-normalized records regardless of the upstream source.

### Cloud-Provider Knowledge Base for RAG-Augmented Interactions

While the agents reason in cloud-agnostic FOCUS terms, the *recommendations they produce* must be actionable in the user's specific cloud environment. Telling a GCP user to "downgrade from Standard_D4s_v3 to Standard_D2s_v3" is meaningless — those are Azure SKU names. The recommendation must reference GCP machine types (`n2-standard-8` → `n2-standard-4`).

To bridge this gap without hardcoding provider-specific knowledge into agent prompts, the architecture includes a **cloud-provider knowledge base** designed for retrieval-augmented generation (RAG):

- **Content:** SKU catalogs and machine-type mappings per provider; pricing models and commitment discount equivalents (Azure Reserved Instances → GCP Committed Use Discounts → AWS Savings Plans); provider-specific CLI commands for executing recommendations; region naming conventions; provider-specific operational constraints (e.g., GCP live migration behavior vs. Azure maintenance events).
- **Indexing:** Documents are chunked and embedded into a vector store, tagged by provider and resource type.
- **Retrieval at recommendation time:** When the FinOps Agent reaches the "propose recommendation" step in its ReAct loop, it retrieves provider-specific context from the knowledge base. The agent's Thought step determines what kind of recommendation to make (rightsize, commitment purchase, decommission); the RAG retrieval provides the provider-specific vocabulary to express that recommendation in actionable terms.
- **Update cadence:** The knowledge base is updated when providers release new SKUs, change pricing, or modify service capabilities. This is a separate pipeline from the cost/metrics extractors — it feeds the agent's *language* about recommendations, not the data it reasons over.

This design means the agent's core reasoning — "this resource is underused, rightsizing would save X per month" — is provider-agnostic and grounded in FOCUS data. Only the final mile of the recommendation — "downgrade from `n2-standard-8` to `n2-standard-4` using `gcloud compute instances set-machine-type`" — is provider-specific, and that specificity comes from RAG retrieval rather than baked-in prompts.

## Tool Definitions: The Agent's Interface to External Systems

The tools defined below are the agent's only mechanism for interacting with data and performing actions. Each tool is a structured function with typed inputs and outputs. The agent selects and invokes tools as **Action** steps in its ReAct loop; the tool's return value becomes the **Observation** that informs the next **Thought**.

All tools that query data resolve to PostgreSQL queries against the FOCUS-normalized schema. All tools that invoke cloud provider APIs do so through the provider abstraction layer — the agent passes provider-neutral parameters, and the abstraction layer routes to the correct provider's API.

### FinOps Agent Tools

#### Read-Only Tools (Autonomous — No Human Approval Required)

| Tool | Purpose | Resolves To | Limitation Addressed |
|------|---------|-------------|---------------------|
| `query_cost_by_service(service_category, date_range, group_by, provider?)` | Retrieve aggregated cost data filtered by FOCUS dimensions | SQL query on `consumption_records` | LLM cannot access billing data; without this tool, cost figures are hallucinated |
| `query_cost_trend(dimension, date_range, granularity)` | Retrieve time-series cost data for trend analysis | SQL query with date bucketing on `consumption_records` | LLM cannot perform time-series aggregation over millions of billing rows |
| `get_anomalies(severity?, date_range?, dimension?)` | Retrieve detected cost anomalies with classification | SQL query on anomaly detection results (computed by scheduled ML pipeline) | LLM cannot run Isolation Forest or Z-score computation |
| `get_commitment_coverage(provider?)` | Retrieve reservation/CUD utilization and coverage gaps | SQL query on commitment tracking tables | LLM has no access to commitment purchase or utilization data |
| `forecast_spend(dimension, horizon, scenario?)` | Project future spend using trained time-series models | Invokes Prophet model via model registry; returns prediction intervals | LLM cannot perform statistical forecasting — no access to trained model weights or historical decomposition |
| `get_optimization_history(scope, status?, date_range?)` | Retrieve past recommendations and their outcomes | SQL query on `optimization_recommendations` table | Prevents the groundless recommendation loop failure mode (see design document) — without this, agent re-proposes rejected actions |
| `delegate_to_sre(resource_ids, question)` | Request infrastructure assessment from SRE Agent | Inter-agent message passing; triggers SRE Agent's ReAct loop | FinOps Agent lacks infrastructure expertise; delegation grounds cost recommendations in operational reality |

#### Write Tools (Human-in-the-Loop — Require Explicit Approval)

| Tool | Purpose | Resolves To | Approval Flow |
|------|---------|-------------|---------------|
| `propose_recommendation(type, resource_ids, target_state, estimated_savings)` | Create a recommendation for user review | INSERT into `optimization_recommendations` with status `'proposed'` | Notification sent to resource owner; agent waits for approval/rejection |
| `execute_recommendation(recommendation_id)` | Execute an approved recommendation | Invokes provider-specific action through abstraction layer (e.g., `gcloud compute instances set-machine-type`) | Only callable after status = `'approved'`; agent cannot bypass approval gate |
| `store_anomaly_resolution(anomaly_id, root_cause, resolution, is_recurring)` | Persist anomaly investigation findings as long-term memory | INSERT/UPDATE on `anomaly_resolutions` table | N/A — write is to agent's own memory, not to infrastructure |

### SRE Agent Tools

#### Read-Only Tools (Autonomous)

| Tool | Purpose | Resolves To | Limitation Addressed |
|------|---------|-------------|---------------------|
| `get_tracked_resources(resource_group?, resource_type?, is_active?, provider?)` | Retrieve resource inventory with provisioned capacity metadata | SQL query on `tracked_resources` joined with `subscriptions` and `resource_groups` | LLM has no awareness of what infrastructure exists or its specifications |
| `get_utilization_summaries(resource_ids, date_range, metrics?)` | Retrieve daily utilization roll-ups with underuse flags | SQL query on `utilization_summaries` | LLM cannot observe real-time infrastructure utilization |
| `get_metric_definitions(resource_type)` | Retrieve available metrics and underuse thresholds for a resource type | SQL query on `metric_definitions` | LLM does not know which metrics are relevant for a given resource type or what thresholds define underuse |
| `query_resource_dependencies(resource_ids)` | Retrieve dependency graph (network, storage, compute relationships) | Provider abstraction layer → GCP Cloud Asset Inventory / Azure Resource Graph | LLM cannot determine if a resource has downstream dependencies that make changes risky |
| `get_infrastructure_baselines(resource_ids)` | Retrieve interpreted utilization baselines from agent memory | SQL query on `infrastructure_baselines` table | Without baselines, the agent flags batch-processing resources as underused every day (false-positive failure mode) |
| `delegate_to_finops(resource_ids, utilization_summary, question)` | Request cost quantification from FinOps Agent | Inter-agent message passing; triggers FinOps Agent's ReAct loop | SRE Agent lacks cost data; delegation translates infrastructure observations into dollar-denominated priorities |

#### Write Tools (Human-in-the-Loop)

| Tool | Purpose | Resolves To | Approval Flow |
|------|---------|-------------|---------------|
| `store_infrastructure_baseline(resource_id, metric, baseline_description, expected_pattern)` | Persist an interpreted utilization baseline as long-term memory | INSERT/UPDATE on `infrastructure_baselines` table | N/A — write is to agent's own memory |
| `update_underuse_threshold(resource_type, metric, new_threshold, justification)` | Adjust the underuse detection threshold for a resource type/metric combination | UPDATE on `metric_definitions` | Requires FinOps engineer approval — threshold changes affect anomaly detection sensitivity across all resources of that type |

## Database as Long-Term Memory: Persistence Tables

The design document identifies four categories of long-term memory: optimization history, anomaly context, infrastructure baselines, and user preferences. These map to specific database tables that extend the existing schema. The existing entities (`consumption_records`, `tracked_resources`, `utilization_summaries`, `metric_definitions`) store **operational data** — what the agents reason *over*. The tables below store **agent memory** — what the agents have *learned*.

### Optimization Recommendations

Stores every recommendation the FinOps Agent has proposed, along with its lifecycle status and outcome.

```
optimization_recommendations
├── id (uuid, PK)
├── provider_name (varchar)              -- 'GCP', 'Azure', 'AWS'
├── resource_id (varchar)                -- provider-neutral resource identifier
├── resource_type (varchar)              -- e.g., 'Compute/VirtualMachine'
├── recommendation_type (varchar)        -- 'rightsize', 'commitment_purchase', 'decommission', 'consolidate'
├── current_state (jsonb)                -- { sku: 'n2-standard-8', monthlyCost: 284.50 }
├── proposed_state (jsonb)               -- { sku: 'n2-standard-4', estimatedMonthlyCost: 142.25 }
├── estimated_monthly_savings (decimal)
├── actual_monthly_savings (decimal?)    -- measured post-execution; null until measured
├── confidence_score (double precision)  -- agent's confidence in the recommendation
├── sre_assessment (jsonb?)              -- SRE Agent's structured assessment (dependencies, risk, utilization context)
├── status (varchar)                     -- 'proposed' | 'approved' | 'rejected' | 'executed' | 'expired'
├── rejection_reason (text?)             -- user-provided reason when status = 'rejected'
├── scope_team (varchar?)                -- team this recommendation belongs to
├── proposed_at (timestamptz)
├── resolved_at (timestamptz?)
├── executed_at (timestamptz?)
├── created_at (timestamptz)
└── updated_at (timestamptz)
```

**Why this table is memory, not just a log:** The agent queries this table *before* generating new recommendations. The query `get_optimization_history(scope='team:data-platform', status='rejected', date_range='last_90d')` prevents the groundless recommendation loop — the specific failure mode identified in the design document. The `rejection_reason` field allows the agent to understand *why* a recommendation was unwanted, not just that it was rejected.

### Anomaly Resolutions

Stores the root-cause analysis and resolution for investigated cost anomalies.

```
anomaly_resolutions
├── id (uuid, PK)
├── anomaly_id (varchar)                 -- reference to the detected anomaly
├── provider_name (varchar)
├── resource_id (varchar)
├── dimension (varchar)                  -- FOCUS dimension where anomaly was detected
├── root_cause_type (varchar)            -- 'sku_change', 'autoscaling', 'new_resource', 'pricing_change', 'usage_spike', 'unknown'
├── root_cause_description (text)        -- agent's natural-language explanation
├── resolution_action (varchar?)         -- what was done: 'reverted', 'accepted', 'mitigated', 'no_action'
├── is_recurring (boolean)               -- whether this anomaly pattern has appeared before
├── recurrence_count (integer)           -- how many times this pattern has been seen
├── investigation_trace (jsonb)          -- compressed ReAct trace (Thought/Action/Observation steps)
├── resolved_by (varchar?)               -- user who confirmed resolution
├── created_at (timestamptz)
└── updated_at (timestamptz)
```

**Why this table is memory, not just a log:** The agent queries this table *during anomaly investigation*. When a new anomaly is detected on a resource, the agent retrieves prior resolutions for the same resource or dimension. If the last anomaly on this resource was caused by an autoscaling misconfiguration 45 days ago, the agent's Thought step can reason: "This resource had a similar spike recently caused by autoscaling — let me check whether the same trigger fired again." The `investigation_trace` field stores a compressed version of the ReAct trace, enabling the agent to learn from its own prior reasoning.

### Infrastructure Baselines

Stores the SRE Agent's interpreted understanding of what "normal" looks like for each resource.

```
infrastructure_baselines
├── id (uuid, PK)
├── tracked_resource_id (uuid, FK → tracked_resources)
├── provider_name (varchar)
├── metric_name (varchar)                -- e.g., 'cpu_utilization', 'memory_utilization'
├── baseline_type (varchar)              -- 'workload_pattern', 'seasonal', 'event_driven'
├── expected_pattern (jsonb)             -- { schedule: 'weekday_nights', expectedUtilization: { low: 5, high: 85 }, description: '...' }
├── suppress_underuse_alerts (boolean)   -- if true, underuse flags for this resource/metric are treated as expected
├── confidence_score (double precision)  -- how confident the SRE Agent is in this baseline
├── evidence (jsonb)                     -- data that supports this baseline (metric samples, user confirmation)
├── established_by (varchar)             -- 'agent_inferred' | 'user_confirmed' | 'user_defined'
├── last_validated (timestamptz)         -- when the baseline was last checked against current data
├── created_at (timestamptz)
└── updated_at (timestamptz)
```

**Why this table is memory, not just data:** The `utilization_summaries` table stores raw numbers — average CPU was 5% today. The `infrastructure_baselines` table stores *interpretation* — 5% CPU during the day is expected for this batch-processing resource because it runs jobs at night. Without this interpreted memory, the SRE Agent would flag the same resources as underused every single day, generating the false-positive alert fatigue described in the design document. The `suppress_underuse_alerts` flag directly prevents this failure mode. The `established_by` field distinguishes between baselines the agent inferred from data patterns and baselines a human confirmed or defined — user-confirmed baselines carry higher weight in reasoning.

### Agent Interaction Memory

Stores conversation summaries and cross-session context for user interactions.

```
agent_interaction_memory
├── id (uuid, PK)
├── session_id (varchar)                 -- groups interactions within a single conversation
├── user_id (varchar)
├── agent_type (varchar)                 -- 'finops' | 'sre'
├── interaction_summary (text)           -- compressed summary of the conversation
├── key_findings (jsonb)                 -- structured extraction: resources discussed, decisions made, numbers cited
├── follow_up_items (jsonb?)             -- actions the user said they would take or asked the agent to track
├── scope_context (jsonb)                -- { team: 'data-platform', provider: 'GCP', resources: [...] }
├── created_at (timestamptz)
└── updated_at (timestamptz)
```

**Why this table matters:** This is how the agent remembers previous interactions with a user. When a FinOps engineer returns and asks "What happened with the compute cost issue we discussed last week?", the agent retrieves relevant entries from `agent_interaction_memory` to reconstruct context without requiring the user to re-explain the situation. The `key_findings` field stores structured facts (resource IDs, dollar amounts, decisions) that can be queried precisely, while `interaction_summary` provides narrative context for the LLM's Thought step.

## How Memory, Tools, and ReAct Connect

The following diagram shows how the components described in this document map to the ReAct loop defined in the design document:

```
User Query or Scheduled Trigger
         │
         ▼
┌─────────────────────────────────────────────────────────┐
│                      THOUGHT                            │
│  "What do I need to know to answer this?"               │
│                                                         │
│  Context sources:                                       │
│  ├─ Short-term memory (current ReAct trace)             │
│  ├─ agent_interaction_memory (prior conversations)      │
│  └─ RAG retrieval (provider-specific knowledge)         │
├─────────────────────────────────────────────────────────┤
│                      ACTION                             │
│  Agent selects a tool from its tool set:                │
│                                                         │
│  Data retrieval tools:                                  │
│  ├─ query_cost_by_service()     → consumption_records   │
│  ├─ get_utilization_summaries() → utilization_summaries │
│  ├─ get_tracked_resources()     → tracked_resources     │
│  └─ query_resource_dependencies() → Provider API        │
│                                                         │
│  Memory retrieval tools:                                │
│  ├─ get_optimization_history()  → optimization_recs     │
│  ├─ get_infrastructure_baselines() → infra_baselines    │
│  └─ (anomaly resolution lookup) → anomaly_resolutions   │
│                                                         │
│  Computation tools:                                     │
│  └─ forecast_spend()            → Prophet model         │
│                                                         │
│  Delegation tools:                                      │
│  ├─ delegate_to_sre()           → SRE Agent ReAct loop  │
│  └─ delegate_to_finops()        → FinOps Agent ReAct    │
│                                                         │
│  Memory write tools:                                    │
│  ├─ store_anomaly_resolution()                          │
│  ├─ store_infrastructure_baseline()                     │
│  └─ propose_recommendation()                            │
├─────────────────────────────────────────────────────────┤
│                    OBSERVATION                          │
│  Tool returns structured data → feeds next Thought      │
└─────────────┬───────────────────────────────────────────┘
              │
              ▼
        Next THOUGHT (loop continues)
              │
              ▼
     Grounded conclusion or human escalation
```

The critical insight is that **memory retrieval and memory writes are tool calls**, not implicit LLM behavior. The agent explicitly decides "I should check if this recommendation was rejected before" and invokes `get_optimization_history()` as an Action. Similarly, the agent explicitly decides "I should remember this root cause" and invokes `store_anomaly_resolution()` as an Action. This makes memory usage auditable — every memory read and write appears in the ReAct trace and can be reviewed.

## Mapping Current Entities to the Cloud-Agnostic Model

The existing database entities are already partially cloud-agnostic thanks to FOCUS alignment. The following table maps the current Azure-centric fields to their cloud-agnostic equivalents and identifies where GCP-specific mapping occurs:

| Entity | Field | Current (Azure) | GCP Equivalent | Agent-Facing (Neutral) |
|--------|-------|-----------------|----------------|----------------------|
| `ConsumptionRecordEntity` | `providerName` | `'Azure'` | `'GCP'` | Agents filter by provider or query across all providers |
| `ConsumptionRecordEntity` | `resourceId` | Azure ARM resource ID (`/subscriptions/.../providers/...`) | GCP resource name (`projects/.../zones/.../instances/...`) | Opaque identifier — agents pass it to tools but do not parse its structure |
| `ConsumptionRecordEntity` | `serviceCategory` | Maps from Azure meter category | Maps from GCP `service.description` | FOCUS-normalized; agents reason over this directly |
| `ConsumptionRecordEntity` | `effectiveCost` | From Azure amortized cost view | From GCP billing export `cost` + credits | FOCUS-normalized; agents reason over this directly |
| `ConsumptionRecordEntity` | `pricingModel` | `'OnDemand'`, `'Reservation'`, `'Spot'` | `'OnDemand'`, `'CommittedUse'`, `'Preemptible'` | Normalized to FOCUS terms at extractor level |
| `TrackedResourceEntity` | `azureResourceId` | Azure ARM resource ID | GCP resource name | **Needs refactoring:** rename to `cloudResourceId` to remove Azure-specific naming |
| `TrackedResourceEntity` | `provisionedCapacity` | `{ vCPUs: 4, memoryGB: 16 }` | `{ vCPUs: 4, memoryGB: 16 }` | Already provider-neutral (JSONB); extractors normalize units |
| `MetricDefinitionEntity` | `metricNamespace` | `'Microsoft.Compute/virtualMachines'` | `'compute.googleapis.com'` | Provider-specific but isolated — agents query by normalized `metricName`, not namespace |
| `SubscriptionEntity` | `subscriptionId` | Azure subscription GUID | GCP project ID | **Needs abstraction:** represents the top-level billing/organizational unit per provider |

The schema changes required for GCP support are minimal: renaming `azureResourceId` to `cloudResourceId` on `TrackedResourceEntity`, and generalizing `SubscriptionEntity` to represent the provider-specific organizational unit (Azure subscription, GCP project, AWS account). The FOCUS-aligned fields on `ConsumptionRecordEntity` require no changes — the GCP extractor normalizes data to FOCUS terms before insertion.

## Design Decisions and Trade-offs

### Why PostgreSQL for Agent Memory Instead of a Dedicated Memory Store

Alternative approaches include vector databases (for semantic memory search), Redis (for fast ephemeral context), or dedicated agent memory frameworks. PostgreSQL was chosen because:

1. **Already deployed:** The operational data (cost records, metrics, resource inventory) already lives in PostgreSQL. Adding memory tables to the same database eliminates an infrastructure dependency.
2. **Queryable and auditable:** Agent memory is not opaque — optimization history, anomaly resolutions, and baselines are structured, queryable records. A FinOps engineer can query `SELECT * FROM optimization_recommendations WHERE scope_team = 'data-platform' AND status = 'rejected'` directly, without going through the agent.
3. **Transactional consistency:** When the agent proposes a recommendation and simultaneously stores the SRE assessment, both writes succeed or fail atomically. A separate memory store would require distributed transaction coordination.
4. **Backup and recovery:** Agent memory is backed up with the same PostgreSQL backup strategy as operational data. If the database is restored, agent memory is restored with it — there is no drift between what the agent "knows" and what the data shows.

The trade-off is that PostgreSQL is not optimized for semantic similarity search. If the agents need to find "recommendations similar to this one" by embedding similarity rather than exact field matching, a vector index (pgvector extension) or a separate vector store may be warranted. This is a future consideration — the current design uses structured queries for memory retrieval, which PostgreSQL handles efficiently.

### Why Extractors Are Separate From Agents

The extractors (`azure-consumption-extractor`, `azure-metrics-extractor`, and the planned `gcp-consumption-extractor`, `gcp-metrics-extractor`) run as separate processes on a schedule. They are not invoked by the agents in real time. This is deliberate:

1. **Rate limits and quotas:** Cloud billing and monitoring APIs have rate limits. Extractors manage pagination, retries, and backoff — concerns that should not pollute the agent's ReAct loop.
2. **Data freshness guarantees:** Extractors ensure that the database contains data up to a known point in time. The agents reason over data with a known freshness, rather than encountering partial or inconsistent data from mid-extraction API calls.
3. **Provider isolation:** Adding GCP support means writing a new extractor, not modifying agent code. The agent's tools query the database — they are unaware of how data arrived there.

The exception is `query_resource_dependencies()`, which may need to call a cloud provider API in real time (Azure Resource Graph or GCP Cloud Asset Inventory) because dependency relationships are not stored in the local database and can change frequently. This tool routes through the provider abstraction layer, which selects the correct API based on the resource's `providerName`.

### The RAG Knowledge Base as a Future Module

The cloud-provider knowledge base described in this document is not part of the initial implementation. The agents can produce cloud-agnostic recommendations ("reduce this resource's capacity by 50%") without provider-specific vocabulary. The knowledge base becomes necessary when the agents need to produce *executable* recommendations — specific CLI commands, SKU names, or console links. This is planned as a separate module that can be developed independently of the core agent logic, since it feeds into the recommendation rendering step rather than the reasoning loop itself.
