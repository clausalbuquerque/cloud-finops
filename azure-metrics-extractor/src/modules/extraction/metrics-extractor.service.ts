import { Injectable, Logger } from '@nestjs/common';
import { InjectRepository } from '@nestjs/typeorm';
import { Repository, DataSource } from 'typeorm';
import { ConfigService } from '@nestjs/config';
import { AzureResourceClientService } from '@modules/metrics/azure-resource-client.service';
import { AzureMonitorClientService } from '@modules/metrics/azure-monitor-client.service';
import { UtilizationMetricsRegistry } from '@modules/metrics/utilization-metrics-registry.service';
import { DiscoveredResource, MetricTimeSeries } from '@modules/metrics/interfaces';
import {
  SubscriptionEntity,
  ResourceGroupEntity,
  TrackedResourceEntity,
  MetricDefinitionEntity,
  MetricDataPointEntity,
  AggregationType,
  MetricUnit,
  TimeGrain,
} from '@modules/database';
import {
  MetricsExtractionParams,
  MetricsExtractionResult,
  MetricsExtractionError,
} from './interfaces';

/** Default batch size for database inserts. */
const DEFAULT_BATCH_SIZE = 500;

/** Default time grain for metric queries. */
const DEFAULT_TIME_GRAIN = 'PT1H';

/**
 * Service that orchestrates the full metrics extraction pipeline:
 *
 * 1. Discover resources via AzureResourceClientService
 * 2. Sync discovered resources to TrackedResource entities
 * 3. Ensure MetricDefinition entities exist for each resource type's metrics
 * 4. Fetch metric data via AzureMonitorClientService (Batch API)
 * 5. Map API responses to MetricDataPoint entities and persist
 *
 * Extraction is idempotent — re-running for the same period updates, not duplicates.
 */
@Injectable()
export class MetricsExtractorService {
  private readonly logger = new Logger(MetricsExtractorService.name);

  constructor(
    private readonly resourceClient: AzureResourceClientService,
    private readonly monitorClient: AzureMonitorClientService,
    private readonly metricsRegistry: UtilizationMetricsRegistry,
    private readonly configService: ConfigService,
    private readonly dataSource: DataSource,
    @InjectRepository(SubscriptionEntity)
    private readonly subscriptionRepo: Repository<SubscriptionEntity>,
    @InjectRepository(ResourceGroupEntity)
    private readonly resourceGroupRepo: Repository<ResourceGroupEntity>,
    @InjectRepository(TrackedResourceEntity)
    private readonly trackedResourceRepo: Repository<TrackedResourceEntity>,
    @InjectRepository(MetricDefinitionEntity)
    private readonly metricDefRepo: Repository<MetricDefinitionEntity>,
  ) {}

