import {
  Entity,
  PrimaryGeneratedColumn,
  Column,
  CreateDateColumn,
  UpdateDateColumn,
  Index,
} from 'typeorm';

/**
 * Represents the root-cause analysis and resolution history for a cost anomaly.
 *
 * Persists agent investigation findings as long-term memory so recurring
 * anomalies on the same resource or dimension can recall prior root causes.
 */
@Entity('anomaly_resolutions')
@Index(['resourceId', 'dimension'])
@Index(['anomalyId'])
@Index(['providerName', 'rootCauseType'])
export class AnomalyResolutionEntity {
  @PrimaryGeneratedColumn('uuid')
  id: string;

  /** Reference identifier for the detected anomaly. */
  @Column({ name: 'anomaly_id' })
  anomalyId: string;

  /** Cloud provider name (e.g. 'GCP', 'Azure', 'AWS'). */
  @Column({ name: 'provider_name', default: 'GCP' })
  providerName: string;

  /** Provider-neutral or opaque resource identifier. */
  @Column({ name: 'resource_id' })
  resourceId: string;

  /** FOCUS dimension where anomaly occurred (e.g. 'serviceCategory', 'resourceId'). */
  @Column()
  dimension: string;

  /** Root cause classification: 'sku_change' | 'autoscaling' | 'new_resource' | 'pricing_change' | 'usage_spike' | 'unknown'. */
  @Column({ name: 'root_cause_type' })
  rootCauseType: string;

  /** Agent's natural-language root-cause explanation. */
  @Column({ name: 'root_cause_description', type: 'text' })
  rootCauseDescription: string;

  /** Action taken to resolve the anomaly: 'reverted' | 'accepted' | 'mitigated' | 'no_action'. */
  @Column({ name: 'resolution_action', type: 'varchar', nullable: true })
  resolutionAction: string | null;

  /** Whether this anomaly pattern has been observed previously. */
  @Column({ name: 'is_recurring', default: false })
  isRecurring: boolean;

  /** Total occurrences recorded for this anomaly pattern. */
  @Column({ name: 'recurrence_count', type: 'integer', default: 1 })
  recurrenceCount: number;

  /** Compressed ReAct reasoning trace (Thought/Action/Observation steps) stored as JSON. */
  @Column({ name: 'investigation_trace', type: 'jsonb', nullable: true })
  investigationTrace: Record<string, unknown> | null;

  /** User or system identifier that confirmed/approved resolution. */
  @Column({ name: 'resolved_by', type: 'varchar', nullable: true })
  resolvedBy: string | null;


  @CreateDateColumn({ name: 'created_at', type: 'timestamp with time zone' })
  createdAt: Date;

  @UpdateDateColumn({ name: 'updated_at', type: 'timestamp with time zone' })
  updatedAt: Date;
}
