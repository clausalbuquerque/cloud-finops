import {
  Entity,
  PrimaryGeneratedColumn,
  Column,
  CreateDateColumn,
  OneToOne,
  JoinColumn,
  Index,
} from 'typeorm';
import { KbChunkEntity } from './kb-chunk.entity';

/**
 * Vector embedding for a single KB chunk.
 */
@Entity('kb_embeddings')
@Index(['chunk'], { unique: true })
export class KbEmbeddingEntity {
  @PrimaryGeneratedColumn('uuid')
  id: string;

  @OneToOne(() => KbChunkEntity, (chunk) => chunk.embedding, { onDelete: 'CASCADE' })
  @JoinColumn({ name: 'chunk_id' })
  chunk: KbChunkEntity;

  @Column({ name: 'chunk_id' })
  chunkId: string;

  /**
   * pgvector column. TypeORM does not include 'vector' in older typings,
   * so it is intentionally cast to keep compatibility.
   */
  @Column({ type: 'vector' as any, length: 768 })
  embedding: number[];

  @Column({ name: 'model_version' })
  modelVersion: string;

  @CreateDateColumn({ name: 'created_at' })
  createdAt: Date;
}