  /**
   * Execute the full metrics extraction pipeline.
   */
  async extract(params: MetricsExtractionParams): Promise<MetricsExtractionResult> {
    const startTime = Date.now();
    const batchSize = params.batchSize ?? DEFAULT_BATCH_SIZE;
    const timeGrain = params.timeGrain ?? DEFAULT_TIME_GRAIN;
    const errors: MetricsExtractionError[] = [];

    let resourcesDiscovered = 0;
    let resourcesSynced = 0;
    let dataPointsFetched = 0;
    let dataPointsPersisted = 0;
    let metricDefinitionsSynced = 0;

    this.logger.log(
      `Starting metrics extraction: ${params.startDate.toISOString()} to ${params.endDate.toISOString()}`,
    );

    // Step 1: Determine resource types to process
    const resourceTypes = params.resourceTypes ?? this.metricsRegistry.getRegisteredTypes();

    this.logger.log(
      `Processing ${resourceTypes.length} resource type(s): ${resourceTypes.join(', ')}`,
    );

    // Step 2: Discover and sync resources per type
    for (const resourceType of resourceTypes) {
      try {
        const discovered = await this.resourceClient.discoverResources({
          subscriptionId: params.subscriptionId,
          resourceType,
          resourceGroup: params.resourceGroup,
        });

        resourcesDiscovered += discovered.length;
        this.logger.log(`Discovered ${discovered.length} ${resourceType} resources`);

        if (discovered.length === 0) {
          continue;
        }

        // Step 3: Sync tracked resources
        const subscription = await this.ensureSubscription(
          params.subscriptionId ?? this.configService.get<string>('azure.subscriptionId', ''),
        );
        const synced = await this.syncTrackedResources(discovered, subscription.id);
        resourcesSynced += synced.length;

        // Step 4: Ensure metric definitions exist
        const metricConfigs = this.metricsRegistry.getMetrics(resourceType);
        const metricDefs = await this.syncMetricDefinitions(resourceType, metricConfigs);
        metricDefinitionsSynced += metricDefs.length;

        // Step 5: Fetch metrics via Batch API
        const metricNames = metricConfigs.map((m) => m.metricName);
        if (metricNames.length === 0) {
          continue;
        }

        const resourceIds = synced.map((r) => r.azureResourceId);
        const queryResult = await this.monitorClient.queryMetricsBatch({
          subscriptionId:
            params.subscriptionId ?? this.configService.get<string>('azure.subscriptionId', ''),
          resourceType,
          resourceIds,
          metricNames,
          startTime: params.startDate,
          endTime: params.endDate,
          timeGrain,
          aggregations: ['Average', 'Minimum', 'Maximum', 'Total', 'Count'],
        });

        dataPointsFetched += queryResult.totalDataPoints;
        this.logger.log(`Fetched ${queryResult.totalDataPoints} data points for ${resourceType}`);

        // Step 6: Persist data points
        const resourceMap = new Map(synced.map((r) => [r.azureResourceId, r]));
        const metricDefMap = new Map(metricDefs.map((d) => [d.metricName, d]));

        const persisted = await this.persistDataPoints(
          queryResult.timeSeries,
          resourceMap,
          metricDefMap,
          timeGrain,
          batchSize,
        );
        dataPointsPersisted += persisted;

        // Update lastMetricSync on tracked resources
        await this.updateLastMetricSync(synced.map((r) => r.id));
      } catch (error: unknown) {
        const message = error instanceof Error ? error.message : String(error);
        this.logger.error(`Failed to process ${resourceType}: ${message}`);
        errors.push({
          phase: 'fetch',
          message,
          resourceContext: resourceType,
        });
      }
    }

    const durationMs = Date.now() - startTime;
    const result: MetricsExtractionResult = {
      resourcesDiscovered,
      resourcesSynced,
      dataPointsFetched,
      dataPointsPersisted,
      metricDefinitionsSynced,
      durationMs,
      errors,
    };

    this.logger.log(
      `Extraction complete: ${resourcesDiscovered} discovered, ${resourcesSynced} synced, ` +
        `${dataPointsPersisted} data points persisted in ${durationMs}ms ` +
        `with ${errors.length} error(s)`,
    );

    return result;
  }

  /**
   * Ensure a subscription entity exists.
   */
  private async ensureSubscription(subscriptionId: string): Promise<SubscriptionEntity> {
    let subscription = await this.subscriptionRepo.findOne({
      where: { subscriptionId },
    });

    if (!subscription) {
      this.logger.log(`Creating subscription record for ${subscriptionId}`);
      subscription = this.subscriptionRepo.create({
        subscriptionId,
        displayName: subscriptionId,
        state: 'Enabled',
      });
      subscription = await this.subscriptionRepo.save(subscription);
    }

    return subscription;
  }

