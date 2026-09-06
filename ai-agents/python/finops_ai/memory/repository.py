"""Agent Long-Term Memory Repository.

Provides persistent read and write operations for recommendations, anomaly
resolutions, infrastructure baselines, and interaction memory in PostgreSQL.
"""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from typing import Any
from uuid import uuid4

from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    Integer,
    Numeric,
    String,
    Text,
    create_engine,
    desc,
    select,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, sessionmaker

from .contracts import (
    AgentInteractionMemory,
    AnomalyResolution,
    InfrastructureBaseline,
    OptimizationRecommendation,
)


class Base(DeclarativeBase):
    pass


class OptimizationRecommendationRecord(Base):
    __tablename__ = "optimization_recommendations"
    __table_args__ = {"schema": "finops"}

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True)
    provider_name: Mapped[str] = mapped_column(String, default="GCP")
    resource_id: Mapped[str] = mapped_column(String)
    resource_type: Mapped[str] = mapped_column(String)
    recommendation_type: Mapped[str] = mapped_column(String)
    current_state: Mapped[dict[str, Any]] = mapped_column(JSONB)
    proposed_state: Mapped[dict[str, Any]] = mapped_column(JSONB)
    estimated_monthly_savings: Mapped[Decimal] = mapped_column(Numeric(18, 6))
    actual_monthly_savings: Mapped[Decimal | None] = mapped_column(Numeric(18, 6), nullable=True)
    confidence_score: Mapped[float] = mapped_column(Float)
    sre_assessment: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    status: Mapped[str] = mapped_column(String, default="proposed")
    rejection_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    scope_team: Mapped[str | None] = mapped_column(String, nullable=True)
    flow_id: Mapped[str | None] = mapped_column(String, nullable=True)
    proposed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    executed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )


class AnomalyResolutionRecord(Base):
    __tablename__ = "anomaly_resolutions"
    __table_args__ = {"schema": "finops"}

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True)
    anomaly_id: Mapped[str] = mapped_column(String)
    provider_name: Mapped[str] = mapped_column(String, default="GCP")
    resource_id: Mapped[str] = mapped_column(String)
    dimension: Mapped[str] = mapped_column(String)
    root_cause_type: Mapped[str] = mapped_column(String)
    root_cause_description: Mapped[str] = mapped_column(Text)
    resolution_action: Mapped[str | None] = mapped_column(String, nullable=True)
    is_recurring: Mapped[bool] = mapped_column(Boolean, default=False)
    recurrence_count: Mapped[int] = mapped_column(Integer, default=1)
    investigation_trace: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    resolved_by: Mapped[str | None] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )


class InfrastructureBaselineRecord(Base):
    __tablename__ = "infrastructure_baselines"
    __table_args__ = {"schema": "finops"}

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True)
    tracked_resource_id: Mapped[str | None] = mapped_column(
        UUID(as_uuid=False), nullable=True
    )
    resource_id: Mapped[str] = mapped_column(String)
    provider_name: Mapped[str] = mapped_column(String, default="GCP")
    metric_name: Mapped[str] = mapped_column(String)
    baseline_type: Mapped[str] = mapped_column(String)
    expected_pattern: Mapped[dict[str, Any]] = mapped_column(JSONB)
    suppress_underuse_alerts: Mapped[bool] = mapped_column(Boolean, default=False)
    confidence_score: Mapped[float] = mapped_column(Float, default=1.0)
    evidence: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    established_by: Mapped[str] = mapped_column(String, default="agent_inferred")
    last_validated: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )


class AgentInteractionMemoryRecord(Base):
    __tablename__ = "agent_interaction_memory"
    __table_args__ = {"schema": "finops"}

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True)
    session_id: Mapped[str] = mapped_column(String)
    user_id: Mapped[str] = mapped_column(String)
    agent_type: Mapped[str] = mapped_column(String)
    interaction_summary: Mapped[str] = mapped_column(Text)
    key_findings: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    follow_up_items: Mapped[list[dict[str, Any]] | dict[str, Any] | None] = mapped_column(
        JSONB, nullable=True
    )
    scope_context: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )


