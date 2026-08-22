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
import { TimeGrain } from './enums';

/**
 * Represents a daily utilization summary for a tracked resource.
 *
 * This is a daily roll-up table computed from raw metric data points.
 * It provides the primary query surface for AI agents and dashboards
 * to identify underused resources.
 */
@Entity('utilization_summaries')
@Index(['trackedResource', 'summaryDate'])
@Index(['isUnderused'])
@Index(['summaryDate'])
export class UtilizationSummaryEntity {
  @PrimaryGeneratedColumn('uuid')
  id: string;

  @ManyToOne(() => TrackedResourceEntity, (tr) => tr.utilizationSummaries, { onDelete: 'CASCADE' })
  @JoinColumn({ name: 'tracked_resource_id' })
  trackedResource: TrackedResourceEntity;

  @Column({ name: 'tracked_resource_id' })
  trackedResourceId: string;

  /** Date of the summary (one row per resource per metric per day). */
  @Column({ name: 'summary_date', type: 'date' })
  summaryDate: Date;

  /** Metric name this summary refers to (e.g., "Percentage CPU"). */
  @Column({ name: 'metric_name' })
  metricName: string;

  /** Average utilization over the day. */
  @Column({ name: 'avg_utilization', type: 'double precision' })
  avgUtilization: number;

  /** Maximum utilization over the day. */
  @Column({ name: 'max_utilization', type: 'double precision' })
  maxUtilization: number;

  /** Minimum utilization over the day. */
  @Column({ name: 'min_utilization', type: 'double precision' })
  minUtilization: number;

  /** 95th percentile utilization (nullable — computed when enough data). */
  @Column({ name: 'p95_utilization', type: 'double precision', nullable: true })
  p95Utilization: number | null;

  /** Number of data point samples used to compute this summary. */
  @Column({ name: 'sample_count', type: 'integer' })
  sampleCount: number;

  /** Time grain of the source data points. */
  @Column({ name: 'time_grain', type: 'enum', enum: TimeGrain, default: TimeGrain.PT1H })
  timeGrain: TimeGrain;

  /** Whether the resource is flagged as underused for this metric on this day. */
  @Column({ name: 'is_underused', default: false })
  isUnderused: boolean;

  /** The threshold that was applied to determine underuse (e.g., 10 for "avg CPU < 10%"). */
  @Column({ name: 'underuse_threshold', type: 'double precision', nullable: true })
  underuseThreshold: number | null;

  @CreateDateColumn({ name: 'created_at' })
  createdAt: Date;

  @UpdateDateColumn({ name: 'updated_at' })
  updatedAt: Date;
}
