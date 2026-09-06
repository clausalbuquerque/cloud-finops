import {
  Entity,
  PrimaryGeneratedColumn,
  Column,
  CreateDateColumn,
  UpdateDateColumn,
  Index,
} from 'typeorm';

/**
 * Represents cross-session interaction context and key findings.
 *
 * Persists summaries, cited facts, and decisions from user conversations
 * to enable multi-turn recall and follow-up across sessions.
 */
@Entity('agent_interaction_memory')
@Index(['userId', 'sessionId'])
@Index(['sessionId'])
@Index(['createdAt'])
export class AgentInteractionMemoryEntity {
  @PrimaryGeneratedColumn('uuid')
  id: string;

  /** Conversation or thread session identifier. */
  @Column({ name: 'session_id' })
  sessionId: string;

  /** User identifier or caller principal. */
  @Column({ name: 'user_id' })
  userId: string;

  /** Agent role in the interaction: 'finops' | 'sre' | 'orchestrator'. */
  @Column({ name: 'agent_type' })
  agentType: string;

  /** Compressed narrative summary of the interaction. */
  @Column({ name: 'interaction_summary', type: 'text' })
  interactionSummary: string;

  /** Structured extraction of facts: resources discussed, decisions made, metrics/costs cited. */
  @Column({ name: 'key_findings', type: 'jsonb', nullable: true })
  keyFindings: Record<string, unknown> | null;

  /** Follow-up actions or deferred tasks identified during the conversation. */
  @Column({ name: 'follow_up_items', type: 'jsonb', nullable: true })
  followUpItems: Array<Record<string, unknown>> | Record<string, unknown> | null;

  /** Scope context active during the interaction (e.g. { team: 'data-platform', provider: 'GCP' }). */
  @Column({ name: 'scope_context', type: 'jsonb', nullable: true })
  scopeContext: Record<string, unknown> | null;

  @CreateDateColumn({ name: 'created_at', type: 'timestamp with time zone' })
  createdAt: Date;

  @UpdateDateColumn({ name: 'updated_at', type: 'timestamp with time zone' })
  updatedAt: Date;
}
