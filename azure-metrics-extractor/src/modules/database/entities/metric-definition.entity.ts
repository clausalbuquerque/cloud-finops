import {
  Entity,
  PrimaryGeneratedColumn,
  Column,
  CreateDateColumn,
  UpdateDateColumn,
  Index,
} from 'typeorm';
import { MetricUnit, AggregationType } from './enums';

/**
 * Represents a metric definition available for a given Azure resource type.
 *
 * This is a local copy for TypeORM registration within this service.
 * The canonical definition lives in `database/src/entities/metric-definition.entity.ts`.
 * Migrations are managed by the `database` package.
 */
@Entity('metric_definitions')
@Index(['resourceType', 'isUtilizationMetric'])
@Index(['resourceType', 'metricName'], { unique: true })
export class MetricDefinitionEntity {
  @PrimaryGeneratedColumn('uuid')
  id: string;

  @Column({ name: 'resource_type' })
  resourceType: string;

  @Column({ name: 'metric_namespace' })
  metricNamespace: string;

  @Column({ name: 'metric_name' })
  metricName: string;

  @Column({ name: 'display_name', nullable: true })
  displayName: string;

  @Column({ type: 'enum', enum: MetricUnit, default: MetricUnit.Unspecified })
  unit: MetricUnit;

  @Column({
    name: 'primary_aggregation_type',
    type: 'enum',
    enum: AggregationType,
    default: AggregationType.Average,
  })
  primaryAggregationType: AggregationType;

  @Column({
    name: 'supported_aggregation_types',
    type: 'text',
    array: true,
    default: '{}',
  })
  supportedAggregationTypes: string[];

  @Column({ name: 'is_utilization_metric', default: false })
  isUtilizationMetric: boolean;

  @CreateDateColumn({ name: 'created_at' })
  createdAt: Date;

  @UpdateDateColumn({ name: 'updated_at' })
  updatedAt: Date;
}
