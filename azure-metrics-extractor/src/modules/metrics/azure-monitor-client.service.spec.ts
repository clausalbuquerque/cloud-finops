import { Test, TestingModule } from '@nestjs/testing';
import { ConfigService } from '@nestjs/config';
import { AzureMonitorClientService } from './azure-monitor-client.service';

// Mock Azure SDK modules
jest.mock('@azure/identity', () => ({
  ClientSecretCredential: jest.fn().mockImplementation(() => ({
    getToken: jest
      .fn()
      .mockResolvedValue({ token: 'mock-token', expiresOnTimestamp: Date.now() + 3600000 }),
  })),
  DefaultAzureCredential: jest.fn().mockImplementation(() => ({
    getToken: jest
      .fn()
      .mockResolvedValue({ token: 'mock-token', expiresOnTimestamp: Date.now() + 3600000 }),
  })),
}));

const mockMetricsList = jest.fn();
const mockMetricDefinitionsList = jest.fn();

jest.mock('@azure/arm-monitor', () => ({
  MonitorClient: jest.fn().mockImplementation(() => ({
    metrics: { list: mockMetricsList },
    metricDefinitions: { list: mockMetricDefinitionsList },
  })),
}));

describe('AzureMonitorClientService', () => {
  let service: AzureMonitorClientService;

  const mockConfigValues: Record<string, string> = {
    'azure.tenantId': 'test-tenant-id',
    'azure.clientId': 'test-client-id',
    'azure.clientSecret': 'test-client-secret',
    'azure.subscriptionId': 'test-subscription-id',
  };

  const mockMetricResponse = {
    value: [
      {
        name: { value: 'Percentage CPU', localizedValue: 'Percentage CPU' },
        unit: 'Percent',
        timeseries: [
          {
            data: [
              {
                timeStamp: new Date('2024-01-15T10:00:00Z'),
                average: 12.5,
                minimum: 2.1,
                maximum: 45.6,
                total: 750,
                count: 60,
              },
              {
                timeStamp: new Date('2024-01-15T11:00:00Z'),
                average: 15.3,
                minimum: 3.2,
                maximum: 52.1,
                total: 918,
                count: 60,
              },
              {
                timeStamp: new Date('2024-01-15T12:00:00Z'),
                average: 8.7,
                minimum: 1.0,
                maximum: 30.4,
                total: 522,
                count: 60,
              },
            ],
          },
        ],
      },
      {
        name: { value: 'Available Memory Bytes', localizedValue: 'Available Memory Bytes' },
        unit: 'Bytes',
        timeseries: [
          {
            data: [
              {
                timeStamp: new Date('2024-01-15T10:00:00Z'),
                average: 6442450944,
                minimum: 5368709120,
                maximum: 7516192768,
                total: undefined,
                count: undefined,
              },
              {
                timeStamp: new Date('2024-01-15T11:00:00Z'),
                average: 6174015488,
                minimum: 5100273664,
                maximum: 7247757312,
                total: undefined,
                count: undefined,
              },
            ],
          },
        ],
      },
    ],
  };

  const mockMetricDefinitionsResponse = [
    {
      name: { value: 'Percentage CPU', localizedValue: 'Percentage CPU' },
      namespace: 'Microsoft.Compute/virtualMachines',
      unit: 'Percent',
      primaryAggregationType: 'Average',
      supportedAggregationTypes: ['Average', 'Minimum', 'Maximum', 'Total', 'Count'],
      metricAvailabilities: [
        { timeGrain: 'PT1M' },
        { timeGrain: 'PT5M' },
        { timeGrain: 'PT15M' },
        { timeGrain: 'PT30M' },
        { timeGrain: 'PT1H' },
        { timeGrain: 'P1D' },
      ],
    },
    {
      name: { value: 'Available Memory Bytes', localizedValue: 'Available Memory Bytes' },
      namespace: 'Microsoft.Compute/virtualMachines',
      unit: 'Bytes',
      primaryAggregationType: 'Average',
      supportedAggregationTypes: ['Average', 'Minimum', 'Maximum'],
      metricAvailabilities: [{ timeGrain: 'PT1M' }, { timeGrain: 'PT1H' }, { timeGrain: 'P1D' }],
    },
  ];

  async function* createAsyncIterator<T>(items: T[]): AsyncIterableIterator<T> {
    for (const item of items) {
      yield item;
    }
  }

  beforeEach(async () => {
    jest.clearAllMocks();
    mockMetricsList.mockResolvedValue(mockMetricResponse);
    mockMetricDefinitionsList.mockReturnValue(createAsyncIterator(mockMetricDefinitionsResponse));

    const module: TestingModule = await Test.createTestingModule({
      providers: [
        AzureMonitorClientService,
        {
          provide: ConfigService,
          useValue: {
            get: jest.fn(
              (key: string, defaultValue?: string) => mockConfigValues[key] ?? defaultValue ?? '',
            ),
          },
        },
      ],
    }).compile();

    service = module.get<AzureMonitorClientService>(AzureMonitorClientService);
  });

  describe('constructor', () => {
    it('should be defined', () => {
      expect(service).toBeDefined();
    });

    it('should use ClientSecretCredential when all credentials are provided', () => {
      const { ClientSecretCredential } = jest.requireMock('@azure/identity');
      expect(ClientSecretCredential).toHaveBeenCalledWith(
        'test-tenant-id',
        'test-client-id',
        'test-client-secret',
      );
    });
  });

  describe('listMetricDefinitions()', () => {
    it('should list metric definitions for a resource', async () => {
      const resourceId =
        '/subscriptions/sub-1/resourceGroups/rg-test/providers/Microsoft.Compute/virtualMachines/vm-1';
      const definitions = await service.listMetricDefinitions(resourceId);

      expect(definitions).toHaveLength(2);
      expect(definitions[0].name).toBe('Percentage CPU');
      expect(definitions[0].displayName).toBe('Percentage CPU');
      expect(definitions[0].unit).toBe('Percent');
      expect(definitions[0].primaryAggregationType).toBe('Average');
    });

    it('should parse supported aggregation types', async () => {
      const resourceId =
        '/subscriptions/sub-1/resourceGroups/rg-test/providers/Microsoft.Compute/virtualMachines/vm-1';
      const definitions = await service.listMetricDefinitions(resourceId);

      expect(definitions[0].supportedAggregationTypes).toEqual([
        'Average',
        'Minimum',
        'Maximum',
        'Total',
        'Count',
      ]);
    });

    it('should parse supported time grains', async () => {
      const resourceId =
        '/subscriptions/sub-1/resourceGroups/rg-test/providers/Microsoft.Compute/virtualMachines/vm-1';
      const definitions = await service.listMetricDefinitions(resourceId);

      expect(definitions[0].supportedTimeGrains).toContain('PT1M');
      expect(definitions[0].supportedTimeGrains).toContain('PT1H');
      expect(definitions[0].supportedTimeGrains).toContain('P1D');
    });
  });

  describe('queryMetrics()', () => {
    const queryParams = {
      resourceId:
        '/subscriptions/sub-1/resourceGroups/rg-test/providers/Microsoft.Compute/virtualMachines/vm-1',
      metricNames: ['Percentage CPU', 'Available Memory Bytes'],
      startTime: new Date('2024-01-15T00:00:00Z'),
      endTime: new Date('2024-01-15T23:59:59Z'),
      timeGrain: 'PT1H',
      aggregations: ['Average', 'Minimum', 'Maximum'],
    };

    it('should query metrics and return time-series data', async () => {
      const result = await service.queryMetrics(queryParams);

      expect(result.timeSeries).toHaveLength(2);
      expect(result.totalDataPoints).toBe(5); // 3 + 2
    });

    it('should correctly parse CPU metric data points', async () => {
      const result = await service.queryMetrics(queryParams);

      const cpuSeries = result.timeSeries.find((ts) => ts.metricName === 'Percentage CPU');
      expect(cpuSeries).toBeDefined();
      expect(cpuSeries?.dataPoints).toHaveLength(3);
      expect(cpuSeries?.dataPoints[0].average).toBe(12.5);
      expect(cpuSeries?.dataPoints[0].minimum).toBe(2.1);
      expect(cpuSeries?.dataPoints[0].maximum).toBe(45.6);
      expect(cpuSeries?.unit).toBe('Percent');
    });

    it('should correctly parse memory metric data points', async () => {
      const result = await service.queryMetrics(queryParams);

      const memorySeries = result.timeSeries.find(
        (ts) => ts.metricName === 'Available Memory Bytes',
      );
      expect(memorySeries).toBeDefined();
      expect(memorySeries?.dataPoints).toHaveLength(2);
      expect(memorySeries?.unit).toBe('Bytes');
    });

    it('should include resource ID and time grain in the result', async () => {
      const result = await service.queryMetrics(queryParams);

      expect(result.timeSeries[0].resourceId).toContain('vm-1');
      expect(result.timeSeries[0].timeGrain).toBe('PT1H');
    });

    it('should call the Azure Monitor API with correct parameters', async () => {
      await service.queryMetrics(queryParams);

      expect(mockMetricsList).toHaveBeenCalledWith(
        queryParams.resourceId,
        expect.objectContaining({
          metricnames: 'Percentage CPU,Available Memory Bytes',
          interval: 'PT1H',
          aggregation: 'Average,Minimum,Maximum',
        }),
      );
    });

    it('should use default time grain when not specified', async () => {
      await service.queryMetrics({
        ...queryParams,
        timeGrain: undefined,
      });

      expect(mockMetricsList).toHaveBeenCalledWith(
        queryParams.resourceId,
        expect.objectContaining({
          interval: 'PT1H', // Default
        }),
      );
    });

    it('should use default aggregations when not specified', async () => {
      await service.queryMetrics({
        ...queryParams,
        aggregations: undefined,
      });

      expect(mockMetricsList).toHaveBeenCalledWith(
        queryParams.resourceId,
        expect.objectContaining({
          aggregation: 'Average,Minimum,Maximum,Total,Count',
        }),
      );
    });

    it('should retry on 429 rate-limit errors', async () => {
      mockMetricsList
        .mockRejectedValueOnce({ statusCode: 429, message: 'Too many requests' })
        .mockResolvedValueOnce(mockMetricResponse);

      // Mock sleep to avoid waiting
      jest.spyOn(service as never, 'sleep').mockResolvedValue(undefined as never);

      const result = await service.queryMetrics(queryParams);
      expect(result.timeSeries).toHaveLength(2);
      expect(mockMetricsList).toHaveBeenCalledTimes(2);
    });

    it('should retry on 500 server errors', async () => {
      mockMetricsList
        .mockRejectedValueOnce({ statusCode: 500, message: 'Internal server error' })
        .mockResolvedValueOnce(mockMetricResponse);

      jest.spyOn(service as never, 'sleep').mockResolvedValue(undefined as never);

      const result = await service.queryMetrics(queryParams);
      expect(result.timeSeries).toHaveLength(2);
      expect(mockMetricsList).toHaveBeenCalledTimes(2);
    });

    it('should not retry on 401 authentication errors', async () => {
      mockMetricsList.mockRejectedValue({ statusCode: 401, message: 'Unauthorized' });

      await expect(service.queryMetrics(queryParams)).rejects.toEqual(
        expect.objectContaining({ statusCode: 401 }),
      );
      expect(mockMetricsList).toHaveBeenCalledTimes(1);
    });

    it('should not retry on 400 bad request errors', async () => {
      mockMetricsList.mockRejectedValue({ statusCode: 400, message: 'Bad request' });

      await expect(service.queryMetrics(queryParams)).rejects.toEqual(
        expect.objectContaining({ statusCode: 400 }),
      );
      expect(mockMetricsList).toHaveBeenCalledTimes(1);
    });
  });

  describe('queryMetricsBatch()', () => {
    const batchParams = {
      subscriptionId: 'test-subscription-id',
      resourceType: 'Microsoft.Compute/virtualMachines',
      resourceIds: [
        '/subscriptions/sub-1/resourceGroups/rg-test/providers/Microsoft.Compute/virtualMachines/vm-1',
        '/subscriptions/sub-1/resourceGroups/rg-test/providers/Microsoft.Compute/virtualMachines/vm-2',
      ],
      metricNames: ['Percentage CPU'],
      startTime: new Date('2024-01-15T00:00:00Z'),
      endTime: new Date('2024-01-15T23:59:59Z'),
      timeGrain: 'PT1H',
    };

    it('should query metrics for multiple resources', async () => {
      const result = await service.queryMetricsBatch(batchParams);

      // Each resource returns 2 metric series (CPU + Memory from mock)
      expect(result.timeSeries.length).toBeGreaterThanOrEqual(2);
      expect(result.totalDataPoints).toBeGreaterThan(0);
    });

    it('should handle individual resource query failures gracefully', async () => {
      mockMetricsList
        .mockResolvedValueOnce(mockMetricResponse)
        .mockRejectedValueOnce(new Error('Resource not found'));

      const result = await service.queryMetricsBatch(batchParams);

      // Should still have results from the first resource
      expect(result.timeSeries.length).toBeGreaterThan(0);
    });

    it('should handle all resource queries failing', async () => {
      mockMetricsList.mockRejectedValue(new Error('All resources failed'));

      const result = await service.queryMetricsBatch(batchParams);

      expect(result.timeSeries).toHaveLength(0);
      expect(result.totalDataPoints).toBe(0);
    });
  });

  describe('parseMetricResponse()', () => {
    it('should handle empty response', () => {
      const result = service.parseMetricResponse('resource-1', { value: [] }, 'PT1H');

      expect(result.timeSeries).toHaveLength(0);
      expect(result.totalDataPoints).toBe(0);
    });

    it('should handle missing timeseries data', () => {
      const result = service.parseMetricResponse(
        'resource-1',
        {
          value: [{ name: { value: 'Percentage CPU' }, unit: 'Percent', timeseries: [] }],
        },
        'PT1H',
      );

      expect(result.timeSeries).toHaveLength(0);
      expect(result.totalDataPoints).toBe(0);
    });

    it('should handle undefined values in response', () => {
      const result = service.parseMetricResponse('resource-1', { value: undefined }, 'PT1H');

      expect(result.timeSeries).toHaveLength(0);
      expect(result.totalDataPoints).toBe(0);
    });
  });
});