  /**
   * Ensure resource group entity exists.
   */
  private async ensureResourceGroup(
    name: string,
    subscriptionEntityId: string,
    location?: string,
  ): Promise<ResourceGroupEntity> {
    let rg = await this.resourceGroupRepo.findOne({
      where: { name, subscriptionId: subscriptionEntityId },
    });

    if (!rg) {
      rg = this.resourceGroupRepo.create({
        name,
        subscriptionId: subscriptionEntityId,
        location,
      });
      rg = await this.resourceGroupRepo.save(rg);
    }

    return rg;
  }

  /**
   * Sync discovered Azure resources to TrackedResource entities.
   * Uses upsert on azureResourceId to avoid duplicates.
   */
  async syncTrackedResources(
    discovered: DiscoveredResource[],
    subscriptionEntityId: string,
  ): Promise<TrackedResourceEntity[]> {
    const synced: TrackedResourceEntity[] = [];

    for (const resource of discovered) {
      try {
        const rg = await this.ensureResourceGroup(
          resource.resourceGroup,
          subscriptionEntityId,
          resource.location,
        );

        let tracked = await this.trackedResourceRepo.findOne({
          where: { azureResourceId: resource.id },
        });

        const provisionedCapacity = resource.sku
          ? {
              skuName: resource.sku.name,
              skuTier: resource.sku.tier,
              skuCapacity: resource.sku.capacity,
            }
          : null;

        if (tracked) {
          // Update existing
          tracked.resourceName = resource.name;
          tracked.resourceType = resource.type;
          tracked.region = resource.location;
          tracked.sku = resource.sku?.name ?? '';
          tracked.provisionedCapacity = provisionedCapacity;
          tracked.isActive = true;
          tracked = await this.trackedResourceRepo.save(tracked);
        } else {
          // Create new
          tracked = this.trackedResourceRepo.create({
            azureResourceId: resource.id,
            resourceName: resource.name,
            resourceType: resource.type,
            region: resource.location,
            sku: resource.sku?.name,
            provisionedCapacity,
            isActive: true,
            subscriptionId: subscriptionEntityId,
            resourceGroupId: rg.id,
          });
          tracked = await this.trackedResourceRepo.save(tracked);
        }

        synced.push(tracked);
      } catch (error: unknown) {
        const message = error instanceof Error ? error.message : String(error);
        this.logger.warn(`Failed to sync resource ${resource.id}: ${message}`);
      }
    }

    this.logger.log(`Synced ${synced.length} tracked resources`);
    return synced;
  }

  /**
   * Ensure MetricDefinition entities exist for the given resource type.
   */
  async syncMetricDefinitions(
    resourceType: string,
    metricConfigs: Array<{
      metricName: string;
      namespace: string;
      displayName: string;
      aggregationType: string;
      isUtilizationMetric: boolean;
    }>,
  ): Promise<MetricDefinitionEntity[]> {
    const definitions: MetricDefinitionEntity[] = [];

    for (const config of metricConfigs) {
      let def = await this.metricDefRepo.findOne({
        where: { resourceType, metricName: config.metricName },
      });

      if (!def) {
        def = this.metricDefRepo.create({
          resourceType,
          metricNamespace: config.namespace,
          metricName: config.metricName,
          displayName: config.displayName,
          unit: MetricUnit.Unspecified,
          primaryAggregationType: this.mapAggregationType(config.aggregationType),
          supportedAggregationTypes: ['Average', 'Minimum', 'Maximum', 'Total', 'Count'],
          isUtilizationMetric: config.isUtilizationMetric,
        });
        def = await this.metricDefRepo.save(def);
      }

      definitions.push(def);
    }

    return definitions;
  }

