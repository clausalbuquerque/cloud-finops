import { Injectable, Logger } from '@nestjs/common';
import { ConfigService } from '@nestjs/config';
import { ClientSecretCredential, DefaultAzureCredential, TokenCredential } from '@azure/identity';
import {
  CostManagementClient,
  QueryDefinition,
  QueryResult,
  QueryColumn,
  KnownExportType,
  KnownTimeframeType,
  KnownGranularityType,
  KnownQueryColumnType,
} from '@azure/arm-costmanagement';
import { CostQueryParams, CostRecord, CostQueryResult, CostQueryColumn } from './interfaces';

/**
 * Service for querying Azure Cost Management API.
 *
 * Handles authentication, query construction, response parsing,
 * and retry logic with exponential backoff for rate-limited requests.
 */
@Injectable()
export class AzureCostClientService {
  private readonly logger = new Logger(AzureCostClientService.name);
  private client: CostManagementClient;
  private readonly defaultSubscriptionId: string;

  /** Maximum number of retry attempts for rate-limited (429) requests. */
  private readonly maxRetries = 5;
  /** Base delay in milliseconds for exponential backoff. */
  private readonly baseDelayMs = 1000;

  constructor(private readonly configService: ConfigService) {
    const tenantId = this.configService.get<string>('azure.tenantId', '');
    const clientId = this.configService.get<string>('azure.clientId', '');
    const clientSecret = this.configService.get<string>('azure.clientSecret', '');
    this.defaultSubscriptionId = this.configService.get<string>('azure.subscriptionId', '');

    const credential = this.createCredential(tenantId, clientId, clientSecret);
    this.client = new CostManagementClient(credential);

    this.logger.log('AzureCostClientService initialized');
  }

  /**
   * Query cost data from Azure Cost Management API.
   *
   * @param params - Query parameters including date range, subscription, and grouping
   * @returns Parsed cost query results with typed records
   */
  async queryCostData(params: CostQueryParams): Promise<CostQueryResult> {
    const subscriptionId = params.subscriptionId || this.defaultSubscriptionId;

    if (!subscriptionId) {
      throw new Error('No subscription ID provided and no default configured');
    }

    const scope = `/subscriptions/${subscriptionId}`;
    const queryDefinition = this.buildQueryDefinition(params);

    this.logger.log(
      `Querying cost data for subscription ${subscriptionId} ` +
        `from ${params.startDate.toISOString()} to ${params.endDate.toISOString()}`,
    );

    const response = await this.executeWithRetry(() =>
      this.client.query.usage(scope, queryDefinition),
    );

    return this.parseQueryResult(response, params.groupBy);
  }

  /**
   * Query cost data grouped by a specific dimension (e.g., ResourceGroup, ServiceName).
   *
   * Convenience wrapper around queryCostData for common grouping scenarios.
   *
   * @param startDate - Start date for the query
   * @param endDate - End date for the query
   * @param dimension - The dimension to group by
   * @param subscriptionId - Optional subscription override
   * @returns Parsed cost query results grouped by the specified dimension
   */
  async queryCostByDimension(
    startDate: Date,
    endDate: Date,
    dimension: string,
    subscriptionId?: string,
  ): Promise<CostQueryResult> {
    return this.queryCostData({
      startDate,
      endDate,
      subscriptionId,
      granularity: 'Daily',
      groupBy: [dimension],
    });
  }

  /**
   * Build an Azure Cost Management QueryDefinition from our params.
   */
  private buildQueryDefinition(params: CostQueryParams): QueryDefinition {
    const granularity = params.granularity === 'None' ? undefined : KnownGranularityType.Daily;

    const grouping = (params.groupBy || []).map((name) => ({
      type: KnownQueryColumnType.Dimension,
      name,
    }));

    return {
      type: KnownExportType.ActualCost,
      timeframe: KnownTimeframeType.Custom,
      timePeriod: {
        from: params.startDate,
        to: params.endDate,
      },
      dataset: {
        granularity,
        aggregation: {
          totalCost: {
            name: 'Cost',
            function: 'Sum',
          },
        },
        grouping: grouping.length > 0 ? grouping : undefined,
      },
    };
  }

