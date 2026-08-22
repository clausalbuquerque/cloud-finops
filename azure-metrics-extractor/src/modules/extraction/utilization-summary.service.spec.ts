import { Test, TestingModule } from '@nestjs/testing';
import { ConfigService } from '@nestjs/config';
import { Repository } from 'typeorm';
import { getRepositoryToken } from '@nestjs/typeorm';
import { UtilizationSummaryService } from './utilization-summary.service';
import { UtilizationMetricsRegistry } from '@modules/metrics/utilization-metrics-registry.service';
import {
  TrackedResourceEntity,
  MetricDefinitionEntity,
  MetricDataPointEntity,
  UtilizationSummaryEntity,
  AggregationType,
  TimeGrain,
  MetricUnit,
} from '@modules/database';

describe('UtilizationSummaryService', () => {
  let service: UtilizationSummaryService;
  let metricDefRepo: jest.Mocked<Repository<MetricDefinitionEntity>>;
  let dataPointRepo: jest.Mocked<Repository<MetricDataPointEntity>>;
  let summaryRepo: jest.Mocked<Repository<UtilizationSummaryEntity>>;

  const mockTrackedResource: TrackedResourceEntity = {
    id: 'tr-uuid-1',
    azureResourceId:
      '/subscriptions/sub/resourceGroups/rg/providers/Microsoft.Compute/virtualMachines/vm-1',
    resourceName: 'vm-1',
    resourceType: 'Microsoft.Compute/virtualMachines',
    region: 'eastus',
    sku: 'Standard_D2s_v3',
    provisionedCapacity: null,
    isActive: true,
    lastMetricSync: null,
    subscription: {} as TrackedResourceEntity['subscription'],
    subscriptionId: 'sub-uuid-1',
    resourceGroup: {} as TrackedResourceEntity['resourceGroup'],
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
    unit: MetricUnit.Percent,
    primaryAggregationType: AggregationType.Average,
    supportedAggregationTypes: ['Average', 'Minimum', 'Maximum'],
    isUtilizationMetric: true,
    createdAt: new Date(),
    updatedAt: new Date(),
  };

  const mockDataPoints: MetricDataPointEntity[] = [
    {
      id: 'dp-1',
      trackedResource: mockTrackedResource,
      trackedResourceId: 'tr-uuid-1',
      metricDefinition: mockMetricDef,
      metricDefinitionId: 'md-uuid-1',
      timestamp: new Date('2026-03-25T00:00:00Z'),
      timeGrain: TimeGrain.PT1H,
      average: 5.0,
      minimum: 1.0,
      maximum: 12.0,
      total: 60.0,
      count: 12,
      dimensionKey: null,
      dimensionValue: null,
      createdAt: new Date(),
    },
    {
      id: 'dp-2',
      trackedResource: mockTrackedResource,
      trackedResourceId: 'tr-uuid-1',
      metricDefinition: mockMetricDef,
      metricDefinitionId: 'md-uuid-1',
      timestamp: new Date('2026-03-25T01:00:00Z'),
      timeGrain: TimeGrain.PT1H,
      average: 8.0,
      minimum: 3.0,
      maximum: 18.0,
      total: 96.0,
      count: 12,
      dimensionKey: null,
      dimensionValue: null,
      createdAt: new Date(),
    },
    {
      id: 'dp-3',
      trackedResource: mockTrackedResource,
      trackedResourceId: 'tr-uuid-1',
      metricDefinition: mockMetricDef,
      metricDefinitionId: 'md-uuid-1',
      timestamp: new Date('2026-03-25T02:00:00Z'),
      timeGrain: TimeGrain.PT1H,
      average: 3.0,
      minimum: 0.5,
      maximum: 9.0,
      total: 36.0,
      count: 12,
      dimensionKey: null,
      dimensionValue: null,
      createdAt: new Date(),
    },
  ];

  const mockQueryBuilder = {
    where: jest.fn().mockReturnThis(),
    andWhere: jest.fn().mockReturnThis(),
    getMany: jest.fn().mockResolvedValue([mockTrackedResource]),
  };

  beforeEach(async () => {
    const module: TestingModule = await Test.createTestingModule({
      providers: [
        UtilizationSummaryService,
        {
          provide: ConfigService,
          useValue: {
            get: jest.fn().mockImplementation((_key: string, defaultValue?: unknown) => {
              return defaultValue;
            }),
          },
        },
        {
          provide: UtilizationMetricsRegistry,
          useFactory: () => new UtilizationMetricsRegistry(),
        },
        {
          provide: getRepositoryToken(TrackedResourceEntity),
          useValue: {
            createQueryBuilder: jest.fn().mockReturnValue(mockQueryBuilder),
          },
        },
        {
          provide: getRepositoryToken(MetricDefinitionEntity),
          useValue: {
            find: jest.fn(),
          },
        },
        {
          provide: getRepositoryToken(MetricDataPointEntity),
          useValue: {
            find: jest.fn(),
          },
        },
        {
          provide: getRepositoryToken(UtilizationSummaryEntity),
          useValue: {
            findOne: jest.fn(),
            create: jest.fn(),
            save: jest.fn(),
          },
        },
      ],
    }).compile();

    service = module.get<UtilizationSummaryService>(UtilizationSummaryService);
    metricDefRepo = module.get(getRepositoryToken(MetricDefinitionEntity));
    dataPointRepo = module.get(getRepositoryToken(MetricDataPointEntity));
    summaryRepo = module.get(getRepositoryToken(UtilizationSummaryEntity));
  });

  it('should be defined', () => {
    expect(service).toBeDefined();
  });

  describe('computePercentile', () => {
    it('should compute p95 correctly', () => {
      const values = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20];
      const p95 = service.computePercentile(values, 95);
      expect(p95).toBeCloseTo(19.05, 1);
    });

    it('should return the single value for a single-element array', () => {
      const p95 = service.computePercentile([42], 95);
      expect(p95).toBe(42);
    });

    it('should compute p50 (median)', () => {
      const values = [10, 20, 30, 40, 50];
      const p50 = service.computePercentile(values, 50);
      expect(p50).toBe(30);
    });

    it('should sort values before computing', () => {
      const values = [50, 10, 30, 20, 40];
      const p50 = service.computePercentile(values, 50);
      expect(p50).toBe(30);
    });
  });

  describe('groupByDay', () => {
    it('should group data points by date', () => {
      const day2Points: MetricDataPointEntity[] = [
        {
          ...mockDataPoints[0],
          timestamp: new Date('2026-03-26T10:00:00Z'),
        },
      ];

      const allPoints = [...mockDataPoints, ...day2Points];
      const groups = service.groupByDay(allPoints);

      expect(groups.size).toBe(2);
      expect(groups.get('2026-03-25')?.length).toBe(3);
      expect(groups.get('2026-03-26')?.length).toBe(1);
    });

    it('should handle empty array', () => {
      const groups = service.groupByDay([]);
      expect(groups.size).toBe(0);
    });
  });

  describe('resolveThreshold', () => {
    it('should return CPU threshold for CPU-related metrics', () => {
      const threshold = service.resolveThreshold('Percentage CPU', 10);
      expect(threshold).toBe(10);
    });

    it('should return memory threshold for memory-related metrics', () => {
      const threshold = service.resolveThreshold('Available Memory Bytes', 80);
      expect(threshold).toBe(80);
    });

    it('should return DTU threshold for DTU metrics', () => {
      const threshold = service.resolveThreshold('dtu_consumption_percent', 15);
      expect(threshold).toBe(15);
    });

    it('should return storage threshold for storage metrics', () => {
      const threshold = service.resolveThreshold('UsedCapacity', 10);
      expect(threshold).toBe(10);
    });

    it('should return storage threshold for capacity metrics', () => {
      const threshold = service.resolveThreshold('storage_percent', 10);
      expect(threshold).toBe(10);
    });

    it('should return registry threshold for unknown metrics', () => {
      const threshold = service.resolveThreshold('SomeCustomMetric', 25);
      expect(threshold).toBe(25);
    });

    it('should return global default when no registry threshold', () => {
      const threshold = service.resolveThreshold('SomeCustomMetric');
      expect(threshold).toBe(10);
    });
  });

  describe('computeDailySummary', () => {
    it('should compute avg, min, max, p95 from data points', () => {
      const summary = service.computeDailySummary(
        mockTrackedResource,
        mockMetricDef,
        mockDataPoints,
        '2026-03-25',
        10,
      );

      // avg of [5, 8, 3] = 5.333
      expect(summary.avgUtilization).toBeCloseTo(5.333, 2);
      expect(summary.maxUtilization).toBe(8);
      expect(summary.minUtilization).toBe(3);
      expect(summary.sampleCount).toBe(3);
      expect(summary.metricName).toBe('Percentage CPU');
      expect(summary.trackedResourceId).toBe('tr-uuid-1');
      expect(summary.timeGrain).toBe(TimeGrain.PT1H);
    });

    it('should flag as underused when avg is below threshold', () => {
      const summary = service.computeDailySummary(
        mockTrackedResource,
        mockMetricDef,
        mockDataPoints,
        '2026-03-25',
        10, // threshold 10%, avg is 5.33 → underused
      );

      expect(summary.isUnderused).toBe(true);
      expect(summary.underuseThreshold).toBe(10);
    });

    it('should not flag as underused when avg is above threshold', () => {
      const highPoints = mockDataPoints.map((dp) => ({
        ...dp,
        average: 50.0,
      }));

      const summary = service.computeDailySummary(
        mockTrackedResource,
        mockMetricDef,
        highPoints,
        '2026-03-25',
        10,
      );

      expect(summary.isUnderused).toBe(false);
    });

    it('should handle data points with null averages', () => {
      const nullPoints = [
        { ...mockDataPoints[0], average: null },
        { ...mockDataPoints[1], average: 20.0 },
        { ...mockDataPoints[2], average: null },
      ];

      const summary = service.computeDailySummary(
        mockTrackedResource,
        mockMetricDef,
        nullPoints,
        '2026-03-25',
        10,
      );

      // Only one valid point: 20.0
      expect(summary.avgUtilization).toBe(20);
      expect(summary.sampleCount).toBe(1);
    });

    it('should handle all null averages', () => {
      const allNullPoints = mockDataPoints.map((dp) => ({
        ...dp,
        average: null,
      }));

      const summary = service.computeDailySummary(
        mockTrackedResource,
        mockMetricDef,
        allNullPoints,
        '2026-03-25',
        10,
      );

      expect(summary.avgUtilization).toBe(0);
      expect(summary.sampleCount).toBe(0);
      expect(summary.isUnderused).toBe(false);
    });

    it('should compute p95 correctly', () => {
      const manyPoints = Array.from({ length: 24 }, (_, i) => ({
        ...mockDataPoints[0],
        id: `dp-${i}`,
        average: i + 1,
      }));

      const summary = service.computeDailySummary(
        mockTrackedResource,
        mockMetricDef,
        manyPoints,
        '2026-03-25',
        10,
      );

      expect(summary.p95Utilization).toBeDefined();
      expect(summary.p95Utilization!).toBeGreaterThan(22);
    });
  });

  describe('computeSummaries', () => {
    it('should compute summaries for tracked resources', async () => {
      metricDefRepo.find.mockResolvedValue([mockMetricDef]);
      dataPointRepo.find.mockResolvedValue(mockDataPoints);
      summaryRepo.findOne.mockResolvedValue(null);
      summaryRepo.create.mockImplementation(
        (data) => ({ id: 'sum-1', ...data }) as UtilizationSummaryEntity,
      );
      summaryRepo.save.mockImplementation(
        (entity) => Promise.resolve(entity) as Promise<UtilizationSummaryEntity>,
      );

      const result = await service.computeSummaries({
        startDate: new Date('2026-03-25'),
        endDate: new Date('2026-03-26'),
      });

      expect(result.summariesComputed).toBeGreaterThan(0);
      expect(result.summariesPersisted).toBeGreaterThan(0);
      expect(result.errors.length).toBe(0);
      expect(result.durationMs).toBeGreaterThanOrEqual(0);
    });

    it('should update existing summaries', async () => {
      const existingSummary: UtilizationSummaryEntity = {
        id: 'sum-existing',
        trackedResource: mockTrackedResource,
        trackedResourceId: 'tr-uuid-1',
        summaryDate: new Date('2026-03-25'),
        metricName: 'Percentage CPU',
        avgUtilization: 10,
        maxUtilization: 20,
        minUtilization: 5,
        p95Utilization: 18,
        sampleCount: 10,
        timeGrain: TimeGrain.PT1H,
        isUnderused: false,
        underuseThreshold: 10,
        createdAt: new Date(),
        updatedAt: new Date(),
      };

      metricDefRepo.find.mockResolvedValue([mockMetricDef]);
      dataPointRepo.find.mockResolvedValue(mockDataPoints);
      summaryRepo.findOne.mockResolvedValue(existingSummary);
      summaryRepo.save.mockResolvedValue(existingSummary);

      const result = await service.computeSummaries({
        startDate: new Date('2026-03-25'),
        endDate: new Date('2026-03-26'),
      });

      expect(result.summariesPersisted).toBeGreaterThan(0);
      expect(summaryRepo.save).toHaveBeenCalledWith(
        expect.objectContaining({ id: 'sum-existing' }),
      );
    });

    it('should handle errors gracefully', async () => {
      metricDefRepo.find.mockRejectedValue(new Error('DB error'));

      const result = await service.computeSummaries({
        startDate: new Date('2026-03-25'),
        endDate: new Date('2026-03-26'),
      });

      expect(result.errors.length).toBe(1);
      expect(result.errors[0].phase).toBe('persist');
    });

    it('should skip resources with no utilization metrics', async () => {
      mockQueryBuilder.getMany.mockResolvedValueOnce([
        { ...mockTrackedResource, resourceType: 'Microsoft.Custom/unknown' },
      ]);
      metricDefRepo.find.mockResolvedValue([]);

      const result = await service.computeSummaries({
        startDate: new Date('2026-03-25'),
        endDate: new Date('2026-03-26'),
      });

      expect(result.summariesComputed).toBe(0);
    });

    it('should skip when no data points exist', async () => {
      metricDefRepo.find.mockResolvedValue([mockMetricDef]);
      dataPointRepo.find.mockResolvedValue([]);

      const result = await service.computeSummaries({
        startDate: new Date('2026-03-25'),
        endDate: new Date('2026-03-26'),
      });

      expect(result.summariesComputed).toBe(0);
    });

    it('should filter by resource types when specified', async () => {
      metricDefRepo.find.mockResolvedValue([mockMetricDef]);
      dataPointRepo.find.mockResolvedValue(mockDataPoints);
      summaryRepo.findOne.mockResolvedValue(null);
      summaryRepo.create.mockImplementation(
        (data) => ({ id: 'sum-1', ...data }) as UtilizationSummaryEntity,
      );
      summaryRepo.save.mockImplementation(
        (entity) => Promise.resolve(entity) as Promise<UtilizationSummaryEntity>,
      );

      await service.computeSummaries({
        startDate: new Date('2026-03-25'),
        endDate: new Date('2026-03-26'),
        resourceTypes: ['Microsoft.Compute/virtualMachines'],
      });

      expect(mockQueryBuilder.andWhere).toHaveBeenCalledWith('tr.resource_type IN (:...types)', {
        types: ['Microsoft.Compute/virtualMachines'],
      });
    });

    it('should filter by tracked resource IDs when specified', async () => {
      metricDefRepo.find.mockResolvedValue([mockMetricDef]);
      dataPointRepo.find.mockResolvedValue(mockDataPoints);
      summaryRepo.findOne.mockResolvedValue(null);
      summaryRepo.create.mockImplementation(
        (data) => ({ id: 'sum-1', ...data }) as UtilizationSummaryEntity,
      );
      summaryRepo.save.mockImplementation(
        (entity) => Promise.resolve(entity) as Promise<UtilizationSummaryEntity>,
      );

      await service.computeSummaries({
        startDate: new Date('2026-03-25'),
        endDate: new Date('2026-03-26'),
        trackedResourceIds: ['tr-uuid-1'],
      });

      expect(mockQueryBuilder.andWhere).toHaveBeenCalledWith('tr.id IN (:...ids)', {
        ids: ['tr-uuid-1'],
      });
    });
  });
});
