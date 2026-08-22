import 'reflect-metadata';
import { getMetadataArgsStorage } from 'typeorm';
import { TrackedResourceEntity } from '../../src/entities/tracked-resource.entity';

describe('TrackedResourceEntity', () => {
  let entity: TrackedResourceEntity;

  beforeEach(() => {
    entity = new TrackedResourceEntity();
  });

  describe('instantiation', () => {
    it('should be defined', () => {
      expect(entity).toBeDefined();
      expect(entity).toBeInstanceOf(TrackedResourceEntity);
    });

    it('should have default values', () => {
      // Properties should be undefined by default (DB defaults apply at persist time)
      expect(entity.id).toBeUndefined();
      expect(entity.azureResourceId).toBeUndefined();
      expect(entity.resourceName).toBeUndefined();
      expect(entity.resourceType).toBeUndefined();
    });
  });

  describe('property assignment', () => {
    it('should accept all required properties', () => {
      entity.azureResourceId =
        '/subscriptions/00000000-0000-0000-0000-000000000000/resourceGroups/rg-test/providers/Microsoft.Compute/virtualMachines/vm-test';
      entity.resourceName = 'vm-test';
      entity.resourceType = 'Microsoft.Compute/virtualMachines';
      entity.subscriptionId = '00000000-0000-0000-0000-000000000001';
      entity.resourceGroupId = '00000000-0000-0000-0000-000000000002';

      expect(entity.azureResourceId).toContain('Microsoft.Compute/virtualMachines/vm-test');
      expect(entity.resourceName).toBe('vm-test');
      expect(entity.resourceType).toBe('Microsoft.Compute/virtualMachines');
    });

    it('should accept optional properties', () => {
      entity.region = 'eastus';
      entity.sku = 'Standard_D2s_v3';
      entity.provisionedCapacity = { vCPUs: 4, memoryGB: 16 };
      entity.isActive = true;
      entity.lastMetricSync = new Date('2024-01-01T00:00:00Z');

      expect(entity.region).toBe('eastus');
      expect(entity.sku).toBe('Standard_D2s_v3');
      expect(entity.provisionedCapacity).toEqual({ vCPUs: 4, memoryGB: 16 });
      expect(entity.isActive).toBe(true);
      expect(entity.lastMetricSync).toBeInstanceOf(Date);
    });

    it('should accept null for nullable properties', () => {
      entity.region = undefined as unknown as string;
      entity.sku = undefined as unknown as string;
      entity.provisionedCapacity = null;
      entity.lastMetricSync = null;

      expect(entity.provisionedCapacity).toBeNull();
      expect(entity.lastMetricSync).toBeNull();
    });
  });

  describe('TypeORM metadata', () => {
    const storage = getMetadataArgsStorage();

    it('should be registered as "tracked_resources" table', () => {
      const tableMetadata = storage.tables.find((t) => t.target === TrackedResourceEntity);
      expect(tableMetadata).toBeDefined();
      expect(tableMetadata?.name).toBe('tracked_resources');
    });

    it('should have a UUID primary generated column', () => {
      const generatedColumns = storage.generations.filter(
        (g) => g.target === TrackedResourceEntity,
      );
      expect(generatedColumns).toHaveLength(1);
      expect(generatedColumns[0].strategy).toBe('uuid');
    });

    it('should have relation to SubscriptionEntity', () => {
      const relations = storage.relations.filter(
        (r) => r.target === TrackedResourceEntity && r.propertyName === 'subscription',
      );
      expect(relations).toHaveLength(1);
      expect(relations[0].relationType).toBe('many-to-one');
    });

    it('should have relation to ResourceGroupEntity', () => {
      const relations = storage.relations.filter(
        (r) => r.target === TrackedResourceEntity && r.propertyName === 'resourceGroup',
      );
      expect(relations).toHaveLength(1);
      expect(relations[0].relationType).toBe('many-to-one');
    });

    it('should have one-to-many relation to MetricDataPointEntity', () => {
      const relations = storage.relations.filter(
        (r) => r.target === TrackedResourceEntity && r.propertyName === 'metricDataPoints',
      );
      expect(relations).toHaveLength(1);
      expect(relations[0].relationType).toBe('one-to-many');
    });

    it('should have one-to-many relation to UtilizationSummaryEntity', () => {
      const relations = storage.relations.filter(
        (r) => r.target === TrackedResourceEntity && r.propertyName === 'utilizationSummaries',
      );
      expect(relations).toHaveLength(1);
      expect(relations[0].relationType).toBe('one-to-many');
    });

    it('should have indexes on azureResourceId, resourceType, and isActive', () => {
      const indexes = storage.indices.filter((i) => i.target === TrackedResourceEntity);
      expect(indexes.length).toBeGreaterThanOrEqual(3);

      const uniqueIndex = indexes.find((i) => i.unique === true);
      expect(uniqueIndex).toBeDefined();
    });

    it('should have join columns for subscription_id and resource_group_id', () => {
      const joinColumns = storage.joinColumns.filter((j) => j.target === TrackedResourceEntity);
      const columnNames = joinColumns.map((j) => j.name);
      expect(columnNames).toContain('subscription_id');
      expect(columnNames).toContain('resource_group_id');
    });
  });
});
