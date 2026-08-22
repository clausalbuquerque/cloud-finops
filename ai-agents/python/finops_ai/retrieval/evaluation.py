from __future__ import annotations

from dataclasses import dataclass
from urllib.parse import urlparse


@dataclass(frozen=True)
class RetrievalEvalCase:
    case_id: str
    provider: str
    resource_type: str
    query: str
    category: str | None
    expected_chunk_ids: list[str]
    expected_source_domains: list[str]
    disallowed_providers: list[str]


@dataclass(frozen=True)
class RetrievalEvalHit:
    chunk_id: str
    provider: str
    source_url: str
    score: float


@dataclass(frozen=True)
class RetrievalEvalThresholds:
    min_recall_at_k: float
    min_mrr_at_k: float
    min_source_citation_coverage: float
    max_cross_provider_contamination_rate: float


@dataclass(frozen=True)
class RetrievalEvalSummary:
    query_count: int
    recall_at_k: float
    mrr_at_k: float
    source_citation_coverage: float
    cross_provider_contamination_rate: float
    passed: bool


def _source_domain(url: str) -> str:
    parsed = urlparse(url)
    return parsed.netloc.lower()


def evaluate_retrieval_results(
    cases: list[RetrievalEvalCase],
    ranked_hits_by_case: dict[str, list[RetrievalEvalHit]],
    k: int,
    thresholds: RetrievalEvalThresholds,
) -> RetrievalEvalSummary:
    if not cases:
        return RetrievalEvalSummary(
            query_count=0,
            recall_at_k=0.0,
            mrr_at_k=0.0,
            source_citation_coverage=0.0,
            cross_provider_contamination_rate=0.0,
            passed=False,
        )

    recall_values: list[float] = []
    reciprocal_ranks: list[float] = []
    source_citation_hits = 0
    contamination_hits = 0

    for case in cases:
        ranked_hits = ranked_hits_by_case.get(case.case_id, [])[:k]

        relevant = set(case.expected_chunk_ids)
        if relevant:
            found_relevant = [hit for hit in ranked_hits if hit.chunk_id in relevant]
            recall_values.append(len(found_relevant) / len(relevant))
        else:
            recall_values.append(0.0)

        rr = 0.0
        for idx, hit in enumerate(ranked_hits, start=1):
            if hit.chunk_id in relevant:
                rr = 1.0 / idx
                break
        reciprocal_ranks.append(rr)

        expected_domains = {domain.lower() for domain in case.expected_source_domains}
        if any(_source_domain(hit.source_url) in expected_domains for hit in ranked_hits):
            source_citation_hits += 1

        disallowed = {provider.upper() for provider in case.disallowed_providers}
        if any(hit.provider.upper() in disallowed for hit in ranked_hits):
            contamination_hits += 1

    case_count = len(cases)
    recall_at_k = sum(recall_values) / case_count
    mrr_at_k = sum(reciprocal_ranks) / case_count
    source_citation_coverage = source_citation_hits / case_count
    cross_provider_contamination_rate = contamination_hits / case_count

    passed = (
        recall_at_k >= thresholds.min_recall_at_k
        and mrr_at_k >= thresholds.min_mrr_at_k
        and source_citation_coverage >= thresholds.min_source_citation_coverage
        and cross_provider_contamination_rate <= thresholds.max_cross_provider_contamination_rate
    )

    return RetrievalEvalSummary(
        query_count=case_count,
        recall_at_k=recall_at_k,
        mrr_at_k=mrr_at_k,
        source_citation_coverage=source_citation_coverage,
        cross_provider_contamination_rate=cross_provider_contamination_rate,
        passed=passed,
    )
