# Source Governance Review Workflow

Use this workflow before adding any new ingestion source to the registry.

## Required Review Metadata

Every non-default source must include:

- `review_ticket`: Security/governance ticket ID
- `approved_by`: Approver identity (team alias or reviewer)

If either field is missing, `SourceRegistry` rejects the source.

## Review Checklist

1. Validate source domain is official provider documentation.
2. Verify document scope is relevant to FinOps recommendations.
3. Confirm legal/compliance posture for content usage.
4. Define integrity expectations if publisher hashes/signatures are available.
5. Record approval in ticket and update source definition.

## Integrity Policy

Where available, configure one or more:

- `expected_raw_content_sha256`
- `signature_header_name`

The ingestion service runs integrity checks before persistence. Failures stop document persistence and mark the run as failed.
