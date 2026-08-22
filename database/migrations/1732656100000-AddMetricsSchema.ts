import { MigrationInterface, QueryRunner } from 'typeorm';

export class AddMetricsSchema1732656100000 implements MigrationInterface {
  name = 'AddMetricsSchema1732656100000';

  public async up(queryRunner: QueryRunner): Promise<void> {
    // Create enums
    await queryRunner.query(`
      CREATE TYPE "finops"."metric_unit_enum" AS ENUM (
        'Count', 'Bytes', 'Seconds', 'CountPerSecond', 'BytesPerSecond',
        'Percent', 'MilliSeconds', 'ByteSeconds', 'Cores', 'MilliCores',
        'NanoCores', 'BitsPerSecond', 'Unspecified'
      )
    `);

    await queryRunner.query(`
      CREATE TYPE "finops"."aggregation_type_enum" AS ENUM (
        'Average', 'Minimum', 'Maximum', 'Total', 'Count', 'None'
      )
    `);

    await queryRunner.query(`
      CREATE TYPE "finops"."time_grain_enum" AS ENUM (
        'PT1M', 'PT5M', 'PT15M', 'PT30M', 'PT1H', 'PT6H', 'PT12H', 'P1D'
      )
    `);

    // ── tracked_resources ──────────────────────────────────────────────
    await queryRunner.query(`
      CREATE TABLE "finops"."tracked_resources" (
        "id" uuid NOT NULL DEFAULT uuid_generate_v4(),
        "azure_resource_id" character varying NOT NULL,
        "resource_name" character varying NOT NULL,
        "resource_type" character varying NOT NULL,
        "region" character varying,
        "sku" character varying,
        "provisioned_capacity" jsonb,
        "is_active" boolean NOT NULL DEFAULT true,
        "last_metric_sync" TIMESTAMP WITH TIME ZONE,
        "subscription_id" uuid NOT NULL,
        "resource_group_id" uuid NOT NULL,
        "created_at" TIMESTAMP NOT NULL DEFAULT now(),
        "updated_at" TIMESTAMP NOT NULL DEFAULT now(),
        CONSTRAINT "PK_tracked_resources" PRIMARY KEY ("id")
      )
    `);

    await queryRunner.query(`
      CREATE UNIQUE INDEX "IDX_tracked_resources_azure_resource_id"
      ON "finops"."tracked_resources" ("azure_resource_id")
    `);

    await queryRunner.query(`
      CREATE INDEX "IDX_tracked_resources_resource_type"
      ON "finops"."tracked_resources" ("resource_type")
    `);

    await queryRunner.query(`
      CREATE INDEX "IDX_tracked_resources_is_active"
      ON "finops"."tracked_resources" ("is_active")
    `);

    await queryRunner.query(`
      ALTER TABLE "finops"."tracked_resources"
      ADD CONSTRAINT "FK_tracked_resources_subscription"
      FOREIGN KEY ("subscription_id") REFERENCES "finops"."subscriptions"("id") ON DELETE CASCADE
    `);

    await queryRunner.query(`
      ALTER TABLE "finops"."tracked_resources"
      ADD CONSTRAINT "FK_tracked_resources_resource_group"
      FOREIGN KEY ("resource_group_id") REFERENCES "finops"."resource_groups"("id") ON DELETE CASCADE
    `);

    // ── metric_definitions ─────────────────────────────────────────────
    await queryRunner.query(`
      CREATE TABLE "finops"."metric_definitions" (
        "id" uuid NOT NULL DEFAULT uuid_generate_v4(),
        "resource_type" character varying NOT NULL,
        "metric_namespace" character varying NOT NULL,
        "metric_name" character varying NOT NULL,
        "display_name" character varying,
        "unit" "finops"."metric_unit_enum" NOT NULL DEFAULT 'Unspecified',
        "primary_aggregation_type" "finops"."aggregation_type_enum" NOT NULL DEFAULT 'Average',
        "supported_aggregation_types" text[] NOT NULL DEFAULT '{}',
        "is_utilization_metric" boolean NOT NULL DEFAULT false,
        "created_at" TIMESTAMP NOT NULL DEFAULT now(),
        "updated_at" TIMESTAMP NOT NULL DEFAULT now(),
        CONSTRAINT "PK_metric_definitions" PRIMARY KEY ("id")
      )
    `);

    await queryRunner.query(`
      CREATE UNIQUE INDEX "IDX_metric_definitions_resource_type_metric_name"
      ON "finops"."metric_definitions" ("resource_type", "metric_name")
    `);

    await queryRunner.query(`
      CREATE INDEX "IDX_metric_definitions_resource_type_is_utilization"
      ON "finops"."metric_definitions" ("resource_type", "is_utilization_metric")
    `);

    // ── metric_data_points ─────────────────────────────────────────────
    await queryRunner.query(`
      CREATE TABLE "finops"."metric_data_points" (
        "id" uuid NOT NULL DEFAULT uuid_generate_v4(),
        "tracked_resource_id" uuid NOT NULL,
        "metric_definition_id" uuid NOT NULL,
        "timestamp" TIMESTAMP WITH TIME ZONE NOT NULL,
        "time_grain" "finops"."time_grain_enum" NOT NULL DEFAULT 'PT1H',
        "average" double precision,
        "minimum" double precision,
        "maximum" double precision,
        "total" double precision,
        "count" double precision,
        "dimension_key" character varying,
        "dimension_value" character varying,
        "created_at" TIMESTAMP NOT NULL DEFAULT now(),
        CONSTRAINT "PK_metric_data_points" PRIMARY KEY ("id")
      )
    `);

    await queryRunner.query(`
      CREATE INDEX "IDX_metric_data_points_resource_definition_timestamp_grain"
      ON "finops"."metric_data_points" ("tracked_resource_id", "metric_definition_id", "timestamp", "time_grain")
    `);

    await queryRunner.query(`
      CREATE INDEX "IDX_metric_data_points_resource_timestamp"
      ON "finops"."metric_data_points" ("tracked_resource_id", "timestamp")
    `);

    await queryRunner.query(`
      CREATE INDEX "IDX_metric_data_points_timestamp"
      ON "finops"."metric_data_points" ("timestamp")
    `);

    await queryRunner.query(`
      ALTER TABLE "finops"."metric_data_points"
      ADD CONSTRAINT "FK_metric_data_points_tracked_resource"
      FOREIGN KEY ("tracked_resource_id") REFERENCES "finops"."tracked_resources"("id") ON DELETE CASCADE
    `);

    await queryRunner.query(`
      ALTER TABLE "finops"."metric_data_points"
      ADD CONSTRAINT "FK_metric_data_points_metric_definition"
      FOREIGN KEY ("metric_definition_id") REFERENCES "finops"."metric_definitions"("id") ON DELETE CASCADE
    `);

    // ── utilization_summaries ──────────────────────────────────────────
    await queryRunner.query(`
      CREATE TABLE "finops"."utilization_summaries" (
        "id" uuid NOT NULL DEFAULT uuid_generate_v4(),
        "tracked_resource_id" uuid NOT NULL,
        "summary_date" date NOT NULL,
        "metric_name" character varying NOT NULL,
        "avg_utilization" double precision NOT NULL,
        "max_utilization" double precision NOT NULL,
        "min_utilization" double precision NOT NULL,
        "p95_utilization" double precision,
        "sample_count" integer NOT NULL,
        "time_grain" "finops"."time_grain_enum" NOT NULL DEFAULT 'PT1H',
        "is_underused" boolean NOT NULL DEFAULT false,
        "underuse_threshold" double precision,
        "created_at" TIMESTAMP NOT NULL DEFAULT now(),
        "updated_at" TIMESTAMP NOT NULL DEFAULT now(),
        CONSTRAINT "PK_utilization_summaries" PRIMARY KEY ("id")
      )
    `);

    await queryRunner.query(`
      CREATE INDEX "IDX_utilization_summaries_resource_date"
      ON "finops"."utilization_summaries" ("tracked_resource_id", "summary_date")
    `);

    await queryRunner.query(`
      CREATE INDEX "IDX_utilization_summaries_is_underused"
      ON "finops"."utilization_summaries" ("is_underused")
    `);

    await queryRunner.query(`
      CREATE INDEX "IDX_utilization_summaries_summary_date"
      ON "finops"."utilization_summaries" ("summary_date")
    `);

    await queryRunner.query(`
      ALTER TABLE "finops"."utilization_summaries"
      ADD CONSTRAINT "FK_utilization_summaries_tracked_resource"
      FOREIGN KEY ("tracked_resource_id") REFERENCES "finops"."tracked_resources"("id") ON DELETE CASCADE
    `);
  }

