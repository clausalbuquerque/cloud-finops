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
 * This is a local copy for TypeORM registration within this service.
 * The canonical definition lives in `database/src/entities/metric-data-point.entity.ts`.
 * Migrations are managed by the `database` package.
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

  @Column({ type: 'timestamptz' })
  timestamp: Date;

  @Column({ name: 'time_grain', type: 'enum', enum: TimeGrain, default: TimeGrain.PT1H })
  timeGrain: TimeGrain;

  @Column({ type: 'double precision', nullable: true })
  average: number | null;

  @Column({ type: 'double precision', nullable: true })
  minimum: number | null;

  @Column({ type: 'double precision', nullable: true })
  maximum: number | null;

  @Column({ type: 'double precision', nullable: true })
  total: number | null;

  @Column({ type: 'double precision', nullable: true })
  count: number | null;

  @Column({ name: 'dimension_key', nullable: true })
  dimensionKey: string | null;

  @Column({ name: 'dimension_value', nullable: true })
  dimensionValue: string | null;

  @CreateDateColumn({ name: 'created_at' })
  createdAt: Date;
}
