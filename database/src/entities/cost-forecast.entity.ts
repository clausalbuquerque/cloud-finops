import { Entity, PrimaryGeneratedColumn, Column, CreateDateColumn, Index } from 'typeorm';

@Entity({ name: 'cost_forecasts', schema: 'finops' })
@Index(['dimension', 'forecastDate'])
@Index(['providerName', 'forecastDate'])
export class CostForecastEntity {
  @PrimaryGeneratedColumn('uuid')
  id: string;

  @Column({ name: 'dimension', type: 'varchar', length: 128 })
  dimension: string;

  @Column({ name: 'provider_name', type: 'varchar', length: 64, default: 'GCP' })
  providerName: string;

  @Column({ name: 'forecast_date', type: 'date' })
  forecastDate: Date;

  @Column({ name: 'expected_cost', type: 'decimal', precision: 18, scale: 6 })
  expectedCost: number;

  @Column({ name: 'lower_bound', type: 'decimal', precision: 18, scale: 6 })
  lowerBound: number;

  @Column({ name: 'upper_bound', type: 'decimal', precision: 18, scale: 6 })
  upperBound: number;

  @Column({ name: 'confidence_level', type: 'double precision', default: 0.95 })
  confidenceLevel: number;

  @Column({ name: 'model_name', type: 'varchar', length: 64, default: 'ridge_seasonal' })
  modelName: string;

  @Column({ name: 'mape', type: 'double precision', nullable: true })
  mape: number | null;

  @CreateDateColumn({ name: 'generated_at', type: 'timestamptz' })
  generatedAt: Date;
}
