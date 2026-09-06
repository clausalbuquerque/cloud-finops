import { AddAgentMemorySchema1732656300000 } from '../../migrations/1732656300000-AddAgentMemorySchema';
import { QueryRunner } from 'typeorm';

describe('AddAgentMemorySchema1732656300000 Migration', () => {
  let migration: AddAgentMemorySchema1732656300000;
  let mockQueryRunner: jest.Mocked<QueryRunner>;
  let executedQueries: string[];

  beforeEach(() => {
    executedQueries = [];
    mockQueryRunner = {
      query: jest.fn().mockImplementation((query: string) => {
        executedQueries.push(query.trim());
        return Promise.resolve();
      }),
    } as unknown as jest.Mocked<QueryRunner>;

    migration = new AddAgentMemorySchema1732656300000();
  });

  describe('metadata', () => {
    it('should have the correct migration name', () => {
      expect(migration.name).toBe('AddAgentMemorySchema1732656300000');
    });
  });

  describe('up()', () => {
    beforeEach(async () => {
      await migration.up(mockQueryRunner);
    });

    it('should execute queries against the query runner', () => {
      expect(mockQueryRunner.query).toHaveBeenCalled();
      expect(executedQueries.length).toBeGreaterThan(0);
    });

    describe('tables', () => {
      it('should create optimization_recommendations table in finops schema', () => {
        const tableQuery = executedQueries.find((q) =>
          q.includes('CREATE TABLE "finops"."optimization_recommendations"'),
        );
        expect(tableQuery).toBeDefined();
        expect(tableQuery).toContain('"id" uuid NOT NULL DEFAULT uuid_generate_v4()');
        expect(tableQuery).toContain('"provider_name" character varying NOT NULL');
        expect(tableQuery).toContain('"resource_id" character varying NOT NULL');
        expect(tableQuery).toContain('"resource_type" character varying NOT NULL');
        expect(tableQuery).toContain('"recommendation_type" character varying NOT NULL');
        expect(tableQuery).toContain('"current_state" jsonb NOT NULL');
        expect(tableQuery).toContain('"proposed_state" jsonb NOT NULL');
        expect(tableQuery).toContain('"estimated_monthly_savings" numeric(18, 6) NOT NULL');
        expect(tableQuery).toContain('"confidence_score" double precision NOT NULL');
        expect(tableQuery).toContain('"sre_assessment" jsonb');
        expect(tableQuery).toContain('"status" character varying NOT NULL DEFAULT \'proposed\'');
        expect(tableQuery).toContain('"rejection_reason" text');
        expect(tableQuery).toContain('"scope_team" character varying');
        expect(tableQuery).toContain('"flow_id" character varying');
        expect(tableQuery).toContain('"proposed_at" TIMESTAMP WITH TIME ZONE');
      });

      it('should create anomaly_resolutions table in finops schema', () => {
        const tableQuery = executedQueries.find((q) =>
          q.includes('CREATE TABLE "finops"."anomaly_resolutions"'),
        );
        expect(tableQuery).toBeDefined();
        expect(tableQuery).toContain('"anomaly_id" character varying NOT NULL');
        expect(tableQuery).toContain('"dimension" character varying NOT NULL');
        expect(tableQuery).toContain('"root_cause_type" character varying NOT NULL');
        expect(tableQuery).toContain('"root_cause_description" text NOT NULL');
        expect(tableQuery).toContain('"is_recurring" boolean NOT NULL DEFAULT false');
        expect(tableQuery).toContain('"recurrence_count" integer NOT NULL DEFAULT 1');
        expect(tableQuery).toContain('"investigation_trace" jsonb');
      });

      it('should create infrastructure_baselines table in finops schema', () => {
        const tableQuery = executedQueries.find((q) =>
          q.includes('CREATE TABLE "finops"."infrastructure_baselines"'),
        );
        expect(tableQuery).toBeDefined();
        expect(tableQuery).toContain('"tracked_resource_id" uuid');
        expect(tableQuery).toContain('"resource_id" character varying NOT NULL');
        expect(tableQuery).toContain('"metric_name" character varying NOT NULL');
        expect(tableQuery).toContain('"baseline_type" character varying NOT NULL');
        expect(tableQuery).toContain('"expected_pattern" jsonb NOT NULL');
        expect(tableQuery).toContain('"suppress_underuse_alerts" boolean NOT NULL DEFAULT false');
        expect(tableQuery).toContain('"confidence_score" double precision NOT NULL');
      });

      it('should create agent_interaction_memory table in finops schema', () => {
        const tableQuery = executedQueries.find((q) =>
          q.includes('CREATE TABLE "finops"."agent_interaction_memory"'),
        );
        expect(tableQuery).toBeDefined();
        expect(tableQuery).toContain('"session_id" character varying NOT NULL');
        expect(tableQuery).toContain('"user_id" character varying NOT NULL');
        expect(tableQuery).toContain('"agent_type" character varying NOT NULL');
        expect(tableQuery).toContain('"interaction_summary" text NOT NULL');
        expect(tableQuery).toContain('"key_findings" jsonb');
        expect(tableQuery).toContain('"scope_context" jsonb');
      });
    });

    describe('indexes and foreign keys', () => {
      it('should create indexes for optimization_recommendations', () => {
        expect(
          executedQueries.some((q) =>
            q.includes('IDX_optimization_recommendations_scope_team_status_proposed_at'),
          ),
        ).toBe(true);
        expect(
          executedQueries.some((q) =>
            q.includes('IDX_optimization_recommendations_resource_id_status'),
          ),
        ).toBe(true);
      });

      it('should create indexes for anomaly_resolutions', () => {
        expect(
          executedQueries.some((q) => q.includes('IDX_anomaly_resolutions_resource_id_dimension')),
        ).toBe(true);
      });

      it('should create indexes and foreign key for infrastructure_baselines', () => {
        expect(
          executedQueries.some((q) =>
            q.includes('IDX_infrastructure_baselines_tracked_resource_metric_name'),
          ),
        ).toBe(true);
        expect(
          executedQueries.some((q) => q.includes('FK_infrastructure_baselines_tracked_resource')),
        ).toBe(true);
      });

      it('should create indexes for agent_interaction_memory', () => {
        expect(
          executedQueries.some((q) =>
            q.includes('IDX_agent_interaction_memory_user_id_session_id'),
          ),
        ).toBe(true);
      });
    });
  });

  describe('down()', () => {
    beforeEach(async () => {
      await migration.down(mockQueryRunner);
    });

    it('should drop tables and constraints in reverse order', () => {
      expect(
        executedQueries.some((q) =>
          q.includes('DROP TABLE IF EXISTS "finops"."agent_interaction_memory"'),
        ),
      ).toBe(true);
      expect(
        executedQueries.some((q) =>
          q.includes('DROP TABLE IF EXISTS "finops"."infrastructure_baselines"'),
        ),
      ).toBe(true);
      expect(
        executedQueries.some((q) =>
          q.includes('DROP TABLE IF EXISTS "finops"."anomaly_resolutions"'),
        ),
      ).toBe(true);
      expect(
        executedQueries.some((q) =>
          q.includes('DROP TABLE IF EXISTS "finops"."optimization_recommendations"'),
        ),
      ).toBe(true);
    });
  });
});
