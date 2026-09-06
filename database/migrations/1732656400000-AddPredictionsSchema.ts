import { MigrationInterface, QueryRunner } from 'typeorm';

export class AddPredictionsSchema1732656400000 implements MigrationInterface {
  name = 'AddPredictionsSchema1732656400000';

  public async up(queryRunner: QueryRunner): Promise<void> {
    // 1. Create finops.cost_forecasts table
    await queryRunner.query(`
      CREATE TABLE "finops"."cost_forecasts" (
        "id" uuid NOT NULL DEFAULT uuid_generate_v4(),
        "dimension" character varying(128) NOT NULL,
        "provider_name" character varying(64) NOT NULL DEFAULT 'GCP',
        "forecast_date" date NOT NULL,
        "expected_cost" numeric(18,6) NOT NULL,
        "lower_bound" numeric(18,6) NOT NULL,
        "upper_bound" numeric(18,6) NOT NULL,
        "confidence_level" double precision NOT NULL DEFAULT 0.95,
        "model_name" character varying(64) NOT NULL DEFAULT 'ridge_seasonal',
        "mape" double precision,
        "generated_at" TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now(),
        CONSTRAINT "PK_cost_forecasts" PRIMARY KEY ("id")
      )
    `);

    await queryRunner.query(`
      CREATE INDEX "IDX_cost_forecasts_dimension_forecast_date"
      ON "finops"."cost_forecasts" ("dimension", "forecast_date")
    `);

    await queryRunner.query(`
      CREATE INDEX "IDX_cost_forecasts_provider_forecast_date"
      ON "finops"."cost_forecasts" ("provider_name", "forecast_date")
    `);

    // 2. Create finops.cost_anomalies table
    await queryRunner.query(`
      CREATE TABLE "finops"."cost_anomalies" (
        "id" uuid NOT NULL DEFAULT uuid_generate_v4(),
        "anomaly_id" character varying(128) NOT NULL,
        "provider_name" character varying(64) NOT NULL DEFAULT 'GCP',
        "resource_id" character varying(512),
        "dimension" character varying(64) NOT NULL,
        "dimension_value" character varying(256) NOT NULL,
        "detected_date" date NOT NULL,
        "actual_cost" numeric(18,6) NOT NULL,
        "expected_cost" numeric(18,6) NOT NULL,
        "cost_delta" numeric(18,6) NOT NULL,
        "percentage_delta" double precision NOT NULL,
        "z_score" double precision,
        "severity" character varying(32) NOT NULL DEFAULT 'medium',
        "anomaly_type" character varying(32) NOT NULL DEFAULT 'spike',
        "status" character varying(32) NOT NULL DEFAULT 'detected',
        "details" jsonb,
        "detected_at" TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now(),
        CONSTRAINT "PK_cost_anomalies" PRIMARY KEY ("id"),
        CONSTRAINT "UQ_cost_anomalies_anomaly_id" UNIQUE ("anomaly_id")
      )
    `);

    await queryRunner.query(`
      CREATE INDEX "IDX_cost_anomalies_dim_val_date"
      ON "finops"."cost_anomalies" ("dimension", "dimension_value", "detected_date")
    `);

    await queryRunner.query(`
      CREATE INDEX "IDX_cost_anomalies_severity_status"
      ON "finops"."cost_anomalies" ("severity", "status")
    `);

    await queryRunner.query(`
      CREATE INDEX "IDX_cost_anomalies_resource_id"
      ON "finops"."cost_anomalies" ("resource_id")
    `);
  }

  public async down(queryRunner: QueryRunner): Promise<void> {
    await queryRunner.query(`DROP INDEX "finops"."IDX_cost_anomalies_resource_id"`);
    await queryRunner.query(`DROP INDEX "finops"."IDX_cost_anomalies_severity_status"`);
    await queryRunner.query(`DROP INDEX "finops"."IDX_cost_anomalies_dim_val_date"`);
    await queryRunner.query(`DROP TABLE "finops"."cost_anomalies"`);

    await queryRunner.query(`DROP INDEX "finops"."IDX_cost_forecasts_provider_forecast_date"`);
    await queryRunner.query(`DROP INDEX "finops"."IDX_cost_forecasts_dimension_forecast_date"`);
    await queryRunner.query(`DROP TABLE "finops"."cost_forecasts"`);
  }
}
