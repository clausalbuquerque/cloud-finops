import { MigrationInterface, QueryRunner } from 'typeorm';

export class InitialCoreSchema1732656000000 implements MigrationInterface {
  name = 'InitialCoreSchema1732656000000';

  public async up(queryRunner: QueryRunner): Promise<void> {
    // Create subscriptions table
    await queryRunner.query(`
      CREATE TABLE "finops"."subscriptions" (
        "id" uuid NOT NULL DEFAULT uuid_generate_v4(),
        "subscription_id" character varying NOT NULL,
        "display_name" character varying NOT NULL,
        "state" character varying,
        "created_at" TIMESTAMP NOT NULL DEFAULT now(),
        "updated_at" TIMESTAMP NOT NULL DEFAULT now(),
        CONSTRAINT "PK_subscriptions" PRIMARY KEY ("id")
      )
    `);

    // Create unique index on subscription_id
    await queryRunner.query(`
      CREATE UNIQUE INDEX "IDX_subscriptions_subscription_id" ON "finops"."subscriptions" ("subscription_id")
    `);

    // Create resource_groups table
    await queryRunner.query(`
      CREATE TABLE "finops"."resource_groups" (
        "id" uuid NOT NULL DEFAULT uuid_generate_v4(),
        "name" character varying NOT NULL,
        "location" character varying,
        "subscription_id" uuid NOT NULL,
        "created_at" TIMESTAMP NOT NULL DEFAULT now(),
        "updated_at" TIMESTAMP NOT NULL DEFAULT now(),
        CONSTRAINT "PK_resource_groups" PRIMARY KEY ("id")
      )
    `);

    // Create unique index on subscription_id + name
    await queryRunner.query(`
      CREATE UNIQUE INDEX "IDX_resource_groups_subscription_name" ON "finops"."resource_groups" ("subscription_id", "name")
    `);

    // Create consumption_records table
    await queryRunner.query(`
      CREATE TABLE "finops"."consumption_records" (
        "id" uuid NOT NULL DEFAULT uuid_generate_v4(),
        "billing_account_id" character varying,
        "billing_account_name" character varying,
        "billing_currency" character varying NOT NULL DEFAULT 'USD',
        "billing_period_end" date,
        "billing_period_start" date,
        "charge_type" character varying,
        "effective_cost" numeric(18,6),
        "invoice_id" character varying,
        "meter_category" character varying,
        "meter_id" character varying,
        "meter_name" character varying,
        "meter_region" character varying,
        "meter_subcategory" character varying,
        "pricing_model" character varying,
        "product_name" character varying,
        "provider_name" character varying NOT NULL DEFAULT 'Azure',
        "publisher_name" character varying,
        "quantity" numeric(18,6),
        "resource_id" character varying,
        "resource_location" character varying,
        "resource_name" character varying,
        "resource_type" character varying,
        "service_category" character varying,
        "service_name" character varying,
        "sku_id" character varying,
        "sku_price_id" character varying,
        "sub_account_id" character varying,
        "sub_account_name" character varying,
        "tags" jsonb,
        "unit_of_measure" character varying,
        "unit_price" numeric(18,6),
        "usage_date" date NOT NULL,
        "usage_quantity" numeric(18,6),
        "usage_unit" character varying,
        "subscription_id" uuid NOT NULL,
        "resource_group_id" uuid NOT NULL,
        "created_at" TIMESTAMP NOT NULL DEFAULT now(),
        "updated_at" TIMESTAMP NOT NULL DEFAULT now(),
        CONSTRAINT "PK_consumption_records" PRIMARY KEY ("id")
      )
    `);

    // Create indexes for consumption_records
    await queryRunner.query(`
      CREATE INDEX "IDX_consumption_records_usage_date" ON "finops"."consumption_records" ("usage_date")
    `);

    await queryRunner.query(`
      CREATE INDEX "IDX_consumption_records_resource_type" ON "finops"."consumption_records" ("resource_type")
    `);

    await queryRunner.query(`
      CREATE INDEX "IDX_consumption_records_meter_category" ON "finops"."consumption_records" ("meter_category")
    `);

    await queryRunner.query(`
      CREATE INDEX "IDX_consumption_records_subscription_resource_group_usage_date" ON "finops"."consumption_records" ("subscription_id", "resource_group_id", "usage_date")
    `);

    // Add foreign key constraints
    await queryRunner.query(`
      ALTER TABLE "finops"."resource_groups"
      ADD CONSTRAINT "FK_resource_groups_subscription"
      FOREIGN KEY ("subscription_id") REFERENCES "finops"."subscriptions"("id") ON DELETE CASCADE ON UPDATE NO ACTION
    `);

    await queryRunner.query(`
      ALTER TABLE "finops"."consumption_records"
      ADD CONSTRAINT "FK_consumption_records_subscription"
      FOREIGN KEY ("subscription_id") REFERENCES "finops"."subscriptions"("id") ON DELETE CASCADE ON UPDATE NO ACTION
    `);

    await queryRunner.query(`
      ALTER TABLE "finops"."consumption_records"
      ADD CONSTRAINT "FK_consumption_records_resource_group"
      FOREIGN KEY ("resource_group_id") REFERENCES "finops"."resource_groups"("id") ON DELETE CASCADE ON UPDATE NO ACTION
    `);
  }

  public async down(queryRunner: QueryRunner): Promise<void> {
    // Drop foreign key constraints
    await queryRunner.query(`ALTER TABLE "finops"."consumption_records" DROP CONSTRAINT "FK_consumption_records_resource_group"`);
    await queryRunner.query(`ALTER TABLE "finops"."consumption_records" DROP CONSTRAINT "FK_consumption_records_subscription"`);
    await queryRunner.query(`ALTER TABLE "finops"."resource_groups" DROP CONSTRAINT "FK_resource_groups_subscription"`);

    // Drop indexes
    await queryRunner.query(`DROP INDEX "finops"."IDX_consumption_records_subscription_resource_group_usage_date"`);
    await queryRunner.query(`DROP INDEX "finops"."IDX_consumption_records_meter_category"`);
    await queryRunner.query(`DROP INDEX "finops"."IDX_consumption_records_resource_type"`);
    await queryRunner.query(`DROP INDEX "finops"."IDX_consumption_records_usage_date"`);
    await queryRunner.query(`DROP INDEX "finops"."IDX_resource_groups_subscription_name"`);
    await queryRunner.query(`DROP INDEX "finops"."IDX_subscriptions_subscription_id"`);

    // Drop tables
    await queryRunner.query(`DROP TABLE "finops"."consumption_records"`);
    await queryRunner.query(`DROP TABLE "finops"."resource_groups"`);
    await queryRunner.query(`DROP TABLE "finops"."subscriptions"`);
  }
}