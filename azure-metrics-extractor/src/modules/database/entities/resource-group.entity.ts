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
import { SubscriptionEntity } from './subscription.entity';

/**
 * Resource group entity mirroring the shared database schema.
 *
 * This is a local copy for TypeORM registration within this service.
 * The canonical definition lives in `database/src/entities/resource-group.entity.ts`.
 * Migrations are managed by the `database` package.
 */
@Entity('resource_groups')
@Index(['subscription', 'name'], { unique: true })
export class ResourceGroupEntity {
  @PrimaryGeneratedColumn('uuid')
  id: string;

  @Column()
  name: string;

  @Column({ nullable: true })
  location: string;

  @ManyToOne(() => SubscriptionEntity, (subscription) => subscription.resourceGroups, {
    onDelete: 'CASCADE',
  })
  @JoinColumn({ name: 'subscription_id' })
  subscription: SubscriptionEntity;

  @Column({ name: 'subscription_id' })
  subscriptionId: string;

  @CreateDateColumn({ name: 'created_at' })
  createdAt: Date;

  @UpdateDateColumn({ name: 'updated_at' })
  updatedAt: Date;
}
