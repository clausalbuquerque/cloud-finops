import { Test, TestingModule } from '@nestjs/testing';
import { ConfigService } from '@nestjs/config';
import { AzureResourceClientService } from './azure-resource-client.service';

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

const mockListIterator = jest.fn();
const mockListByResourceGroupIterator = jest.fn();

jest.mock('@azure/arm-resources', () => ({
  ResourceManagementClient: jest.fn().mockImplementation(() => ({
    resources: {
      list: jest.fn().mockImplementation(() => mockListIterator()),
      listByResourceGroup: jest.fn().mockImplementation(() => mockListByResourceGroupIterator()),
    },
  })),
}));

describe('AzureResourceClientService', () => {
  let service: AzureResourceClientService;

  const mockConfigValues: Record<string, string> = {
    'azure.tenantId': 'test-tenant-id',
    'azure.clientId': 'test-client-id',
    'azure.clientSecret': 'test-client-secret',
    'azure.subscriptionId': 'test-subscription-id',
  };

  const mockResources = [
    {
      id: '/subscriptions/sub-1/resourceGroups/rg-test/providers/Microsoft.Compute/virtualMachines/vm-1',
      name: 'vm-1',
      type: 'Microsoft.Compute/virtualMachines',
      location: 'eastus',
      sku: { name: 'Standard_D2s_v3', tier: 'Standard', capacity: undefined },
      tags: { environment: 'dev' },
    },
    {
      id: '/subscriptions/sub-1/resourceGroups/rg-test/providers/Microsoft.Web/sites/app-1',
      name: 'app-1',
      type: 'Microsoft.Web/sites',
      location: 'westeurope',
      sku: undefined,
      tags: {},
    },
    {
      id: '/subscriptions/sub-1/resourceGroups/rg-prod/providers/Microsoft.Sql/servers/sql-1/databases/db-1',
      name: 'db-1',
      type: 'Microsoft.Sql/servers/databases',
      location: 'eastus',
      sku: { name: 'S1', tier: 'Standard', capacity: 20 },
      tags: undefined,
    },
  ];

  async function* createAsyncIterator<T>(items: T[]): AsyncIterableIterator<T> {
    for (const item of items) {
      yield item;
    }
  }

  beforeEach(async () => {
    jest.clearAllMocks();
    mockListIterator.mockReturnValue(createAsyncIterator(mockResources));
    mockListByResourceGroupIterator.mockReturnValue(createAsyncIterator(mockResources.slice(0, 2)));

    const module: TestingModule = await Test.createTestingModule({
      providers: [
        AzureResourceClientService,
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

    service = module.get<AzureResourceClientService>(AzureResourceClientService);
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

  describe('discoverResources()', () => {
    it('should list all resources in the default subscription', async () => {
      const resources = await service.discoverResources();

      expect(resources).toHaveLength(3);
      expect(resources[0].name).toBe('vm-1');
      expect(resources[0].type).toBe('Microsoft.Compute/virtualMachines');
      expect(resources[0].location).toBe('eastus');
    });

    it('should extract resource group from resource ID', async () => {
      const resources = await service.discoverResources();

      expect(resources[0].resourceGroup).toBe('rg-test');
      expect(resources[2].resourceGroup).toBe('rg-prod');
    });

    it('should map SKU information when available', async () => {
      const resources = await service.discoverResources();

      expect(resources[0].sku).toBeDefined();
      expect(resources[0].sku?.name).toBe('Standard_D2s_v3');
      expect(resources[0].sku?.tier).toBe('Standard');
    });

    it('should handle resources without SKU', async () => {
      const resources = await service.discoverResources();

      expect(resources[1].sku).toBeUndefined();
    });

    it('should map tags when present', async () => {
      const resources = await service.discoverResources();

      expect(resources[0].tags).toEqual({ environment: 'dev' });
    });

    it('should filter by resource group', async () => {
      const resources = await service.discoverResources({ resourceGroup: 'rg-test' });

      expect(resources).toHaveLength(2);
    });

    it('should throw when no subscription ID is available', async () => {
      // Create a service with no subscription ID
      const moduleNoSub: TestingModule = await Test.createTestingModule({
        providers: [
          AzureResourceClientService,
          {
            provide: ConfigService,
            useValue: {
              get: jest.fn((_key: string, defaultValue?: string) => defaultValue ?? ''),
            },
          },
        ],
      }).compile();

      const serviceNoSub = moduleNoSub.get<AzureResourceClientService>(AzureResourceClientService);

      await expect(serviceNoSub.discoverResources()).rejects.toThrow('No subscription ID provided');
    });
  });

  describe('mapResource()', () => {
    it('should return null for resources with missing required fields', () => {
      const result = service.mapResource({
        id: undefined,
        name: undefined,
        type: undefined,
      } as never);
      expect(result).toBeNull();
    });

    it('should handle resource ID without resource group pattern', () => {
      const result = service.mapResource({
        id: '/subscriptions/sub-1/providers/Microsoft.Something/thing-1',
        name: 'thing-1',
        type: 'Microsoft.Something/things',
        location: 'eastus',
      } as never);

      expect(result?.resourceGroup).toBe('unknown');
    });
  });

  describe('listResourceTypes()', () => {
    it('should return distinct resource types sorted', async () => {
      const types = await service.listResourceTypes();

      expect(types).toHaveLength(3);
      expect(types).toContain('Microsoft.Compute/virtualMachines');
      expect(types).toContain('Microsoft.Web/sites');
      expect(types).toContain('Microsoft.Sql/servers/databases');
      // Should be sorted
      expect(types).toEqual([...types].sort());
    });
  });
});
