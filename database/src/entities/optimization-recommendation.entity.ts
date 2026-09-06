import {
  Entity,
  PrimaryGeneratedColumn,
  Column,
  CreateDateColumn,
  UpdateDateColumn,
  Index,
} from 'typeorm';

/**
 * Represents an optimization recommendation proposed by the FinOps Agent.
 *
 * Stores the full lifecycle of a recommendation (proposed -> approved/rejected -> executed/expired),
 * estimated and actual savings, confidence scores, and SRE safety assessments.
 */
@Entity('optimization_recommendations')
@Index(['scopeTeam', 'status', 'proposedAt'])
@Index(['resourceId', 'status'])
@Index(['providerName', 'recommendationType'])
export class OptimizationRecommendationEntity {
  @PrimaryGeneratedColumn('uuid')
  id: string;

  /** Cloud provider name (e.g. 'GCP', 'Azure', 'AWS'). */
  @Column({ name: 'provider_name', default: 'GCP' })
  providerName: string;

  /** Provider-neutral or opaque resource identifier. */
  @Column({ name: 'resource_id' })
  resourceId: string;

  /** Normalized resource type (e.g. 'Compute/VirtualMachine', 'compute/instance'). */
  @Column({ name: 'resource_type' })
  resourceType: string;

  /** Recommendation category (e.g. 'rightsize', 'commitment_purchase', 'decommission', 'consolidate'). */
  @Column({ name: 'recommendation_type' })
  recommendationType: string;

  /** Current state snapshot, e.g. { sku: 'n2-standard-8', monthlyCost: 284.50 }. */
  @Column({ name: 'current_state', type: 'jsonb' })
  currentState: Record<string, unknown>;

  /** Proposed target state, e.g. { sku: 'n2-standard-4', estimatedMonthlyCost: 142.25 }. */
  @Column({ name: 'proposed_state', type: 'jsonb' })
  proposedState: Record<string, unknown>;

  /** Estimated monthly cost reduction in billing currency. */
  @Column({ name: 'estimated_monthly_savings', type: 'decimal', precision: 18, scale: 6 })
  estimatedMonthlySavings: number;

  /** Measured monthly cost reduction post-execution. Null until verified. */
  @Column({
    name: 'actual_monthly_savings',
    type: 'decimal',
    precision: 18,
    scale: 6,
    nullable: true,
  })
  actualMonthlySavings: number | null;

  /** Agent confidence score (0.0 to 1.0). */
  @Column({ name: 'confidence_score', type: 'double precision' })
  confidenceScore: number;

  /** SRE Agent structured safety assessment (dependencies, utilization, risk). */
  @Column({ name: 'sre_assessment', type: 'jsonb', nullable: true })
  sreAssessment: Record<string, unknown> | null;

  /** Status in lifecycle: 'proposed' | 'approved' | 'rejected' | 'executed' | 'expired'. */
  @Column({ default: 'proposed' })
  status: string;

  /** User-provided rejection reason or feedback notes. */
  @Column({ name: 'rejection_reason', type: 'text', nullable: true })
  rejectionReason: string | null;

  /** Team or cost-center scope (e.g. 'data-platform'). */
  @Column({ name: 'scope_team', type: 'varchar', nullable: true })
  scopeTeam: string | null;

  /** ID of the orchestration flow instance managing this recommendation's HITL gate. */
  @Column({ name: 'flow_id', type: 'varchar', nullable: true })
  flowId: string | null;


  /** Timestamp when the recommendation was proposed. */
  @Column({
    name: 'proposed_at',
    type: 'timestamp with time zone',
    default: () => 'CURRENT_TIMESTAMP',
  })
  proposedAt: Date;

  /** Timestamp when the recommendation was resolved (approved or rejected). */
  @Column({ name: 'resolved_at', type: 'timestamp with time zone', nullable: true })
  resolvedAt: Date | null;

  /** Timestamp when the approved action was executed. */
  @Column({ name: 'executed_at', type: 'timestamp with time zone', nullable: true })
  executedAt: Date | null;

  @CreateDateColumn({ name: 'created_at', type: 'timestamp with time zone' })
  createdAt: Date;

  @UpdateDateColumn({ name: 'updated_at', type: 'timestamp with time zone' })
  updatedAt: Date;
}
