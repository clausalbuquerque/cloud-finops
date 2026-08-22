/**
 * Parameters for a consumption data extraction run.
 */
export interface ExtractionParams {
  /** Start date for the extraction period (inclusive). */
  startDate: Date;
  /** End date for the extraction period (inclusive). */
  endDate: Date;
  /** Optional Azure subscription ID. If omitted, uses the configured default. */
  subscriptionId?: string;
  /** Batch size for database inserts. Defaults to 500. */
  batchSize?: number;
}

/**
 * Result of a consumption data extraction run.
 */
export interface ExtractionResult {
  /** Total records fetched from the Azure Cost Management API. */
  recordsFetched: number;
  /** Total records persisted to the database. */
  recordsPersisted: number;
  /** Number of records that were updated (upsert matched existing). */
  recordsUpdated: number;
  /** Number of records that were newly inserted. */
  recordsInserted: number;
  /** Number of batches processed. */
  batchesProcessed: number;
  /** Duration of the extraction in milliseconds. */
  durationMs: number;
  /** Any errors encountered (non-fatal; fatal errors throw). */
  errors: ExtractionError[];
}

/**
 * Non-fatal error encountered during extraction.
 */
export interface ExtractionError {
  /** The phase where the error occurred (fetch, map, persist). */
  phase: 'fetch' | 'map' | 'persist';
  /** Human-readable error message. */
  message: string;
  /** Number of records affected by this error, if applicable. */
  recordsAffected?: number;
}

/**
 * Intermediate mapped record ready for persistence.
 * Contains all fields needed to create/update a ConsumptionRecordEntity.
 */
export interface MappedConsumptionRecord {
  /** The Azure subscription ID this record belongs to. */
  subscriptionId: string;
  /** The resource group name (parsed from groupings or resource ID). */
  resourceGroupName: string;
  /** Usage date parsed from the API response. */
  usageDate: Date;
  /** Cost amount. */
  cost: number;
  /** Currency code. */
  currency: string;
  /** Resource group display name from grouping dimension. */
  resourceGroup?: string;
  /** Service/meter category from grouping dimension. */
  meterCategory?: string;
  /** Service name from grouping dimension. */
  serviceName?: string;
  /** Resource type from grouping dimension. */
  resourceType?: string;
}
