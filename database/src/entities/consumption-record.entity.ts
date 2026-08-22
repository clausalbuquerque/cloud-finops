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
import { ResourceGroupEntity } from './resource-group.entity';

@Entity('consumption_records')
@Index(['subscription', 'resourceGroup', 'usageDate'])
@Index(['usageDate'])
@Index(['resourceType'])
@Index(['meterCategory'])
export class ConsumptionRecordEntity {
  @PrimaryGeneratedColumn('uuid')
  id: string;

  // FOCUS Core Fields
  @Column({ name: 'billing_account_id', nullable: true })
  billingAccountId: string;

  @Column({ name: 'billing_account_name', nullable: true })
  billingAccountName: string;

  @Column({ name: 'billing_currency', default: 'USD' })
  billingCurrency: string;

  @Column({ name: 'billing_period_end', type: 'date', nullable: true })
  billingPeriodEnd: Date;

  @Column({ name: 'billing_period_start', type: 'date', nullable: true })
  billingPeriodStart: Date;

  @Column({ name: 'charge_type', nullable: true })
  chargeType: string;

  @Column({ name: 'effective_cost', type: 'decimal', precision: 18, scale: 6, nullable: true })
  effectiveCost: number;

  @Column({ name: 'invoice_id', nullable: true })
  invoiceId: string;

  @Column({ name: 'meter_category', nullable: true })
  meterCategory: string;

  @Column({ name: 'meter_id', nullable: true })
  meterId: string;

  @Column({ name: 'meter_name', nullable: true })
  meterName: string;

  @Column({ name: 'meter_region', nullable: true })
  meterRegion: string;

  @Column({ name: 'meter_subcategory', nullable: true })
  meterSubcategory: string;

  @Column({ name: 'pricing_model', nullable: true })
  pricingModel: string;

  @Column({ name: 'product_name', nullable: true })
  productName: string;

  @Column({ name: 'provider_name', default: 'Azure' })
  providerName: string;

  @Column({ name: 'publisher_name', nullable: true })
  publisherName: string;

  @Column({ name: 'quantity', type: 'decimal', precision: 18, scale: 6, nullable: true })
  quantity: number;

  @Column({ name: 'resource_id', nullable: true })
  resourceId: string;

  @Column({ name: 'resource_location', nullable: true })
  resourceLocation: string;

  @Column({ name: 'resource_name', nullable: true })
  resourceName: string;

  @Column({ name: 'resource_type', nullable: true })
  resourceType: string;

  @Column({ name: 'service_category', nullable: true })
  serviceCategory: string;

  @Column({ name: 'service_name', nullable: true })
  serviceName: string;

  @Column({ name: 'sku_id', nullable: true })
  skuId: string;

  @Column({ name: 'sku_price_id', nullable: true })
  skuPriceId: string;

  @Column({ name: 'sub_account_id', nullable: true })
  subAccountId: string;

  @Column({ name: 'sub_account_name', nullable: true })
  subAccountName: string;

  @Column({ name: 'tags', type: 'jsonb', nullable: true })
  tags: Record<string, unknown>;

  @Column({ name: 'unit_of_measure', nullable: true })
  unitOfMeasure: string;

  @Column({ name: 'unit_price', type: 'decimal', precision: 18, scale: 6, nullable: true })
  unitPrice: number;

  @Column({ name: 'usage_date', type: 'date' })
  usageDate: Date;

  @Column({ name: 'usage_quantity', type: 'decimal', precision: 18, scale: 6, nullable: true })
  usageQuantity: number;

  @Column({ name: 'usage_unit', nullable: true })
  usageUnit: string;

  // Relations
  @ManyToOne(() => SubscriptionEntity, (subscription) => subscription.resourceGroups, {
    onDelete: 'CASCADE',
  })
  @JoinColumn({ name: 'subscription_id' })
  subscription: SubscriptionEntity;

  @Column({ name: 'subscription_id' })
  subscriptionId: string;

  @ManyToOne(() => ResourceGroupEntity, (resourceGroup) => resourceGroup.consumptionRecords, {
    onDelete: 'CASCADE',
  })
  @JoinColumn({ name: 'resource_group_id' })
  resourceGroup: ResourceGroupEntity;

  @Column({ name: 'resource_group_id' })
  resourceGroupId: string;

  @CreateDateColumn({ name: 'created_at' })
  createdAt: Date;

  @UpdateDateColumn({ name: 'updated_at' })
  updatedAt: Date;
}
