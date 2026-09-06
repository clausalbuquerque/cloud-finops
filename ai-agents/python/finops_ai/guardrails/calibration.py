from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

class CalibratedConfidenceReport(BaseModel):
    """Deterministic confidence report detailing ambiguity and risk."""
    overall_confidence: float = Field(ge=0.0, le=1.0)
    telemetry_completeness_score: float = Field(ge=0.0, le=1.0)
    headroom_margin_score: float = Field(ge=0.0, le=1.0)
    rag_similarity_score: float = Field(ge=0.0, le=1.0)
    is_ambiguous: bool
    escalation_required: bool
    ambiguity_reasons: list[str] = Field(default_factory=list)
    weights_used: dict[str, float] = Field(default_factory=dict)


class ConfidenceCalibrationScorer:
    """Computes deterministic confidence scores based on objective evidence metrics."""
    
    def __init__(
        self,
        w_telemetry: float = 0.35,
        w_headroom: float = 0.40,
        w_rag: float = 0.25,
        escalation_threshold: float = 0.85,
    ) -> None:
        self.w_telemetry = w_telemetry
        self.w_headroom = w_headroom
        self.w_rag = w_rag
        self.escalation_threshold = escalation_threshold

    def score_telemetry_completeness(self, metrics: dict[str, Any] | list[dict[str, Any]]) -> tuple[float, list[str]]:
        reasons = []
        score = 0.0
        
        has_cpu = False
        has_mem = False
        sample_count = 0
        
        # Parse list or dict
        if isinstance(metrics, dict):
            metrics_list = [metrics]
        else:
            metrics_list = metrics or []
            
        for m in metrics_list:
            if "cpu" in str(m).lower() or m.get("metric_name", "").lower() == "cpu":
                has_cpu = True
            if "memory" in str(m).lower() or m.get("metric_name", "").lower() == "memory" or "mem" in str(m).lower():
                has_mem = True
            
            samples = m.get("sample_count", 0)
            if isinstance(samples, int):
                sample_count += samples

        if has_cpu:
            score += 0.4
        if has_mem:
            score += 0.4
        else:
            reasons.append("MISSING_MEMORY_TELEMETRY")
            
        if sample_count >= 24:
            score += 0.2
        elif sample_count > 0:
            score += 0.1
        else:
            reasons.append("LOW_SAMPLE_COUNT")
            
        if not has_cpu and not has_mem:
            score = 0.0
            reasons.append("NO_CRITICAL_TELEMETRY")
            
        return min(1.0, score), reasons

    def score_headroom_margin(
        self,
        peak_cpu: float | None = None,
        peak_memory: float | None = None,
        cpu_limit: float = 75.0,
        mem_limit: float = 80.0
    ) -> tuple[float, list[str]]:
        reasons = []
        score = 1.0
        
        cpu_val = peak_cpu if peak_cpu is not None else 0.0
        mem_val = peak_memory if peak_memory is not None else 0.0
        
        if cpu_val > cpu_limit:
            reasons.append("HEADROOM_THRESHOLD_BREACH_CPU")
            return 0.0, reasons
            
        if mem_val > mem_limit:
            reasons.append("HEADROOM_THRESHOLD_BREACH_MEM")
            return 0.0, reasons
            
        # Normalize distance from safe limit
        # Example: if limit is 75 and peak is 50, distance is 25.
        cpu_margin_score = (cpu_limit - cpu_val) / cpu_limit if cpu_limit > 0 else 0
        mem_margin_score = (mem_limit - mem_val) / mem_limit if mem_limit > 0 else 0
        
        score = (cpu_margin_score + mem_margin_score) / 2.0
        
        # Scale score to [0.5, 1.0] if under limits to maintain decent score
        score = 0.5 + (score * 0.5)
        
        if peak_cpu is None and peak_memory is None:
            return 0.5, ["MISSING_HEADROOM_DATA"]
            
        return min(1.0, max(0.0, score)), reasons

    def score_rag_similarity(self, sku_found: bool, similarity_score: float = 1.0, is_exact_match: bool = False) -> tuple[float, list[str]]:
        reasons = []
        if not sku_found:
            reasons.append("SKU_NOT_FOUND")
            return 0.0, reasons
            
        if is_exact_match:
            return 1.0, reasons
            
        if similarity_score < 0.7:
            reasons.append("LOW_RAG_SIMILARITY")
            
        return min(1.0, max(0.0, similarity_score)), reasons

    def compute_confidence(
        self,
        metrics: dict[str, Any] | list[dict[str, Any]] | None = None,
        peak_cpu: float | None = None,
        peak_memory: float | None = None,
        cpu_limit: float = 75.0,
        mem_limit: float = 80.0,
        sku_found: bool = True,
        sku_similarity: float = 1.0,
        is_exact_sku: bool = True,
    ) -> CalibratedConfidenceReport:
        t_score, t_reasons = self.score_telemetry_completeness(metrics or [])
        h_score, h_reasons = self.score_headroom_margin(peak_cpu, peak_memory, cpu_limit, mem_limit)
        r_score, r_reasons = self.score_rag_similarity(sku_found, sku_similarity, is_exact_sku)
        
        overall = (
            self.w_telemetry * t_score +
            self.w_headroom * h_score +
            self.w_rag * r_score
        )
        
        reasons = t_reasons + h_reasons + r_reasons
        is_ambiguous = overall < self.escalation_threshold or "MISSING_MEMORY_TELEMETRY" in reasons
        
        return CalibratedConfidenceReport(
            overall_confidence=round(overall, 4),
            telemetry_completeness_score=round(t_score, 4),
            headroom_margin_score=round(h_score, 4),
            rag_similarity_score=round(r_score, 4),
            is_ambiguous=is_ambiguous,
            escalation_required=is_ambiguous,
            ambiguity_reasons=reasons,
            weights_used={
                "telemetry": self.w_telemetry,
                "headroom": self.w_headroom,
                "rag": self.w_rag,
            }
        )
