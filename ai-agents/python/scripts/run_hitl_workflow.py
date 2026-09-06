#!/usr/bin/env python3
"""CLI demonstration runner for Human-in-the-Loop (HITL) approval workflows.

Shows propose -> review -> approve/reject -> execute lifecycle.
"""

from __future__ import annotations

import argparse
import json
import sys
from uuid import uuid4

from finops_ai.hitl import (
    ApprovalEngine,
    ApprovalOutcome,
    HumanFeedbackDecision,
)
from finops_ai.memory.contracts import OptimizationRecommendation


def main() -> int:
    parser = argparse.ArgumentParser(description="Run FinOps HITL approval workflow lifecycle.")
    parser.add_argument("--resource-id", default="projects/my-proj/zones/us-central1-a/instances/analytics-worker-02")
    parser.add_argument("--savings", type=float, default=142.25)
    parser.add_argument("--reviewer", default="jane.doe@company.com")
    parser.add_argument("--role", default="finops_lead")
    parser.add_argument("--decision", choices=["approved", "rejected", "needs_revision"], default="approved")
    parser.add_argument("--dry-run", action="store_true", default=True)
    args = parser.parse_args()

    engine = ApprovalEngine()

    print("\n" + "=" * 70)
    print(" 🚀 CLOUD FINOPS HUMAN-IN-THE-LOOP (HITL) APPROVAL WORKFLOW")
    print("=" * 70)

    # 1. Propose Recommendation
    print("\n[Step 1] Proposing optimization recommendation...")
    rec = OptimizationRecommendation(
        id=str(uuid4()),
        resource_id=args.resource_id,
        resource_type="compute/instance",
        recommendation_type="rightsize",
        current_state={"machine_type": "n2-standard-16"},
        proposed_state={"target_sku": "n2-standard-8"},
        estimated_monthly_savings=args.savings,
        confidence_score=92.0,
        provider_name="GCP",
        sre_assessment={"safe_to_modify": True, "headroom_pct": 56.0, "dependency_risk": "LOW"},
    )
    proposed = engine.propose(rec, flow_id=str(uuid4()))
    print(f" -> ID: {proposed.id}")
    print(f" -> Resource: {proposed.resource_id}")
    print(f" -> Status: {proposed.status}")
    print(f" -> Projected Savings: ${proposed.estimated_monthly_savings:.2f}/mo")


    # 2. Process Human Feedback
    print(f"\n[Step 2] Human reviewer ({args.reviewer}, role: {args.role}) evaluates recommendation...")
    decision = HumanFeedbackDecision(
        recommendation_id=proposed.id,
        reviewer_id=args.reviewer,
        reviewer_role=args.role,
        outcome=ApprovalOutcome(args.decision),
        feedback_notes="Approved for maintenance window deployment after SRE safety review.",
    )
    reviewed = engine.process_feedback(proposed.id, decision)
    print(f" -> Status updated to: {reviewed.status.upper()}")

    # 3. Action Execution (if approved)
    if reviewed.status == "approved":
        print("\n[Step 3] Executing approved action...")
        result = engine.execute(
            recommendation_id=reviewed.id,
            executor_id=args.reviewer,
            actual_monthly_savings=args.savings,
            dry_run=args.dry_run,
        )
        print(f" -> Execution Status: {result.status.value.upper()}")
        print(f" -> Generated CLI: {result.execution_command}")
        print(f" -> Rollback Plan: {result.rollback_command}")
        print(f" -> Drift Detected: {result.drift_detected}")
    else:
        print(f"\n[Step 3] Execution skipped (status is '{reviewed.status}').")

    print("\n" + "=" * 70)
    print(" ✅ HITL Workflow Lifecycle Completed Successfully.")
    print("=" * 70 + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
