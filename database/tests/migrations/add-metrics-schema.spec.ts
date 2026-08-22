import { AddMetricsSchema1732656100000 } from '../../migrations/1732656100000-AddMetricsSchema';
import { QueryRunner } from 'typeorm';

describe('AddMetricsSchema1732656100000 Migration', () => {
  let migration: AddMetricsSchema1732656100000;
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

    migration = new AddMetricsSchema1732656100000();
  });

  describe('metadata', () => {
    it('should have the correct migration name', () => {
      expect(migration.name).toBe('AddMetricsSchema1732656100000');
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

    describe('enum types', () => {
      it('should create metric_unit_enum type in finops schema', () => {
        const enumQuery = executedQueries.find((q) => q.includes('metric_unit_enum'));
        expect(enumQuery).toBeDefined();
        expect(enumQuery).toContain('CREATE TYPE "finops"."metric_unit_enum"');
        expect(enumQuery).toContain("'Count'");
        expect(enumQuery).toContain("'Bytes'");
        expect(enumQuery).toContain("'Percent'");
        expect(enumQuery).toContain("'Unspecified'");
      });

      it('should create aggregation_type_enum type in finops schema', () => {
        const enumQuery = executedQueries.find((q) => q.includes('aggregation_type_enum'));
        expect(enumQuery).toBeDefined();
        expect(enumQuery).toContain('CREATE TYPE "finops"."aggregation_type_enum"');
        expect(enumQuery).toContain("'Average'");
        expect(enumQuery).toContain("'Maximum'");
        expect(enumQuery).toContain("'Count'");
      });

      it('should create time_grain_enum type in finops schema', () => {
        const enumQuery = executedQueries.find((q) => q.includes('time_grain_enum'));
        expect(enumQuery).toBeDefined();
        expect(enumQuery).toContain('CREATE TYPE "finops"."time_grain_enum"');
        expect(enumQuery).toContain("'PT1M'");
        expect(enumQuery).toContain("'PT1H'");
        expect(enumQuery).toContain("'P1D'");
      });
    });

    describe('tables', () => {
      it('should create tracked_resources table in finops schema', () => {
        const tableQuery = executedQueries.find((q) =>
          q.includes('CREATE TABLE "finops"."tracked_resources"'),
        );
        expect(tableQuery).toBeDefined();
        expect(tableQuery).toContain('"id" uuid');
        expect(tableQuery).toContain('"azure_resource_id" character varying NOT NULL');
        expect(tableQuery).toContain('"resource_name" character varying NOT NULL');
        expect(tableQuery).toContain('"resource_type" character varying NOT NULL');
        expect(tableQuery).toContain('"provisioned_capacity" jsonb');
        expect(tableQuery).toContain('"is_active" boolean NOT NULL DEFAULT true');
        expect(tableQuery).toContain('"subscription_id" uuid NOT NULL');
        expect(tableQuery).toContain('"resource_group_id" uuid NOT NULL');
      });

      it('should create metric_definitions table in finops schema', () => {
        const tableQuery = executedQueries.find((q) =>
          q.includes('CREATE TABLE "finops"."metric_definitions"'),
        );
        expect(tableQuery).toBeDefined();
        expect(tableQuery).toContain('"resource_type" character varying NOT NULL');
        expect(tableQuery).toContain('"metric_namespace" character varying NOT NULL');
        expect(tableQuery).toContain('"metric_name" character varying NOT NULL');
        expect(tableQuery).toContain('"finops"."metric_unit_enum"');
        expect(tableQuery).toContain('"finops"."aggregation_type_enum"');
        expect(tableQuery).toContain('"supported_aggregation_types" text[]');
        expect(tableQuery).toContain('"is_utilization_metric" boolean');
      });

      it('should create metric_data_points table in finops schema', () => {
        const tableQuery = executedQueries.find((q) =>
          q.includes('CREATE TABLE "finops"."metric_data_points"'),
        );
        expect(tableQuery).toBeDefined();
        expect(tableQuery).toContain('"tracked_resource_id" uuid NOT NULL');
        expect(tableQuery).toContain('"metric_definition_id" uuid NOT NULL');
        expect(tableQuery).toContain('TIMESTAMP WITH TIME ZONE NOT NULL');
        expect(tableQuery).toContain('"finops"."time_grain_enum"');
        expect(tableQuery).toContain('"average" double precision');
        expect(tableQuery).toContain('"minimum" double precision');
        expect(tableQuery).toContain('"maximum" double precision');
        expect(tableQuery).toContain('"total" double precision');
        expect(tableQuery).toContain('"count" double precision');
      });

      it('should create utilization_summaries table in finops schema', () => {
        const tableQuery = executedQueries.find((q) =>
          q.includes('CREATE TABLE "finops"."utilization_summaries"'),
        );
        expect(tableQuery).toBeDefined();
        expect(tableQuery).toContain('"tracked_resource_id" uuid NOT NULL');
        expect(tableQuery).toContain('"summary_date" date NOT NULL');
        expect(tableQuery).toContain('"metric_name" character varying NOT NULL');
        expect(tableQuery).toContain('"avg_utilization" double precision NOT NULL');
        expect(tableQuery).toContain('"max_utilization" double precision NOT NULL');
        expect(tableQuery).toContain('"min_utilization" double precision NOT NULL');
        expect(tableQuery).toContain('"p95_utilization" double precision');
        expect(tableQuery).toContain('"sample_count" integer NOT NULL');
        expect(tableQuery).toContain('"is_underused" boolean NOT NULL DEFAULT false');
        expect(tableQuery).toContain('"underuse_threshold" double precision');
      });
    });

    describe('indexes', () => {
      it('should create unique index on tracked_resources.azure_resource_id', () => {
        const idxQuery = executedQueries.find((q) =>
          q.includes('IDX_tracked_resources_azure_resource_id'),
        );
        expect(idxQuery).toBeDefined();
        expect(idxQuery).toContain('UNIQUE INDEX');
        expect(idxQuery).toContain('"azure_resource_id"');
      });

      it('should create unique index on metric_definitions (resource_type, metric_name)', () => {
        const idxQuery = executedQueries.find((q) =>
          q.includes('IDX_metric_definitions_resource_type_metric_name'),
        );
        expect(idxQuery).toBeDefined();
        expect(idxQuery).toContain('UNIQUE INDEX');
        expect(idxQuery).toContain('"resource_type"');
        expect(idxQuery).toContain('"metric_name"');
      });

      it('should create composite index on metric_data_points for time-series queries', () => {
        const idxQuery = executedQueries.find((q) =>
          q.includes('IDX_metric_data_points_resource_definition_timestamp_grain'),
        );
        expect(idxQuery).toBeDefined();
        expect(idxQuery).toContain('"tracked_resource_id"');
        expect(idxQuery).toContain('"metric_definition_id"');
        expect(idxQuery).toContain('"timestamp"');
        expect(idxQuery).toContain('"time_grain"');
      });

      it('should create index on utilization_summaries.is_underused', () => {
        const idxQuery = executedQueries.find((q) =>
          q.includes('IDX_utilization_summaries_is_underused'),
        );
        expect(idxQuery).toBeDefined();
        expect(idxQuery).toContain('"is_underused"');
      });
    });

    describe('foreign keys', () => {
      it('should add FK from tracked_resources to subscriptions with CASCADE', () => {
        const fkQuery = executedQueries.find((q) =>
          q.includes('FK_tracked_resources_subscription'),
        );
        expect(fkQuery).toBeDefined();
        expect(fkQuery).toContain('REFERENCES "finops"."subscriptions"("id")');
        expect(fkQuery).toContain('ON DELETE CASCADE');
      });

      it('should add FK from tracked_resources to resource_groups with CASCADE', () => {
        const fkQuery = executedQueries.find((q) =>
          q.includes('FK_tracked_resources_resource_group'),
        );
        expect(fkQuery).toBeDefined();
        expect(fkQuery).toContain('REFERENCES "finops"."resource_groups"("id")');
        expect(fkQuery).toContain('ON DELETE CASCADE');
      });

      it('should add FK from metric_data_points to tracked_resources with CASCADE', () => {
        const fkQuery = executedQueries.find((q) =>
          q.includes('FK_metric_data_points_tracked_resource'),
        );
        expect(fkQuery).toBeDefined();
        expect(fkQuery).toContain('REFERENCES "finops"."tracked_resources"("id")');
        expect(fkQuery).toContain('ON DELETE CASCADE');
      });

      it('should add FK from metric_data_points to metric_definitions with CASCADE', () => {
        const fkQuery = executedQueries.find((q) =>
          q.includes('FK_metric_data_points_metric_definition'),
        );
        expect(fkQuery).toBeDefined();
        expect(fkQuery).toContain('REFERENCES "finops"."metric_definitions"("id")');
        expect(fkQuery).toContain('ON DELETE CASCADE');
      });

      it('should add FK from utilization_summaries to tracked_resources with CASCADE', () => {
        const fkQuery = executedQueries.find((q) =>
          q.includes('FK_utilization_summaries_tracked_resource'),
        );
        expect(fkQuery).toBeDefined();
        expect(fkQuery).toContain('REFERENCES "finops"."tracked_resources"("id")');
        expect(fkQuery).toContain('ON DELETE CASCADE');
      });
    });
  });

  describe('down()', () => {
    beforeEach(async () => {
      await migration.down(mockQueryRunner);
    });

    it('should execute queries for rollback', () => {
      expect(mockQueryRunner.query).toHaveBeenCalled();
      expect(executedQueries.length).toBeGreaterThan(0);
    });

    it('should drop foreign key constraints', () => {
      const fkDrops = executedQueries.filter((q) => q.includes('DROP CONSTRAINT'));
      expect(fkDrops.length).toBeGreaterThanOrEqual(5);
    });

    it('should drop tables in correct dependency order', () => {
      const tableDrops = executedQueries.filter((q) => q.includes('DROP TABLE'));
      expect(tableDrops).toHaveLength(4);

      // utilization_summaries and metric_data_points must be dropped before tracked_resources
      const summariesIdx = tableDrops.findIndex((q) => q.includes('utilization_summaries'));
      const dataPointsIdx = tableDrops.findIndex((q) => q.includes('metric_data_points'));
      const trackedResourcesIdx = tableDrops.findIndex((q) => q.includes('tracked_resources'));
      const definitionsIdx = tableDrops.findIndex((q) => q.includes('metric_definitions'));

      expect(summariesIdx).toBeLessThan(trackedResourcesIdx);
      expect(dataPointsIdx).toBeLessThan(trackedResourcesIdx);
      expect(definitionsIdx).toBeLessThan(trackedResourcesIdx);
    });

    it('should drop enum types', () => {
      const typeDrops = executedQueries.filter((q) => q.includes('DROP TYPE'));
      expect(typeDrops).toHaveLength(3);
      expect(typeDrops.some((q) => q.includes('metric_unit_enum'))).toBe(true);
      expect(typeDrops.some((q) => q.includes('aggregation_type_enum'))).toBe(true);
      expect(typeDrops.some((q) => q.includes('time_grain_enum'))).toBe(true);
    });

    it('should drop indexes before tables', () => {
      const indexDrops = executedQueries.filter((q) => q.includes('DROP INDEX'));
      const tableDrops = executedQueries.filter((q) => q.includes('DROP TABLE'));

      // All index drops should come before table drops
      const lastIndexDropPos = executedQueries.lastIndexOf(indexDrops[indexDrops.length - 1]);
      const firstTableDropPos = executedQueries.indexOf(tableDrops[0]);
      expect(lastIndexDropPos).toBeLessThan(firstTableDropPos);
    });
  });
});
