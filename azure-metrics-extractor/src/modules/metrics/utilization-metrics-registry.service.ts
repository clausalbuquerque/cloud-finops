import { Injectable, Logger } from '@nestjs/common';
import { UtilizationMetricConfig } from './interfaces';

/**
 * Configurable registry that maps Azure resource types to their key utilization metrics.
 *
 * This registry drives the metrics extraction pipeline — it tells the system
 * which metrics to collect for each resource type, what aggregation to use,
 * and what threshold indicates underuse.
 *
 * Pre-loaded with default configurations for the most common Azure resource types.
 * Can be extended at runtime via `registerMetrics()`.
 */
@Injectable()
export class UtilizationMetricsRegistry {
  private readonly logger = new Logger(UtilizationMetricsRegistry.name);
  private readonly registry = new Map<string, UtilizationMetricConfig[]>();

  constructor() {
    this.loadDefaults();
    this.logger.log(
      `UtilizationMetricsRegistry initialized with ${this.registry.size} resource types`,
    );
  }

  /**
   * Get the utilization metrics configured for a given resource type.
   *
   * @param resourceType - Azure resource type (e.g., Microsoft.Compute/virtualMachines)
   * @returns Array of metric configurations, or empty array if type is not registered
   */
  getMetrics(resourceType: string): UtilizationMetricConfig[] {
    return this.registry.get(resourceType) || [];
  }

  /**
   * Get only the utilization-relevant metrics for a resource type (isUtilizationMetric = true).
   */
  getUtilizationMetrics(resourceType: string): UtilizationMetricConfig[] {
    return this.getMetrics(resourceType).filter((m) => m.isUtilizationMetric);
  }

  /**
   * Get all registered resource types.
   */
  getRegisteredTypes(): string[] {
    return [...this.registry.keys()];
  }

  /**
   * Get the metric names for a resource type (convenient for passing to the Monitor API).
   */
  getMetricNames(resourceType: string): string[] {
    return this.getMetrics(resourceType).map((m) => m.metricName);
  }

  /**
   * Register or override metrics for a resource type.
   */
  registerMetrics(resourceType: string, metrics: UtilizationMetricConfig[]): void {
    this.registry.set(resourceType, metrics);
    this.logger.log(`Registered ${metrics.length} metrics for ${resourceType}`);
  }

  /**
   * Check if a resource type has registered metrics.
   */
  hasMetrics(resourceType: string): boolean {
    return this.registry.has(resourceType) && this.registry.get(resourceType)!.length > 0;
  }

