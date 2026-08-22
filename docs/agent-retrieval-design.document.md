# Agent Retrieval Design: When and Why Semantic Retrieval Is Needed

**Companion document to:** [agent-persistance-tools.document.md](agent-persistance-tools.document.md)

Author: Claus Albuquerque

Course: Agentic AI Program: Building Autonomous Systems for Real-World Applications

Date: August 8, 2026.

---

## Is Retrieval Required for This Agent?

**Yes — but only for one specific step in the reasoning loop, and not for the core analytical reasoning.**

The FinOps and SRE agents reason over structured, FOCUS-normalized data stored in PostgreSQL. Their primary data access pattern is structured tool calls — `query_cost_by_service(service_category='Compute', date_range='last_14d')` resolves to a SQL `WHERE` clause, not a semantic search. The agent knows exactly what it is looking for (cost records for a specific service category in a specific time range) and constructs precise queries against known columns. This is deterministic retrieval via a tool, not RAG.

However, retrieval becomes necessary at the **recommendation rendering step** — the point where the agent translates a cloud-agnostic analytical conclusion into a provider-specific, actionable recommendation. The agent's reasoning produces conclusions like "this resource is overprovisioned; reducing capacity by 50% would save approximately $142/month." To make this actionable for a GCP user, the agent must produce: "downgrade from `n2-standard-8` to `n2-standard-4` using `gcloud compute instances set-machine-type --machine-type=n2-standard-4`." This provider-specific vocabulary — machine type names, CLI commands, pricing tiers, commitment discount structures — is where semantic retrieval is required.

### Why Structured Queries Are Sufficient for Core Reasoning

The database serves as a **tool**, not a retrieval-augmented knowledge source. The distinction:

- **Tool pattern:** The agent decides "I need compute costs for the last 14 days" and constructs a parameterized query. The query is deterministic — same parameters, same results. The agent *knows what it is looking for* before invoking the tool.
- **RAG pattern:** The agent has a natural-language need ("how do I rightsize a GCE instance?") and must find semantically relevant information from a corpus where the exact location of the answer is unknown.

The core reasoning loop — detecting anomalies, correlating utilization with cost, identifying underused resources, checking optimization history — is entirely served by structured queries against FOCUS-normalized tables. The agent never needs to ask "find me cost records *similar to* this one." It asks "find me cost records *where* `service_category = 'Compute' AND usage_date > '2026-07-25'`." No vectorization, no embedding, no semantic similarity is needed for this.

### Why Retrieval Is Required for Recommendation Rendering

The cloud-provider knowledge that makes recommendations actionable is:

1. **Unstructured** — SKU documentation, pricing pages, CLI references, and operational constraints are natural-language documents, not tabular data.
2. **Broad** — hundreds of machine types, dozens of pricing models, provider-specific operational constraints. Too large to include in every prompt.
3. **Variable by context** — the relevant subset depends on the resource type, region, and recommendation type. The agent cannot predict which specific document chunk it needs until it has completed its analytical reasoning.

These three characteristics — unstructured content, broad corpus, context-dependent relevance — are precisely what semantic retrieval is designed for.

### Why Not a Web Search Tool Instead?

A web search tool could deliver similar *content* (provider documentation, pricing pages) but with fundamentally different reliability properties:

| Property | Web Search | Local Knowledge Base |
|----------|-----------|---------------------|
| Determinism | Same query may return different results on different days | Same query returns same results until explicitly updated |
| Quality control | Results include outdated blogs, SEO content, incorrect community answers | Only vetted, approved documentation |
| Security | Queries leak internal infrastructure context to external APIs | No information leaves the infrastructure |
| Prompt injection | Web content may contain adversarial text | Curated content; minimal attack surface |
| Auditability | Cannot reproduce which search result informed a recommendation after the fact | Every chunk that influenced a recommendation is logged |
| Availability | External dependency; outage prevents actionable recommendations | Local; no external dependency |

