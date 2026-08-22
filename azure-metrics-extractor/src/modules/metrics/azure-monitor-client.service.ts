import { Injectable, Logger } from '@nestjs/common';
import { ConfigService } from '@nestjs/config';
import { ClientSecretCredential, DefaultAzureCredential, TokenCredential } from '@azure/identity';
import { MonitorClient } from '@azure/arm-monitor';
import {
  MetricQueryParams,
  BatchMetricQueryParams,
  MetricDefinition,
  MetricDataPoint,
  MetricTimeSeries,
  MetricQueryResult,
} from './interfaces';

/** Maximum number of resources per Batch Metrics API call. */
const MAX_BATCH_SIZE = 50;

/** Maximum retry attempts for rate-limited requests. */
const MAX_RETRIES = 5;

/** Base delay in ms for exponential backoff. */
const BASE_DELAY_MS = 1000;

/** Default time grain if not specified. */
const DEFAULT_TIME_GRAIN = 'PT1H';

/** Default aggregations if not specified. */
const DEFAULT_AGGREGATIONS = 'Average,Minimum,Maximum,Total,Count';

/**
 * Service for querying Azure Monitor metrics.
 *
 * Provides methods to:
 * - List metric definitions for a given resource
 * - Query metric data for a single resource
 * - Query metric data in batch (up to 50 resources per call)
 *
 * Includes exponential backoff retry for rate-limited (429) requests.
 */
@Injectable()
export class AzureMonitorClientService {
  private readonly logger = new Logger(AzureMonitorClientService.name);
  private readonly client: MonitorClient;
  private readonly defaultSubscriptionId: string;
  private readonly credential: TokenCredential;

  constructor(private readonly configService: ConfigService) {
    const tenantId = this.configService.get<string>('azure.tenantId', '');
    const clientId = this.configService.get<string>('azure.clientId', '');
    const clientSecret = this.configService.get<string>('azure.clientSecret', '');
    this.defaultSubscriptionId = this.configService.get<string>('azure.subscriptionId', '');

    this.credential = this.createCredential(tenantId, clientId, clientSecret);
    this.client = new MonitorClient(this.credential, this.defaultSubscriptionId);

    this.logger.log('AzureMonitorClientService initialized');
  }

  /**
   * List available metric definitions for a given resource.
   *
   * @param resourceId - Full Azure ARM resource ID
   * @returns Array of metric definitions
   */
  async listMetricDefinitions(resourceId: string): Promise<MetricDefinition[]> {
    this.logger.log(`Listing metric definitions for ${resourceId}`);

    try {
      const definitions: MetricDefinition[] = [];

      const iterator = this.client.metricDefinitions.list(resourceId);
      for await (const def of iterator) {
        definitions.push({
          name: def.name?.value || '',
          displayName: def.name?.localizedValue || def.name?.value || '',
          namespace: def.namespace || '',
          unit: def.unit || 'Unspecified',
          primaryAggregationType: def.primaryAggregationType || 'Average',
          supportedAggregationTypes: (def.supportedAggregationTypes || []) as string[],
          supportedTimeGrains: (def.metricAvailabilities || [])
            .map((a) => a.timeGrain || '')
            .filter(Boolean),
        });
      }

      this.logger.log(`Found ${definitions.length} metric definitions`);
      return definitions;
    } catch (error: unknown) {
      this.handleError(error, 'listing metric definitions');
      throw error;
    }
  }

  /**
   * Query metric data for a single resource.
   *
   * @param params - Query parameters (resource, metrics, time range, time grain, aggregations)
   * @returns Metric query result with time-series data
   */
  async queryMetrics(params: MetricQueryParams): Promise<MetricQueryResult> {
    const timeGrain = params.timeGrain || DEFAULT_TIME_GRAIN;
    const aggregations = params.aggregations?.join(',') || DEFAULT_AGGREGATIONS;
    const metricNames = params.metricNames.join(',');

    this.logger.log(
      `Querying metrics [${metricNames}] for ${params.resourceId} ` +
        `(${params.startTime.toISOString()} to ${params.endTime.toISOString()}, grain: ${timeGrain})`,
    );

    const response = await this.executeWithRetry(() =>
      this.client.metrics.list(params.resourceId, {
        metricnames: metricNames,
        timespan: `${params.startTime.toISOString()}/${params.endTime.toISOString()}`,
        interval: timeGrain,
        aggregation: aggregations,
      }),
    );

    return this.parseMetricResponse(params.resourceId, response, timeGrain);
  }