  /**
   * Parse the raw Azure QueryResult into typed CostQueryResult.
   */
  private parseQueryResult(result: QueryResult, groupByDimensions?: string[]): CostQueryResult {
    const columns: CostQueryColumn[] = (result.columns || []).map((col: QueryColumn) => ({
      name: col.name || '',
      type: col.type || '',
    }));

    const columnIndex = new Map<string, number>();
    columns.forEach((col, idx) => {
      columnIndex.set(col.name, idx);
    });

    const records: CostRecord[] = (result.rows || []).map((row) => {
      const costIdx = columnIndex.get('Cost') ?? columnIndex.get('PreTaxCost') ?? 0;
      const dateIdx = columnIndex.get('UsageDate');
      const currencyIdx = columnIndex.get('Currency') ?? columnIndex.get('BillingCurrency');

      const groupings: Record<string, string> = {};
      if (groupByDimensions) {
        for (const dim of groupByDimensions) {
          const dimIdx = columnIndex.get(dim);
          if (dimIdx !== undefined) {
            groupings[dim] = String(row[dimIdx] ?? '');
          }
        }
      }

      return {
        cost: Number(row[costIdx] ?? 0),
        usageDate: dateIdx !== undefined ? (row[dateIdx] as number | null) : null,
        currency: currencyIdx !== undefined ? String(row[currencyIdx]) : 'USD',
        groupings,
      };
    });

    this.logger.log(`Parsed ${records.length} cost records`);

    return {
      records,
      totalRecords: records.length,
      columns,
    };
  }

  /**
   * Execute an async operation with exponential backoff retry on rate-limit (429) errors.
   *
   * @param operation - The async operation to execute
   * @returns The operation result
   */
  private async executeWithRetry<T>(operation: () => Promise<T>): Promise<T> {
    for (let attempt = 0; attempt <= this.maxRetries; attempt++) {
      try {
        return await operation();
      } catch (error: unknown) {
        const statusCode = this.extractStatusCode(error);
        const isRateLimited = statusCode === 429;
        const isServerError = statusCode !== undefined && statusCode >= 500;
        const isRetryable = isRateLimited || isServerError;

        if (!isRetryable || attempt === this.maxRetries) {
          this.handleError(error);
          throw error;
        }

        const retryAfterMs = this.getRetryDelay(error, attempt);
        this.logger.warn(
          `Rate limited (attempt ${attempt + 1}/${this.maxRetries + 1}). ` +
            `Retrying in ${retryAfterMs}ms...`,
        );

        await this.sleep(retryAfterMs);
      }
    }

    // Should not be reached, but TypeScript needs it
    throw new Error('Retry loop exhausted');
  }

  /**
   * Create an Azure credential based on available configuration.
   *
   * Uses ClientSecretCredential when all three values are present,
   * otherwise falls back to DefaultAzureCredential (supports managed identity, CLI, etc.).
   */
  private createCredential(
    tenantId: string,
    clientId: string,
    clientSecret: string,
  ): TokenCredential {
    if (tenantId && clientId && clientSecret) {
      this.logger.log('Using ClientSecretCredential for authentication');
      return new ClientSecretCredential(tenantId, clientId, clientSecret);
    }

    this.logger.log('Using DefaultAzureCredential for authentication');
    return new DefaultAzureCredential();
  }

  /**
   * Extract HTTP status code from an error, if available.
   */
  private extractStatusCode(error: unknown): number | undefined {
    if (error && typeof error === 'object' && 'statusCode' in error) {
      return (error as { statusCode: number }).statusCode;
    }
    return undefined;
  }

  /**
   * Calculate retry delay using exponential backoff with jitter.
   * Respects the Retry-After header if present.
   */
  private getRetryDelay(error: unknown, attempt: number): number {
    // Check for Retry-After header in error response
    if (error && typeof error === 'object' && 'response' in error) {
      const response = (error as { response?: { headers?: { get?: (key: string) => string } } })
        .response;
      const retryAfter = response?.headers?.get?.('retry-after');
      if (retryAfter) {
        const retryAfterSeconds = parseInt(retryAfter, 10);
        if (!isNaN(retryAfterSeconds)) {
          return retryAfterSeconds * 1000;
        }
      }
    }

    // Exponential backoff with jitter: baseDelay * 2^attempt + random jitter
    const exponentialDelay = this.baseDelayMs * Math.pow(2, attempt);
    const jitter = Math.random() * this.baseDelayMs;
    return exponentialDelay + jitter;
  }

  /**
   * Log meaningful error details based on the error type.
   */
  private handleError(error: unknown): void {
    const statusCode = this.extractStatusCode(error);
    const message = error instanceof Error ? error.message : String(error);

    if (statusCode === 401 || statusCode === 403) {
      this.logger.error(
        `Authentication/authorization failed (${statusCode}): ${message}. ` +
          'Verify AZURE_TENANT_ID, AZURE_CLIENT_ID, and AZURE_CLIENT_SECRET are correct ' +
          'and the service principal has Cost Management Reader role.',
      );
    } else if (statusCode === 429) {
      this.logger.error(`Rate limit exceeded after all retries: ${message}`);
    } else if (statusCode !== undefined && statusCode >= 400) {
      this.logger.error(`Azure API error (${statusCode}): ${message}`);
    } else {
      this.logger.error(`Unexpected error querying Azure Cost Management: ${message}`);
    }
  }

  /**
   * Sleep for the specified number of milliseconds.
   */
  private sleep(ms: number): Promise<void> {
    return new Promise((resolve) => setTimeout(resolve, ms));
  }
}
