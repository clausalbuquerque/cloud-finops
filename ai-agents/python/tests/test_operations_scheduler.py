from __future__ import annotations

import json
import tempfile
import unittest

from finops_ai.operations import OperationsScheduler, OperationsSchedulerConfig


class OperationsSchedulerTests(unittest.TestCase):
    def test_default_intervals_cover_weekly_and_incremental(self) -> None:
        config = OperationsSchedulerConfig()
        self.assertEqual(7 * 24 * 60 * 60, config.weekly_ingestion_interval_seconds)
        self.assertEqual(24 * 60 * 60, config.incremental_indexing_interval_seconds)

    def test_retry_eventually_succeeds(self) -> None:
        attempts = {"count": 0}

        def flaky_job() -> dict[str, object]:
            attempts["count"] += 1
            if attempts["count"] < 2:
                raise RuntimeError("transient")
            return {"ok": True}

        scheduler = OperationsScheduler(
            OperationsSchedulerConfig(max_retries=3, retry_backoff_seconds=0.0)
        )
        result = scheduler.run_with_retry("job:flaky", flaky_job)

        self.assertTrue(result.success)
        self.assertEqual(2, result.attempts)
        self.assertEqual({"ok": True}, result.payload)

    def test_dead_letter_written_after_retry_exhaustion(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            dead_letter_path = f"{temp_dir}/dead-letter.jsonl"

            def failing_job() -> dict[str, object]:
                raise RuntimeError("hard failure")

            scheduler = OperationsScheduler(
                OperationsSchedulerConfig(
                    max_retries=2,
                    retry_backoff_seconds=0.0,
                    dead_letter_path=dead_letter_path,
                )
            )
            result = scheduler.run_with_retry("job:failing", failing_job)

            self.assertFalse(result.success)
            self.assertEqual(2, result.attempts)

            with open(dead_letter_path, "r", encoding="utf-8") as handle:
                lines = [line.strip() for line in handle.readlines() if line.strip()]

            self.assertEqual(1, len(lines))
            payload = json.loads(lines[0])
            self.assertEqual("job:failing", payload["job_name"])
            self.assertIn("hard failure", payload["error"])


if __name__ == "__main__":
    unittest.main()
