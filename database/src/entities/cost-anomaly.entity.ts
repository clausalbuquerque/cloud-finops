import { Entity, PrimaryGeneratedColumn, Column, CreateDateColumn, Index } from 'typeorm';

export type AnomalySeverity = 'low' | 'medium' | 'high' | 'critical';
export type AnomalyType = 'spike' | 'drift' | 'drop' | 'new_resource';
export type AnomalyStatus = 'detected' | 'investigating' | 'resolved' | 'dismissed';

@Entity({ name: 'cost_anomalies', schema: 'finops' })
@Index(['dimension', 'dimensionValue', 'detectedDate'])
@Index(['severity', 'status'])
@Index(['resourceId'])
export class CostAnomalyEntity {
  @PrimaryGeneratedColumn('uuid')
  id: string;

  @Column({ name: 'anomaly_id', type: 'varchar', length: 128, unique: true })
  anomalyId: string;

  @Column({ name: 'provider_name', type: 'varchar', length: 64, default: 'GCP' })
  providerName: string;

  @Column({ name: 'resource_id', type: 'varchar', length: 512, nullable: true })
  resourceId: string | null;

  @Column({ name: 'dimension', type: 'varchar', length: 64 })
  dimension: string;

  @Column({ name: 'dimension_value', type: 'varchar', length: 256 })
  dimensionValue: string;

  @Column({ name: 'detected_date', type: 'date' })
  detectedDate: Date;

  @Column({ name: 'actual_cost', type: 'decimal', precision: 18, scale: 6 })
  actualCost: number;

  @Column({ name: 'expected_cost', type: 'decimal', precision: 18, scale: 6 })
  expectedCost: number;

  @Column({ name: 'cost_delta', type: 'decimal', precision: 18, scale: 6 })
  costDelta: number;

  @Column({ name: 'percentage_delta', type: 'double precision' })
  percentageDelta: number;

  @Column({ name: 'z_score', type: 'double precision', nullable: true })
  zScore: number | null;

  @Column({ name: 'severity', type: 'varchar', length: 32, default: 'medium' })
  severity: AnomalySeverity;

  @Column({ name: 'anomaly_type', type: 'varchar', length: 32, default: 'spike' })
  anomalyType: AnomalyType;

  @Column({ name: 'status', type: 'varchar', length: 32, default: 'detected' })
  status: AnomalyStatus;

  @Column({ name: 'details', type: 'jsonb', nullable: true })
  details: Record<string, unknown> | null;

  @CreateDateColumn({ name: 'detected_at', type: 'timestamptz' })
  detectedAt: Date;
}
