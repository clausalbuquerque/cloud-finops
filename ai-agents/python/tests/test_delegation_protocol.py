from __future__ import annotations

import unittest
from unittest.mock import MagicMock

from finops_ai.orchestration import (
    DelegationController,
    DelegationRequest,
    DependencyRisk,
    FinOpsDelegationVerdict,
    SREDelegationVerdict,
)
from finops_ai.tools.delegation_tools import delegate_to_finops, delegate_to_sre


class TestDelegationProtocol(unittest.TestCase):
    def setUp(self) -> None:
        self.mock_sink = MagicMock()
        self.controller = DelegationController(
            max_delegation_depth=2,
            observability_sink=self.mock_sink,
        )

    def test_delegate_to_sre_verdict_schema(self) -> None:
        req = DelegationRequest(
            caller_agent="FinOps Specialist",
            target_agent="SRE Specialist",
            resource_ids=["projects/p1/zones/z1/instances/analytics-worker-02"],
            question="Is it safe to downsize this VM to n2-standard-8?",
            delegation_depth=1,
            call_stack=["FinOps Specialist"],
        )

        verdict = self.controller.delegate_to_sre(req)
        self.assertIsInstance(verdict, SREDelegationVerdict)
        self.assertTrue(verdict.safe_to_modify)
        self.assertEqual(verdict.target_resources, ["projects/p1/zones/z1/instances/analytics-worker-02"])
        self.assertEqual(verdict.headroom_buffer_pct, 56.0)
        self.assertEqual(verdict.dependency_risk, DependencyRisk.LOW)
        self.assertEqual(verdict.recommended_sku, "n2-standard-8")

        # Check observability calls
        self.assertEqual(self.mock_sink.emit.call_count, 2)
        start_call = self.mock_sink.emit.call_args_list[0]
        self.assertEqual(start_call[0][0], "delegation.start")
        complete_call = self.mock_sink.emit.call_args_list[1]
        self.assertEqual(complete_call[0][0], "delegation.complete")

    def test_delegate_to_finops_verdict_schema(self) -> None:
        req = DelegationRequest(
            caller_agent="SRE Specialist",
            target_agent="FinOps Specialist",
            resource_ids=["projects/p1/zones/z1/instances/idle-db-01"],
            question="What is the cost saving if we shut down this idle DB?",
            context={"utilization_summary": "CPU < 1% for 30 days"},
            delegation_depth=1,
            call_stack=["SRE Specialist"],
        )

        verdict = self.controller.delegate_to_finops(req)
        self.assertIsInstance(verdict, FinOpsDelegationVerdict)
        self.assertEqual(verdict.quantified_savings_monthly, 142.25)
        self.assertEqual(verdict.current_monthly_cost, 284.50)
        self.assertEqual(verdict.pricing_model, "OnDemand")

    def test_delegation_depth_limit_protection(self) -> None:
        req = DelegationRequest(
            caller_agent="FinOps Specialist",
            target_agent="SRE Specialist",
            resource_ids=["analytics-worker-02"],
            question="Test recursive depth",
            delegation_depth=3,  # Exceeds max depth of 2
            call_stack=["FinOps Specialist", "SRE Specialist", "FinOps Specialist"],
        )

        with self.assertRaises(ValueError) as ctx:
            self.controller.delegate_to_sre(req)
        self.assertIn("Maximum delegation depth (2) exceeded", str(ctx.exception))

    def test_delegation_cycle_detection(self) -> None:
        req = DelegationRequest(
            caller_agent="FinOps Specialist",
            target_agent="SRE Specialist",
            resource_ids=["analytics-worker-02"],
            question="Test cycle loop",
            delegation_depth=2,
            call_stack=["FinOps Specialist", "SRE Specialist"],  # SRE is already in stack
        )

        with self.assertRaises(ValueError) as ctx:
            self.controller.delegate_to_sre(req)
        self.assertIn("Circular delegation loop detected", str(ctx.exception))

    def test_delegation_tools_execution(self) -> None:
        sre_tool_result = delegate_to_sre._run(
            resource_ids=["analytics-worker-02"],
            question="Evaluate headroom for right-sizing",
        )
        self.assertIsInstance(sre_tool_result, dict)
        self.assertTrue(sre_tool_result["safe_to_modify"])
        self.assertEqual(sre_tool_result["dependency_risk"], "LOW")

        finops_tool_result = delegate_to_finops._run(
            resource_ids=["analytics-worker-02"],
            utilization_summary="P95 CPU 18%",
            question="Calculate potential savings",
        )
        self.assertIsInstance(finops_tool_result, dict)
        self.assertEqual(finops_tool_result["quantified_savings_monthly"], 142.25)

