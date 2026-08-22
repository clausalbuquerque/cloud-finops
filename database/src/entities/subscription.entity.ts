import {
  Entity,
  PrimaryGeneratedColumn,
  Column,
  CreateDateColumn,
  UpdateDateColumn,
  OneToMany,
} from 'typeorm';
import { ResourceGroupEntity } from './resource-group.entity';

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