class AgentMemoryRepository:
    """DAO for querying and persisting agent memory records."""

    def __init__(self, session_factory: sessionmaker[Session]) -> None:
        self._session_factory = session_factory

    @classmethod
    def from_url(cls, db_url: str) -> "AgentMemoryRepository":
        engine = create_engine(db_url, future=True)
        return cls(session_factory=sessionmaker(bind=engine, future=True))

    # ── Optimization Recommendations ───────────────────────────────────

    def store_recommendation(self, rec: OptimizationRecommendation) -> str:
        """Persist a new optimization recommendation."""
        row_id = rec.id or str(uuid4())
        record = OptimizationRecommendationRecord(
            id=row_id,
            provider_name=rec.provider_name,
            resource_id=rec.resource_id,
            resource_type=rec.resource_type,
            recommendation_type=rec.recommendation_type,
            current_state=rec.current_state,
            proposed_state=rec.proposed_state,
            estimated_monthly_savings=Decimal(str(rec.estimated_monthly_savings)),
            actual_monthly_savings=(
                Decimal(str(rec.actual_monthly_savings))
                if rec.actual_monthly_savings is not None
                else None
            ),
            confidence_score=rec.confidence_score,
            sre_assessment=rec.sre_assessment,
            status=rec.status,
            rejection_reason=rec.rejection_reason,
            scope_team=rec.scope_team,
            flow_id=rec.flow_id,
            proposed_at=rec.proposed_at,
            resolved_at=rec.resolved_at,
            executed_at=rec.executed_at,
            created_at=rec.created_at,
            updated_at=rec.updated_at,
        )
        with self._session_factory() as session:
            session.add(record)
            session.commit()
        return row_id

    def get_optimization_history(
        self,
        scope_team: str | None = None,
        resource_id: str | None = None,
        status: str | None = None,
        provider_name: str | None = None,
        limit: int = 50,
    ) -> list[OptimizationRecommendation]:
        """Query optimization history filtered by team, resource, or status."""
        stmt = select(OptimizationRecommendationRecord)
        if scope_team is not None:
            stmt = stmt.where(OptimizationRecommendationRecord.scope_team == scope_team)
        if resource_id is not None:
            stmt = stmt.where(OptimizationRecommendationRecord.resource_id == resource_id)
        if status is not None:
            stmt = stmt.where(OptimizationRecommendationRecord.status == status)
        if provider_name is not None:
            stmt = stmt.where(OptimizationRecommendationRecord.provider_name == provider_name)

        stmt = stmt.order_by(desc(OptimizationRecommendationRecord.proposed_at)).limit(limit)

        with self._session_factory() as session:
            rows = session.scalars(stmt).all()

        return [
            OptimizationRecommendation(
                id=str(r.id),
                provider_name=r.provider_name,
                resource_id=r.resource_id,
                resource_type=r.resource_type,
                recommendation_type=r.recommendation_type,
                current_state=r.current_state,
                proposed_state=r.proposed_state,
                estimated_monthly_savings=float(r.estimated_monthly_savings),
                actual_monthly_savings=(
                    float(r.actual_monthly_savings)
                    if r.actual_monthly_savings is not None
                    else None
                ),
                confidence_score=float(r.confidence_score),
                sre_assessment=r.sre_assessment,
                status=r.status,
                rejection_reason=r.rejection_reason,
                scope_team=r.scope_team,
                flow_id=r.flow_id,
                proposed_at=r.proposed_at,
                resolved_at=r.resolved_at,
                executed_at=r.executed_at,
                created_at=r.created_at,
                updated_at=r.updated_at,
            )
            for r in rows
        ]

    def update_recommendation_status(
        self,
        recommendation_id: str,
        status: str,
        rejection_reason: str | None = None,
        actual_monthly_savings: float | None = None,
        resolved_at: datetime | None = None,
        executed_at: datetime | None = None,
    ) -> bool:
        """Update status and resolution fields on a recommendation."""
        with self._session_factory() as session:
            rec = session.get(OptimizationRecommendationRecord, recommendation_id)
            if not rec:
                return False
            rec.status = status
            if rejection_reason is not None:
                rec.rejection_reason = rejection_reason
            if actual_monthly_savings is not None:
                rec.actual_monthly_savings = Decimal(str(actual_monthly_savings))
            if resolved_at is not None:
                rec.resolved_at = resolved_at
            if executed_at is not None:
                rec.executed_at = executed_at
            rec.updated_at = datetime.now(timezone.utc)
            session.commit()
            return True

    # ── Anomaly Resolutions ─────────────────────────────────────────────

    def store_anomaly_resolution(self, res: AnomalyResolution) -> str:
        """Persist findings from an anomaly root-cause investigation."""
        row_id = res.id or str(uuid4())
        record = AnomalyResolutionRecord(
            id=row_id,
            anomaly_id=res.anomaly_id,
            provider_name=res.provider_name,
            resource_id=res.resource_id,
            dimension=res.dimension,
            root_cause_type=res.root_cause_type,
            root_cause_description=res.root_cause_description,
            resolution_action=res.resolution_action,
            is_recurring=res.is_recurring,
            recurrence_count=res.recurrence_count,
            investigation_trace=res.investigation_trace,
            resolved_by=res.resolved_by,
            created_at=res.created_at,
            updated_at=res.updated_at,
        )
        with self._session_factory() as session:
            session.add(record)
            session.commit()
        return row_id

    def get_anomaly_resolutions(
        self,
        resource_id: str | None = None,
        dimension: str | None = None,
        anomaly_id: str | None = None,
        limit: int = 20,
    ) -> list[AnomalyResolution]:
        """Retrieve anomaly resolutions matching resource, dimension, or anomaly ID."""
        stmt = select(AnomalyResolutionRecord)
        if resource_id is not None:
            stmt = stmt.where(AnomalyResolutionRecord.resource_id == resource_id)
        if dimension is not None:
            stmt = stmt.where(AnomalyResolutionRecord.dimension == dimension)
        if anomaly_id is not None:
            stmt = stmt.where(AnomalyResolutionRecord.anomaly_id == anomaly_id)

        stmt = stmt.order_by(desc(AnomalyResolutionRecord.created_at)).limit(limit)

        with self._session_factory() as session:
            rows = session.scalars(stmt).all()

        return [
            AnomalyResolution(
                id=str(r.id),
                anomaly_id=r.anomaly_id,
                provider_name=r.provider_name,
                resource_id=r.resource_id,
                dimension=r.dimension,
                root_cause_type=r.root_cause_type,
                root_cause_description=r.root_cause_description,
                resolution_action=r.resolution_action,
                is_recurring=r.is_recurring,
                recurrence_count=r.recurrence_count,
                investigation_trace=r.investigation_trace,
                resolved_by=r.resolved_by,
                created_at=r.created_at,
                updated_at=r.updated_at,
            )
            for r in rows
        ]

    # ── Infrastructure Baselines ────────────────────────────────────────

    def store_infrastructure_baseline(self, baseline: InfrastructureBaseline) -> str:
        """Persist an interpreted workload baseline."""
        row_id = baseline.id or str(uuid4())
        record = InfrastructureBaselineRecord(
            id=row_id,
            tracked_resource_id=baseline.tracked_resource_id,
            resource_id=baseline.resource_id,
            provider_name=baseline.provider_name,
            metric_name=baseline.metric_name,
            baseline_type=baseline.baseline_type,
            expected_pattern=baseline.expected_pattern,
            suppress_underuse_alerts=baseline.suppress_underuse_alerts,
            confidence_score=baseline.confidence_score,
            evidence=baseline.evidence,
            established_by=baseline.established_by,
            last_validated=baseline.last_validated,
            created_at=baseline.created_at,
            updated_at=baseline.updated_at,
        )
        with self._session_factory() as session:
            session.add(record)
            session.commit()
        return row_id

    def get_infrastructure_baselines(
        self,
        resource_id: str | None = None,
        metric_name: str | None = None,
        provider_name: str | None = None,
        limit: int = 50,
    ) -> list[InfrastructureBaseline]:
        """Retrieve infrastructure baselines for contextualizing utilization metrics."""
        stmt = select(InfrastructureBaselineRecord)
        if resource_id is not None:
            stmt = stmt.where(InfrastructureBaselineRecord.resource_id == resource_id)
        if metric_name is not None:
            stmt = stmt.where(InfrastructureBaselineRecord.metric_name == metric_name)
        if provider_name is not None:
            stmt = stmt.where(InfrastructureBaselineRecord.provider_name == provider_name)

        stmt = stmt.order_by(desc(InfrastructureBaselineRecord.created_at)).limit(limit)

        with self._session_factory() as session:
            rows = session.scalars(stmt).all()

        return [
            InfrastructureBaseline(
                id=str(r.id),
                tracked_resource_id=str(r.tracked_resource_id) if r.tracked_resource_id else None,
                resource_id=r.resource_id,
                provider_name=r.provider_name,
                metric_name=r.metric_name,
                baseline_type=r.baseline_type,
                expected_pattern=r.expected_pattern,
                suppress_underuse_alerts=r.suppress_underuse_alerts,
                confidence_score=float(r.confidence_score),
                evidence=r.evidence,
                established_by=r.established_by,
                last_validated=r.last_validated,
                created_at=r.created_at,
                updated_at=r.updated_at,
            )
            for r in rows
        ]

    # ── Agent Interaction Memory ────────────────────────────────────────

    def store_interaction_memory(self, memory: AgentInteractionMemory) -> str:
        """Persist a conversation turn summary and structured findings."""
        row_id = memory.id or str(uuid4())
        record = AgentInteractionMemoryRecord(
            id=row_id,
            session_id=memory.session_id,
            user_id=memory.user_id,
            agent_type=memory.agent_type,
            interaction_summary=memory.interaction_summary,
            key_findings=memory.key_findings,
            follow_up_items=memory.follow_up_items,
            scope_context=memory.scope_context,
            created_at=memory.created_at,
            updated_at=memory.updated_at,
        )
        with self._session_factory() as session:
            session.add(record)
            session.commit()
        return row_id

    def get_interaction_memory(
        self,
        session_id: str | None = None,
        user_id: str | None = None,
        agent_type: str | None = None,
        limit: int = 10,
    ) -> list[AgentInteractionMemory]:
        """Retrieve interaction summaries and findings across sessions."""
        stmt = select(AgentInteractionMemoryRecord)
        if session_id is not None:
            stmt = stmt.where(AgentInteractionMemoryRecord.session_id == session_id)
        if user_id is not None:
            stmt = stmt.where(AgentInteractionMemoryRecord.user_id == user_id)
        if agent_type is not None:
            stmt = stmt.where(AgentInteractionMemoryRecord.agent_type == agent_type)

        stmt = stmt.order_by(desc(AgentInteractionMemoryRecord.created_at)).limit(limit)

        with self._session_factory() as session:
            rows = session.scalars(stmt).all()

        return [
            AgentInteractionMemory(
                id=str(r.id),
                session_id=r.session_id,
                user_id=r.user_id,
                agent_type=r.agent_type,
                interaction_summary=r.interaction_summary,
                key_findings=r.key_findings,
                follow_up_items=r.follow_up_items,
                scope_context=r.scope_context,
                created_at=r.created_at,
                updated_at=r.updated_at,
            )
            for r in rows
        ]

