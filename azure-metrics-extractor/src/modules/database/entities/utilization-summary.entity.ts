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
 * This is a local copy for TypeORM registration within this service.
 * The canonical definition lives in `database/src/entities/utilization-summary.entity.ts`.
 * Migrations are managed by the `database` package.
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

  @Column({ name: 'summary_date', type: 'date' })
  summaryDate: Date;

  @Column({ name: 'metric_name' })
  metricName: string;

  @Column({ name: 'avg_utilization', type: 'double precision' })
  avgUtilization: number;

  @Column({ name: 'max_utilization', type: 'double precision' })
  maxUtilization: number;

  @Column({ name: 'min_utilization', type: 'double precision' })
  minUtilization: number;

  @Column({ name: 'p95_utilization', type: 'double precision', nullable: true })
  p95Utilization: number | null;

  @Column({ name: 'sample_count', type: 'integer' })
  sampleCount: number;

  @Column({ name: 'time_grain', type: 'enum', enum: TimeGrain, default: TimeGrain.PT1H })
  timeGrain: TimeGrain;

  @Column({ name: 'is_underused', default: false })
  isUnderused: boolean;

  @Column({ name: 'underuse_threshold', type: 'double precision', nullable: true })
  underuseThreshold: number | null;

  @CreateDateColumn({ name: 'created_at' })
  createdAt: Date;

  @UpdateDateColumn({ name: 'updated_at' })
  updatedAt: Date;
}
