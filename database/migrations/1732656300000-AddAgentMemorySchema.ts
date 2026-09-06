import { MigrationInterface, QueryRunner } from 'typeorm';

export class AddAgentMemorySchema1732656300000 implements MigrationInterface {
  name = 'AddAgentMemorySchema1732656300000';

  public async up(queryRunner: QueryRunner): Promise<void> {
    // ── optimization_recommendations ────────────────────────────────────
    await queryRunner.query(`
      CREATE TABLE "finops"."optimization_recommendations" (
        "id" uuid NOT NULL DEFAULT uuid_generate_v4(),
        "provider_name" character varying NOT NULL DEFAULT 'GCP',
        "resource_id" character varying NOT NULL,
        "resource_type" character varying NOT NULL,
        "recommendation_type" character varying NOT NULL,
        "current_state" jsonb NOT NULL,
        "proposed_state" jsonb NOT NULL,
        "estimated_monthly_savings" numeric(18, 6) NOT NULL,
        "actual_monthly_savings" numeric(18, 6),
        "confidence_score" double precision NOT NULL,
        "sre_assessment" jsonb,
        "status" character varying NOT NULL DEFAULT 'proposed',
        "rejection_reason" text,
        "scope_team" character varying,
        "flow_id" character varying,
        "proposed_at" TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now(),
        "resolved_at" TIMESTAMP WITH TIME ZONE,
        "executed_at" TIMESTAMP WITH TIME ZONE,
        "created_at" TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now(),
        "updated_at" TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now(),
        CONSTRAINT "PK_optimization_recommendations" PRIMARY KEY ("id")
      )
    `);

    await queryRunner.query(`
      CREATE INDEX "IDX_optimization_recommendations_scope_team_status_proposed_at"
      ON "finops"."optimization_recommendations" ("scope_team", "status", "proposed_at")
    `);

    await queryRunner.query(`
      CREATE INDEX "IDX_optimization_recommendations_resource_id_status"
      ON "finops"."optimization_recommendations" ("resource_id", "status")
    `);

    await queryRunner.query(`
      CREATE INDEX "IDX_optimization_recommendations_provider_recommendation_type"
      ON "finops"."optimization_recommendations" ("provider_name", "recommendation_type")
    `);

    // ── anomaly_resolutions ─────────────────────────────────────────────
    await queryRunner.query(`
      CREATE TABLE "finops"."anomaly_resolutions" (
        "id" uuid NOT NULL DEFAULT uuid_generate_v4(),
        "anomaly_id" character varying NOT NULL,
        "provider_name" character varying NOT NULL DEFAULT 'GCP',
        "resource_id" character varying NOT NULL,
        "dimension" character varying NOT NULL,
        "root_cause_type" character varying NOT NULL,
        "root_cause_description" text NOT NULL,
        "resolution_action" character varying,
        "is_recurring" boolean NOT NULL DEFAULT false,
        "recurrence_count" integer NOT NULL DEFAULT 1,
        "investigation_trace" jsonb,
        "resolved_by" character varying,
        "created_at" TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now(),
        "updated_at" TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now(),
        CONSTRAINT "PK_anomaly_resolutions" PRIMARY KEY ("id")
      )
    `);

    await queryRunner.query(`
      CREATE INDEX "IDX_anomaly_resolutions_resource_id_dimension"
      ON "finops"."anomaly_resolutions" ("resource_id", "dimension")
    `);

    await queryRunner.query(`
      CREATE INDEX "IDX_anomaly_resolutions_anomaly_id"
      ON "finops"."anomaly_resolutions" ("anomaly_id")
    `);

    await queryRunner.query(`
      CREATE INDEX "IDX_anomaly_resolutions_provider_root_cause_type"
      ON "finops"."anomaly_resolutions" ("provider_name", "root_cause_type")
    `);

    // ── infrastructure_baselines ────────────────────────────────────────
    await queryRunner.query(`
      CREATE TABLE "finops"."infrastructure_baselines" (
        "id" uuid NOT NULL DEFAULT uuid_generate_v4(),
        "tracked_resource_id" uuid,
        "resource_id" character varying NOT NULL,
        "provider_name" character varying NOT NULL DEFAULT 'GCP',
        "metric_name" character varying NOT NULL,
        "baseline_type" character varying NOT NULL,
        "expected_pattern" jsonb NOT NULL,
        "suppress_underuse_alerts" boolean NOT NULL DEFAULT false,
        "confidence_score" double precision NOT NULL DEFAULT 1.0,
        "evidence" jsonb,
        "established_by" character varying NOT NULL DEFAULT 'agent_inferred',
        "last_validated" TIMESTAMP WITH TIME ZONE,
        "created_at" TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now(),
        "updated_at" TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now(),
        CONSTRAINT "PK_infrastructure_baselines" PRIMARY KEY ("id")
      )
    `);

    await queryRunner.query(`
      CREATE INDEX "IDX_infrastructure_baselines_tracked_resource_metric_name"
      ON "finops"."infrastructure_baselines" ("tracked_resource_id", "metric_name")
    `);

    await queryRunner.query(`
      CREATE INDEX "IDX_infrastructure_baselines_resource_id_metric_name"
      ON "finops"."infrastructure_baselines" ("resource_id", "metric_name")
    `);

    await queryRunner.query(`
      CREATE INDEX "IDX_infrastructure_baselines_provider_suppress_alerts"
      ON "finops"."infrastructure_baselines" ("provider_name", "suppress_underuse_alerts")
    `);

    await queryRunner.query(`
      ALTER TABLE "finops"."infrastructure_baselines"
      ADD CONSTRAINT "FK_infrastructure_baselines_tracked_resource"
      FOREIGN KEY ("tracked_resource_id") REFERENCES "finops"."tracked_resources"("id") ON DELETE SET NULL ON UPDATE NO ACTION
    `);

    // ── agent_interaction_memory ────────────────────────────────────────
    await queryRunner.query(`
      CREATE TABLE "finops"."agent_interaction_memory" (
        "id" uuid NOT NULL DEFAULT uuid_generate_v4(),
        "session_id" character varying NOT NULL,
        "user_id" character varying NOT NULL,
        "agent_type" character varying NOT NULL,
        "interaction_summary" text NOT NULL,
        "key_findings" jsonb,
        "follow_up_items" jsonb,
        "scope_context" jsonb,
        "created_at" TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now(),
        "updated_at" TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now(),
        CONSTRAINT "PK_agent_interaction_memory" PRIMARY KEY ("id")
      )
    `);

    await queryRunner.query(`
      CREATE INDEX "IDX_agent_interaction_memory_user_id_session_id"
      ON "finops"."agent_interaction_memory" ("user_id", "session_id")
    `);

    await queryRunner.query(`
      CREATE INDEX "IDX_agent_interaction_memory_session_id"
      ON "finops"."agent_interaction_memory" ("session_id")
    `);

    await queryRunner.query(`
      CREATE INDEX "IDX_agent_interaction_memory_created_at"
      ON "finops"."agent_interaction_memory" ("created_at")
    `);
  }

  public async down(queryRunner: QueryRunner): Promise<void> {
    await queryRunner.query(`DROP TABLE IF EXISTS "finops"."agent_interaction_memory"`);

    await queryRunner.query(`
      ALTER TABLE "finops"."infrastructure_baselines"
      DROP CONSTRAINT IF EXISTS "FK_infrastructure_baselines_tracked_resource"
    `);
    await queryRunner.query(`DROP TABLE IF EXISTS "finops"."infrastructure_baselines"`);

    await queryRunner.query(`DROP TABLE IF EXISTS "finops"."anomaly_resolutions"`);

    await queryRunner.query(`DROP TABLE IF EXISTS "finops"."optimization_recommendations"`);
  }
}

