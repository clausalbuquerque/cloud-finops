import { Entity, PrimaryGeneratedColumn, Column, CreateDateColumn, Index } from 'typeorm';

/**
 * Audit log for ingestion/index pipeline runs.
 */
@Entity('kb_ingestion_runs')
@Index(['runType', 'status'])
@Index(['startedAt'])
export class KbIngestionRunEntity {
  @PrimaryGeneratedColumn('uuid')
  id: string;

  /** ingest, index, verify */
  @Column({ name: 'run_type' })
  runType: string;

  @Column({ name: 'source_id', type: 'varchar', nullable: true })
  sourceId: string | null;

  /** running, completed, failed */
  @Column()
  status: string;

  @Column({ name: 'documents_processed', type: 'integer', default: 0 })
  documentsProcessed: number;

  @Column({ name: 'chunks_created', type: 'integer', default: 0 })
  chunksCreated: number;

  @Column({ name: 'chunks_updated', type: 'integer', default: 0 })
  chunksUpdated: number;

  @Column({ name: 'chunks_deprecated', type: 'integer', default: 0 })
  chunksDeprecated: number;

  @Column({ type: 'jsonb', nullable: true })
  errors: Record<string, unknown> | null;

  @CreateDateColumn({ name: 'started_at' })
  startedAt: Date;

  @Column({ name: 'completed_at', type: 'timestamptz', nullable: true })
  completedAt: Date | null;
}
