import {
  Entity,
  PrimaryGeneratedColumn,
  Column,
  CreateDateColumn,
  UpdateDateColumn,
  ManyToOne,
  JoinColumn,
  Index,
} from 'typeorm';
import { TrackedResourceEntity } from './tracked-resource.entity';

/**
 * Represents the SRE Agent's interpreted understanding of normal utilization patterns.
 *
 * Stores workload baselines (e.g. night-time batch job vs daytime interactive) to
 * contextualize raw metrics and suppress false-positive underuse alerts.
 */
@Entity('infrastructure_baselines')
@Index(['trackedResourceId', 'metricName'])
@Index(['resourceId', 'metricName'])
@Index(['providerName', 'suppressUnderuseAlerts'])
export class InfrastructureBaselineEntity {
  @PrimaryGeneratedColumn('uuid')
  id: string;

  @ManyToOne(() => TrackedResourceEntity, { onDelete: 'SET NULL', nullable: true })
  @JoinColumn({ name: 'tracked_resource_id' })
  trackedResource: TrackedResourceEntity | null;

  @Column({ name: 'tracked_resource_id', type: 'uuid', nullable: true })
  trackedResourceId: string | null;

  /** Provider-neutral or opaque resource identifier. */
  @Column({ name: 'resource_id' })
  resourceId: string;

  /** Cloud provider name (e.g. 'GCP', 'Azure', 'AWS'). */
  @Column({ name: 'provider_name', default: 'GCP' })
  providerName: string;

  /** Metric name this baseline characterizes (e.g. 'Percentage CPU', 'cpu_utilization'). */
  @Column({ name: 'metric_name' })
  metricName: string;

  /** Classification: 'workload_pattern' | 'seasonal' | 'event_driven'. */
  @Column({ name: 'baseline_type' })
  baselineType: string;

  /**
   * Expected pattern definition stored as JSON.
   * e.g. { schedule: 'weekday_nights', expectedUtilization: { low: 5, high: 85 }, description: 'Nightly batch ETL' }
   */
  @Column({ name: 'expected_pattern', type: 'jsonb' })
  expectedPattern: Record<string, unknown>;

  /** Whether underuse alerts should be suppressed when metrics match the expected pattern. */
  @Column({ name: 'suppress_underuse_alerts', default: false })
  suppressUnderuseAlerts: boolean;

  /** Confidence score in this baseline (0.0 to 1.0). */
  @Column({ name: 'confidence_score', type: 'double precision', default: 1.0 })
  confidenceScore: number;

  /** Metric samples, telemetry window, or user notes supporting this baseline. */
  @Column({ type: 'jsonb', nullable: true })
  evidence: Record<string, unknown> | null;

  /** Provenance of the baseline: 'agent_inferred' | 'user_confirmed' | 'user_defined'. */
  @Column({ name: 'established_by', default: 'agent_inferred' })
  establishedBy: string;

  /** Timestamp when this baseline was last verified against live metric distributions. */
  @Column({ name: 'last_validated', type: 'timestamp with time zone', nullable: true })
  lastValidated: Date | null;

  @CreateDateColumn({ name: 'created_at', type: 'timestamp with time zone' })
  createdAt: Date;

  @UpdateDateColumn({ name: 'updated_at', type: 'timestamp with time zone' })
  updatedAt: Date;
}