For a system producing cost recommendations that affect production infrastructure, **auditability and determinism are non-negotiable**. When a FinOps engineer asks "why did the agent recommend `n2-standard-4`?", the answer must be traceable to a specific, versioned document — not to a search result that may no longer exist.

The chosen approach: **web search feeds the knowledge base maintenance pipeline** (keeping it current), while the **agent retrieves from the local knowledge base** during reasoning (deterministic, auditable). This gives freshness without sacrificing reliability.

## Semantic Retrieval Integration

### Data Source: Cloud-Provider Documentation Corpus

The knowledge base contains provider-specific documentation organized by category:

| Category | Content | Source | Update Cadence |
|----------|---------|--------|----------------|
| Machine types / SKUs | Instance specifications, vCPUs, memory, pricing per hour | GCP Compute Engine docs, pricing pages | Weekly automated scrape + validation |
| Pricing models | On-demand, committed use discounts (CUDs), sustained use discounts, preemptible/spot | GCP pricing documentation | Weekly |
| CLI references | `gcloud` commands for resizing, stopping, migrating resources | GCP CLI documentation | Monthly |
| Operational constraints | Live migration behavior, maintenance windows, regional availability, quota limits | GCP operational docs, release notes | Monthly |
| Equivalent mappings | Cross-provider SKU equivalents (Azure ↔ GCP ↔ AWS), pricing model equivalents | Curated internal mapping document | On provider release |

For the initial GCP target, the corpus is scoped to GCP documentation. As additional providers are added, each provider's documentation is ingested as a separate tagged partition within the same vector store.

### Document Segmentation and Chunking

Documents are segmented using a **hierarchical chunking strategy**:

1. **Primary split:** By document section headers (H2/H3 in markdown). Each section becomes a candidate chunk. This preserves semantic coherence — a section about "N2 machine types" stays together rather than being split mid-table.
2. **Size constraint:** Chunks exceeding 512 tokens are split at paragraph boundaries within the section. Chunks below 100 tokens are merged with the preceding chunk.
3. **Metadata enrichment:** Each chunk carries structured metadata:
   ```json
   {
     "provider": "GCP",
     "category": "machine_types",
     "resource_type": "compute/instance",
     "region_scope": "global",
     "last_verified": "2026-08-01",
     "source_url": "https://cloud.google.com/compute/docs/machine-types"
   }
   ```
4. **Overlap:** Adjacent chunks share 50 tokens of overlap to preserve context across boundaries.

The metadata enables **filtered retrieval** — when the agent is generating a recommendation for a GCP compute instance, the retrieval query is scoped to `provider='GCP' AND resource_type='compute/instance'`, reducing the search space and improving precision.

### Retrieval Mechanism

The retrieval pipeline uses **pgvector** (PostgreSQL vector extension) to keep the knowledge base in the same database as operational data and agent memory. This avoids introducing a separate vector database while leveraging the existing PostgreSQL infrastructure.

```
Agent Thought: "I need to recommend a specific target machine type for this 
               GCE instance. Current: n2-standard-8 (4 vCPUs, 32GB). 
               Target: ~50% reduction in capacity."
         │
         ▼
┌─────────────────────────────────────────────────────────┐
│              Retrieval Tool Call                         │
│  retrieve_provider_context(                             │
│    provider='GCP',                                      │
│    resource_type='compute/instance',                    │
│    query='n2 machine type 4 vCPUs 16GB memory',        │
│    top_k=5                                              │
│  )                                                      │
├─────────────────────────────────────────────────────────┤
│              Retrieval Pipeline                          │
│  1. Embed query using same model as document chunks     │
│  2. Filter: provider='GCP' AND resource_type matches    │
│  3. Vector similarity search (cosine) within filtered   │
│     subset, returning top 5 chunks                      │
│  4. Return chunks with metadata and similarity scores   │
└─────────────────────────────────────────────────────────┘
         │
         ▼
Observation: [chunk about N2 standard machine types with specs table,
              chunk about gcloud set-machine-type command,
              chunk about sustained use discounts for N2 family, ...]
         │
         ▼
Next Thought: "n2-standard-4 has 4 vCPUs and 16GB memory at $0.1942/hour.
              The gcloud command is `gcloud compute instances set-machine-type`.
              Sustained use discount applies automatically. I can now produce
              the specific recommendation."
```

