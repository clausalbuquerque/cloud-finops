from __future__ import annotations

import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock

from finops_ai.hitl.approval_engine import ApprovalEngine
from finops_ai.hitl.contracts import ApprovalOutcome, ApprovalStatus, HumanFeedbackDecision
from finops_ai.memory.contracts import OptimizationRecommendation
from finops_ai.monitoring.canary_watcher import (
    CanaryCheckpoint,
    CanarySession,
    CanaryStatus,
    CanaryWatcher,
)


class TestCanaryMonitorAndRollback(unittest.TestCase):
    def setUp(self) -> None:
        self.mock_repo = MagicMock()
        self.mock_sink = MagicMock()
        self.approval_engine = ApprovalEngine(
            memory_repo=self.mock_repo,
            observability_sink=self.mock_sink,
        )
        self.watcher = CanaryWatcher(
            approval_engine=self.approval_engine,
            observability_sink=self.mock_sink,
            cpu_threshold=90.0,
            memory_threshold=90.0,
        )

    def _create_executed_recommendation(
        self,
        rec_id: str = "rec-canary-01",
        res_id: str = "analytics-worker-02",
        baseline_sku: str = "n2-standard-16",
        target_sku: str = "n2-standard-8",
    ) -> OptimizationRecommendation:
        rec = OptimizationRecommendation(
            id=rec_id,
            resource_id=res_id,
            resource_type="compute/instance",
            recommendation_type="rightsize",
            current_state={"current_sku": baseline_sku},
            proposed_state={"target_sku": target_sku},
            estimated_monthly_savings=142.25,
            confidence_score=0.92,
            provider_name="GCP",
            status="proposed",
            sre_assessment={"safe_to_modify": True},
        )
        self.approval_engine.propose(rec)
        self.approval_engine.process_feedback(
            recommendation_id=rec_id,
            decision=HumanFeedbackDecision(
                recommendation_id=rec_id,
                reviewer_id="lead_sre@corp.internal",
                reviewer_role="finops_engineer",
                outcome=ApprovalOutcome.APPROVED,
            ),
        )
        self.approval_engine.execute(rec_id, dry_run=True)
        return rec

    def test_canary_session_window_tracking(self) -> None:
        start_time = datetime(2026, 9, 4, 12, 0, 0, tzinfo=timezone.utc)
        session = self.watcher.start_canary(
            recommendation_id="rec-001",
            resource_id="worker-01",
            baseline_sku="n2-standard-16",
            target_sku="n2-standard-8",
            duration_minutes=60,
            started_at=start_time,
        )

        self.assertEqual(session.status, CanaryStatus.ACTIVE)
        self.assertEqual(session.duration_minutes, 60)

        # After 25 minutes, 35 minutes remaining
        time_25m = start_time + timedelta(minutes=25)
        self.assertAlmostEqual(session.remaining_minutes(time_25m), 35.0, places=1)
        self.assertFalse(session.is_expired(time_25m))

        # After 65 minutes, window is expired
        time_65m = start_time + timedelta(minutes=65)
        self.assertEqual(session.remaining_minutes(time_65m), 0.0)
        self.assertTrue(session.is_expired(time_65m))

    def test_normal_telemetry_healthy_completion(self) -> None:
        start_time = datetime(2026, 9, 4, 12, 0, 0, tzinfo=timezone.utc)
        self.watcher.start_canary(
            recommendation_id="rec-healthy",
            resource_id="worker-healthy",
            baseline_sku="n2-standard-16",
            target_sku="n2-standard-8",
            duration_minutes=60,
            started_at=start_time,
        )

        # Normal telemetry sample
        cp = self.watcher.record_checkpoint(
            recommendation_id="rec-healthy",
            cpu_utilization=45.0,
            memory_utilization=50.0,
            error_rate=0.1,
            heartbeat_ok=True,
        )
        self.assertFalse(cp.is_degraded)
        self.assertEqual(len(cp.degradation_reasons), 0)

        session = self.watcher.get_session("rec-healthy")
        self.assertIsNotNone(session)
        self.assertEqual(session.status, CanaryStatus.ACTIVE)

        # Conclude window after 60m
        concluded = self.watcher.check_window_expiration(
            "rec-healthy",
            current_time=start_time + timedelta(minutes=61),
        )
        self.assertEqual(concluded.status, CanaryStatus.HEALTHY)

    def test_cpu_breach_triggers_degraded_alert(self) -> None:
        self.watcher.start_canary(
            recommendation_id="rec-cpu-spike",
            resource_id="worker-spike",
            baseline_sku="n2-standard-16",
            target_sku="n2-standard-8",
        )

        # Spike to 94.2% CPU
        cp = self.watcher.record_checkpoint(
            recommendation_id="rec-cpu-spike",
            cpu_utilization=94.2,
            memory_utilization=65.0,
        )

        self.assertTrue(cp.is_degraded)
        self.assertTrue(any("CPU utilization (94.2%) breached" in r for r in cp.degradation_reasons))

        session = self.watcher.get_session("rec-cpu-spike")
        self.assertEqual(session.status, CanaryStatus.DEGRADED)
        self.assertTrue(session.alert_triggered)

    def test_memory_and_heartbeat_failure(self) -> None:
        self.watcher.start_canary(
            recommendation_id="rec-mem-fail",
            resource_id="worker-mem",
            baseline_sku="n2-standard-16",
            target_sku="n2-standard-8",
        )

        # Memory breach + heartbeat failure
        cp = self.watcher.record_checkpoint(
            recommendation_id="rec-mem-fail",
            cpu_utilization=70.0,
            memory_utilization=95.0,
            heartbeat_ok=False,
        )

        self.assertTrue(cp.is_degraded)
        self.assertEqual(len(cp.degradation_reasons), 2)
        session = self.watcher.get_session("rec-mem-fail")
        self.assertEqual(session.status, CanaryStatus.DEGRADED)

    def test_rollback_execution_restores_baseline_sku(self) -> None:
        self._create_executed_recommendation(
            rec_id="rec-rollback-test",
            res_id="analytics-worker-02",
            baseline_sku="n2-standard-16",
            target_sku="n2-standard-8",
        )

        self.watcher.start_canary(
            recommendation_id="rec-rollback-test",
            resource_id="analytics-worker-02",
            baseline_sku="n2-standard-16",
            target_sku="n2-standard-8",
        )

        # Record degradation
        self.watcher.record_checkpoint(
            recommendation_id="rec-rollback-test",
            cpu_utilization=93.5,
            memory_utilization=88.0,
        )

        # Trigger 1-click rollback
        res = self.watcher.trigger_rollback(
            recommendation_id="rec-rollback-test",
            reason="CPU breached 90% canary limit",
            initiated_by="oncall_sre",
        )

        self.assertEqual(res.status, ApprovalStatus.ROLLED_BACK)
        self.assertEqual(res.restored_sku, "n2-standard-16")
        self.assertIn("n2-standard-16", res.rollback_command)
        self.assertEqual(res.rolled_back_by, "oncall_sre")

        session = self.watcher.get_session("rec-rollback-test")
        self.assertEqual(session.status, CanaryStatus.ROLLED_BACK)
        self.assertTrue(session.rollback_executed)

    def test_automated_rollback_on_degradation(self) -> None:
        self._create_executed_recommendation(
            rec_id="rec-auto-rollback",
            res_id="analytics-worker-02",
            baseline_sku="n2-standard-16",
            target_sku="n2-standard-8",
        )

        # Enable auto_rollback
        self.watcher.start_canary(
            recommendation_id="rec-auto-rollback",
            resource_id="analytics-worker-02",
            baseline_sku="n2-standard-16",
            target_sku="n2-standard-8",
            auto_rollback=True,
        )

        # Severe spike
        self.watcher.record_checkpoint(
            recommendation_id="rec-auto-rollback",
            cpu_utilization=96.0,
            memory_utilization=92.0,
        )

        session = self.watcher.get_session("rec-auto-rollback")
        self.assertEqual(session.status, CanaryStatus.ROLLED_BACK)
        self.assertTrue(session.rollback_executed)
        self.assertIn("Automated rollback", session.rollback_reason)

    def test_rollback_fails_if_not_executed(self) -> None:
        unexecuted_rec = OptimizationRecommendation(
            id="rec-unexecuted",
            resource_id="worker-unexecuted",
            resource_type="compute/instance",
            recommendation_type="rightsize",
            current_state={"current_sku": "n2-standard-16"},
            proposed_state={"target_sku": "n2-standard-8"},
            estimated_monthly_savings=50.0,
            confidence_score=0.9,
            status="proposed",
        )
        self.approval_engine.propose(unexecuted_rec)

        with self.assertRaises(PermissionError):
            self.approval_engine.rollback("rec-unexecuted")


if __name__ == "__main__":
    unittest.main()
