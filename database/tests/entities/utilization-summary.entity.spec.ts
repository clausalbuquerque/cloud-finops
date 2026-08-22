import 'reflect-metadata';
import { getMetadataArgsStorage } from 'typeorm';
import { UtilizationSummaryEntity } from '../../src/entities/utilization-summary.entity';
import { TimeGrain } from '../../src/entities/enums';

describe('UtilizationSummaryEntity', () => {
  let entity: UtilizationSummaryEntity;

  beforeEach(() => {
    entity = new UtilizationSummaryEntity();
  });

  describe('instantiation', () => {
    it('should be defined', () => {
      expect(entity).toBeDefined();
      expect(entity).toBeInstanceOf(UtilizationSummaryEntity);
    });
  });

  describe('property assignment', () => {
    it('should accept all required properties', () => {
      entity.trackedResourceId = '00000000-0000-0000-0000-000000000001';
      entity.summaryDate = new Date('2024-01-15');
      entity.metricName = 'Percentage CPU';
      entity.avgUtilization = 12.5;
      entity.maxUtilization = 45.8;
      entity.minUtilization = 2.1;
      entity.sampleCount = 24;
      entity.timeGrain = TimeGrain.PT1H;

      expect(entity.trackedResourceId).toBeDefined();
      expect(entity.summaryDate).toBeInstanceOf(Date);
      expect(entity.metricName).toBe('Percentage CPU');
      expect(entity.avgUtilization).toBe(12.5);
      expect(entity.maxUtilization).toBe(45.8);
      expect(entity.minUtilization).toBe(2.1);
      expect(entity.sampleCount).toBe(24);
      expect(entity.timeGrain).toBe('PT1H');
    });

    it('should accept optional p95 utilization', () => {
      entity.p95Utilization = 38.2;
      expect(entity.p95Utilization).toBe(38.2);
    });

    it('should accept null for p95 utilization', () => {
      entity.p95Utilization = null;
      expect(entity.p95Utilization).toBeNull();
    });

    it('should accept underuse detection properties', () => {
      entity.isUnderused = true;
      entity.underuseThreshold = 10.0;

      expect(entity.isUnderused).toBe(true);
      expect(entity.underuseThreshold).toBe(10.0);
    });

    it('should accept null for underuse threshold', () => {
      entity.underuseThreshold = null;
      expect(entity.underuseThreshold).toBeNull();
    });

    it('should handle a realistic underused VM scenario', () => {
      entity.trackedResourceId = '00000000-0000-0000-0000-000000000001';
      entity.summaryDate = new Date('2024-01-15');
      entity.metricName = 'Percentage CPU';
      entity.avgUtilization = 3.2;
      entity.maxUtilization = 15.1;
      entity.minUtilization = 0.5;
      entity.p95Utilization = 8.7;
      entity.sampleCount = 24;
      entity.timeGrain = TimeGrain.PT1H;
      entity.isUnderused = true;
      entity.underuseThreshold = 10.0;

      // Validate underuse logic: avg < threshold
      expect(entity.avgUtilization).toBeLessThan(entity.underuseThreshold!);
      expect(entity.isUnderused).toBe(true);
    });

    it('should handle a normally utilized resource scenario', () => {
      entity.trackedResourceId = '00000000-0000-0000-0000-000000000001';
      entity.summaryDate = new Date('2024-01-15');
      entity.metricName = 'Percentage CPU';
      entity.avgUtilization = 55.8;
      entity.maxUtilization = 92.3;
      entity.minUtilization = 22.1;
      entity.p95Utilization = 78.5;
      entity.sampleCount = 24;
      entity.timeGrain = TimeGrain.PT1H;
      entity.isUnderused = false;
      entity.underuseThreshold = 10.0;

      // Validate: avg >= threshold
      expect(entity.avgUtilization).toBeGreaterThanOrEqual(entity.underuseThreshold!);
      expect(entity.isUnderused).toBe(false);
    });

    it('should validate min <= avg <= max utilization invariant', () => {
      entity.avgUtilization = 50.0;
      entity.maxUtilization = 95.0;
      entity.minUtilization = 5.0;

      expect(entity.minUtilization).toBeLessThanOrEqual(entity.avgUtilization);
      expect(entity.avgUtilization).toBeLessThanOrEqual(entity.maxUtilization);
    });
  });

  describe('TypeORM metadata', () => {
    const storage = getMetadataArgsStorage();

    it('should be registered as "utilization_summaries" table', () => {
      const tableMetadata = storage.tables.find((t) => t.target === UtilizationSummaryEntity);
      expect(tableMetadata).toBeDefined();
      expect(tableMetadata?.name).toBe('utilization_summaries');
    });

    it('should have a UUID primary generated column', () => {
      const generatedColumns = storage.generations.filter(
        (g) => g.target === UtilizationSummaryEntity,
      );
      expect(generatedColumns).toHaveLength(1);
      expect(generatedColumns[0].strategy).toBe('uuid');
    });

    it('should have many-to-one relation to TrackedResourceEntity', () => {
      const relations = storage.relations.filter(
        (r) => r.target === UtilizationSummaryEntity && r.propertyName === 'trackedResource',
      );
      expect(relations).toHaveLength(1);
      expect(relations[0].relationType).toBe('many-to-one');
    });

    it('should have enum column for timeGrain', () => {
      const columns = storage.columns.filter(
        (c) => c.target === UtilizationSummaryEntity && c.propertyName === 'timeGrain',
      );
      expect(columns).toHaveLength(1);
      expect(columns[0].options.type).toBe('enum');
      expect(columns[0].options.enum).toBe(TimeGrain);
    });

    it('should have date column for summaryDate', () => {
      const columns = storage.columns.filter(
        (c) => c.target === UtilizationSummaryEntity && c.propertyName === 'summaryDate',
      );
      expect(columns).toHaveLength(1);
      expect(columns[0].options.type).toBe('date');
    });

    it('should have double precision columns for utilization metrics', () => {
      const metricProperties = ['avgUtilization', 'maxUtilization', 'minUtilization'];
      for (const prop of metricProperties) {
        const columns = storage.columns.filter(
          (c) => c.target === UtilizationSummaryEntity && c.propertyName === prop,
        );
        expect(columns).toHaveLength(1);
        expect(columns[0].options.type).toBe('double precision');
      }
    });

    it('should have indexes for underuse queries', () => {
      const indexes = storage.indices.filter((i) => i.target === UtilizationSummaryEntity);
      expect(indexes.length).toBeGreaterThanOrEqual(3);
    });

    it('should have join column for tracked_resource_id', () => {
      const joinColumns = storage.joinColumns.filter((j) => j.target === UtilizationSummaryEntity);
      const columnNames = joinColumns.map((j) => j.name);
      expect(columnNames).toContain('tracked_resource_id');
    });
  });
});
