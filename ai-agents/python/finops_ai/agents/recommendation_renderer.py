from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Protocol
from uuid import uuid4

from finops_ai.observability import LoggingObservabilitySink, ObservabilitySink
from finops_ai.retrieval import RetrieveProviderContextInput, RetrieveProviderContextOutput, RetrievedChunk
from finops_ai.retrieval.freshness import chunk_age_days

from .contracts import RecommendationCandidate, RenderedRecommendation


class RetrievalServiceProtocol(Protocol):
    def retrieve_provider_context(
        self,
        request: RetrieveProviderContextInput,
    ) -> RetrieveProviderContextOutput: ...


@dataclass(frozen=True)
class RecommendationRendererConfig:
    retrieval_top_k: int = 5
    retrieval_min_score: float = 0.5
    retrieval_max_age_days: int = 30
    high_savings_warning_threshold_usd: float = 100.0
    pricing_low_freshness_days: int = 21
    observability_sink: ObservabilitySink | None = None


class RecommendationRenderer:
    def __init__(
        self,
        retrieval_service: RetrievalServiceProtocol,
        config: RecommendationRendererConfig | None = None,
    ) -> None:
        self._retrieval_service = retrieval_service
        self._config = config or RecommendationRendererConfig()
        self._sink = self._config.observability_sink or LoggingObservabilitySink()

    def render(self, candidate: RecommendationCandidate) -> RenderedRecommendation:
        trace_id = str(uuid4())
        self._sink.emit(
            "recommendation.start",
            {
                "trace_id": trace_id,
                "provider": candidate.provider,
                "resource_type": candidate.resource_type,
                "resource_name": candidate.resource_name,
                "estimated_monthly_savings_usd": candidate.estimated_monthly_savings_usd,
            },
        )

        retrieval_request = RetrieveProviderContextInput(
            provider=candidate.provider,
            resource_type=candidate.resource_type,
            query=f"{candidate.action_summary}. {candidate.rationale}",
            top_k=self._config.retrieval_top_k,
            max_age_days=self._config.retrieval_max_age_days,
            trace_id=trace_id,
            parent_step="agent.recommendation.render",
        )

        retrieval_result = self._retrieval_service.retrieve_provider_context(retrieval_request)
        high_confidence_chunks = [
            chunk for chunk in retrieval_result.chunks if chunk.score >= self._config.retrieval_min_score
        ]

        if not high_confidence_chunks:
            fallback = self._render_fallback(candidate)
            self._sink.emit(
                "recommendation.complete",
                {
                    "trace_id": trace_id,
                    "used_retrieval": False,
                    "source_count": 0,
                    "fallback_used": True,
                },
            )
            return fallback

        context_lines = [
            f"- [{chunk.category}] {chunk.content[:180].strip()} (source: {chunk.source_url})"
            for chunk in high_confidence_chunks
        ]

        warning_line = self._build_pricing_staleness_warning(candidate, high_confidence_chunks)
        warning_block = f"{warning_line}\n\n" if warning_line else ""

        body = (
            f"Resource: {candidate.resource_name}\n"
            f"Action: {candidate.action_summary}\n"
            f"Rationale: {candidate.rationale}\n"
            f"Estimated monthly savings: ${candidate.estimated_monthly_savings_usd:.2f}\n\n"
            + warning_block
            +
            "Provider context:\n"
            + "\n".join(context_lines)
        )

        output = RenderedRecommendation(
            title=f"Optimization for {candidate.resource_name}",
            body=body,
            used_retrieval=True,
            fallback_note=warning_line,
        )
        self._sink.emit(
            "recommendation.complete",
            {
                "trace_id": trace_id,
                "used_retrieval": True,
                "source_count": len(high_confidence_chunks),
                "fallback_used": False,
                "warning_present": warning_line is not None,
            },
        )
        return output

    @staticmethod
    def _render_fallback(candidate: RecommendationCandidate) -> RenderedRecommendation:
        body = (
            f"Resource: {candidate.resource_name}\n"
            f"Action: {candidate.action_summary}\n"
            f"Rationale: {candidate.rationale}\n"
            f"Estimated monthly savings: ${candidate.estimated_monthly_savings_usd:.2f}\n\n"
            "Provider-specific details unavailable. Verify target configuration manually."
        )
        return RenderedRecommendation(
            title=f"Optimization for {candidate.resource_name}",
            body=body,
            used_retrieval=False,
            fallback_note="Provider-specific details unavailable. Verify target configuration manually.",
        )

    def _build_pricing_staleness_warning(
        self,
        candidate: RecommendationCandidate,
        chunks: list[RetrievedChunk],
    ) -> str | None:
        if candidate.estimated_monthly_savings_usd < self._config.high_savings_warning_threshold_usd:
            return None

        pricing_chunks = [chunk for chunk in chunks if chunk.category == "pricing"]
        if not pricing_chunks:
            return None

        now = datetime.now(timezone.utc)
        lowest_freshness = max(
            (chunk_age_days(last_verified=chunk.last_verified, now=now) for chunk in pricing_chunks),
            default=0.0,
        )
        if lowest_freshness < self._config.pricing_low_freshness_days:
            return None

        return (
            "Warning: Pricing evidence is aging. Validate current provider pricing "
            "before executing this high-savings change."
        )


def summarize_analysis_without_retrieval(
    anomaly_summary: str,
    forecast_summary: str,
) -> str:
    """
    Guardrail helper: core analytical summaries must not depend on retrieval.
    """
    return f"Anomaly: {anomaly_summary}\nForecast: {forecast_summary}"
