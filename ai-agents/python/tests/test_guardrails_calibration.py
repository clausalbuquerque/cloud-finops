from __future__ import annotations

import unittest

from finops_ai.guardrails.calibration import (
    ConfidenceCalibrationScorer,
    CalibratedConfidenceReport,
)
from finops_ai.orchestration.contracts import FinOpsOrchestrationState
from finops_ai.orchestration.policy_gates import PolicyGateEngine


class TestConfidenceCalibrationScorer(unittest.TestCase):
    def setUp(self) -> None:
        self.scorer = ConfidenceCalibrationScorer()

    def test_perfect_telemetry_safe_headroom_exact_sku(self) -> None:
        metrics = [
            {"metric_name": "cpu_utilization", "sample_count": 72},
            {"metric_name": "memory_utilization", "sample_count": 72},
        ]
        report = self.scorer.compute_confidence(
            metrics=metrics,
            peak_cpu=50.0,
            peak_memory=60.0,
            sku_found=True,
            sku_similarity=1.0,
            is_exact_sku=True,
        )
        
        self.assertFalse(report.is_ambiguous)
        self.assertFalse(report.escalation_required)
        self.assertGreaterEqual(report.overall_confidence, 0.85)
        self.assertEqual(report.telemetry_completeness_score, 1.0)
        self.assertEqual(len(report.ambiguity_reasons), 0)

    def test_missing_memory_telemetry(self) -> None:
        metrics = [
            {"metric_name": "cpu_utilization", "sample_count": 24},
        ]
        report = self.scorer.compute_confidence(
            metrics=metrics,
            peak_cpu=50.0,
            peak_memory=None,
            sku_found=True,
            is_exact_sku=True,
        )
        
        self.assertTrue(report.is_ambiguous)
        self.assertIn("MISSING_MEMORY_TELEMETRY", report.ambiguity_reasons)
        self.assertLess(report.overall_confidence, 0.85)
        # 0.4 CPU + 0.2 sample count = 0.6
        self.assertAlmostEqual(report.telemetry_completeness_score, 0.6)

    def test_headroom_breach(self) -> None:
        metrics = [
            {"metric_name": "cpu_utilization", "sample_count": 24},
            {"metric_name": "memory_utilization", "sample_count": 24},
        ]
        report = self.scorer.compute_confidence(
            metrics=metrics,
            peak_cpu=80.0,  # Limit is 75.0
            peak_memory=60.0,
            sku_found=True,
            is_exact_sku=True,
        )
        
        self.assertTrue(report.is_ambiguous)
        self.assertIn("HEADROOM_THRESHOLD_BREACH_CPU", report.ambiguity_reasons)
        self.assertEqual(report.headroom_margin_score, 0.0)
        self.assertLess(report.overall_confidence, 0.85)

    def test_unverified_sku_low_rag_similarity(self) -> None:
        metrics = [
            {"metric_name": "cpu_utilization", "sample_count": 24},
            {"metric_name": "memory_utilization", "sample_count": 24},
        ]
        report = self.scorer.compute_confidence(
            metrics=metrics,
            peak_cpu=40.0,
            peak_memory=40.0,
            sku_found=True,
            sku_similarity=0.4,
            is_exact_sku=False,
        )
        
        self.assertTrue(report.is_ambiguous)
        self.assertIn("LOW_RAG_SIMILARITY", report.ambiguity_reasons)
        self.assertEqual(report.rag_similarity_score, 0.4)
        self.assertLess(report.overall_confidence, 0.85)


class TestPolicyGateIntegration(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = PolicyGateEngine()

    def test_policy_gate_passes_with_calibrated_score(self) -> None:
        report = CalibratedConfidenceReport(
            overall_confidence=0.92,
            telemetry_completeness_score=1.0,
            headroom_margin_score=0.9,
            rag_similarity_score=1.0,
            is_ambiguous=False,
            escalation_required=False,
            ambiguity_reasons=[]
        )
        state = FinOpsOrchestrationState(calibrated_confidence_report=report)
        res = self.engine.check_confidence_threshold(state)
        
        self.assertTrue(res.passed)
        self.assertFalse(res.fail_closed)
        self.assertIn("Calibrated confidence threshold satisfied", res.reason)

    def test_policy_gate_fails_with_ambiguous_calibrated_score(self) -> None:
        report = CalibratedConfidenceReport(
            overall_confidence=0.92,  # Score might be high but it could have an ambiguity flag
            telemetry_completeness_score=0.6,
            headroom_margin_score=0.9,
            rag_similarity_score=1.0,
            is_ambiguous=True,
            escalation_required=True,
            ambiguity_reasons=["MISSING_MEMORY_TELEMETRY"]
        )
        state = FinOpsOrchestrationState(calibrated_confidence_report=report)
        res = self.engine.check_confidence_threshold(state)
        
        self.assertFalse(res.passed)
        self.assertTrue(res.fail_closed)
        self.assertIn("MISSING_MEMORY_TELEMETRY", res.reason)


if __name__ == "__main__":
    unittest.main()
