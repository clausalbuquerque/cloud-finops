import { MigrationInterface, QueryRunner } from 'typeorm';

export class AddKnowledgeBaseVectorSchema1732656200000 implements MigrationInterface {
  name = 'AddKnowledgeBaseVectorSchema1732656200000';

  public async up(queryRunner: QueryRunner): Promise<void> {
    // Enable pgvector extension for vector embeddings.
    await queryRunner.query(`CREATE EXTENSION IF NOT EXISTS vector`);

    // ── kb_documents ───────────────────────────────────────────────────
    await queryRunner.query(`
      CREATE TABLE "finops"."kb_documents" (
        "id" uuid NOT NULL DEFAULT uuid_generate_v4(),
        "source_id" character varying NOT NULL,
        "source_url" character varying NOT NULL,
        "provider" character varying NOT NULL,
        "category" character varying NOT NULL,
        "content_hash" character varying NOT NULL,
        "last_fetched" TIMESTAMP WITH TIME ZONE,
        "last_changed" TIMESTAMP WITH TIME ZONE,
        "fetch_status" character varying NOT NULL DEFAULT 'success',
        "is_active" boolean NOT NULL DEFAULT true,
        "created_at" TIMESTAMP NOT NULL DEFAULT now(),
        "updated_at" TIMESTAMP NOT NULL DEFAULT now(),
        CONSTRAINT "PK_kb_documents" PRIMARY KEY ("id")
      )
    `);

    await queryRunner.query(`
      CREATE UNIQUE INDEX "IDX_kb_documents_source_id"
      ON "finops"."kb_documents" ("source_id")
    `);

    await queryRunner.query(`
      CREATE INDEX "IDX_kb_documents_provider_category_active"
      ON "finops"."kb_documents" ("provider", "category", "is_active")
    `);

    // ── kb_chunks ──────────────────────────────────────────────────────
    await queryRunner.query(`
      CREATE TABLE "finops"."kb_chunks" (
        "id" uuid NOT NULL DEFAULT uuid_generate_v4(),
        "document_id" uuid NOT NULL,
        "chunk_index" integer NOT NULL,
        "content" text NOT NULL,
        "token_count" integer NOT NULL,
        "content_hash" character varying NOT NULL,
        "provider" character varying NOT NULL,
        "resource_type" character varying NOT NULL,
        "category" character varying NOT NULL,
        "source_url" character varying NOT NULL,
        "last_verified" TIMESTAMP WITH TIME ZONE,
        "is_deprecated" boolean NOT NULL DEFAULT false,
        "metadata" jsonb,
        "created_at" TIMESTAMP NOT NULL DEFAULT now(),
        "updated_at" TIMESTAMP NOT NULL DEFAULT now(),
        CONSTRAINT "PK_kb_chunks" PRIMARY KEY ("id")
      )
    `);

    await queryRunner.query(`
      CREATE UNIQUE INDEX "IDX_kb_chunks_document_chunk_index"
      ON "finops"."kb_chunks" ("document_id", "chunk_index")
    `);

    await queryRunner.query(`
      CREATE INDEX "IDX_kb_chunks_provider_resource_type_is_deprecated"
      ON "finops"."kb_chunks" ("provider", "resource_type", "is_deprecated")
    `);

    await queryRunner.query(`
      CREATE INDEX "IDX_kb_chunks_content_hash"
      ON "finops"."kb_chunks" ("content_hash")
    `);

    await queryRunner.query(`
      ALTER TABLE "finops"."kb_chunks"
      ADD CONSTRAINT "FK_kb_chunks_document"
      FOREIGN KEY ("document_id") REFERENCES "finops"."kb_documents"("id") ON DELETE CASCADE ON UPDATE NO ACTION
    `);

    // ── kb_embeddings ──────────────────────────────────────────────────
    await queryRunner.query(`
      CREATE TABLE "finops"."kb_embeddings" (
        "id" uuid NOT NULL DEFAULT uuid_generate_v4(),
        "chunk_id" uuid NOT NULL,
        "embedding" vector(768) NOT NULL,
        "model_version" character varying NOT NULL,
        "created_at" TIMESTAMP NOT NULL DEFAULT now(),
        CONSTRAINT "PK_kb_embeddings" PRIMARY KEY ("id")
      )
    `);

    await queryRunner.query(`
      CREATE UNIQUE INDEX "IDX_kb_embeddings_chunk_id"
      ON "finops"."kb_embeddings" ("chunk_id")
    `);

    await queryRunner.query(`
      CREATE INDEX "IDX_kb_embeddings_embedding_cosine"
      ON "finops"."kb_embeddings"
      USING ivfflat ("embedding" vector_cosine_ops)
      WITH (lists = 100)
    `);

    await queryRunner.query(`
      ALTER TABLE "finops"."kb_embeddings"
      ADD CONSTRAINT "FK_kb_embeddings_chunk"
      FOREIGN KEY ("chunk_id") REFERENCES "finops"."kb_chunks"("id") ON DELETE CASCADE ON UPDATE NO ACTION
    `);

    // ── kb_ingestion_runs ──────────────────────────────────────────────
    await queryRunner.query(`
      CREATE TABLE "finops"."kb_ingestion_runs" (
        "id" uuid NOT NULL DEFAULT uuid_generate_v4(),
        "run_type" character varying NOT NULL,
        "source_id" character varying,
        "status" character varying NOT NULL,
        "documents_processed" integer NOT NULL DEFAULT 0,
        "chunks_created" integer NOT NULL DEFAULT 0,
        "chunks_updated" integer NOT NULL DEFAULT 0,
        "chunks_deprecated" integer NOT NULL DEFAULT 0,
        "errors" jsonb,
        "started_at" TIMESTAMP NOT NULL DEFAULT now(),
        "completed_at" TIMESTAMP WITH TIME ZONE,
        CONSTRAINT "PK_kb_ingestion_runs" PRIMARY KEY ("id")
      )
    `);

    await queryRunner.query(`
      CREATE INDEX "IDX_kb_ingestion_runs_run_type_status"
      ON "finops"."kb_ingestion_runs" ("run_type", "status")
    `);

    await queryRunner.query(`
      CREATE INDEX "IDX_kb_ingestion_runs_started_at"
      ON "finops"."kb_ingestion_runs" ("started_at")
    `);
  }

