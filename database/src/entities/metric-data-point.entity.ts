import {
  Entity,
  PrimaryGeneratedColumn,
  Column,
  CreateDateColumn,
  ManyToOne,
  JoinColumn,
  Index,
} from 'typeorm';
import { TrackedResourceEntity } from './tracked-resource.entity';
import { MetricDefinitionEntity } from './metric-definition.entity';
import { TimeGrain } from './enums';

/**
 * Represents a single metric data point collected from Azure Monitor.
 *
 * Each row stores one time-series data point for a specific resource and metric,
 * with all aggregation values (avg, min, max, total, count) for a given time grain.
 */
@Entity('metric_data_points')
@Index(['trackedResource', 'metricDefinition', 'timestamp', 'timeGrain'])
@Index(['trackedResource', 'timestamp'])
@Index(['timestamp'])
export class MetricDataPointEntity {
  @PrimaryGeneratedColumn('uuid')
  id: string;

  @ManyToOne(() => TrackedResourceEntity, (tr) => tr.metricDataPoints, { onDelete: 'CASCADE' })
  @JoinColumn({ name: 'tracked_resource_id' })
  trackedResource: TrackedResourceEntity;

  @Column({ name: 'tracked_resource_id' })
  trackedResourceId: string;

  @ManyToOne(() => MetricDefinitionEntity, { onDelete: 'CASCADE' })
  @JoinColumn({ name: 'metric_definition_id' })
  metricDefinition: MetricDefinitionEntity;

  @Column({ name: 'metric_definition_id' })
  metricDefinitionId: string;

  /** Timestamp of the data point (UTC). */
  @Column({ type: 'timestamptz' })
  timestamp: Date;

  /** Time grain (resolution) of the data point. */
  @Column({ name: 'time_grain', type: 'enum', enum: TimeGrain, default: TimeGrain.PT1H })
  timeGrain: TimeGrain;

  /** Average value over the time grain period. */
  @Column({ type: 'double precision', nullable: true })
  average: number | null;

  /** Minimum value over the time grain period. */
  @Column({ type: 'double precision', nullable: true })
  minimum: number | null;

  /** Maximum value over the time grain period. */
  @Column({ type: 'double precision', nullable: true })
  maximum: number | null;

  /** Sum of values over the time grain period. */
  @Column({ type: 'double precision', nullable: true })
  total: number | null;

  /** Count of data points aggregated in this time grain period. */
  @Column({ type: 'double precision', nullable: true })
  count: number | null;

  /** Optional dimension key for multi-dimensional metrics (e.g., "Tier", "StatusCode"). */
  @Column({ name: 'dimension_key', type: 'varchar', nullable: true })
  dimensionKey: string | null;

  /** Optional dimension value (e.g., "Hot", "200"). */
  @Column({ name: 'dimension_value', type: 'varchar', nullable: true })
  dimensionValue: string | null;

  @CreateDateColumn({ name: 'created_at' })
  createdAt: Date;
}
