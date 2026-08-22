import { Test, TestingModule } from '@nestjs/testing';
import { ConfigService } from '@nestjs/config';
import { AzureCostClientService } from './azure-cost-client.service';

// Mock the Azure SDK modules
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

const mockUsage = jest.fn();
jest.mock('@azure/arm-costmanagement', () => ({
  CostManagementClient: jest.fn().mockImplementation(() => ({
    query: { usage: mockUsage },
  })),
  KnownExportType: { ActualCost: 'ActualCost' },
  KnownTimeframeType: { Custom: 'Custom' },
  KnownGranularityType: { Daily: 'Daily' },
  KnownQueryColumnType: { Dimension: 'Dimension' },
}));

describe('AzureCostClientService', () => {
  let service: AzureCostClientService;

  const mockConfigValues: Record<string, string> = {
    'azure.tenantId': 'test-tenant-id',
    'azure.clientId': 'test-client-id',
    'azure.clientSecret': 'test-client-secret',
    'azure.subscriptionId': 'test-subscription-id',
  };

  beforeEach(async () => {
    jest.clearAllMocks();
    mockUsage.mockReset();

    const module: TestingModule = await Test.createTestingModule({
      providers: [
        AzureCostClientService,
        {
          provide: ConfigService,
          useValue: {
            get: jest.fn((key: string, defaultValue?: string) => {
              return mockConfigValues[key] ?? defaultValue ?? '';
            }),
          },
        },
      ],
    }).compile();

    service = module.get<AzureCostClientService>(AzureCostClientService);
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

    it('should use DefaultAzureCredential when credentials are incomplete', async () => {
      jest.clearAllMocks();

      const incompleteConfig: Record<string, string> = {
        'azure.tenantId': '',
        'azure.clientId': '',
        'azure.clientSecret': '',
        'azure.subscriptionId': 'test-subscription-id',
      };

      const module: TestingModule = await Test.createTestingModule({
        providers: [
          AzureCostClientService,
          {
            provide: ConfigService,
            useValue: {
              get: jest.fn((key: string, defaultValue?: string) => {
                return incompleteConfig[key] ?? defaultValue ?? '';
              }),
            },
          },
        ],
      }).compile();

      module.get<AzureCostClientService>(AzureCostClientService);
      const { DefaultAzureCredential } = jest.requireMock('@azure/identity');
      expect(DefaultAzureCredential).toHaveBeenCalled();
    });
  });

  describe('queryCostData', () => {
    const mockQueryResult = {
      columns: [
        { name: 'Cost', type: 'Number' },
        { name: 'UsageDate', type: 'Number' },
        { name: 'Currency', type: 'String' },
      ],
      rows: [
        [150.5, 20260301, 'USD'],
        [200.75, 20260302, 'USD'],
        [175.25, 20260303, 'USD'],
      ],
    };

    it('should query cost data and parse results', async () => {
      mockUsage.mockResolvedValue(mockQueryResult);

      const result = await service.queryCostData({
        startDate: new Date('2026-03-01'),
        endDate: new Date('2026-03-31'),
      });

      expect(result.totalRecords).toBe(3);
      expect(result.records[0]).toEqual({
        cost: 150.5,
        usageDate: 20260301,
        currency: 'USD',
        groupings: {},
      });
      expect(result.records[1]).toEqual({
        cost: 200.75,
        usageDate: 20260302,
        currency: 'USD',
        groupings: {},
      });
      expect(result.columns).toEqual([
        { name: 'Cost', type: 'Number' },
        { name: 'UsageDate', type: 'Number' },
        { name: 'Currency', type: 'String' },
      ]);
    });

    it('should use the default subscription when none provided', async () => {
      mockUsage.mockResolvedValue(mockQueryResult);

      await service.queryCostData({
        startDate: new Date('2026-03-01'),
        endDate: new Date('2026-03-31'),
      });

      expect(mockUsage).toHaveBeenCalledWith(
        '/subscriptions/test-subscription-id',
        expect.objectContaining({
          type: 'ActualCost',
          timeframe: 'Custom',
        }),
      );
    });

    it('should use a provided subscription ID override', async () => {
      mockUsage.mockResolvedValue(mockQueryResult);

      await service.queryCostData({
        startDate: new Date('2026-03-01'),
        endDate: new Date('2026-03-31'),
        subscriptionId: 'custom-subscription',
      });

      expect(mockUsage).toHaveBeenCalledWith(
        '/subscriptions/custom-subscription',
        expect.anything(),
      );
    });

    it('should throw error when no subscription ID available', async () => {
      const noSubConfig: Record<string, string> = {
        'azure.tenantId': 'test-tenant-id',
        'azure.clientId': 'test-client-id',
        'azure.clientSecret': 'test-client-secret',
        'azure.subscriptionId': '',
      };

      const module: TestingModule = await Test.createTestingModule({
        providers: [
          AzureCostClientService,
          {
            provide: ConfigService,
            useValue: {
              get: jest.fn((key: string, defaultValue?: string) => {
                return noSubConfig[key] ?? defaultValue ?? '';
              }),
            },
          },
        ],
      }).compile();

      const noSubService = module.get<AzureCostClientService>(AzureCostClientService);

      await expect(
        noSubService.queryCostData({
          startDate: new Date('2026-03-01'),
          endDate: new Date('2026-03-31'),
        }),
      ).rejects.toThrow('No subscription ID provided');
    });

    it('should build query definition with daily granularity', async () => {
      mockUsage.mockResolvedValue(mockQueryResult);

      await service.queryCostData({
        startDate: new Date('2026-03-01'),
        endDate: new Date('2026-03-31'),
        granularity: 'Daily',
      });

      expect(mockUsage).toHaveBeenCalledWith(
        expect.any(String),
        expect.objectContaining({
          dataset: expect.objectContaining({
            granularity: 'Daily',
          }),
        }),
      );
    });

    it('should build query definition with groupBy dimensions', async () => {
      const groupedResult = {
        columns: [
          { name: 'Cost', type: 'Number' },
          { name: 'UsageDate', type: 'Number' },
          { name: 'ResourceGroup', type: 'String' },
          { name: 'Currency', type: 'String' },
        ],
        rows: [
          [100.0, 20260301, 'rg-prod', 'USD'],
          [50.5, 20260301, 'rg-dev', 'USD'],
        ],
      };
      mockUsage.mockResolvedValue(groupedResult);

      const result = await service.queryCostData({
        startDate: new Date('2026-03-01'),
        endDate: new Date('2026-03-31'),
        groupBy: ['ResourceGroup'],
      });

      expect(mockUsage).toHaveBeenCalledWith(
        expect.any(String),
        expect.objectContaining({
          dataset: expect.objectContaining({
            grouping: [{ type: 'Dimension', name: 'ResourceGroup' }],
          }),
        }),
      );
      expect(result.records[0].groupings).toEqual({ ResourceGroup: 'rg-prod' });
      expect(result.records[1].groupings).toEqual({ ResourceGroup: 'rg-dev' });
    });

    it('should handle empty results gracefully', async () => {
      mockUsage.mockResolvedValue({ columns: [], rows: [] });

      const result = await service.queryCostData({
        startDate: new Date('2026-03-01'),
        endDate: new Date('2026-03-31'),
      });

      expect(result.totalRecords).toBe(0);
      expect(result.records).toEqual([]);
    });

    it('should handle undefined columns and rows in response', async () => {
      mockUsage.mockResolvedValue({});

      const result = await service.queryCostData({
        startDate: new Date('2026-03-01'),
        endDate: new Date('2026-03-31'),
      });

      expect(result.totalRecords).toBe(0);
      expect(result.records).toEqual([]);
      expect(result.columns).toEqual([]);
    });
  });

  describe('queryCostByDimension', () => {
    it('should call queryCostData with the correct params', async () => {
      const groupedResult = {
        columns: [
          { name: 'Cost', type: 'Number' },
          { name: 'UsageDate', type: 'Number' },
          { name: 'ServiceName', type: 'String' },
          { name: 'Currency', type: 'String' },
        ],
        rows: [[500.0, 20260301, 'Virtual Machines', 'USD']],
      };
      mockUsage.mockResolvedValue(groupedResult);

      const result = await service.queryCostByDimension(
        new Date('2026-03-01'),
        new Date('2026-03-31'),
        'ServiceName',
      );

      expect(result.records[0].groupings).toEqual({ ServiceName: 'Virtual Machines' });
      expect(mockUsage).toHaveBeenCalledWith(
        expect.any(String),
        expect.objectContaining({
          dataset: expect.objectContaining({
            granularity: 'Daily',
            grouping: [{ type: 'Dimension', name: 'ServiceName' }],
          }),
        }),
      );
    });
  });

  describe('retry logic', () => {
    it('should retry on 429 rate limit errors', async () => {
      const rateLimitError = { statusCode: 429, message: 'Rate limited' };
      const successResult = {
        columns: [{ name: 'Cost', type: 'Number' }],
        rows: [[100.0]],
      };

      mockUsage
        .mockRejectedValueOnce(rateLimitError)
        .mockRejectedValueOnce(rateLimitError)
        .mockResolvedValueOnce(successResult);

      // Override sleep to avoid actual delays in tests
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      jest.spyOn(service as any, 'sleep').mockResolvedValue(undefined);

      const result = await service.queryCostData({
        startDate: new Date('2026-03-01'),
        endDate: new Date('2026-03-31'),
      });

      expect(mockUsage).toHaveBeenCalledTimes(3);
      expect(result.records[0].cost).toBe(100.0);
    });

    it('should retry on 500 server errors', async () => {
      const serverError = { statusCode: 500, message: 'Internal Server Error' };
      const successResult = {
        columns: [{ name: 'Cost', type: 'Number' }],
        rows: [[200.0]],
      };

      mockUsage.mockRejectedValueOnce(serverError).mockResolvedValueOnce(successResult);

      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      jest.spyOn(service as any, 'sleep').mockResolvedValue(undefined);

      const result = await service.queryCostData({
        startDate: new Date('2026-03-01'),
        endDate: new Date('2026-03-31'),
      });

      expect(mockUsage).toHaveBeenCalledTimes(2);
      expect(result.records[0].cost).toBe(200.0);
    });

    it('should throw after max retries exhausted', async () => {
      const rateLimitError = { statusCode: 429, message: 'Rate limited' };
      mockUsage.mockRejectedValue(rateLimitError);

      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      jest.spyOn(service as any, 'sleep').mockResolvedValue(undefined);

      await expect(
        service.queryCostData({
          startDate: new Date('2026-03-01'),
          endDate: new Date('2026-03-31'),
        }),
      ).rejects.toEqual(rateLimitError);

      // 1 initial + 5 retries = 6 calls
      expect(mockUsage).toHaveBeenCalledTimes(6);
    });

    it('should not retry on 401 authentication errors', async () => {
      const authError = { statusCode: 401, message: 'Unauthorized' };
      mockUsage.mockRejectedValue(authError);

      await expect(
        service.queryCostData({
          startDate: new Date('2026-03-01'),
          endDate: new Date('2026-03-31'),
        }),
      ).rejects.toEqual(authError);

      expect(mockUsage).toHaveBeenCalledTimes(1);
    });

    it('should not retry on 400 bad request errors', async () => {
      const badRequestError = { statusCode: 400, message: 'Bad Request' };
      mockUsage.mockRejectedValue(badRequestError);

      await expect(
        service.queryCostData({
          startDate: new Date('2026-03-01'),
          endDate: new Date('2026-03-31'),
        }),
      ).rejects.toEqual(badRequestError);

      expect(mockUsage).toHaveBeenCalledTimes(1);
    });

    it('should not retry on non-HTTP errors', async () => {
      const networkError = new Error('Network failure');
      mockUsage.mockRejectedValue(networkError);

      await expect(
        service.queryCostData({
          startDate: new Date('2026-03-01'),
          endDate: new Date('2026-03-31'),
        }),
      ).rejects.toThrow('Network failure');

      expect(mockUsage).toHaveBeenCalledTimes(1);
    });
  });
});