  public async down(queryRunner: QueryRunner): Promise<void> {
    // Drop FK constraints
    await queryRunner.query(`ALTER TABLE "finops"."utilization_summaries" DROP CONSTRAINT "FK_utilization_summaries_tracked_resource"`);
    await queryRunner.query(`ALTER TABLE "finops"."metric_data_points" DROP CONSTRAINT "FK_metric_data_points_metric_definition"`);
    await queryRunner.query(`ALTER TABLE "finops"."metric_data_points" DROP CONSTRAINT "FK_metric_data_points_tracked_resource"`);
    await queryRunner.query(`ALTER TABLE "finops"."tracked_resources" DROP CONSTRAINT "FK_tracked_resources_resource_group"`);
    await queryRunner.query(`ALTER TABLE "finops"."tracked_resources" DROP CONSTRAINT "FK_tracked_resources_subscription"`);

    // Drop indexes
    await queryRunner.query(`DROP INDEX "finops"."IDX_utilization_summaries_summary_date"`);
    await queryRunner.query(`DROP INDEX "finops"."IDX_utilization_summaries_is_underused"`);
    await queryRunner.query(`DROP INDEX "finops"."IDX_utilization_summaries_resource_date"`);
    await queryRunner.query(`DROP INDEX "finops"."IDX_metric_data_points_timestamp"`);
    await queryRunner.query(`DROP INDEX "finops"."IDX_metric_data_points_resource_timestamp"`);
    await queryRunner.query(`DROP INDEX "finops"."IDX_metric_data_points_resource_definition_timestamp_grain"`);
    await queryRunner.query(`DROP INDEX "finops"."IDX_metric_definitions_resource_type_is_utilization"`);
    await queryRunner.query(`DROP INDEX "finops"."IDX_metric_definitions_resource_type_metric_name"`);
    await queryRunner.query(`DROP INDEX "finops"."IDX_tracked_resources_is_active"`);
    await queryRunner.query(`DROP INDEX "finops"."IDX_tracked_resources_resource_type"`);
    await queryRunner.query(`DROP INDEX "finops"."IDX_tracked_resources_azure_resource_id"`);

    // Drop tables
    await queryRunner.query(`DROP TABLE "finops"."utilization_summaries"`);
    await queryRunner.query(`DROP TABLE "finops"."metric_data_points"`);
    await queryRunner.query(`DROP TABLE "finops"."metric_definitions"`);
    await queryRunner.query(`DROP TABLE "finops"."tracked_resources"`);

    // Drop enums
    await queryRunner.query(`DROP TYPE "finops"."time_grain_enum"`);
    await queryRunner.query(`DROP TYPE "finops"."aggregation_type_enum"`);
    await queryRunner.query(`DROP TYPE "finops"."metric_unit_enum"`);
  }
}
