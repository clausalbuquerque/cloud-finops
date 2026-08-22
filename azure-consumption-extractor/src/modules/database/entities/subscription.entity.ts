import {
  Entity,
  PrimaryGeneratedColumn,
  Column,
  CreateDateColumn,
  UpdateDateColumn,
  OneToMany,
} from 'typeorm';
import { ResourceGroupEntity } from './resource-group.entity';

/**
 * Subscription entity mirroring the shared database schema.
 *
 * This is a local copy for TypeORM registration within this service.
 * The canonical definition lives in `database/src/entities/subscription.entity.ts`.
 * Migrations are managed by the `database` package.
 */
@Entity('subscriptions')
export class SubscriptionEntity {
  @PrimaryGeneratedColumn('uuid')
  id: string;

  @Column({ name: 'subscription_id', unique: true })
  subscriptionId: string;

  @Column({ name: 'display_name' })
  displayName: string;

  @Column({ nullable: true })
  state: string;

  @CreateDateColumn({ name: 'created_at' })
  createdAt: Date;

  @UpdateDateColumn({ name: 'updated_at' })
  updatedAt: Date;

  @OneToMany(() => ResourceGroupEntity, (resourceGroup) => resourceGroup.subscription)
  resourceGroups: ResourceGroupEntity[];
}
