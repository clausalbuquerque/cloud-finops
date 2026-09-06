#!/usr/bin/env python3
"""CLI runner for the full FinOps Agentic Engine Integration Test Suite.

Executes all test modules, calculates SLO latencies, and outputs formatted summary.
"""

from __future__ import annotations

import sys
import time
import unittest


def main() -> int:
    print("\n" + "=" * 75)
    print(" 🧪 CLOUD FINOPS AGENTIC ENGINE INTEGRATION TEST SUITE")
    print("=" * 75)

    loader = unittest.TestLoader()
    suite = loader.discover("tests", pattern="test_*.py")

    start_time = time.time()
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    elapsed = time.time() - start_time

    print("\n" + "=" * 75)
    print(" 📊 INTEGRATION TEST SUITE SUMMARY")
    print("=" * 75)
    print(f" -> Total Tests Executed: {result.testsRun}")
    print(f" -> Passed: {result.testsRun - len(result.failures) - len(result.errors)}")
    print(f" -> Failures: {len(result.failures)}")
    print(f" -> Errors: {len(result.errors)}")
    print(f" -> Total Elapsed Time: {elapsed:.3f}s")
    print(f" -> Average Latency per Test: {(elapsed / max(result.testsRun, 1)) * 1000:.2f}ms")

    if result.wasSuccessful():
        print("\n ✅ ALL AGENT ENGINE INTEGRATION TESTS PASSED (100% SUCCESS RATE)")
        print("=" * 75 + "\n")
        return 0
    else:
        print("\n ❌ INTEGRATION SUITE ENCOUNTERED FAILURES/ERRORS")
        print("=" * 75 + "\n")
        return 1


if __name__ == "__main__":
    sys.exit(main())

