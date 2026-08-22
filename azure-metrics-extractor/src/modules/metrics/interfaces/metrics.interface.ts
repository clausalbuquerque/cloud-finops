/**
 * Represents a discovered Azure resource.
 */
export interface DiscoveredResource {
  /** Full Azure ARM resource ID. */
  id: string;
  /** Display name of the resource. */
  name: string;
  /** Azure resource type (e.g., Microsoft.Compute/virtualMachines). */
  type: string;
  /** Resource group name. */
  resourceGroup: string;
  /** Azure region (e.g., eastus, westeurope). */
  location: string;
  /** SKU information, if available. */
  sku?: ResourceSku;
  /** Resource tags. */
  tags?: Record<string, string>;
}

/**
 * SKU information for a discovered resource.
 */
export interface ResourceSku {
  /** SKU name (e.g., Standard_D2s_v3, P1v3). */
  name?: string;
  /** SKU tier (e.g., Standard, Premium). */
  tier?: string;
  /** SKU capacity. */
  capacity?: number;
}

/**
 * Parameters for resource discovery.
 */
export interface ResourceDiscoveryParams {
  /** Azure subscription ID. */
  subscriptionId?: string;
  /** Filter by resource type (e.g., Microsoft.Compute/virtualMachines). */
  resourceType?: string;
  /** Filter by resource group name. */
  resourceGroup?: string;
  /** Filter by tags (key-value pairs). */
  tags?: Record<string, string>;
}

/**
 * Parameters for querying metric data.
 */
export interface MetricQueryParams {
  /** Full Azure ARM resource ID. */
  resourceId: string;
  /** Metric names to query (e.g., ['Percentage CPU', 'Available Memory Bytes']). */
  metricNames: string[];
  /** Start time (UTC). */
  startTime: Date;
  /** End time (UTC). */
  endTime: Date;
  /** Time grain / resolution (ISO 8601 duration, e.g., PT1H, P1D). */
  timeGrain?: string;
  /** Aggregation types (e.g., ['Average', 'Maximum']). */
  aggregations?: string[];
}

/**
 * Parameters for the Batch Metrics API.
 */
export interface BatchMetricQueryParams {
  /** Azure subscription ID. */
  subscriptionId: string;
  /** Resource type (e.g., Microsoft.Compute/virtualMachines). */
  resourceType: string;
  /** List of full resource IDs (max 50). */
  resourceIds: string[];
  /** Metric names to query. */
  metricNames: string[];
  /** Start time (UTC). */
  startTime: Date;
  /** End time (UTC). */
  endTime: Date;
  /** Time grain / resolution. */
  timeGrain?: string;
  /** Aggregation types. */
  aggregations?: string[];
}

/**
 * A single metric definition from Azure Monitor.
 */
export interface MetricDefinition {
  /** Metric name. */
  name: string;
  /** Display name. */
  displayName: string;
  /** Metric namespace. */
  namespace: string;
  /** Unit of measure. */
  unit: string;
  /** Primary aggregation type. */
  primaryAggregationType: string;
  /** Supported aggregation types. */
  supportedAggregationTypes: string[];
  /** Supported time grains. */
  supportedTimeGrains: string[];
}

/**
 * A metric time-series data point.
 */
export interface MetricDataPoint {
  /** Timestamp of the data point (UTC). */
  timestamp: Date;
  /** Average value. */
  average?: number;
  /** Minimum value. */
  minimum?: number;
  /** Maximum value. */
  maximum?: number;
  /** Total/sum value. */
  total?: number;
  /** Count of samples. */
  count?: number;
}

/**
 * A metric time-series result for a single metric on a single resource.
 */
export interface MetricTimeSeries {
  /** Resource ID. */
  resourceId: string;
  /** Metric name. */
  metricName: string;
  /** Metric namespace. */
  namespace: string;
  /** Unit of measure. */
  unit: string;
  /** Time grain used. */
  timeGrain: string;
  /** Data points in the series. */
  dataPoints: MetricDataPoint[];
}

/**
 * Result from a metric query (single or batch).
 */
export interface MetricQueryResult {
  /** Time-series results, one per metric per resource. */
  timeSeries: MetricTimeSeries[];
  /** Total number of data points across all series. */
  totalDataPoints: number;
}

/**
 * Configuration for a utilization metric tracked per resource type.
 */
export interface UtilizationMetricConfig {
  /** Azure Monitor metric name. */
  metricName: string;
  /** Azure Monitor metric namespace (usually same as resource type). */
  namespace: string;
  /** Display name for dashboards. */
  displayName: string;
  /** Primary aggregation type to collect. */
  aggregationType: string;
  /** Whether this metric is relevant for underuse detection. */
  isUtilizationMetric: boolean;
  /** Default underuse threshold (avg below this = underused). */
  underuseThreshold?: number;
}
