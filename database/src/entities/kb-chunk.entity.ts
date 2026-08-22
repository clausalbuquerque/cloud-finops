import {
  Entity,
  PrimaryGeneratedColumn,
  Column,
  CreateDateColumn,
  UpdateDateColumn,
  ManyToOne,
  JoinColumn,
  OneToOne,
  Index,
} from 'typeorm';
import { KbDocumentEntity } from './kb-document.entity';
import { KbEmbeddingEntity } from './kb-embedding.entity';

/**
 * Chunked knowledge-base content with retrieval metadata.
 */
@Entity('kb_chunks')
@Index(['document', 'chunkIndex'], { unique: true })
@Index(['provider', 'resourceType', 'isDeprecated'])
@Index(['contentHash'])
export class KbChunkEntity {
  @PrimaryGeneratedColumn('uuid')
  id: string;

  @ManyToOne(() => KbDocumentEntity, (document) => document.chunks, { onDelete: 'CASCADE' })
  @JoinColumn({ name: 'document_id' })
  document: KbDocumentEntity;

  @Column({ name: 'document_id' })
  documentId: string;

  @Column({ name: 'chunk_index', type: 'integer' })
  chunkIndex: number;

  @Column({ type: 'text' })
  content: string;

  @Column({ name: 'token_count', type: 'integer' })
  tokenCount: number;

  @Column({ name: 'content_hash' })
  contentHash: string;

  @Column()
  provider: string;

  @Column({ name: 'resource_type' })
  resourceType: string;

  @Column()
  category: string;

  @Column({ name: 'source_url' })
  sourceUrl: string;

  @Column({ name: 'last_verified', type: 'timestamptz', nullable: true })
  lastVerified: Date | null;

  @Column({ name: 'is_deprecated', default: false })
  isDeprecated: boolean;

  @Column({ type: 'jsonb', nullable: true })
  metadata: Record<string, unknown> | null;

  @CreateDateColumn({ name: 'created_at' })
  createdAt: Date;

  @UpdateDateColumn({ name: 'updated_at' })
  updatedAt: Date;

  @OneToOne(() => KbEmbeddingEntity, (embedding) => embedding.chunk)
  embedding: KbEmbeddingEntity;
}