  /**
   * Load default utilization metric configurations for common Azure resource types.
   */
  private loadDefaults(): void {
    // Virtual Machines
    this.registry.set('Microsoft.Compute/virtualMachines', [
      {
        metricName: 'Percentage CPU',
        namespace: 'Microsoft.Compute/virtualMachines',
        displayName: 'CPU Utilization',
        aggregationType: 'Average',
        isUtilizationMetric: true,
        underuseThreshold: 10,
      },
      {
        metricName: 'Available Memory Bytes',
        namespace: 'Microsoft.Compute/virtualMachines',
        displayName: 'Available Memory',
        aggregationType: 'Average',
        isUtilizationMetric: true,
        underuseThreshold: 80, // > 80% available = underused (< 20% used)
      },
      {
        metricName: 'Network In Total',
        namespace: 'Microsoft.Compute/virtualMachines',
        displayName: 'Network In',
        aggregationType: 'Total',
        isUtilizationMetric: false,
      },
      {
        metricName: 'Network Out Total',
        namespace: 'Microsoft.Compute/virtualMachines',
        displayName: 'Network Out',
        aggregationType: 'Total',
        isUtilizationMetric: false,
      },
      {
        metricName: 'Disk Read Bytes',
        namespace: 'Microsoft.Compute/virtualMachines',
        displayName: 'Disk Read',
        aggregationType: 'Total',
        isUtilizationMetric: false,
      },
      {
        metricName: 'Disk Write Bytes',
        namespace: 'Microsoft.Compute/virtualMachines',
        displayName: 'Disk Write',
        aggregationType: 'Total',
        isUtilizationMetric: false,
      },
    ]);

    // App Services (Web Apps)
    this.registry.set('Microsoft.Web/sites', [
      {
        metricName: 'CpuPercentage',
        namespace: 'Microsoft.Web/sites',
        displayName: 'CPU Percentage',
        aggregationType: 'Average',
        isUtilizationMetric: true,
        underuseThreshold: 10,
      },
      {
        metricName: 'MemoryPercentage',
        namespace: 'Microsoft.Web/sites',
        displayName: 'Memory Percentage',
        aggregationType: 'Average',
        isUtilizationMetric: true,
        underuseThreshold: 20,
      },
      {
        metricName: 'Requests',
        namespace: 'Microsoft.Web/sites',
        displayName: 'Request Count',
        aggregationType: 'Total',
        isUtilizationMetric: false,
      },
      {
        metricName: 'AverageResponseTime',
        namespace: 'Microsoft.Web/sites',
        displayName: 'Average Response Time',
        aggregationType: 'Average',
        isUtilizationMetric: false,
      },
    ]);

    // SQL Databases
    this.registry.set('Microsoft.Sql/servers/databases', [
      {
        metricName: 'cpu_percent',
        namespace: 'Microsoft.Sql/servers/databases',
        displayName: 'CPU Percentage',
        aggregationType: 'Average',
        isUtilizationMetric: true,
        underuseThreshold: 10,
      },
      {
        metricName: 'dtu_consumption_percent',
        namespace: 'Microsoft.Sql/servers/databases',
        displayName: 'DTU Consumption',
        aggregationType: 'Average',
        isUtilizationMetric: true,
        underuseThreshold: 15,
      },
      {
        metricName: 'storage_percent',
        namespace: 'Microsoft.Sql/servers/databases',
        displayName: 'Storage Utilization',
        aggregationType: 'Average',
        isUtilizationMetric: true,
        underuseThreshold: 10,
      },
      {
        metricName: 'connection_successful',
        namespace: 'Microsoft.Sql/servers/databases',
        displayName: 'Successful Connections',
        aggregationType: 'Total',
        isUtilizationMetric: false,
      },
    ]);

    // Storage Accounts
    this.registry.set('Microsoft.Storage/storageAccounts', [
      {
        metricName: 'UsedCapacity',
        namespace: 'Microsoft.Storage/storageAccounts',
        displayName: 'Used Capacity',
        aggregationType: 'Average',
        isUtilizationMetric: true,
        underuseThreshold: 10,
      },
      {
        metricName: 'Transactions',
        namespace: 'Microsoft.Storage/storageAccounts',
        displayName: 'Transaction Count',
        aggregationType: 'Total',
        isUtilizationMetric: false,
      },
      {
        metricName: 'Ingress',
        namespace: 'Microsoft.Storage/storageAccounts',
        displayName: 'Data Ingress',
        aggregationType: 'Total',
        isUtilizationMetric: false,
      },
      {
        metricName: 'Egress',
        namespace: 'Microsoft.Storage/storageAccounts',
        displayName: 'Data Egress',
        aggregationType: 'Total',
        isUtilizationMetric: false,
      },
    ]);

    // Cosmos DB
    this.registry.set('Microsoft.DocumentDB/databaseAccounts', [
      {
        metricName: 'TotalRequestUnits',
        namespace: 'Microsoft.DocumentDB/databaseAccounts',
        displayName: 'Total RU Consumption',
        aggregationType: 'Total',
        isUtilizationMetric: true,
        underuseThreshold: 15,
      },
      {
        metricName: 'NormalizedRUConsumption',
        namespace: 'Microsoft.DocumentDB/databaseAccounts',
        displayName: 'Normalized RU Consumption',
        aggregationType: 'Maximum',
        isUtilizationMetric: true,
        underuseThreshold: 15,
      },
      {
        metricName: 'TotalRequests',
        namespace: 'Microsoft.DocumentDB/databaseAccounts',
        displayName: 'Total Requests',
        aggregationType: 'Count',
        isUtilizationMetric: false,
      },
    ]);

    // AKS Clusters
    this.registry.set('Microsoft.ContainerService/managedClusters', [
      {
        metricName: 'node_cpu_usage_percentage',
        namespace: 'Microsoft.ContainerService/managedClusters',
        displayName: 'Node CPU Usage',
        aggregationType: 'Average',
        isUtilizationMetric: true,
        underuseThreshold: 10,
      },
      {
        metricName: 'node_memory_rss_percentage',
        namespace: 'Microsoft.ContainerService/managedClusters',
        displayName: 'Node Memory Usage',
        aggregationType: 'Average',
        isUtilizationMetric: true,
        underuseThreshold: 20,
      },
    ]);
  }
}
