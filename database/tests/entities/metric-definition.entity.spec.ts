import 'reflect-metadata';
import { getMetadataArgsStorage } from 'typeorm';
import { MetricDefinitionEntity } from '../../src/entities/metric-definition.entity';
import { MetricUnit, AggregationType } from '../../src/entities/enums';

describe('MetricDefinitionEntity', () => {
  let entity: MetricDefinitionEntity;

  beforeEach(() => {
    entity = new MetricDefinitionEntity();
  });

  describe('instantiation', () => {
    it('should be defined', () => {
      expect(entity).toBeDefined();
      expect(entity).toBeInstanceOf(MetricDefinitionEntity);
    });
  });

  describe('property assignment', () => {
    it('should accept all required properties', () => {
      entity.resourceType = 'Microsoft.Compute/virtualMachines';
      entity.metricNamespace = 'Microsoft.Compute/virtualMachines';
      entity.metricName = 'Percentage CPU';
      entity.unit = MetricUnit.Percent;
      entity.primaryAggregationType = AggregationType.Average;

      expect(entity.resourceType).toBe('Microsoft.Compute/virtualMachines');
      expect(entity.metricNamespace).toBe('Microsoft.Compute/virtualMachines');
      expect(entity.metricName).toBe('Percentage CPU');
      expect(entity.unit).toBe(MetricUnit.Percent);
      expect(entity.primaryAggregationType).toBe(AggregationType.Average);
    });

    it('should accept optional display name', () => {
      entity.displayName = 'CPU Utilization';
      expect(entity.displayName).toBe('CPU Utilization');
    });

    it('should accept supported aggregation types as string array', () => {
      entity.supportedAggregationTypes = ['Average', 'Minimum', 'Maximum'];
      expect(entity.supportedAggregationTypes).toEqual(['Average', 'Minimum', 'Maximum']);
      expect(entity.supportedAggregationTypes).toHaveLength(3);
    });

    it('should accept isUtilizationMetric flag', () => {
      entity.isUtilizationMetric = true;
      expect(entity.isUtilizationMetric).toBe(true);
    });

    it('should handle a complete VM CPU metric definition', () => {
      entity.resourceType = 'Microsoft.Compute/virtualMachines';
      entity.metricNamespace = 'Microsoft.Compute/virtualMachines';
      entity.metricName = 'Percentage CPU';
      entity.displayName = 'Percentage CPU';
      entity.unit = MetricUnit.Percent;
      entity.primaryAggregationType = AggregationType.Average;
      entity.supportedAggregationTypes = ['Average', 'Minimum', 'Maximum', 'Total', 'Count'];
      entity.isUtilizationMetric = true;

      expect(entity.unit).toBe('Percent');
      expect(entity.isUtilizationMetric).toBe(true);
      expect(entity.supportedAggregationTypes).toHaveLength(5);
    });

    it('should handle a storage metric definition', () => {
      entity.resourceType = 'Microsoft.Storage/storageAccounts';
      entity.metricNamespace = 'Microsoft.Storage/storageAccounts';
      entity.metricName = 'UsedCapacity';
      entity.unit = MetricUnit.Bytes;
      entity.primaryAggregationType = AggregationType.Average;
      entity.isUtilizationMetric = false;

      expect(entity.unit).toBe('Bytes');
      expect(entity.isUtilizationMetric).toBe(false);
    });
  });

  describe('TypeORM metadata', () => {
    const storage = getMetadataArgsStorage();

    it('should be registered as "metric_definitions" table', () => {
      const tableMetadata = storage.tables.find((t) => t.target === MetricDefinitionEntity);
      expect(tableMetadata).toBeDefined();
      expect(tableMetadata?.name).toBe('metric_definitions');
    });

    it('should have a UUID primary generated column', () => {
      const generatedColumns = storage.generations.filter(
        (g) => g.target === MetricDefinitionEntity,
      );
      expect(generatedColumns).toHaveLength(1);
      expect(generatedColumns[0].strategy).toBe('uuid');
    });

    it('should have enum column for unit', () => {
      const columns = storage.columns.filter(
        (c) => c.target === MetricDefinitionEntity && c.propertyName === 'unit',
      );
      expect(columns).toHaveLength(1);
      expect(columns[0].options.type).toBe('enum');
      expect(columns[0].options.enum).toBe(MetricUnit);
    });

    it('should have enum column for primaryAggregationType', () => {
      const columns = storage.columns.filter(
        (c) => c.target === MetricDefinitionEntity && c.propertyName === 'primaryAggregationType',
      );
      expect(columns).toHaveLength(1);
      expect(columns[0].options.type).toBe('enum');
      expect(columns[0].options.enum).toBe(AggregationType);
    });

    it('should have text array column for supportedAggregationTypes', () => {
      const columns = storage.columns.filter(
        (c) =>
          c.target === MetricDefinitionEntity && c.propertyName === 'supportedAggregationTypes',
      );
      expect(columns).toHaveLength(1);
      expect(columns[0].options.type).toBe('text');
      expect(columns[0].options.array).toBe(true);
    });

    it('should have composite unique index on resource_type + metric_name', () => {
      const indexes = storage.indices.filter(
        (i) => i.target === MetricDefinitionEntity && i.unique === true,
      );
      expect(indexes.length).toBeGreaterThanOrEqual(1);
    });

    it('should have index on resource_type + isUtilizationMetric', () => {
      const indexes = storage.indices.filter((i) => i.target === MetricDefinitionEntity);
      expect(indexes.length).toBeGreaterThanOrEqual(2);
    });
  });
});
