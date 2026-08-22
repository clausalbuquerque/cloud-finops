import { Test, TestingModule } from '@nestjs/testing';
import { getRepositoryToken } from '@nestjs/typeorm';
import { Repository, DataSource, EntityManager } from 'typeorm';
import { ConsumptionExtractorService } from './consumption-extractor.service';
import { AzureCostClientService } from '@modules/cost';
import {
  SubscriptionEntity,
  ResourceGroupEntity,
  ConsumptionRecordEntity,
} from '@modules/database';
import { CostQueryResult } from '@modules/cost';

describe('ConsumptionExtractorService', () => {
  let service: ConsumptionExtractorService;
  let costClient: jest.Mocked<AzureCostClientService>;
  let subscriptionRepo: jest.Mocked<Repository<SubscriptionEntity>>;
  let resourceGroupRepo: jest.Mocked<Repository<ResourceGroupEntity>>;
  let dataSource: jest.Mocked<DataSource>;

  const mockSubscription: Partial<SubscriptionEntity> = {
    id: 'sub-uuid-1',
    subscriptionId: 'test-subscription-id',
    displayName: 'Test Subscription',
    state: 'Enabled',
  };

  const mockResourceGroup: Partial<ResourceGroupEntity> = {
    id: 'rg-uuid-1',
    name: 'rg-test',
    subscriptionId: 'sub-uuid-1',
  };

  const mockCostQueryResult: CostQueryResult = {
    records: [
      {
        cost: 150.5,
        usageDate: 20240115,
        currency: 'USD',
        groupings: { ResourceGroup: 'rg-test', MeterCategory: 'Virtual Machines' },
      },
      {
        cost: 75.25,
        usageDate: 20240115,
        currency: 'USD',
        groupings: { ResourceGroup: 'rg-test', MeterCategory: 'Storage' },
      },
      {
        cost: 200.0,
        usageDate: 20240116,
        currency: 'USD',
        groupings: { ResourceGroup: 'rg-prod', MeterCategory: 'Virtual Machines' },
      },
    ],
    totalRecords: 3,
    columns: [
      { name: 'Cost', type: 'Number' },
      { name: 'UsageDate', type: 'Number' },
      { name: 'Currency', type: 'String' },
      { name: 'ResourceGroup', type: 'String' },
      { name: 'MeterCategory', type: 'String' },
    ],
  };

  // Mock transaction manager
  let mockTransactionManager: jest.Mocked<EntityManager>;
  let mockTransactionRepo: {
    findOne: jest.Mock;
    create: jest.Mock;
    save: jest.Mock;
  };

  beforeEach(async () => {
    mockTransactionRepo = {
      findOne: jest.fn().mockResolvedValue(null),
      create: jest.fn().mockImplementation((data) => ({ id: 'new-record-uuid', ...data })),
      save: jest.fn().mockImplementation((entity) => Promise.resolve(entity)),
    };

    mockTransactionManager = {
      getRepository: jest.fn().mockReturnValue(mockTransactionRepo),
    } as unknown as jest.Mocked<EntityManager>;

    const module: TestingModule = await Test.createTestingModule({
      providers: [
        ConsumptionExtractorService,
        {
          provide: AzureCostClientService,
          useValue: {
            queryCostData: jest.fn().mockResolvedValue(mockCostQueryResult),
          },
        },
        {
          provide: DataSource,
          useValue: {
            transaction: jest
              .fn()
              .mockImplementation((cb: (manager: EntityManager) => Promise<void>) =>
                cb(mockTransactionManager),
              ),
          },
        },
        {
          provide: getRepositoryToken(SubscriptionEntity),
          useValue: {
            findOne: jest.fn().mockResolvedValue(mockSubscription),
            create: jest.fn().mockImplementation((data) => ({ id: 'new-sub-uuid', ...data })),
            save: jest.fn().mockImplementation((entity) => Promise.resolve(entity)),
          },
        },
        {
          provide: getRepositoryToken(ResourceGroupEntity),
          useValue: {
            findOne: jest.fn().mockResolvedValue(mockResourceGroup),
            create: jest.fn().mockImplementation((data) => ({ id: 'new-rg-uuid', ...data })),
            save: jest.fn().mockImplementation((entity) => Promise.resolve(entity)),
          },
        },
      ],
    }).compile();

    service = module.get<ConsumptionExtractorService>(ConsumptionExtractorService);
    costClient = module.get(AzureCostClientService);
    subscriptionRepo = module.get(getRepositoryToken(SubscriptionEntity));
    resourceGroupRepo = module.get(getRepositoryToken(ResourceGroupEntity));
    dataSource = module.get(DataSource);
  });

  describe('instantiation', () => {
    it('should be defined', () => {
      expect(service).toBeDefined();
    });
  });

  describe('parseUsageDate()', () => {
    it('should parse YYYYMMDD number to Date', () => {
      const date = service.parseUsageDate(20240115);
      expect(date.getUTCFullYear()).toBe(2024);
      expect(date.getUTCMonth()).toBe(0); // January = 0
      expect(date.getUTCDate()).toBe(15);
    });

    it('should parse different dates correctly', () => {
      const date = service.parseUsageDate(20231201);
      expect(date.getUTCFullYear()).toBe(2023);
      expect(date.getUTCMonth()).toBe(11); // December = 11
      expect(date.getUTCDate()).toBe(1);
    });

    it('should return current date for null usage date', () => {
      const before = Date.now();
      const date = service.parseUsageDate(null);
      const after = Date.now();
      expect(date.getTime()).toBeGreaterThanOrEqual(before);
      expect(date.getTime()).toBeLessThanOrEqual(after);
    });

    it('should return current date for zero usage date', () => {
      const before = Date.now();
      const date = service.parseUsageDate(0);
      const after = Date.now();
      expect(date.getTime()).toBeGreaterThanOrEqual(before);
      expect(date.getTime()).toBeLessThanOrEqual(after);
    });
  });

  describe('mapCostRecords()', () => {
    it('should map CostRecord array to MappedConsumptionRecord array', () => {
      const mapped = service.mapCostRecords(mockCostQueryResult.records, 'test-subscription-id');

      expect(mapped).toHaveLength(3);
      expect(mapped[0].subscriptionId).toBe('test-subscription-id');
      expect(mapped[0].resourceGroupName).toBe('rg-test');
      expect(mapped[0].cost).toBe(150.5);
      expect(mapped[0].currency).toBe('USD');
      expect(mapped[0].meterCategory).toBe('Virtual Machines');
    });

    it('should use "unknown" for missing resource group', () => {
      const records = [
        {
          cost: 10,
          usageDate: 20240115,
          currency: 'USD',
          groupings: {},
        },
      ];

      const mapped = service.mapCostRecords(records, 'sub-1');
      expect(mapped[0].resourceGroupName).toBe('unknown');
    });

    it('should preserve all grouping dimensions', () => {
      const records = [
        {
          cost: 100,
          usageDate: 20240115,
          currency: 'EUR',
          groupings: {
            ResourceGroup: 'rg-eu',
            MeterCategory: 'Networking',
            ServiceName: 'VPN Gateway',
            ResourceType: 'Microsoft.Network/vpnGateways',
          },
        },
      ];

      const mapped = service.mapCostRecords(records, 'sub-eu');
      expect(mapped[0].meterCategory).toBe('Networking');
      expect(mapped[0].serviceName).toBe('VPN Gateway');
      expect(mapped[0].resourceType).toBe('Microsoft.Network/vpnGateways');
    });

    it('should parse usage date from number format', () => {
      const records = [
        {
          cost: 50,
          usageDate: 20240301,
          currency: 'USD',
          groupings: { ResourceGroup: 'rg-1' },
        },
      ];

      const mapped = service.mapCostRecords(records, 'sub-1');
      expect(mapped[0].usageDate.getUTCFullYear()).toBe(2024);
      expect(mapped[0].usageDate.getUTCMonth()).toBe(2); // March
      expect(mapped[0].usageDate.getUTCDate()).toBe(1);
    });
  });

  describe('chunkDateRange()', () => {
    it('should return a single chunk for ranges <= 31 days', () => {
      const start = new Date('2024-01-01');
      const end = new Date('2024-01-31');
      const chunks = service.chunkDateRange(start, end);

      expect(chunks).toHaveLength(1);
      expect(chunks[0].start).toEqual(start);
      expect(chunks[0].end).toEqual(end);
    });

    it('should split ranges > 31 days into multiple chunks', () => {
      const start = new Date('2024-01-01');
      const end = new Date('2024-03-31');
      const chunks = service.chunkDateRange(start, end);

      expect(chunks.length).toBeGreaterThan(1);
      // First chunk should span 31 days
      expect(chunks[0].start).toEqual(new Date('2024-01-01'));
    });

    it('should handle same-day range', () => {
      const date = new Date('2024-01-15');
      const chunks = service.chunkDateRange(date, date);

      expect(chunks).toHaveLength(1);
      expect(chunks[0].start).toEqual(date);
      expect(chunks[0].end).toEqual(date);
    });

    it('should ensure last chunk end does not exceed the original end date', () => {
      const start = new Date('2024-01-01');
      const end = new Date('2024-02-15');
      const chunks = service.chunkDateRange(start, end);

      const lastChunk = chunks[chunks.length - 1];
      expect(lastChunk.end.getTime()).toBeLessThanOrEqual(end.getTime());
    });
  });

  describe('extract()', () => {
    it('should fetch cost data and persist records', async () => {
      // Set up second resource group mock
      resourceGroupRepo.findOne
        .mockResolvedValueOnce(mockResourceGroup as ResourceGroupEntity)
        .mockResolvedValueOnce({
          ...mockResourceGroup,
          id: 'rg-uuid-2',
          name: 'rg-prod',
        } as ResourceGroupEntity);

      const result = await service.extract({
        startDate: new Date('2024-01-15'),
        endDate: new Date('2024-01-16'),
        subscriptionId: 'test-subscription-id',
      });

      expect(result.recordsFetched).toBe(3);
      expect(result.recordsPersisted).toBe(3);
      expect(result.batchesProcessed).toBe(1);
      expect(result.errors).toHaveLength(0);
      expect(result.durationMs).toBeGreaterThanOrEqual(0);
    });

    it('should call Azure Cost Client with correct parameters', async () => {
      await service.extract({
        startDate: new Date('2024-01-01'),
        endDate: new Date('2024-01-31'),
        subscriptionId: 'test-sub-id',
      });

      expect(costClient.queryCostData).toHaveBeenCalledWith({
        startDate: expect.any(Date),
        endDate: expect.any(Date),
        subscriptionId: 'test-sub-id',
        granularity: 'Daily',
        groupBy: ['ResourceGroup', 'MeterCategory'],
      });
    });

    it('should ensure subscription exists before processing', async () => {
      await service.extract({
        startDate: new Date('2024-01-15'),
        endDate: new Date('2024-01-15'),
        subscriptionId: 'test-subscription-id',
      });

      expect(subscriptionRepo.findOne).toHaveBeenCalledWith({
        where: { subscriptionId: 'test-subscription-id' },
      });
    });

    it('should create subscription if not found', async () => {
      subscriptionRepo.findOne.mockResolvedValueOnce(null);
      subscriptionRepo.save.mockResolvedValueOnce({
        id: 'new-sub-uuid',
        subscriptionId: 'new-sub',
        displayName: 'new-sub',
        state: 'Enabled',
      } as SubscriptionEntity);

      await service.extract({
        startDate: new Date('2024-01-15'),
        endDate: new Date('2024-01-15'),
        subscriptionId: 'new-sub',
      });

      expect(subscriptionRepo.create).toHaveBeenCalled();
      expect(subscriptionRepo.save).toHaveBeenCalled();
    });

    it('should handle empty API results gracefully', async () => {
      costClient.queryCostData.mockResolvedValueOnce({
        records: [],
        totalRecords: 0,
        columns: [],
      });

      const result = await service.extract({
        startDate: new Date('2024-01-15'),
        endDate: new Date('2024-01-15'),
        subscriptionId: 'test-subscription-id',
      });

      expect(result.recordsFetched).toBe(0);
      expect(result.recordsPersisted).toBe(0);
      expect(result.batchesProcessed).toBe(0);
    });

    it('should handle API fetch errors and record them', async () => {
      costClient.queryCostData.mockRejectedValueOnce(new Error('API rate limited'));

      const result = await service.extract({
        startDate: new Date('2024-01-15'),
        endDate: new Date('2024-01-15'),
        subscriptionId: 'test-subscription-id',
      });

      expect(result.errors).toHaveLength(1);
      expect(result.errors[0].phase).toBe('fetch');
      expect(result.errors[0].message).toContain('API rate limited');
    });

    it('should handle database persist errors and record them', async () => {
      dataSource.transaction.mockRejectedValueOnce(new Error('DB connection lost'));

      const result = await service.extract({
        startDate: new Date('2024-01-15'),
        endDate: new Date('2024-01-15'),
        subscriptionId: 'test-subscription-id',
      });

      expect(result.errors).toHaveLength(1);
      expect(result.errors[0].phase).toBe('persist');
      expect(result.errors[0].message).toContain('DB connection lost');
    });

    it('should use the provided batch size', async () => {
      // Create a result with 3 records but batch size of 2
      const result = await service.extract({
        startDate: new Date('2024-01-15'),
        endDate: new Date('2024-01-15'),
        subscriptionId: 'test-subscription-id',
        batchSize: 2,
      });

      // Should have processed 2 batches (2 + 1)
      expect(result.batchesProcessed).toBe(2);
    });

    it('should report correct insert counts for new records', async () => {
      // All records are new (findOne returns null by default in mockTransactionRepo)
      const result = await service.extract({
        startDate: new Date('2024-01-15'),
        endDate: new Date('2024-01-15'),
        subscriptionId: 'test-subscription-id',
      });

      expect(result.recordsInserted).toBe(3);
      expect(result.recordsUpdated).toBe(0);
    });

    it('should report correct update counts for existing records', async () => {
      // Make all records appear as existing
      mockTransactionRepo.findOne.mockResolvedValue({
        id: 'existing-uuid',
        effectiveCost: 100,
        billingCurrency: 'USD',
      } as ConsumptionRecordEntity);

      const result = await service.extract({
        startDate: new Date('2024-01-15'),
        endDate: new Date('2024-01-15'),
        subscriptionId: 'test-subscription-id',
      });

      expect(result.recordsUpdated).toBe(3);
      expect(result.recordsInserted).toBe(0);
    });

    it('should use transactions for batch persistence', async () => {
      await service.extract({
        startDate: new Date('2024-01-15'),
        endDate: new Date('2024-01-15'),
        subscriptionId: 'test-subscription-id',
      });

      expect(dataSource.transaction).toHaveBeenCalled();
    });

    it('should chunk large date ranges', async () => {
      await service.extract({
        startDate: new Date('2024-01-01'),
        endDate: new Date('2024-06-30'),
        subscriptionId: 'test-subscription-id',
      });

      // ~180 days / 31 days per chunk = ~6 chunks
      const callCount = costClient.queryCostData.mock.calls.length;
      expect(callCount).toBeGreaterThan(1);
    });

    it('should ensure resource groups are created per unique name', async () => {
      // Two distinct RG names in the mock data: rg-test and rg-prod
      resourceGroupRepo.findOne
        .mockResolvedValueOnce(null) // rg-test not found
        .mockResolvedValueOnce(null); // rg-prod not found

      resourceGroupRepo.save
        .mockResolvedValueOnce({
          id: 'new-rg-1',
          name: 'rg-test',
          subscriptionId: 'sub-uuid-1',
        } as ResourceGroupEntity)
        .mockResolvedValueOnce({
          id: 'new-rg-2',
          name: 'rg-prod',
          subscriptionId: 'sub-uuid-1',
        } as ResourceGroupEntity);

      await service.extract({
        startDate: new Date('2024-01-15'),
        endDate: new Date('2024-01-16'),
        subscriptionId: 'test-subscription-id',
      });

      expect(resourceGroupRepo.create).toHaveBeenCalledTimes(2);
      expect(resourceGroupRepo.save).toHaveBeenCalledTimes(2);
    });

    it('should include duration in the result', async () => {
      const result = await service.extract({
        startDate: new Date('2024-01-15'),
        endDate: new Date('2024-01-15'),
        subscriptionId: 'test-subscription-id',
      });

      expect(typeof result.durationMs).toBe('number');
      expect(result.durationMs).toBeGreaterThanOrEqual(0);
    });
  });
});
