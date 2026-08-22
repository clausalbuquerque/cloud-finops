/**
 * Parameters for a metrics extraction run.
 */
export interface MetricsExtractionParams {
  /** Start of the time range to extract metrics for. */
  startDate: Date;
  /** End of the time range to extract metrics for. */
  endDate: Date;
  /** Azure subscription ID (uses default if not provided). */
  subscriptionId?: string;
  /** Filter by resource types (e.g., ['Microsoft.Compute/virtualMachines']). */
  resourceTypes?: string[];
  /** Filter by resource group name. */
  resourceGroup?: string;
  /** Time grain / resolution (ISO 8601 duration). Defaults to PT1H. */
  timeGrain?: string;
  /** Batch size for database inserts. Defaults to 500. */
  batchSize?: number;
}

/**
 * Result of a metrics extraction run.
 */
export interface MetricsExtractionResult {
  /** Number of resources discovered from Azure. */
  resourcesDiscovered: number;
  /** Number of tracked resources synced to the database. */
  resourcesSynced: number;
  /** Number of metric data points fetched from Azure Monitor. */
  dataPointsFetched: number;
  /** Number of metric data points persisted to the database. */
  dataPointsPersisted: number;
  /** Number of metric definitions synced. */
  metricDefinitionsSynced: number;
  /** Total duration in milliseconds. */
  durationMs: number;
  /** Non-fatal errors encountered during extraction. */
  errors: MetricsExtractionError[];
}

/**
 * Non-fatal error encountered during metrics extraction.
 */
export interface MetricsExtractionError {
  /** Phase where the error occurred. */
  phase: 'discover' | 'sync' | 'fetch' | 'persist';
  /** Error message. */
  message: string;
  /** Number of records affected by the error. */
  recordsAffected?: number;
  /** Resource ID or type related to the error. */
  resourceContext?: string;
}

/**
 * Parameters for computing utilization summaries.
 */
export interface UtilizationSummaryParams {
  /** Start date for the summary period. */
  startDate: Date;
  /** End date for the summary period. */
  endDate: Date;
  /** Optional list of tracked resource IDs to compute summaries for. */
  trackedResourceIds?: string[];
  /** Optional list of resource types to compute summaries for. */
  resourceTypes?: string[];
}

/**
 * Result of utilization summary computation.
 */
export interface UtilizationSummaryResult {
  /** Number of summaries computed. */
  summariesComputed: number;
  /** Number of summaries persisted (inserted or updated). */
  summariesPersisted: number;
  /** Number of resources flagged as underused. */
  resourcesFlaggedUnderused: number;
  /** Total duration in milliseconds. */
  durationMs: number;
  /** Non-fatal errors encountered. */
  errors: MetricsExtractionError[];
}
