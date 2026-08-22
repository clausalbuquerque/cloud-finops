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
 * This is a local copy for TypeORM registration within this service.
 * The canonical definition lives in `database/src/entities/tracked-resource.entity.ts`.
 * Migrations are managed by the `database` package.
 */
@Entity('tracked_resources')
@Index(['azureResourceId'], { unique: true })
@Index(['resourceType'])
@Index(['isActive'])
export class TrackedResourceEntity {
  @PrimaryGeneratedColumn('uuid')
  id: string;

  @Column({ name: 'azure_resource_id' })
  azureResourceId: string;

  @Column({ name: 'resource_name' })
  resourceName: string;

  @Column({ name: 'resource_type' })
  resourceType: string;

  @Column({ nullable: true })
  region: string;

  @Column({ nullable: true })
  sku: string;

  @Column({ name: 'provisioned_capacity', type: 'jsonb', nullable: true })
  provisionedCapacity: Record<string, unknown> | null;

  @Column({ name: 'is_active', default: true })
  isActive: boolean;

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
