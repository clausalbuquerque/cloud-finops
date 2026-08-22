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
 * Maps to Azure Monitor metric definitions. The `isUtilizationMetric` flag
 * marks metrics relevant for underuse detection.
 */
@Entity('metric_definitions')
@Index(['resourceType', 'isUtilizationMetric'])
@Index(['resourceType', 'metricName'], { unique: true })
export class MetricDefinitionEntity {
  @PrimaryGeneratedColumn('uuid')
  id: string;

  /** Azure resource type this metric applies to (e.g., Microsoft.Compute/virtualMachines). */
  @Column({ name: 'resource_type' })
  resourceType: string;

  /** Azure Monitor metric namespace (e.g., Microsoft.Compute/virtualMachines). */
  @Column({ name: 'metric_namespace' })
  metricNamespace: string;

  /** Azure Monitor metric name (e.g., Percentage CPU, Available Memory Bytes). */
  @Column({ name: 'metric_name' })
  metricName: string;

  /** Human-readable display name. */
  @Column({ name: 'display_name', nullable: true })
  displayName: string;

  /** Unit of measure for this metric. */
  @Column({ type: 'enum', enum: MetricUnit, default: MetricUnit.Unspecified })
  unit: MetricUnit;

  /** Primary aggregation type recommended by Azure for this metric. */
  @Column({
    name: 'primary_aggregation_type',
    type: 'enum',
    enum: AggregationType,
    default: AggregationType.Average,
  })
  primaryAggregationType: AggregationType;

  /** All aggregation types supported by this metric. */
  @Column({
    name: 'supported_aggregation_types',
    type: 'text',
    array: true,
    default: '{}',
  })
  supportedAggregationTypes: string[];

  /** Whether this metric is relevant for utilization/underuse detection. */
  @Column({ name: 'is_utilization_metric', default: false })
  isUtilizationMetric: boolean;

  @CreateDateColumn({ name: 'created_at' })
  createdAt: Date;

  @UpdateDateColumn({ name: 'updated_at' })
  updatedAt: Date;
}
