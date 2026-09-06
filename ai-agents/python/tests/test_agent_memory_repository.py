from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
import unittest
from unittest.mock import MagicMock

from finops_ai.memory.contracts import (
    AgentInteractionMemory,
    AnomalyResolution,
    InfrastructureBaseline,
    OptimizationRecommendation,
)
from finops_ai.memory.repository import (
    AgentMemoryRepository,
    AgentInteractionMemoryRecord,
    AnomalyResolutionRecord,
    InfrastructureBaselineRecord,
    OptimizationRecommendationRecord,
)


class TestAgentMemoryContracts(unittest.TestCase):
    def test_optimization_recommendation_contract(self) -> None:
        rec = OptimizationRecommendation(
            resource_id="projects/p1/zones/z1/instances/w1",
            resource_type="compute/instance",
            recommendation_type="rightsize",
            current_state={"sku": "n2-standard-8", "monthlyCost": 284.5},
            proposed_state={"sku": "n2-standard-4", "estimatedMonthlyCost": 142.25},
            estimated_monthly_savings=142.25,
            confidence_score=0.95,
            scope_team="data-platform",
            flow_id="flow-123",
        )
        self.assertEqual(rec.resource_id, "projects/p1/zones/z1/instances/w1")
        self.assertEqual(rec.provider_name, "GCP")
        self.assertEqual(rec.status, "proposed")
        self.assertEqual(rec.estimated_monthly_savings, 142.25)
        self.assertEqual(rec.scope_team, "data-platform")
        self.assertEqual(rec.flow_id, "flow-123")

    def test_anomaly_resolution_contract(self) -> None:
        res = AnomalyResolution(
            anomaly_id="anom-01",
            resource_id="projects/p1/zones/z1/instances/w1",
            dimension="serviceCategory",
            root_cause_type="sku_change",
            root_cause_description="Instance upgraded from n2-standard-4 to n2-standard-8",
            resolution_action="reverted",
            is_recurring=True,
            recurrence_count=2,
            resolved_by="user-1",
        )
        self.assertEqual(res.anomaly_id, "anom-01")
        self.assertEqual(res.root_cause_type, "sku_change")
        self.assertTrue(res.is_recurring)
        self.assertEqual(res.recurrence_count, 2)
        self.assertEqual(res.resolved_by, "user-1")

    def test_infrastructure_baseline_contract(self) -> None:
        base = InfrastructureBaseline(
            resource_id="projects/p1/zones/z1/instances/batch-01",
            metric_name="cpu_utilization",
            baseline_type="workload_pattern",
            expected_pattern={"schedule": "weekday_nights", "expectedUtilization": {"low": 5, "high": 85}},
            suppress_underuse_alerts=True,
            confidence_score=0.99,
            established_by="user_confirmed",
        )
        self.assertEqual(base.metric_name, "cpu_utilization")
        self.assertTrue(base.suppress_underuse_alerts)
        self.assertEqual(base.confidence_score, 0.99)
        self.assertEqual(base.established_by, "user_confirmed")

    def test_agent_interaction_memory_contract(self) -> None:
        mem = AgentInteractionMemory(
            session_id="sess-01",
            user_id="user-01",
            agent_type="finops",
            interaction_summary="Investigated compute cost surge in data-platform",
            key_findings={"spikeUsd": 320.0},
            scope_context={"team": "data-platform"},
        )
        self.assertEqual(mem.session_id, "sess-01")
        self.assertEqual(mem.user_id, "user-01")
        self.assertEqual(mem.agent_type, "finops")
        self.assertIn("data-platform", mem.interaction_summary)


