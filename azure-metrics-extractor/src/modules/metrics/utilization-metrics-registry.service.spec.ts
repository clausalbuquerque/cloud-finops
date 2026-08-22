import { UtilizationMetricsRegistry } from './utilization-metrics-registry.service';

describe('UtilizationMetricsRegistry', () => {
  let registry: UtilizationMetricsRegistry;

  beforeEach(() => {
    registry = new UtilizationMetricsRegistry();
  });

  describe('initialization', () => {
    it('should be defined', () => {
      expect(registry).toBeDefined();
    });

    it('should pre-load default resource types', () => {
      const types = registry.getRegisteredTypes();
      expect(types.length).toBeGreaterThanOrEqual(6);
    });

    it('should include all required resource types', () => {
      const types = registry.getRegisteredTypes();
      expect(types).toContain('Microsoft.Compute/virtualMachines');
      expect(types).toContain('Microsoft.Web/sites');
      expect(types).toContain('Microsoft.Sql/servers/databases');
      expect(types).toContain('Microsoft.Storage/storageAccounts');
      expect(types).toContain('Microsoft.DocumentDB/databaseAccounts');
      expect(types).toContain('Microsoft.ContainerService/managedClusters');
    });
  });

  describe('Virtual Machines metrics', () => {
    const vmType = 'Microsoft.Compute/virtualMachines';

    it('should have VM metrics registered', () => {
      expect(registry.hasMetrics(vmType)).toBe(true);
    });

    it('should include Percentage CPU as a utilization metric', () => {
      const metrics = registry.getUtilizationMetrics(vmType);
      const cpuMetric = metrics.find((m) => m.metricName === 'Percentage CPU');

      expect(cpuMetric).toBeDefined();
      expect(cpuMetric?.isUtilizationMetric).toBe(true);
      expect(cpuMetric?.underuseThreshold).toBe(10);
      expect(cpuMetric?.aggregationType).toBe('Average');
    });

    it('should include Available Memory Bytes as a utilization metric', () => {
      const metrics = registry.getUtilizationMetrics(vmType);
      const memMetric = metrics.find((m) => m.metricName === 'Available Memory Bytes');

      expect(memMetric).toBeDefined();
      expect(memMetric?.isUtilizationMetric).toBe(true);
      expect(memMetric?.underuseThreshold).toBe(80);
    });

    it('should include network and disk metrics as non-utilization', () => {
      const allMetrics = registry.getMetrics(vmType);
      const networkIn = allMetrics.find((m) => m.metricName === 'Network In Total');
      const diskRead = allMetrics.find((m) => m.metricName === 'Disk Read Bytes');

      expect(networkIn?.isUtilizationMetric).toBe(false);
      expect(diskRead?.isUtilizationMetric).toBe(false);
    });

    it('should have 6 total VM metrics', () => {
      const metrics = registry.getMetrics(vmType);
      expect(metrics).toHaveLength(6);
    });

    it('should return correct metric names', () => {
      const names = registry.getMetricNames(vmType);
      expect(names).toContain('Percentage CPU');
      expect(names).toContain('Available Memory Bytes');
      expect(names).toContain('Network In Total');
      expect(names).toContain('Network Out Total');
      expect(names).toContain('Disk Read Bytes');
      expect(names).toContain('Disk Write Bytes');
    });
  });

  describe('App Services metrics', () => {
    const appType = 'Microsoft.Web/sites';

    it('should have App Service metrics registered', () => {
      expect(registry.hasMetrics(appType)).toBe(true);
    });

    it('should include CPU and memory utilization metrics', () => {
      const metrics = registry.getUtilizationMetrics(appType);
      expect(metrics).toHaveLength(2);
      expect(metrics.some((m) => m.metricName === 'CpuPercentage')).toBe(true);
      expect(metrics.some((m) => m.metricName === 'MemoryPercentage')).toBe(true);
    });

    it('should have correct underuse thresholds', () => {
      const metrics = registry.getUtilizationMetrics(appType);
      const cpu = metrics.find((m) => m.metricName === 'CpuPercentage');
      const mem = metrics.find((m) => m.metricName === 'MemoryPercentage');

      expect(cpu?.underuseThreshold).toBe(10);
      expect(mem?.underuseThreshold).toBe(20);
    });
  });

  describe('SQL Database metrics', () => {
    const sqlType = 'Microsoft.Sql/servers/databases';

    it('should include DTU consumption as a utilization metric', () => {
      const metrics = registry.getUtilizationMetrics(sqlType);
      const dtu = metrics.find((m) => m.metricName === 'dtu_consumption_percent');

      expect(dtu).toBeDefined();
      expect(dtu?.underuseThreshold).toBe(15);
    });

    it('should have 3 utilization metrics for SQL', () => {
      const metrics = registry.getUtilizationMetrics(sqlType);
      expect(metrics).toHaveLength(3);
    });
  });

  describe('Storage Account metrics', () => {
    const storageType = 'Microsoft.Storage/storageAccounts';

    it('should include UsedCapacity as a utilization metric', () => {
      const metrics = registry.getUtilizationMetrics(storageType);
      expect(metrics).toHaveLength(1);
      expect(metrics[0].metricName).toBe('UsedCapacity');
    });
  });

  describe('Cosmos DB metrics', () => {
    const cosmosType = 'Microsoft.DocumentDB/databaseAccounts';

    it('should include RU consumption metrics', () => {
      const metrics = registry.getUtilizationMetrics(cosmosType);
      expect(metrics).toHaveLength(2);
      expect(metrics.some((m) => m.metricName === 'TotalRequestUnits')).toBe(true);
      expect(metrics.some((m) => m.metricName === 'NormalizedRUConsumption')).toBe(true);
    });
  });

  describe('AKS metrics', () => {
    const aksType = 'Microsoft.ContainerService/managedClusters';

    it('should include node CPU and memory metrics', () => {
      const metrics = registry.getUtilizationMetrics(aksType);
      expect(metrics).toHaveLength(2);
      expect(metrics.some((m) => m.metricName === 'node_cpu_usage_percentage')).toBe(true);
      expect(metrics.some((m) => m.metricName === 'node_memory_rss_percentage')).toBe(true);
    });
  });

  describe('getMetrics() for unregistered type', () => {
    it('should return empty array for unknown resource type', () => {
      const metrics = registry.getMetrics('Microsoft.Unknown/things');
      expect(metrics).toEqual([]);
    });

    it('should report hasMetrics as false for unknown type', () => {
      expect(registry.hasMetrics('Microsoft.Unknown/things')).toBe(false);
    });
  });

  describe('registerMetrics()', () => {
    it('should allow registering new resource type metrics', () => {
      registry.registerMetrics('Microsoft.Custom/widgets', [
        {
          metricName: 'WidgetUsage',
          namespace: 'Microsoft.Custom/widgets',
          displayName: 'Widget Usage',
          aggregationType: 'Average',
          isUtilizationMetric: true,
          underuseThreshold: 5,
        },
      ]);

      expect(registry.hasMetrics('Microsoft.Custom/widgets')).toBe(true);
      expect(registry.getMetricNames('Microsoft.Custom/widgets')).toEqual(['WidgetUsage']);
    });

    it('should allow overriding existing resource type metrics', () => {
      const originalCount = registry.getMetrics('Microsoft.Compute/virtualMachines').length;

      registry.registerMetrics('Microsoft.Compute/virtualMachines', [
        {
          metricName: 'CustomCPU',
          namespace: 'Microsoft.Compute/virtualMachines',
          displayName: 'Custom CPU',
          aggregationType: 'Average',
          isUtilizationMetric: true,
          underuseThreshold: 5,
        },
      ]);

      const newCount = registry.getMetrics('Microsoft.Compute/virtualMachines').length;
      expect(newCount).toBe(1);
      expect(newCount).not.toBe(originalCount);
    });
  });
});
