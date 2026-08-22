import {
  Entity,
  PrimaryGeneratedColumn,
  Column,
  CreateDateColumn,
  UpdateDateColumn,
  ManyToOne,
  OneToMany,
  JoinColumn,
  Index,
} from 'typeorm';
import { SubscriptionEntity } from './subscription.entity';
import { ResourceGroupEntity } from './resource-group.entity';
import { MetricDataPointEntity } from './metric-data-point.entity';
import { UtilizationSummaryEntity } from './utilization-summary.entity';

/**
 * Represents an Azure resource tracked for utilization metrics collection.
 *
 * Each tracked resource maps to a single Azure ARM resource and stores
 * provisioned capacity metadata needed for right-sizing analysis.
 */
@Entity('tracked_resources')
@Index(['azureResourceId'], { unique: true })
@Index(['resourceType'])
@Index(['isActive'])
export class TrackedResourceEntity {
  @PrimaryGeneratedColumn('uuid')
  id: string;

  /** Full Azure ARM resource ID (e.g., /subscriptions/.../providers/Microsoft.Compute/virtualMachines/my-vm). */
  @Column({ name: 'azure_resource_id' })
  azureResourceId: string;

  /** Display name of the resource. */
  @Column({ name: 'resource_name' })
  resourceName: string;

  /** Azure resource type (e.g., Microsoft.Compute/virtualMachines). */
  @Column({ name: 'resource_type' })
  resourceType: string;

  /** Azure region (e.g., eastus, westeurope). */
  @Column({ nullable: true })
  region: string;

  /** SKU or pricing tier (e.g., Standard_D2s_v3, P1v3). */
  @Column({ nullable: true })
  sku: string;

  /**
   * Provisioned capacity metadata as JSON.
   * Stores resource-specific capacity info for right-sizing context.
   * Examples: { vCPUs: 4, memoryGB: 16 }, { dtu: 100 }, { storageTB: 2 }
   */
  @Column({ name: 'provisioned_capacity', type: 'jsonb', nullable: true })
  provisionedCapacity: Record<string, unknown> | null;

  /** Whether this resource is currently active and being monitored. */
  @Column({ name: 'is_active', default: true })
  isActive: boolean;

  /** Timestamp of the last successful metric sync for this resource. */
  @Column({ name: 'last_metric_sync', type: 'timestamptz', nullable: true })
  lastMetricSync: Date | null;

  @ManyToOne(() => SubscriptionEntity, { onDelete: 'CASCADE' })
  @JoinColumn({ name: 'subscription_id' })
  subscription: SubscriptionEntity;

  @Column({ name: 'subscription_id' })
  subscriptionId: string;

  @ManyToOne(() => ResourceGroupEntity, { onDelete: 'CASCADE' })
  @JoinColumn({ name: 'resource_group_id' })
  resourceGroup: ResourceGroupEntity;

  @Column({ name: 'resource_group_id' })
  resourceGroupId: string;

  @CreateDateColumn({ name: 'created_at' })
  createdAt: Date;

  @UpdateDateColumn({ name: 'updated_at' })
  updatedAt: Date;

  @OneToMany(() => MetricDataPointEntity, (dp) => dp.trackedResource)
  metricDataPoints: MetricDataPointEntity[];

  @OneToMany(() => UtilizationSummaryEntity, (us) => us.trackedResource)
  utilizationSummaries: UtilizationSummaryEntity[];
}
