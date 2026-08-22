import { Test, TestingModule } from '@nestjs/testing';
import { ConfigService } from '@nestjs/config';
import { DataSource, Repository } from 'typeorm';
import { getRepositoryToken } from '@nestjs/typeorm';
import { MetricsExtractorService } from './metrics-extractor.service';
import { AzureResourceClientService } from '@modules/metrics/azure-resource-client.service';
import { AzureMonitorClientService } from '@modules/metrics/azure-monitor-client.service';
import { UtilizationMetricsRegistry } from '@modules/metrics/utilization-metrics-registry.service';
import {
  SubscriptionEntity,
  ResourceGroupEntity,
  TrackedResourceEntity,
  MetricDefinitionEntity,
  MetricDataPointEntity,
  AggregationType,
  TimeGrain,
} from '@modules/database';
import { DiscoveredResource, MetricQueryResult } from '@modules/metrics/interfaces';

describe('MetricsExtractorService', () => {
  let service: MetricsExtractorService;
  let resourceClient: jest.Mocked<AzureResourceClientService>;
  let monitorClient: jest.Mocked<AzureMonitorClientService>;
  let metricsRegistry: UtilizationMetricsRegistry;
  let subscriptionRepo: jest.Mocked<Repository<SubscriptionEntity>>;
  let resourceGroupRepo: jest.Mocked<Repository<ResourceGroupEntity>>;
  let trackedResourceRepo: jest.Mocked<Repository<TrackedResourceEntity>>;
  let metricDefRepo: jest.Mocked<Repository<MetricDefinitionEntity>>;

  const mockSubscription: SubscriptionEntity = {
    id: 'sub-uuid-1',
    subscriptionId: 'azure-sub-123',
    displayName: 'Test Sub',
    state: 'Enabled',
    createdAt: new Date(),
    updatedAt: new Date(),
    resourceGroups: [],
  };

  const mockResourceGroup: ResourceGroupEntity = {
    id: 'rg-uuid-1',
    name: 'test-rg',
    location: 'eastus',
    subscription: mockSubscription,
    subscriptionId: 'sub-uuid-1',
    createdAt: new Date(),
    updatedAt: new Date(),
  };

  const mockDiscoveredResources: DiscoveredResource[] = [
    {
      id: '/subscriptions/azure-sub-123/resourceGroups/test-rg/providers/Microsoft.Compute/virtualMachines/vm-1',
      name: 'vm-1',
      type: 'Microsoft.Compute/virtualMachines',
      resourceGroup: 'test-rg',
      location: 'eastus',
      sku: { name: 'Standard_D2s_v3', tier: 'Standard', capacity: 2 },
      tags: { env: 'dev' },
    },
    {
      id: '/subscriptions/azure-sub-123/resourceGroups/test-rg/providers/Microsoft.Compute/virtualMachines/vm-2',
      name: 'vm-2',
      type: 'Microsoft.Compute/virtualMachines',
      resourceGroup: 'test-rg',
      location: 'eastus',
    },
  ];

  const mockTrackedResource: TrackedResourceEntity = {
    id: 'tr-uuid-1',
    azureResourceId: mockDiscoveredResources[0].id,
    resourceName: 'vm-1',
    resourceType: 'Microsoft.Compute/virtualMachines',
    region: 'eastus',
    sku: 'Standard_D2s_v3',
    provisionedCapacity: { skuName: 'Standard_D2s_v3', skuTier: 'Standard', skuCapacity: 2 },
    isActive: true,
    lastMetricSync: null,
    subscription: mockSubscription,
    subscriptionId: 'sub-uuid-1',
    resourceGroup: mockResourceGroup,
    resourceGroupId: 'rg-uuid-1',
    createdAt: new Date(),
    updatedAt: new Date(),
    metricDataPoints: [],
    utilizationSummaries: [],
  };

  const mockMetricDef: MetricDefinitionEntity = {
    id: 'md-uuid-1',
    resourceType: 'Microsoft.Compute/virtualMachines',
    metricNamespace: 'Microsoft.Compute/virtualMachines',
    metricName: 'Percentage CPU',
    displayName: 'CPU Utilization',
    unit: 'Unspecified' as never,
    primaryAggregationType: AggregationType.Average,
    supportedAggregationTypes: ['Average', 'Minimum', 'Maximum'],
    isUtilizationMetric: true,
    createdAt: new Date(),
    updatedAt: new Date(),
  };

  const mockMetricQueryResult: MetricQueryResult = {
    timeSeries: [
      {
        resourceId: mockDiscoveredResources[0].id,
        metricName: 'Percentage CPU',
        namespace: 'Microsoft.Compute/virtualMachines',
        unit: 'Percent',
        timeGrain: 'PT1H',
        dataPoints: [
          {
            timestamp: new Date('2026-03-25T00:00:00Z'),
            average: 15.5,
            minimum: 2.0,
            maximum: 45.0,
            total: 186.0,
            count: 12,
          },
          {
            timestamp: new Date('2026-03-25T01:00:00Z'),
            average: 22.3,
            minimum: 5.0,
            maximum: 60.0,
            total: 267.6,
            count: 12,
          },
        ],
      },
    ],
    totalDataPoints: 2,
  };

  // Mock transaction manager
  const mockTransactionManager = {
    getRepository: jest.fn().mockReturnValue({
      findOne: jest.fn().mockResolvedValue(null),
      create: jest.fn().mockImplementation((data: Record<string, unknown>) => data),
      save: jest
        .fn()
        .mockImplementation((entity: Record<string, unknown>) =>
          Promise.resolve({ id: 'dp-uuid-1', ...entity }),
        ),
    }),
  };

  const mockDataSource = {
    transaction: jest
      .fn()
      .mockImplementation(
        async (callback: (manager: typeof mockTransactionManager) => Promise<void>) => {
          await callback(mockTransactionManager);
        },
      ),
  };

  const mockQueryBuilder = {
    update: jest.fn().mockReturnThis(),
    set: jest.fn().mockReturnThis(),
    whereInIds: jest.fn().mockReturnThis(),
    execute: jest.fn().mockResolvedValue({ affected: 1 }),
  };

  beforeEach(async () => {
    const module: TestingModule = await Test.createTestingModule({
      providers: [
        MetricsExtractorService,
        {
          provide: AzureResourceClientService,
          useValue: {
            discoverResources: jest.fn(),
          },
        },
        {
          provide: AzureMonitorClientService,
          useValue: {
            queryMetricsBatch: jest.fn(),
          },
        },
        {
          provide: UtilizationMetricsRegistry,
          useFactory: () => new UtilizationMetricsRegistry(),
        },
        {
          provide: ConfigService,
          useValue: {
            get: jest.fn().mockImplementation((key: string, defaultValue?: unknown) => {
              const values: Record<string, string> = {
                'azure.subscriptionId': 'azure-sub-123',
              };
              return values[key] ?? defaultValue ?? '';
            }),
          },
        },
        {
          provide: DataSource,
          useValue: mockDataSource,
        },
        {
          provide: getRepositoryToken(SubscriptionEntity),
          useValue: {
            findOne: jest.fn(),
            create: jest.fn(),
            save: jest.fn(),
          },
        },
        {
          provide: getRepositoryToken(ResourceGroupEntity),
          useValue: {
            findOne: jest.fn(),
            create: jest.fn(),
            save: jest.fn(),
          },
        },
        {
          provide: getRepositoryToken(TrackedResourceEntity),
          useValue: {
            findOne: jest.fn(),
            create: jest.fn(),
            save: jest.fn(),
            createQueryBuilder: jest.fn().mockReturnValue(mockQueryBuilder),
          },
        },
        {
          provide: getRepositoryToken(MetricDefinitionEntity),
          useValue: {
            findOne: jest.fn(),
            create: jest.fn(),
            save: jest.fn(),
          },
        },
        {
          provide: getRepositoryToken(MetricDataPointEntity),
          useValue: {
            findOne: jest.fn(),
            create: jest.fn(),
            save: jest.fn(),
          },
        },
      ],
    }).compile();

    service = module.get<MetricsExtractorService>(MetricsExtractorService);
    resourceClient = module.get(AzureResourceClientService);
    monitorClient = module.get(AzureMonitorClientService);
    metricsRegistry = module.get(UtilizationMetricsRegistry);
    subscriptionRepo = module.get(getRepositoryToken(SubscriptionEntity));
    resourceGroupRepo = module.get(getRepositoryToken(ResourceGroupEntity));
    trackedResourceRepo = module.get(getRepositoryToken(TrackedResourceEntity));
    metricDefRepo = module.get(getRepositoryToken(MetricDefinitionEntity));
  });

  it('should be defined', () => {
    expect(service).toBeDefined();
  });

  describe('mapAggregationType', () => {
    it('should map known aggregation types', () => {
      expect(service.mapAggregationType('Average')).toBe(AggregationType.Average);
      expect(service.mapAggregationType('Minimum')).toBe(AggregationType.Minimum);
      expect(service.mapAggregationType('Maximum')).toBe(AggregationType.Maximum);
      expect(service.mapAggregationType('Total')).toBe(AggregationType.Total);
      expect(service.mapAggregationType('Count')).toBe(AggregationType.Count);
    });

    it('should default to Average for unknown types', () => {
      expect(service.mapAggregationType('Unknown')).toBe(AggregationType.Average);
    });
  });

  describe('mapTimeGrain', () => {
    it('should map known time grains', () => {
      expect(service.mapTimeGrain('PT1H')).toBe(TimeGrain.PT1H);
      expect(service.mapTimeGrain('P1D')).toBe(TimeGrain.P1D);
      expect(service.mapTimeGrain('PT5M')).toBe(TimeGrain.PT5M);
    });

    it('should default to PT1H for unknown grains', () => {
      expect(service.mapTimeGrain('INVALID')).toBe(TimeGrain.PT1H);
    });
  });

  describe('syncTrackedResources', () => {
    it('should create new tracked resources', async () => {
      resourceGroupRepo.findOne.mockResolvedValue(null);
      resourceGroupRepo.create.mockReturnValue(mockResourceGroup);
      resourceGroupRepo.save.mockResolvedValue(mockResourceGroup);

      trackedResourceRepo.findOne.mockResolvedValue(null);
      trackedResourceRepo.create.mockReturnValue(mockTrackedResource);
      trackedResourceRepo.save.mockResolvedValue(mockTrackedResource);

      const result = await service.syncTrackedResources(
        mockDiscoveredResources,
        mockSubscription.id,
      );

      expect(result.length).toBe(2);
      expect(trackedResourceRepo.create).toHaveBeenCalled();
      expect(trackedResourceRepo.save).toHaveBeenCalled();
    });

    it('should update existing tracked resources', async () => {
      resourceGroupRepo.findOne.mockResolvedValue(mockResourceGroup);
      trackedResourceRepo.findOne.mockResolvedValue({ ...mockTrackedResource });
      trackedResourceRepo.save.mockResolvedValue(mockTrackedResource);

      const result = await service.syncTrackedResources(
        [mockDiscoveredResources[0]],
        mockSubscription.id,
      );

      expect(result.length).toBe(1);
      expect(trackedResourceRepo.create).not.toHaveBeenCalled();
      expect(trackedResourceRepo.save).toHaveBeenCalledWith(
        expect.objectContaining({ isActive: true }),
      );
    });

    it('should handle errors for individual resources gracefully', async () => {
      resourceGroupRepo.findOne.mockRejectedValue(new Error('DB error'));

      const result = await service.syncTrackedResources(
        [mockDiscoveredResources[0]],
        mockSubscription.id,
      );

      expect(result.length).toBe(0);
    });
  });

  describe('syncMetricDefinitions', () => {
    const metricConfigs = [
      {
        metricName: 'Percentage CPU',
        namespace: 'Microsoft.Compute/virtualMachines',
        displayName: 'CPU Utilization',
        aggregationType: 'Average',
        isUtilizationMetric: true,
      },
    ];

    it('should create metric definitions when they do not exist', async () => {
      metricDefRepo.findOne.mockResolvedValue(null);
      metricDefRepo.create.mockReturnValue(mockMetricDef);
      metricDefRepo.save.mockResolvedValue(mockMetricDef);

      const result = await service.syncMetricDefinitions(
        'Microsoft.Compute/virtualMachines',
        metricConfigs,
      );

      expect(result.length).toBe(1);
      expect(metricDefRepo.create).toHaveBeenCalledWith(
        expect.objectContaining({
          metricName: 'Percentage CPU',
          isUtilizationMetric: true,
        }),
      );
    });

    it('should return existing metric definitions', async () => {
      metricDefRepo.findOne.mockResolvedValue(mockMetricDef);

      const result = await service.syncMetricDefinitions(
        'Microsoft.Compute/virtualMachines',
        metricConfigs,
      );

      expect(result.length).toBe(1);
      expect(metricDefRepo.create).not.toHaveBeenCalled();
    });
  });

  describe('extract', () => {
    it('should execute full extraction pipeline', async () => {
      // Setup mocks
      resourceClient.discoverResources.mockResolvedValue(mockDiscoveredResources);
      monitorClient.queryMetricsBatch.mockResolvedValue(mockMetricQueryResult);

      subscriptionRepo.findOne.mockResolvedValue(mockSubscription);
      resourceGroupRepo.findOne.mockResolvedValue(mockResourceGroup);
      trackedResourceRepo.findOne.mockResolvedValue(null);
      trackedResourceRepo.create.mockReturnValue(mockTrackedResource);
      trackedResourceRepo.save.mockResolvedValue(mockTrackedResource);

      metricDefRepo.findOne.mockResolvedValue(null);
      metricDefRepo.create.mockReturnValue(mockMetricDef);
      metricDefRepo.save.mockResolvedValue(mockMetricDef);

      const result = await service.extract({
        startDate: new Date('2026-03-25'),
        endDate: new Date('2026-03-26'),
        subscriptionId: 'azure-sub-123',
        resourceTypes: ['Microsoft.Compute/virtualMachines'],
      });

      expect(result.resourcesDiscovered).toBe(2);
      expect(result.resourcesSynced).toBe(2);
      expect(result.errors.length).toBe(0);
      expect(result.durationMs).toBeGreaterThanOrEqual(0);
      expect(resourceClient.discoverResources).toHaveBeenCalledWith(
        expect.objectContaining({
          subscriptionId: 'azure-sub-123',
          resourceType: 'Microsoft.Compute/virtualMachines',
        }),
      );
      expect(monitorClient.queryMetricsBatch).toHaveBeenCalled();
    });

    it('should handle errors during resource discovery gracefully', async () => {
      resourceClient.discoverResources.mockRejectedValue(new Error('ARM API error'));

      const result = await service.extract({
        startDate: new Date('2026-03-25'),
        endDate: new Date('2026-03-26'),
        resourceTypes: ['Microsoft.Compute/virtualMachines'],
      });

      expect(result.errors.length).toBe(1);
      expect(result.errors[0].phase).toBe('fetch');
      expect(result.errors[0].message).toContain('ARM API error');
    });

    it('should skip resource types with no metrics configured', async () => {
      resourceClient.discoverResources.mockResolvedValue(mockDiscoveredResources);
      subscriptionRepo.findOne.mockResolvedValue(mockSubscription);
      resourceGroupRepo.findOne.mockResolvedValue(mockResourceGroup);
      trackedResourceRepo.findOne.mockResolvedValue(null);
      trackedResourceRepo.create.mockReturnValue(mockTrackedResource);
      trackedResourceRepo.save.mockResolvedValue(mockTrackedResource);

      // Register an empty metrics config
      metricsRegistry.registerMetrics('Microsoft.Custom/empty', []);

      const result = await service.extract({
        startDate: new Date('2026-03-25'),
        endDate: new Date('2026-03-26'),
        resourceTypes: ['Microsoft.Custom/empty'],
      });

      expect(result.dataPointsFetched).toBe(0);
      expect(monitorClient.queryMetricsBatch).not.toHaveBeenCalled();
    });

    it('should use registered resource types when none specified', async () => {
      resourceClient.discoverResources.mockResolvedValue([]);

      const result = await service.extract({
        startDate: new Date('2026-03-25'),
        endDate: new Date('2026-03-26'),
      });

      // Should have called discover for each registered type
      const registeredTypes = metricsRegistry.getRegisteredTypes();
      expect(resourceClient.discoverResources).toHaveBeenCalledTimes(registeredTypes.length);
      expect(result.resourcesDiscovered).toBe(0);
    });

    it('should skip empty discovery results', async () => {
      resourceClient.discoverResources.mockResolvedValue([]);

      const result = await service.extract({
        startDate: new Date('2026-03-25'),
        endDate: new Date('2026-03-26'),
        resourceTypes: ['Microsoft.Compute/virtualMachines'],
      });

      expect(result.resourcesSynced).toBe(0);
      expect(result.dataPointsFetched).toBe(0);
      expect(monitorClient.queryMetricsBatch).not.toHaveBeenCalled();
    });
  });
});
