# TASK-033 Manual Verification Checklist

Date: 2026-08-08

Evidence inputs:

- `docs/e2e-validation-report.json`
- `docs/task-033-e2e-documentation-report.md`
- latest scheduler/run-status command outputs from dev/staging/prod environments

## Representative FinOps Use Cases

1. Rightsizing recommendation for under-utilized compute instance
- [ ] Recommendation is actionable and includes provider context sources
- [ ] Savings estimate/rationale are coherent
- Pass criteria: recommendation references relevant GCP source snippets and no contradictory action guidance.

2. Pricing-context validation
- [ ] Recommendation includes current pricing references
- [ ] Stale-pricing warning appears for aged pricing evidence
- Pass criteria: warning appears when pricing evidence exceeds freshness expectation.

3. Constraint-sensitive recommendation
- [ ] Statefulness/operational constraints are reflected in recommendation wording
- Pass criteria: recommendation avoids unsafe resize language for stateful/high-risk workloads.

4. Failure/fallback behavior
- [ ] Retrieval failure or empty context still returns safe fallback recommendation
- Pass criteria: response remains actionable and never includes broken citation placeholders.

5. SLO and reliability checks
- [ ] Retrieval latency is within configured threshold for sampled runs
- [ ] Recommendation latency is within configured threshold for sampled runs
- [ ] No unresolved ingestion/index failures in latest run-status output

## Sign-off

- FinOps reviewer: [ ]
- SRE reviewer: [ ]
- Product/owner reviewer: [ ]

Notes:

Final decision:

- [ ] Go
- [ ] No-Go