**Number of results retrieved:** 5 chunks per retrieval call (top_k=5). This provides sufficient context for most recommendations (target SKU specs, relevant CLI command, pricing info) without overwhelming the LLM's context window. The agent can issue multiple retrieval calls within a single ReAct episode if the first retrieval is insufficient — this is rare because the metadata filtering narrows the search space effectively.

## Example: How Retrieved Context Changes the Agent's Output

### Without Retrieval (Cloud-Agnostic Only)

The agent completes its analytical reasoning and produces:

> "Resource `projects/prod-analytics/zones/us-central1-a/instances/analytics-worker-02` is overprovisioned. Average CPU utilization: 12%. Average memory utilization: 18% over 30 days. Current provisioned capacity: 8 vCPUs, 32GB RAM. Recommended action: reduce capacity by approximately 50%. Estimated monthly savings: ~$142."

This is *correct* but **not actionable**. The FinOps engineer cannot execute "reduce capacity by approximately 50%" without additional research.

### With Retrieval (Provider-Specific Context Injected)

The agent retrieves from the knowledge base at the recommendation step. Retrieved chunks include:

- **Chunk 1:** N2 machine type specifications table — `n2-standard-4: 4 vCPUs, 16 GB memory, $0.0971/hour (us-central1)`
- **Chunk 2:** `gcloud compute instances set-machine-type` reference — syntax, required flags, constraint that instance must be stopped first
- **Chunk 3:** Sustained use discounts — N2 instances receive automatic discounts up to 20% for sustained monthly usage

The agent synthesizes this into:

> "VM `analytics-worker-02` in `prod-analytics` has averaged 12% CPU and 18% memory over 30 days. **Downgrade from `n2-standard-8` (8 vCPUs, 32GB, $0.1942/hr) to `n2-standard-4` (4 vCPUs, 16GB, $0.0971/hr).** Estimated savings: $142/month after sustained use discount. Note: instance must be stopped before resize. SRE assessment confirms no availability group membership — brief downtime is acceptable for this batch workload. [Approve] [Dismiss]"

The retrieval transformed a generic analytical conclusion into a specific, executable recommendation with the exact target SKU, dollar amounts, operational constraints (must stop instance), and the relevant CLI path. This is the difference between the agent being an analytical tool and being an actionable assistant.

## Key Retrieval Design Choices

### 1. Data Source Selection

The knowledge base exclusively contains **official provider documentation** — not community blogs, Stack Overflow answers, or third-party pricing aggregators. This choice sacrifices breadth (no community tips or workarounds) in favor of accuracy and auditability. Every chunk traces back to an official source URL that can be verified.

### 2. Retrieval Scope: Metadata Filtering Before Vector Search

Retrieval is **not** a pure semantic search across the entire corpus. The agent first applies structured metadata filters (`provider`, `resource_type`, `category`) to narrow the candidate set, then performs vector similarity search within that subset. This two-stage approach:

- Eliminates false matches from other providers (an Azure VM SKU document is never retrieved for a GCP recommendation)
- Reduces the search space by 80-90%, improving both precision and latency
- Allows the embedding model to focus on semantic nuance within a narrow domain rather than discriminating across the entire cloud computing landscape

### 3. Chunk Size and Granularity

512-token chunks with 50-token overlap, split at section boundaries. This size balances:

- **Sufficient context** — a machine type table with 5-6 entries fits in a single chunk
- **Specificity** — chunks are narrow enough that similarity scores are meaningful (a 2000-token document about "all GCP machine families" would match too broadly)
- **Context budget** — 5 chunks × 512 tokens = ~2,560 tokens of retrieved context, leaving ample room for the agent's reasoning trace and tool outputs in the LLM context window

### 4. Embedding Model

The same embedding model is used for both document indexing and query embedding (consistency is critical for cosine similarity to be meaningful). The model is chosen for strong performance on technical documentation retrieval — domain-specific terms like `n2-standard-4`, `gcloud compute`, and `committed use discount` must embed close to their conceptual descriptions.

### 5. Knowledge Base Update Pipeline

```
Source documents (GCP docs, pricing pages)
    │
    ▼
Automated weekly scrape → diff against existing chunks
    │
    ▼
Changed/new sections → re-chunk → re-embed → upsert into pgvector
    │
    ▼
Removed sections → mark chunks as deprecated (soft delete, not hard delete)
    │
    ▼
Validation: spot-check sample queries against updated chunks
```

Soft deletion of outdated chunks (rather than hard deletion) preserves auditability — if a past recommendation was informed by a chunk that has since been deprecated, the audit trail remains intact.

## Retrieval Failure Mode: Stale Knowledge Leading to Invalid Recommendations

### The Failure

The most significant retrieval-related failure mode is **stale knowledge** — the knowledge base contains outdated information that causes the agent to produce recommendations referencing deprecated SKUs, incorrect pricing, or removed machine types.

Concrete scenario: GCP deprecates the `n1-standard` family and replaces it with `n2-standard` at different price points. The knowledge base still contains `n1-standard` chunks. The agent retrieves these stale chunks and recommends: "Downgrade to `n1-standard-4` at $0.0475/hour." The user attempts to execute this and discovers the machine type is no longer available in their region, or the pricing is wrong. Trust in the agent erodes.

This failure is particularly insidious because:

1. The retrieval *appears* successful — a high-similarity chunk is returned with confident-looking specifications
2. The agent cannot distinguish a stale chunk from a current one by content alone
3. The recommendation looks precise and actionable, giving the user no reason to doubt it

### How the Design Reduces This Risk

**1. `last_verified` metadata on every chunk.** Each chunk carries a timestamp of when its source document was last validated. The retrieval tool filters out chunks where `last_verified` is older than a configurable threshold (default: 30 days). Stale chunks are excluded from results before the agent ever sees them.

**2. Automated freshness pipeline.** The weekly update pipeline re-scrapes source URLs and diffs against stored content. Chunks whose source content has changed are re-embedded and upserted. Chunks whose source URLs return 404 are flagged for review and excluded from retrieval.

**3. Confidence degradation for aging chunks.** Chunks that haven't been re-verified in 14+ days receive a retrieval score penalty (cosine similarity × freshness_factor, where freshness_factor decays from 1.0 to 0.7 over 30 days). This biases retrieval toward recently verified content without hard-excluding older chunks that may still be valid.

**4. Agent-level validation prompt.** The system prompt instructs the agent to include a caveat when retrieved pricing data is older than 7 days: "Pricing based on documentation verified on [date]. Confirm current pricing before executing." This shifts the trust boundary — the agent acknowledges uncertainty rather than presenting stale data as authoritative.

**5. Post-execution feedback loop.** When a recommendation is executed and the actual cost differs from the estimate by more than 10%, the system flags a potential knowledge staleness issue. The affected chunks are queued for immediate re-verification. This creates a self-healing mechanism — staleness that slips through the weekly pipeline is caught by real-world execution outcomes.

### Residual Risk

The design reduces but does not eliminate staleness risk. The 7-day window between update checks means a price change on day 1 could produce incorrect recommendations for up to 6 days. For critical recommendations (estimated savings > $1,000/month), the agent appends an explicit verification step: "This recommendation is based on pricing data. Verify current rates at [source_url] before approving." This accepts that retrieval cannot guarantee real-time accuracy and compensates with transparency.