  /**
   * Query metrics for multiple resources using the Batch Metrics API pattern.
   *
   * Splits large lists into chunks of MAX_BATCH_SIZE and queries each chunk.
   * Note: Uses parallel single-resource queries as the ARM Batch API
   * may not be available in all regions. Future enhancement: use actual Batch API endpoint.
   *
   * @param params - Batch query parameters
   * @returns Combined metric query result
   */
  async queryMetricsBatch(params: BatchMetricQueryParams): Promise<MetricQueryResult> {
    const allTimeSeries: MetricTimeSeries[] = [];
    let totalDataPoints = 0;

    // Split into chunks of MAX_BATCH_SIZE
    const chunks = this.createChunks(params.resourceIds, MAX_BATCH_SIZE);
    this.logger.log(
      `Batch querying ${params.resourceIds.length} resources in ${chunks.length} chunk(s)`,
    );

    for (const chunk of chunks) {
      // Process resources in parallel within each chunk
      const promises = chunk.map((resourceId) =>
        this.queryMetrics({
          resourceId,
          metricNames: params.metricNames,
          startTime: params.startTime,
          endTime: params.endTime,
          timeGrain: params.timeGrain,
          aggregations: params.aggregations,
        }).catch((error) => {
          const message = error instanceof Error ? error.message : String(error);
          this.logger.warn(`Failed to query metrics for ${resourceId}: ${message}`);
          return null;
        }),
      );

      const results = await Promise.all(promises);

      for (const result of results) {
        if (result) {
          allTimeSeries.push(...result.timeSeries);
          totalDataPoints += result.totalDataPoints;
        }
      }
    }

    this.logger.log(
      `Batch query complete: ${allTimeSeries.length} series, ${totalDataPoints} data points`,
    );

    return { timeSeries: allTimeSeries, totalDataPoints };
  }

  /**
   * Parse Azure Monitor metrics response into typed MetricQueryResult.
   */
  parseMetricResponse(
    resourceId: string,
    response: {
      value?: Array<{
        name?: { value?: string };
        unit?: string;
        timeseries?: Array<{
          data?: Array<{
            timeStamp?: Date;
            average?: number;
            minimum?: number;
            maximum?: number;
            total?: number;
            count?: number;
          }>;
        }>;
      }>;
    },
    timeGrain: string,
  ): MetricQueryResult {
    const timeSeries: MetricTimeSeries[] = [];
    let totalDataPoints = 0;

    for (const metric of response.value || []) {
      const metricName = metric.name?.value || '';
      const unit = metric.unit || 'Unspecified';

      for (const ts of metric.timeseries || []) {
        const dataPoints: MetricDataPoint[] = (ts.data || []).map((dp) => ({
          timestamp: dp.timeStamp ? new Date(dp.timeStamp) : new Date(),
          average: dp.average,
          minimum: dp.minimum,
          maximum: dp.maximum,
          total: dp.total,
          count: dp.count,
        }));

        totalDataPoints += dataPoints.length;

        timeSeries.push({
          resourceId,
          metricName,
          namespace: '',
          unit,
          timeGrain,
          dataPoints,
        });
      }
    }

    return { timeSeries, totalDataPoints };
  }

  /**
   * Execute an async operation with exponential backoff retry on 429/5xx errors.
   */
  private async executeWithRetry<T>(operation: () => Promise<T>): Promise<T> {
    for (let attempt = 0; attempt <= MAX_RETRIES; attempt++) {
      try {
        return await operation();
      } catch (error: unknown) {
        const statusCode = this.extractStatusCode(error);
        const isRateLimited = statusCode === 429;
        const isServerError = statusCode !== undefined && statusCode >= 500;
        const isRetryable = isRateLimited || isServerError;

        if (!isRetryable || attempt === MAX_RETRIES) {
          this.handleError(error, 'querying metrics');
          throw error;
        }

        const delayMs = this.getRetryDelay(error, attempt);
        this.logger.warn(
          `Retryable error (${statusCode}) on attempt ${attempt + 1}/${MAX_RETRIES + 1}. ` +
            `Retrying in ${delayMs}ms...`,
        );

        await this.sleep(delayMs);
      }
    }

    throw new Error('Retry loop exhausted');
  }

  /**
   * Calculate retry delay with exponential backoff and jitter.
   * Respects Retry-After header if present.
   */
  private getRetryDelay(error: unknown, attempt: number): number {
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

    const exponentialDelay = BASE_DELAY_MS * Math.pow(2, attempt);
    const jitter = Math.random() * BASE_DELAY_MS;
    return exponentialDelay + jitter;
  }

  /**
   * Create an Azure credential based on available configuration.
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
   * Log meaningful error details.
   */
  private handleError(error: unknown, context: string): void {
    const statusCode = this.extractStatusCode(error);
    const message = error instanceof Error ? error.message : String(error);

    if (statusCode === 401 || statusCode === 403) {
      this.logger.error(
        `Authentication/authorization failed while ${context} (${statusCode}): ${message}`,
      );
    } else if (statusCode === 429) {
      this.logger.error(`Rate limit exceeded while ${context}: ${message}`);
    } else if (statusCode !== undefined && statusCode >= 500) {
      this.logger.error(`Server error while ${context} (${statusCode}): ${message}`);
    } else {
      this.logger.error(`Error while ${context}: ${message}`);
    }
  }

  /**
   * Extract HTTP status code from an error.
   */
  private extractStatusCode(error: unknown): number | undefined {
    if (error && typeof error === 'object' && 'statusCode' in error) {
      return (error as { statusCode: number }).statusCode;
    }
    return undefined;
  }

  /**
   * Split an array into chunks.
   */
  private createChunks<T>(items: T[], chunkSize: number): T[][] {
    const chunks: T[][] = [];
    for (let i = 0; i < items.length; i += chunkSize) {
      chunks.push(items.slice(i, i + chunkSize));
    }
    return chunks;
  }

  /**
   * Sleep for the specified number of milliseconds.
   */
  private sleep(ms: number): Promise<void> {
    return new Promise((resolve) => setTimeout(resolve, ms));
  }
}