class TestAgentMemoryRepository(unittest.TestCase):
    def setUp(self) -> None:
        self.mock_session = MagicMock()
        self.mock_session_factory = MagicMock()
        self.mock_session_factory.return_value.__enter__.return_value = self.mock_session
        self.repo = AgentMemoryRepository(self.mock_session_factory)

    def test_store_recommendation(self) -> None:
        rec = OptimizationRecommendation(
            id="rec-123",
            resource_id="res-01",
            resource_type="compute/instance",
            recommendation_type="rightsize",
            current_state={"sku": "n2-standard-8"},
            proposed_state={"sku": "n2-standard-4"},
            estimated_monthly_savings=150.0,
            confidence_score=0.9,
            scope_team="team-a",
        )
        returned_id = self.repo.store_recommendation(rec)
        self.assertEqual(returned_id, "rec-123")
        self.mock_session.add.assert_called_once()
        self.mock_session.commit.assert_called_once()

    def test_get_optimization_history(self) -> None:
        record = OptimizationRecommendationRecord()
        record.id = "rec-123"
        record.provider_name = "GCP"
        record.resource_id = "res-01"
        record.resource_type = "compute/instance"
        record.recommendation_type = "rightsize"
        record.current_state = {"sku": "n2-standard-8"}
        record.proposed_state = {"sku": "n2-standard-4"}
        record.estimated_monthly_savings = Decimal("150.000000")
        record.actual_monthly_savings = None
        record.confidence_score = 0.9
        record.sre_assessment = {"safe": True}
        record.status = "proposed"
        record.rejection_reason = None
        record.scope_team = "team-a"
        record.flow_id = "flow-1"
        record.proposed_at = datetime.now(timezone.utc)
        record.resolved_at = None
        record.executed_at = None
        record.created_at = datetime.now(timezone.utc)
        record.updated_at = datetime.now(timezone.utc)

        self.mock_session.scalars.return_value.all.return_value = [record]

        history = self.repo.get_optimization_history(scope_team="team-a", status="proposed")
        self.assertEqual(len(history), 1)
        self.assertEqual(history[0].id, "rec-123")
        self.assertEqual(history[0].estimated_monthly_savings, 150.0)
        self.assertEqual(history[0].scope_team, "team-a")

    def test_update_recommendation_status(self) -> None:
        record = MagicMock(spec=OptimizationRecommendationRecord)
        self.mock_session.get.return_value = record

        success = self.repo.update_recommendation_status(
            recommendation_id="rec-123",
            status="rejected",
            rejection_reason="Workload expanding next week",
        )
        self.assertTrue(success)
        self.assertEqual(record.status, "rejected")
        self.assertEqual(record.rejection_reason, "Workload expanding next week")
        self.mock_session.commit.assert_called_once()

    def test_update_recommendation_status_not_found(self) -> None:
        self.mock_session.get.return_value = None
        success = self.repo.update_recommendation_status(
            recommendation_id="rec-nonexistent",
            status="approved",
        )
        self.assertFalse(success)

    def test_store_and_get_anomaly_resolutions(self) -> None:
        res = AnomalyResolution(
            id="anom-res-01",
            anomaly_id="anom-01",
            resource_id="res-01",
            dimension="serviceCategory",
            root_cause_type="sku_change",
            root_cause_description="Accidental scale up",
        )
        stored_id = self.repo.store_anomaly_resolution(res)
        self.assertEqual(stored_id, "anom-res-01")
        self.mock_session.add.assert_called_once()

        record = AnomalyResolutionRecord()
        record.id = "anom-res-01"
        record.anomaly_id = "anom-01"
        record.provider_name = "GCP"
        record.resource_id = "res-01"
        record.dimension = "serviceCategory"
        record.root_cause_type = "sku_change"
        record.root_cause_description = "Accidental scale up"
        record.resolution_action = "reverted"
        record.is_recurring = False
        record.recurrence_count = 1
        record.investigation_trace = None
        record.resolved_by = "admin"
        record.created_at = datetime.now(timezone.utc)
        record.updated_at = datetime.now(timezone.utc)

        self.mock_session.scalars.return_value.all.return_value = [record]
        results = self.repo.get_anomaly_resolutions(resource_id="res-01")
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].anomaly_id, "anom-01")
        self.assertEqual(results[0].root_cause_type, "sku_change")

    def test_store_and_get_infrastructure_baselines(self) -> None:
        baseline = InfrastructureBaseline(
            id="base-01",
            resource_id="res-01",
            metric_name="cpu_utilization",
            baseline_type="workload_pattern",
            expected_pattern={"schedule": "weekday_nights"},
            suppress_underuse_alerts=True,
        )
        stored_id = self.repo.store_infrastructure_baseline(baseline)
        self.assertEqual(stored_id, "base-01")

        record = InfrastructureBaselineRecord()
        record.id = "base-01"
        record.tracked_resource_id = None
        record.resource_id = "res-01"
        record.provider_name = "GCP"
        record.metric_name = "cpu_utilization"
        record.baseline_type = "workload_pattern"
        record.expected_pattern = {"schedule": "weekday_nights"}
        record.suppress_underuse_alerts = True
        record.confidence_score = 1.0
        record.evidence = None
        record.established_by = "agent_inferred"
        record.last_validated = None
        record.created_at = datetime.now(timezone.utc)
        record.updated_at = datetime.now(timezone.utc)

        self.mock_session.scalars.return_value.all.return_value = [record]
        results = self.repo.get_infrastructure_baselines(resource_id="res-01")
        self.assertEqual(len(results), 1)
        self.assertTrue(results[0].suppress_underuse_alerts)

    def test_store_and_get_interaction_memory(self) -> None:
        mem = AgentInteractionMemory(
            id="mem-01",
            session_id="sess-01",
            user_id="u-01",
            agent_type="finops",
            interaction_summary="Summary text",
        )
        stored_id = self.repo.store_interaction_memory(mem)
        self.assertEqual(stored_id, "mem-01")

        record = AgentInteractionMemoryRecord()
        record.id = "mem-01"
        record.session_id = "sess-01"
        record.user_id = "u-01"
        record.agent_type = "finops"
        record.interaction_summary = "Summary text"
        record.key_findings = None
        record.follow_up_items = None
        record.scope_context = None
        record.created_at = datetime.now(timezone.utc)
        record.updated_at = datetime.now(timezone.utc)

        self.mock_session.scalars.return_value.all.return_value = [record]
        results = self.repo.get_interaction_memory(session_id="sess-01")
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].session_id, "sess-01")

