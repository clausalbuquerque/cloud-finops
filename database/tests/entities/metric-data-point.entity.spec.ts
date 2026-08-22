import 'reflect-metadata';
import { getMetadataArgsStorage } from 'typeorm';
import { MetricDataPointEntity } from '../../src/entities/metric-data-point.entity';
import { TimeGrain } from '../../src/entities/enums';

describe('MetricDataPointEntity', () => {
  let entity: MetricDataPointEntity;

  beforeEach(() => {
    entity = new MetricDataPointEntity();
  });

  describe('instantiation', () => {
    it('should be defined', () => {
      expect(entity).toBeDefined();
      expect(entity).toBeInstanceOf(MetricDataPointEntity);
    });
  });

  describe('property assignment', () => {
    it('should accept all required properties', () => {
      entity.trackedResourceId = '00000000-0000-0000-0000-000000000001';
      entity.metricDefinitionId = '00000000-0000-0000-0000-000000000002';
      entity.timestamp = new Date('2024-01-15T10:00:00Z');
      entity.timeGrain = TimeGrain.PT1H;

      expect(entity.trackedResourceId).toBeDefined();
      expect(entity.metricDefinitionId).toBeDefined();
      expect(entity.timestamp).toBeInstanceOf(Date);
      expect(entity.timeGrain).toBe('PT1H');
    });

    it('should accept all aggregation values', () => {
      entity.average = 45.5;
      entity.minimum = 10.2;
      entity.maximum = 92.8;
      entity.total = 1092.0;
      entity.count = 24;

      expect(entity.average).toBe(45.5);
      expect(entity.minimum).toBe(10.2);
      expect(entity.maximum).toBe(92.8);
      expect(entity.total).toBe(1092.0);
      expect(entity.count).toBe(24);
    });

    it('should accept null for nullable aggregation values', () => {
      entity.average = null;
      entity.minimum = null;
      entity.maximum = null;
      entity.total = null;
      entity.count = null;

      expect(entity.average).toBeNull();
      expect(entity.minimum).toBeNull();
      expect(entity.maximum).toBeNull();
      expect(entity.total).toBeNull();
      expect(entity.count).toBeNull();
    });

    it('should accept optional dimension properties', () => {
      entity.dimensionKey = 'StatusCode';
      entity.dimensionValue = '200';

      expect(entity.dimensionKey).toBe('StatusCode');
      expect(entity.dimensionValue).toBe('200');
    });

    it('should accept null for dimension properties', () => {
      entity.dimensionKey = null;
      entity.dimensionValue = null;

      expect(entity.dimensionKey).toBeNull();
      expect(entity.dimensionValue).toBeNull();
    });

    it('should support all TimeGrain values', () => {
      const grains = [
        TimeGrain.PT1M,
        TimeGrain.PT5M,
        TimeGrain.PT15M,
        TimeGrain.PT30M,
        TimeGrain.PT1H,
        TimeGrain.PT6H,
        TimeGrain.PT12H,
        TimeGrain.P1D,
      ];

      for (const grain of grains) {
        entity.timeGrain = grain;
        expect(entity.timeGrain).toBe(grain);
      }
    });

    it('should handle a realistic CPU metric data point', () => {
      entity.trackedResourceId = '00000000-0000-0000-0000-000000000001';
      entity.metricDefinitionId = '00000000-0000-0000-0000-000000000002';
      entity.timestamp = new Date('2024-01-15T10:00:00Z');
      entity.timeGrain = TimeGrain.PT1H;
      entity.average = 12.3;
      entity.minimum = 2.1;
      entity.maximum = 45.6;
      entity.total = 738.0;
      entity.count = 60;
      entity.dimensionKey = null;
      entity.dimensionValue = null;

      expect(entity.average).toBeLessThan(100);
      expect(entity.minimum).toBeLessThanOrEqual(entity.average);
      expect(entity.maximum).toBeGreaterThanOrEqual(entity.average);
    });
  });

  describe('TypeORM metadata', () => {
    const storage = getMetadataArgsStorage();

    it('should be registered as "metric_data_points" table', () => {
      const tableMetadata = storage.tables.find((t) => t.target === MetricDataPointEntity);
      expect(tableMetadata).toBeDefined();
      expect(tableMetadata?.name).toBe('metric_data_points');
    });

    it('should have a UUID primary generated column', () => {
      const generatedColumns = storage.generations.filter(
        (g) => g.target === MetricDataPointEntity,
      );
      expect(generatedColumns).toHaveLength(1);
      expect(generatedColumns[0].strategy).toBe('uuid');
    });

    it('should have many-to-one relation to TrackedResourceEntity', () => {
      const relations = storage.relations.filter(
        (r) => r.target === MetricDataPointEntity && r.propertyName === 'trackedResource',
      );
      expect(relations).toHaveLength(1);
      expect(relations[0].relationType).toBe('many-to-one');
    });

    it('should have many-to-one relation to MetricDefinitionEntity', () => {
      const relations = storage.relations.filter(
        (r) => r.target === MetricDataPointEntity && r.propertyName === 'metricDefinition',
      );
      expect(relations).toHaveLength(1);
      expect(relations[0].relationType).toBe('many-to-one');
    });

    it('should have enum column for timeGrain', () => {
      const columns = storage.columns.filter(
        (c) => c.target === MetricDataPointEntity && c.propertyName === 'timeGrain',
      );
      expect(columns).toHaveLength(1);
      expect(columns[0].options.type).toBe('enum');
      expect(columns[0].options.enum).toBe(TimeGrain);
    });

    it('should have double precision columns for metric values', () => {
      const metricProperties = ['average', 'minimum', 'maximum', 'total', 'count'];
      for (const prop of metricProperties) {
        const columns = storage.columns.filter(
          (c) => c.target === MetricDataPointEntity && c.propertyName === prop,
        );
        expect(columns).toHaveLength(1);
        expect(columns[0].options.type).toBe('double precision');
        expect(columns[0].options.nullable).toBe(true);
      }
    });

    it('should have indexes for time-series queries', () => {
      const indexes = storage.indices.filter((i) => i.target === MetricDataPointEntity);
      expect(indexes.length).toBeGreaterThanOrEqual(3);
    });

    it('should have join columns for tracked_resource_id and metric_definition_id', () => {
      const joinColumns = storage.joinColumns.filter((j) => j.target === MetricDataPointEntity);
      const columnNames = joinColumns.map((j) => j.name);
      expect(columnNames).toContain('tracked_resource_id');
      expect(columnNames).toContain('metric_definition_id');
    });
  });
});
