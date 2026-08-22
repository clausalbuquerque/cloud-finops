from __future__ import annotations

from datetime import datetime, timezone
import unittest

from finops_ai.retrieval import RetrievedChunk
from finops_ai.retrieval.reverification import (
    ReverificationRequest,
    estimate_drift_pct,
    trigger_reverification_on_drift,
)


class FakeReverificationQueue:
    def __init__(self) -> None:
        self.requests: list[ReverificationRequest] = []

    def enqueue(self, request: ReverificationRequest) -> None:
        self.requests.append(request)


class ReverificationPolicyTests(unittest.TestCase):
    def test_drift_below_threshold_does_not_enqueue(self) -> None:
        queue = FakeReverificationQueue()
        chunk = RetrievedChunk(
            chunk_id="kb1",
            content="Pricing context",
            score=0.9,
            source_url="https://cloud.google.com/pricing",
            last_verified=datetime.now(timezone.utc),
            category="pricing",
            provider="GCP",
            resource_type="compute/instance",
        )

        enqueued = trigger_reverification_on_drift(
            chunks=[chunk],
            estimated_monthly_savings_usd=100.0,
            actual_monthly_savings_usd=92.0,
            queue=queue,
            drift_threshold_pct=10.0,
        )

        self.assertEqual(0, enqueued)
        self.assertEqual(0, len(queue.requests))

    def test_drift_above_threshold_enqueues_sources(self) -> None:
        queue = FakeReverificationQueue()
        chunk = RetrievedChunk(
            chunk_id="kb2",
            content="Pricing context",
            score=0.9,
            source_url="https://cloud.google.com/pricing",
            last_verified=datetime.now(timezone.utc),
            category="pricing",
            provider="GCP",
            resource_type="compute/instance",
        )

        enqueued = trigger_reverification_on_drift(
            chunks=[chunk],
            estimated_monthly_savings_usd=100.0,
            actual_monthly_savings_usd=70.0,
            queue=queue,
            drift_threshold_pct=10.0,
        )

        self.assertEqual(1, enqueued)
        self.assertEqual(1, len(queue.requests))
        self.assertEqual("post_execution_drift_exceeded", queue.requests[0].reason)

    def test_drift_percentage_calculation(self) -> None:
        self.assertAlmostEqual(30.0, estimate_drift_pct(100.0, 70.0), places=4)


if __name__ == "__main__":
    unittest.main()
