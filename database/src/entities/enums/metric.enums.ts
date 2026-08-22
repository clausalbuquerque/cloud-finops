/**
 * Enum representing the unit of measure for Azure Monitor metrics.
 * Values match the Azure Monitor MetricUnit specification.
 *
 * @see https://learn.microsoft.com/en-us/azure/azure-monitor/essentials/metrics-supported
 */
export enum MetricUnit {
  Count = 'Count',
  Bytes = 'Bytes',
  Seconds = 'Seconds',
  CountPerSecond = 'CountPerSecond',
  BytesPerSecond = 'BytesPerSecond',
  Percent = 'Percent',
  MilliSeconds = 'MilliSeconds',
  ByteSeconds = 'ByteSeconds',
  Cores = 'Cores',
  MilliCores = 'MilliCores',
  NanoCores = 'NanoCores',
  BitsPerSecond = 'BitsPerSecond',
  Unspecified = 'Unspecified',
}

/**
 * Enum representing the aggregation type for Azure Monitor metrics.
 */
export enum AggregationType {
  Average = 'Average',
  Minimum = 'Minimum',
  Maximum = 'Maximum',
  Total = 'Total',
  Count = 'Count',
  None = 'None',
}

/**
 * Enum representing the time grain (resolution) for metric data points.
 */
export enum TimeGrain {
  PT1M = 'PT1M',
  PT5M = 'PT5M',
  PT15M = 'PT15M',
  PT30M = 'PT30M',
  PT1H = 'PT1H',
  PT6H = 'PT6H',
  PT12H = 'PT12H',
  P1D = 'P1D',
}
