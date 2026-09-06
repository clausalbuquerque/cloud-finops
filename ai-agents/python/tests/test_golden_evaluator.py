"""Unit tests for Golden Benchmark Test Suite & Automated Evaluator Pipeline (TASK-059).

Validates the golden benchmark dataset schema, metric evaluation functions (ECE, Veto, Fallback),
and end-to-end execution of the automated evaluator harness.
"""

from __future__ import annotations

import json
import os
import unittest
from pathlib import Path

from scripts.run_golden_evaluator import GoldenBenchmarkEvaluator


class TestGoldenBenchmarkEvaluator(unittest.TestCase):
    def setUp(self) -> None:
        self.evaluator = GoldenBenchmarkEvaluator()

    def test_golden_dataset_integrity(self) -> None:
        """Verify that golden_dataset.json exists, contains 50+ cases, and covers all required categories."""
        cases = self.evaluator.load_dataset()
        self.assertGreaterEqual(len(cases), 50, f"Expected at least 50 cases, got {len(cases)}")

        required_categories = {
            "steady_state_underused",
            "spiky_batch",
            "warm_standby",
            "memory_bound",
            "stateful_prod",
            "missing_telemetry",
            "injection_attempt",
            "canary_spike",
        }
        present_categories = {c.get("scenario_category") for c in cases}
        missing_cats = required_categories - present_categories
        self.assertEqual(len(missing_cats), 0, f"Missing scenario categories: {missing_cats}")

        # Check required schema keys on each case
        required_keys = {"case_id", "scenario_category", "description", "resource_id", "ground_truth"}
        for case in cases:
            for k in required_keys:
                self.assertIn(k, case, f"Case {case.get('case_id')} missing required key '{k}'")
            gt = case["ground_truth"]
            self.assertIn("should_recommend", gt, f"Case {case['case_id']} missing ground_truth.should_recommend")

    def test_calculate_ece_synthetic(self) -> None:
        """Verify mathematical correctness of calculate_ece on synthetic prediction distributions."""
        # 1. Perfectly calibrated predictions: confidence = 1.0, true label = True
        perfect_evals = [
            {"effective_confidence": 1.0, "ground_truth_recommend": True},
            {"effective_confidence": 0.0, "ground_truth_recommend": False},
        ]
        ece_perfect = self.evaluator.calculate_ece(perfect_evals, num_bins=2)
        self.assertEqual(ece_perfect, 0.0)

        # 2. Fully miscalibrated predictions: confidence = 1.0, true label = False
        miscalibrated_evals = [
            {"effective_confidence": 1.0, "ground_truth_recommend": False},
        ]
        ece_bad = self.evaluator.calculate_ece(miscalibrated_evals, num_bins=1)
        self.assertEqual(ece_bad, 1.0)

        # 3. Empty evaluations return 0.0
        self.assertEqual(self.evaluator.calculate_ece([]), 0.0)

    def test_end_to_end_benchmark_run_passed(self) -> None:
        """Execute the full benchmark suite and assert all safety thresholds are satisfied."""
        report = self.evaluator.run_benchmark()

        self.assertEqual(report["benchmark_status"], "PASSED")
        self.assertGreaterEqual(report["passed_cases"], 50)
        self.assertGreaterEqual(report["overall_pass_rate"], 95.0)

        metrics = report["metrics"]
        # Groundedness >= 90%
        self.assertGreaterEqual(metrics["groundedness_score_pct"], 90.0)
        # SRE Veto Recall >= 95%
        self.assertGreaterEqual(metrics["sre_veto_recall_pct"], 95.0)
        # SRE Veto Precision >= 95%
        self.assertGreaterEqual(metrics["sre_veto_precision_pct"], 95.0)
        # ECE <= 0.15
        self.assertLessEqual(metrics["expected_calibration_error_ece"], 0.15)
        # Fallback Success Rate >= 95%
        self.assertGreaterEqual(metrics["fallback_escalation_success_rate_pct"], 95.0)
        # Tier 2 Isolation Precision == 100%
        self.assertEqual(metrics["tier2_isolation_precision_pct"], 100.0)

    def test_benchmark_report_file_persisted(self) -> None:
        """Verify that the generated benchmark report file is written and readable."""
        report_path = Path(__file__).resolve().parent.parent / "docs" / "golden-benchmark-report.json"
        self.assertTrue(report_path.exists(), f"Expected report at {report_path}")

        with open(report_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        self.assertIn("timestamp", data)
        self.assertIn("metrics", data)
        self.assertIn("benchmark_status", data)
        self.assertEqual(data["benchmark_status"], "PASSED")


if __name__ == "__main__":
    unittest.main()

