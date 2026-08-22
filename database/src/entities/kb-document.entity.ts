import {
  Entity,
  PrimaryGeneratedColumn,
  Column,
  CreateDateColumn,
  UpdateDateColumn,
  OneToMany,
  Index,
} from 'typeorm';
import { KbChunkEntity } from './kb-chunk.entity';

/**
 * Source document registry for provider knowledge-base ingestion.
 */
@Entity('kb_documents')
@Index(['sourceId'], { unique: true })
@Index(['provider', 'category', 'isActive'])
export class KbDocumentEntity {
  @PrimaryGeneratedColumn('uuid')
  id: string;

  /** Stable source identifier (e.g. gcp-compute-machine-types). */
  @Column({ name: 'source_id' })
  sourceId: string;

  /** Original provider documentation URL. */
  @Column({ name: 'source_url' })
  sourceUrl: string;

  /** Cloud provider identifier (GCP, Azure, AWS). */
  @Column()
  provider: string;

  /** Document category (machine_types, pricing, cli, constraints, mappings). */
  @Column()
  category: string;

  /** SHA-256 hash of fetched raw source content. */
  @Column({ name: 'content_hash' })
  contentHash: string;

  @Column({ name: 'last_fetched', type: 'timestamptz', nullable: true })
  lastFetched: Date | null;

  @Column({ name: 'last_changed', type: 'timestamptz', nullable: true })
  lastChanged: Date | null;

  /** Last fetch status: success, error, not_found. */
  @Column({ name: 'fetch_status', default: 'success' })
  fetchStatus: string;

  @Column({ name: 'is_active', default: true })
  isActive: boolean;

  @CreateDateColumn({ name: 'created_at' })
  createdAt: Date;

  @UpdateDateColumn({ name: 'updated_at' })
  updatedAt: Date;

  @OneToMany(() => KbChunkEntity, (chunk) => chunk.document)
  chunks: KbChunkEntity[];
}
