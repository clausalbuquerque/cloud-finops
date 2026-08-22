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
import { ConsumptionRecordEntity } from './consumption-record.entity';

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

  @OneToMany(() => ConsumptionRecordEntity, (consumptionRecord) => consumptionRecord.resourceGroup)
  consumptionRecords: ConsumptionRecordEntity[];
}
