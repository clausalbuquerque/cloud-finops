"""Post-Execution Canary Telemetry Monitor & Rollback Engine.

Enforces an active 60-minute observation window for applied rightsizing mutations.
Detects post-execution performance regressions (CPU/memory utilization > 90%, error spikes,
or heartbeat failures) and orchestrates 1-click or automated rollbacks to baseline SKUs.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field

from finops_ai.hitl.approval_engine import ApprovalEngine
from finops_ai.hitl.contracts import RollbackResult
from finops_ai.observability import LoggingObservabilitySink, ObservabilitySink


class CanaryStatus(str, Enum):
    """Lifecycle state of a post-execution canary observation session."""

    ACTIVE = "active"
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    ROLLED_BACK = "rolled_back"
    EXPIRED = "expired"


class CanaryCheckpoint(BaseModel):
    """Point-in-time telemetry sample evaluated during a canary observation window."""

    checkpoint_id: str = Field(default_factory=lambda: str(uuid4()))
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    cpu_utilization: float = Field(ge=0.0, le=100.0)
    memory_utilization: float = Field(ge=0.0, le=100.0)
    error_rate: float = Field(default=0.0, ge=0.0)
    heartbeat_ok: bool = True
    is_degraded: bool = False
    degradation_reasons: list[str] = Field(default_factory=list)


class CanarySession(BaseModel):
    """Tracks the 60-minute canary lifecycle and telemetry checkpoints for a resource."""

    session_id: str = Field(default_factory=lambda: str(uuid4()))
    recommendation_id: str
    resource_id: str
    baseline_sku: str
    target_sku: str
    started_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    duration_minutes: int = 60
    status: CanaryStatus = CanaryStatus.ACTIVE
    checkpoints: list[CanaryCheckpoint] = Field(default_factory=list)
    alert_triggered: bool = False
    rollback_executed: bool = False
    rollback_reason: str | None = None
    auto_rollback: bool = False

    def remaining_minutes(self, now: datetime | None = None) -> float:
        """Calculate the remaining observation time in minutes."""
        current = now or datetime.now(timezone.utc)
        elapsed = (current - self.started_at).total_seconds() / 60.0
        remaining = self.duration_minutes - elapsed
        return max(0.0, round(remaining, 1))

    def is_expired(self, now: datetime | None = None) -> bool:
        """Check whether the canary observation window has expired."""
        return self.remaining_minutes(now) <= 0.0


class CanaryWatcher:
    """Monitors telemetry during the canary window and triggers degradation alerts or rollbacks."""

    DEFAULT_CPU_THRESHOLD: float = 90.0
    DEFAULT_MEMORY_THRESHOLD: float = 90.0
    DEFAULT_ERROR_RATE_THRESHOLD: float = 5.0
    DEFAULT_CANARY_WINDOW_MINUTES: int = 60

    def __init__(
        self,
        approval_engine: ApprovalEngine | None = None,
        observability_sink: ObservabilitySink | None = None,
        cpu_threshold: float = DEFAULT_CPU_THRESHOLD,
        memory_threshold: float = DEFAULT_MEMORY_THRESHOLD,
        error_rate_threshold: float = DEFAULT_ERROR_RATE_THRESHOLD,
    ) -> None:
        self.approval_engine = approval_engine or ApprovalEngine()
        self.sink = observability_sink or LoggingObservabilitySink()
        self.cpu_threshold = cpu_threshold
        self.memory_threshold = memory_threshold
        self.error_rate_threshold = error_rate_threshold
        self._sessions: dict[str, CanarySession] = {}

    def start_canary(
        self,
        recommendation_id: str,
        resource_id: str,
        baseline_sku: str,
        target_sku: str,
        duration_minutes: int = DEFAULT_CANARY_WINDOW_MINUTES,
        auto_rollback: bool = False,
        started_at: datetime | None = None,
    ) -> CanarySession:
        """Initiate a 60-minute canary observation session for an executed recommendation."""
        session = CanarySession(
            recommendation_id=recommendation_id,
            resource_id=resource_id,
            baseline_sku=baseline_sku,
            target_sku=target_sku,
            duration_minutes=duration_minutes,
            auto_rollback=auto_rollback,
            started_at=started_at or datetime.now(timezone.utc),
        )
        self._sessions[recommendation_id] = session

        self.sink.emit(
            "canary.started",
            {
                "session_id": session.session_id,
                "recommendation_id": recommendation_id,
                "resource_id": resource_id,
                "baseline_sku": baseline_sku,
                "target_sku": target_sku,
                "duration_minutes": duration_minutes,
                "auto_rollback": auto_rollback,
            },
        )
        return session

    def record_checkpoint(
        self,
        recommendation_id: str,
        cpu_utilization: float,
        memory_utilization: float,
        error_rate: float = 0.0,
        heartbeat_ok: bool = True,
        timestamp: datetime | None = None,
    ) -> CanaryCheckpoint:
        """Sample resource telemetry and evaluate against safety thresholds."""
        session = self.get_session(recommendation_id)
        if not session:
            raise ValueError(f"No active canary session found for recommendation '{recommendation_id}'.")

        reasons: list[str] = []
        is_degraded = False

        if cpu_utilization > self.cpu_threshold:
            is_degraded = True
            reasons.append(
                f"CPU utilization ({cpu_utilization:.1f}%) breached the {self.cpu_threshold:.1f}% safety limit."
            )

        if memory_utilization > self.memory_threshold:
            is_degraded = True
            reasons.append(
                f"Memory utilization ({memory_utilization:.1f}%) breached the {self.memory_threshold:.1f}% safety limit."
            )

        if error_rate > self.error_rate_threshold:
            is_degraded = True
            reasons.append(
                f"Service error rate ({error_rate:.1f}%) exceeded allowable limit ({self.error_rate_threshold:.1f}%)."
            )

        if not heartbeat_ok:
            is_degraded = True
            reasons.append("Health check heartbeat failed.")

        checkpoint = CanaryCheckpoint(
            timestamp=timestamp or datetime.now(timezone.utc),
            cpu_utilization=cpu_utilization,
            memory_utilization=memory_utilization,
            error_rate=error_rate,
            heartbeat_ok=heartbeat_ok,
            is_degraded=is_degraded,
            degradation_reasons=reasons,
        )
        session.checkpoints.append(checkpoint)

        if is_degraded:
            session.status = CanaryStatus.DEGRADED
            session.alert_triggered = True

            self.sink.emit(
                "canary.degradation_alert",
                {
                    "session_id": session.session_id,
                    "recommendation_id": recommendation_id,
                    "resource_id": session.resource_id,
                    "reasons": reasons,
                    "cpu": cpu_utilization,
                    "memory": memory_utilization,
                    "error_rate": error_rate,
                },
            )

            # Automated rollback if enabled on this session
            if session.auto_rollback and not session.rollback_executed:
                self.trigger_rollback(
                    recommendation_id=recommendation_id,
                    reason=f"Automated rollback: {'; '.join(reasons)}",
                    initiated_by="automated_canary_watcher",
                )

        return checkpoint

    def check_window_expiration(
        self,
        recommendation_id: str,
        current_time: datetime | None = None,
    ) -> CanarySession:
        """Evaluate if the 60-minute canary period has successfully concluded."""
        session = self.get_session(recommendation_id)
        if not session:
            raise ValueError(f"No canary session found for recommendation '{recommendation_id}'.")

        if session.status == CanaryStatus.ACTIVE and session.is_expired(current_time):
            session.status = CanaryStatus.HEALTHY
            self.sink.emit(
                "canary.completed_healthy",
                {
                    "session_id": session.session_id,
                    "recommendation_id": recommendation_id,
                    "resource_id": session.resource_id,
                    "duration_minutes": session.duration_minutes,
                },
            )

        return session

    def trigger_rollback(
        self,
        recommendation_id: str,
        reason: str = "Performance degradation detected during canary observation window.",
        initiated_by: str = "canary_watcher",
        dry_run: bool = True,
    ) -> RollbackResult:
        """Execute a rollback to revert the resource to its pre-execution baseline SKU."""
        session = self.get_session(recommendation_id)
        if session:
            session.status = CanaryStatus.ROLLED_BACK
            session.rollback_executed = True
            session.rollback_reason = reason

        result = self.approval_engine.rollback(
            recommendation_id=recommendation_id,
            reason=reason,
            executor_id=initiated_by,
            dry_run=dry_run,
        )

        self.sink.emit(
            "canary.rollback_executed",
            {
                "recommendation_id": recommendation_id,
                "resource_id": result.resource_id,
                "restored_sku": result.restored_sku,
                "initiated_by": initiated_by,
                "reason": reason,
            },
        )
        return result

    def get_session(self, recommendation_id: str) -> CanarySession | None:
        """Fetch an active or historical canary session by recommendation ID."""
        return self._sessions.get(recommendation_id)

    def list_sessions(self) -> list[CanarySession]:
        """Return all tracked canary sessions."""
        return list(self._sessions.values())
