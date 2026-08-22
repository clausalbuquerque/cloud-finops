/**
 * Cost query request parameters.
 */
export interface CostQueryParams {
  /** Start date for the cost query (inclusive). */
  startDate: Date;
  /** End date for the cost query (inclusive). */
  endDate: Date;
  /** Azure subscription ID. If not provided, uses the configured default. */
  subscriptionId?: string;
  /** Granularity of the results: 'Daily' or 'None' (aggregated total). */
  granularity?: 'Daily' | 'None';
  /** Group results by these dimensions (e.g., 'ResourceGroup', 'ServiceName', 'MeterCategory'). Max 2. */
  groupBy?: string[];
}

/**
 * A single row of cost query results, mapped to named fields.
 */
export interface CostRecord {
  /** The cost amount. */
  cost: number;
  /** The usage date (YYYYMMDD number format from Azure, or null for aggregated). */
  usageDate: number | null;
  /** Currency code (e.g., 'USD', 'EUR'). */
  currency: string;
  /** Dynamic grouping values keyed by dimension name. */
  groupings: Record<string, string>;
}

/**
 * Parsed cost query response.
 */
export interface CostQueryResult {
  /** The parsed cost records. */
  records: CostRecord[];
  /** Total number of records returned. */
  totalRecords: number;
  /** Column metadata from the API response. */
  columns: CostQueryColumn[];
}

/**
 * Column metadata from a cost query response.
 */
export interface CostQueryColumn {
  /** Column name. */
  name: string;
  /** Column type (e.g., 'Number', 'String'). */
  type: string;
}