  public async down(queryRunner: QueryRunner): Promise<void> {
    // Drop indexes
    await queryRunner.query(`DROP INDEX "finops"."IDX_kb_ingestion_runs_started_at"`);
    await queryRunner.query(`DROP INDEX "finops"."IDX_kb_ingestion_runs_run_type_status"`);
    await queryRunner.query(`DROP INDEX "finops"."IDX_kb_embeddings_embedding_cosine"`);
    await queryRunner.query(`DROP INDEX "finops"."IDX_kb_embeddings_chunk_id"`);
    await queryRunner.query(`DROP INDEX "finops"."IDX_kb_chunks_content_hash"`);
    await queryRunner.query(`DROP INDEX "finops"."IDX_kb_chunks_provider_resource_type_is_deprecated"`);
    await queryRunner.query(`DROP INDEX "finops"."IDX_kb_chunks_document_chunk_index"`);
    await queryRunner.query(`DROP INDEX "finops"."IDX_kb_documents_provider_category_active"`);
    await queryRunner.query(`DROP INDEX "finops"."IDX_kb_documents_source_id"`);

    // Drop FK constraints
    await queryRunner.query(`ALTER TABLE "finops"."kb_embeddings" DROP CONSTRAINT "FK_kb_embeddings_chunk"`);
    await queryRunner.query(`ALTER TABLE "finops"."kb_chunks" DROP CONSTRAINT "FK_kb_chunks_document"`);

    // Drop tables
    await queryRunner.query(`DROP TABLE "finops"."kb_ingestion_runs"`);
    await queryRunner.query(`DROP TABLE "finops"."kb_embeddings"`);
    await queryRunner.query(`DROP TABLE "finops"."kb_chunks"`);
    await queryRunner.query(`DROP TABLE "finops"."kb_documents"`);
  }
}