  /**
   * Persist metric data points in batched transactions.
   * Uses upsert-like logic: finds existing by resource+metric+timestamp, updates or inserts.
   */
  private async persistDataPoints(
    timeSeries: MetricTimeSeries[],
    resourceMap: Map<string, TrackedResourceEntity>,
    metricDefMap: Map<string, MetricDefinitionEntity>,
    timeGrain: string,
    batchSize: number,
  ): Promise<number> {
    let totalPersisted = 0;
    const allPoints: Array<{
      trackedResourceId: string;
      metricDefinitionId: string;
      timestamp: Date;
      timeGrain: TimeGrain;
      average: number | null;
      minimum: number | null;
      maximum: number | null;
      total: number | null;
      count: number | null;
    }> = [];

    for (const series of timeSeries) {
      const tracked = resourceMap.get(series.resourceId);
      const metricDef = metricDefMap.get(series.metricName);

      if (!tracked || !metricDef) {
        continue;
      }

      for (const dp of series.dataPoints) {
        allPoints.push({
          trackedResourceId: tracked.id,
          metricDefinitionId: metricDef.id,
          timestamp: dp.timestamp,
          timeGrain: this.mapTimeGrain(timeGrain),
          average: dp.average ?? null,
          minimum: dp.minimum ?? null,
          maximum: dp.maximum ?? null,
          total: dp.total ?? null,
          count: dp.count ?? null,
        });
      }
    }

    // Persist in batches within transactions
    const batches = this.createBatches(allPoints, batchSize);

    for (const batch of batches) {
      try {
        await this.dataSource.transaction(async (manager) => {
          const repo = manager.getRepository(MetricDataPointEntity);

          for (const point of batch) {
            // Upsert: check for existing data point
            const existing = await repo.findOne({
              where: {
                trackedResourceId: point.trackedResourceId,
                metricDefinitionId: point.metricDefinitionId,
                timestamp: point.timestamp,
                timeGrain: point.timeGrain,
              },
            });

            if (existing) {
              existing.average = point.average;
              existing.minimum = point.minimum;
              existing.maximum = point.maximum;
              existing.total = point.total;
              existing.count = point.count;
              await repo.save(existing);
            } else {
              const entity = repo.create(point);
              await repo.save(entity);
            }
          }
        });

        totalPersisted += batch.length;
      } catch (error: unknown) {
        const message = error instanceof Error ? error.message : String(error);
        this.logger.error(`Failed to persist batch of ${batch.length} data points: ${message}`);
      }
    }

    return totalPersisted;
  }

  /**
   * Update lastMetricSync timestamp on tracked resources.
   */
  private async updateLastMetricSync(trackedResourceIds: string[]): Promise<void> {
    if (trackedResourceIds.length === 0) {
      return;
    }

    await this.trackedResourceRepo
      .createQueryBuilder()
      .update()
      .set({ lastMetricSync: new Date() })
      .whereInIds(trackedResourceIds)
      .execute();
  }

  /**
   * Map a string aggregation type to the AggregationType enum.
   */
  mapAggregationType(aggregationType: string): AggregationType {
    const mapping: Record<string, AggregationType> = {
      Average: AggregationType.Average,
      Minimum: AggregationType.Minimum,
      Maximum: AggregationType.Maximum,
      Total: AggregationType.Total,
      Count: AggregationType.Count,
    };
    return mapping[aggregationType] ?? AggregationType.Average;
  }

  /**
   * Map a time grain string to the TimeGrain enum.
   */
  mapTimeGrain(timeGrain: string): TimeGrain {
    const mapping: Record<string, TimeGrain> = {
      PT1M: TimeGrain.PT1M,
      PT5M: TimeGrain.PT5M,
      PT15M: TimeGrain.PT15M,
      PT30M: TimeGrain.PT30M,
      PT1H: TimeGrain.PT1H,
      PT6H: TimeGrain.PT6H,
      PT12H: TimeGrain.PT12H,
      P1D: TimeGrain.P1D,
    };
    return mapping[timeGrain] ?? TimeGrain.PT1H;
  }

  /**
   * Split an array into chunks.
   */
  private createBatches<T>(items: T[], batchSize: number): T[][] {
    const batches: T[][] = [];
    for (let i = 0; i < items.length; i += batchSize) {
      batches.push(items.slice(i, i + batchSize));
    }
    return batches;
  }
}
