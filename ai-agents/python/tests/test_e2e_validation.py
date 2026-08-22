from __future__ import annotations

import unittest

from finops_ai.operations import SLOThresholds, evaluate_slos


class E2EValidationTests(unittest.TestCase):
    def test_slo_passes_under_threshold(self) -> None:
        result = evaluate_slos(
            retrieval_latency_ms=400.0,
            recommendation_latency_ms=200.0,
            thresholds=SLOThresholds(max_retrieval_latency_ms=1500.0, max_recommendation_latency_ms=2000.0),
        )

        self.assertTrue(result.passed)
        self.assertEqual([], result.violations)

    def test_slo_fails_when_threshold_exceeded(self) -> None:
        result = evaluate_slos(
            retrieval_latency_ms=1800.0,
            recommendation_latency_ms=2200.0,
            thresholds=SLOThresholds(max_retrieval_latency_ms=1500.0, max_recommendation_latency_ms=2000.0),
        )

        self.assertFalse(result.passed)
        self.assertEqual(2, len(result.violations))


if __name__ == "__main__":
    unittest.main()
