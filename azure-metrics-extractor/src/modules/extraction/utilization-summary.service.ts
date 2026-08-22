import { Injectable, Logger } from '@nestjs/common';
import { InjectRepository } from '@nestjs/typeorm';
import { Repository, Between } from 'typeorm';
import { ConfigService } from '@nestjs/config';
import { UtilizationMetricsRegistry } from '@modules/metrics/utilization-metrics-registry.service';
import {
  TrackedResourceEntity,
  MetricDefinitionEntity,
  MetricDataPointEntity,
  UtilizationSummaryEntity,
  TimeGrain,
} from '@modules/database';
import {
  UtilizationSummaryParams,
  UtilizationSummaryResult,
  MetricsExtractionError,
} from './interfaces';

/**
 * Service for computing daily utilization summaries from raw metric data points.
 *
 * For each tracked resource and each utilization metric, this service:
 * - Aggregates raw data points into daily summaries (avg, min, max, p95)
 * - Applies configurable underuse thresholds to flag underutilized resources
 * - Upserts summaries to avoid duplicates on re-runs
 *
 * Underuse thresholds are configurable via environment variables:
 * - UNDERUSE_THRESHOLD_CPU (default: 10%)
 * - UNDERUSE_THRESHOLD_MEMORY (default: 20%)
 * - UNDERUSE_THRESHOLD_DTU (default: 15%)
 * - UNDERUSE_THRESHOLD_RU (default: 15%)
 * - UNDERUSE_THRESHOLD_STORAGE (default: 10%)
 * - UNDERUSE_THRESHOLD_DEFAULT (default: 10%)
 */
@Injectable()
export class UtilizationSummaryService {
  private readonly logger = new Logger(UtilizationSummaryService.name);

  constructor(
    private readonly configService: ConfigService,
    private readonly metricsRegistry: UtilizationMetricsRegistry,
    @InjectRepository(TrackedResourceEntity)
    private readonly trackedResourceRepo: Repository<TrackedResourceEntity>,
    @InjectRepository(MetricDefinitionEntity)
    private readonly metricDefRepo: Repository<MetricDefinitionEntity>,
    @InjectRepository(MetricDataPointEntity)
    private readonly dataPointRepo: Repository<MetricDataPointEntity>,
    @InjectRepository(UtilizationSummaryEntity)
    private readonly summaryRepo: Repository<UtilizationSummaryEntity>,
  ) {}

  /**
   * Compute utilization summaries for the given time range.
   */
  async computeSummaries(params: UtilizationSummaryParams): Promise<UtilizationSummaryResult> {
    const startTime = Date.now();
    const errors: MetricsExtractionError[] = [];
    let summariesComputed = 0;
    let summariesPersisted = 0;
    let resourcesFlaggedUnderused = 0;

    this.logger.log(
      `Computing utilization summaries: ${params.startDate.toISOString()} to ${params.endDate.toISOString()}`,
    );

    // Find tracked resources to process
    const resources = await this.findTrackedResources(params);
    this.logger.log(`Processing ${resources.length} tracked resources`);

    for (const resource of resources) {
      try {
        // Get utilization metric definitions for this resource type
        const utilizationMetrics = this.metricsRegistry.getUtilizationMetrics(
          resource.resourceType,
        );

        if (utilizationMetrics.length === 0) {
          continue;
        }

        // Find the metric definitions in DB
        const metricDefs = await this.metricDefRepo.find({
          where: {
            resourceType: resource.resourceType,
            isUtilizationMetric: true,
          },
        });

        for (const metricDef of metricDefs) {
          const registryConfig = utilizationMetrics.find(
            (m) => m.metricName === metricDef.metricName,
          );
          if (!registryConfig) {
            continue;
          }

          // Get data points for this resource and metric in the date range
          const dataPoints = await this.dataPointRepo.find({
            where: {
              trackedResourceId: resource.id,
              metricDefinitionId: metricDef.id,
              timestamp: Between(params.startDate, params.endDate),
            },
            order: { timestamp: 'ASC' },
          });

          if (dataPoints.length === 0) {
            continue;
          }

          // Group data points by day
          const dailyGroups = this.groupByDay(dataPoints);

          for (const [dateStr, dayPoints] of dailyGroups) {
            const summary = this.computeDailySummary(
              resource,
              metricDef,
              dayPoints,
              dateStr,
              registryConfig.underuseThreshold,
            );

            summariesComputed++;

            // Upsert the summary
            const persisted = await this.upsertSummary(summary);
            if (persisted) {
              summariesPersisted++;
              if (persisted.isUnderused) {
                resourcesFlaggedUnderused++;
              }
            }
          }
        }
      } catch (error: unknown) {
        const message = error instanceof Error ? error.message : String(error);
        this.logger.error(
          `Failed to compute summaries for ${resource.azureResourceId}: ${message}`,
        );
        errors.push({
          phase: 'persist',
          message,
          resourceContext: resource.azureResourceId,
        });
      }
    }

    const durationMs = Date.now() - startTime;
    const result: UtilizationSummaryResult = {
      summariesComputed,
      summariesPersisted,
      resourcesFlaggedUnderused,
      durationMs,
      errors,
    };

    this.logger.log(
      `Summary computation complete: ${summariesComputed} computed, ` +
        `${summariesPersisted} persisted, ${resourcesFlaggedUnderused} flagged underused ` +
        `in ${durationMs}ms with ${errors.length} error(s)`,
    );

    return result;
  }

  /**
   * Compute a daily summary for a resource and metric.
   */
  computeDailySummary(
    resource: TrackedResourceEntity,
    metricDef: MetricDefinitionEntity,
    dataPoints: MetricDataPointEntity[],
    dateStr: string,
    registryThreshold?: number,
  ): {
    trackedResourceId: string;
    summaryDate: Date;
    metricName: string;
    avgUtilization: number;
    maxUtilization: number;
    minUtilization: number;
    p95Utilization: number | null;
    sampleCount: number;
    timeGrain: TimeGrain;
    isUnderused: boolean;
    underuseThreshold: number | null;
  } {
    const values = dataPoints
      .map((dp) => dp.average)
      .filter((v): v is number => v !== null && v !== undefined);

    const avg = values.length > 0 ? values.reduce((a, b) => a + b, 0) / values.length : 0;
    const max = values.length > 0 ? Math.max(...values) : 0;
    const min = values.length > 0 ? Math.min(...values) : 0;
    const p95 = values.length > 0 ? this.computePercentile(values, 95) : null;

    // Determine threshold: config overrides > registry defaults > global default
    const threshold = this.resolveThreshold(metricDef.metricName, registryThreshold);
    const isUnderused = values.length > 0 && avg < threshold;

    return {
      trackedResourceId: resource.id,
      summaryDate: new Date(dateStr),
      metricName: metricDef.metricName,
      avgUtilization: Math.round(avg * 1000) / 1000,
      maxUtilization: Math.round(max * 1000) / 1000,
      minUtilization: Math.round(min * 1000) / 1000,
      p95Utilization: p95 !== null ? Math.round(p95 * 1000) / 1000 : null,
      sampleCount: values.length,
      timeGrain: dataPoints[0]?.timeGrain ?? TimeGrain.PT1H,
      isUnderused,
      underuseThreshold: threshold,
    };
  }

  /**
   * Resolve the underuse threshold for a metric, checking config overrides first.
   */
  resolveThreshold(metricName: string, registryThreshold?: number): number {
    const lowerName = metricName.toLowerCase();

    // Check config overrides by metric category
    if (lowerName.includes('cpu')) {
      return this.configService.get<number>('underuseThresholds.cpu', registryThreshold ?? 10);
    }
    if (lowerName.includes('memory') || lowerName.includes('mem')) {
      return this.configService.get<number>('underuseThresholds.memory', registryThreshold ?? 20);
    }
    if (lowerName.includes('dtu')) {
      return this.configService.get<number>('underuseThresholds.dtu', registryThreshold ?? 15);
    }
    if (lowerName.includes('ru') && lowerName.includes('request')) {
      return this.configService.get<number>('underuseThresholds.ru', registryThreshold ?? 15);
    }
    if (lowerName.includes('storage') || lowerName.includes('capacity')) {
      return this.configService.get<number>('underuseThresholds.storage', registryThreshold ?? 10);
    }

    // Fall back to registry threshold or global default
    return registryThreshold ?? this.configService.get<number>('underuseThresholds.default', 10);
  }

  /**
   * Compute a percentile value from a sorted array.
   */
  computePercentile(values: number[], percentile: number): number {
    const sorted = [...values].sort((a, b) => a - b);
    const index = (percentile / 100) * (sorted.length - 1);
    const lower = Math.floor(index);
    const upper = Math.ceil(index);

    if (lower === upper) {
      return sorted[lower];
    }

    const fraction = index - lower;
    return sorted[lower] + fraction * (sorted[upper] - sorted[lower]);
  }

  /**
   * Group data points by day (YYYY-MM-DD).
   */
  groupByDay(dataPoints: MetricDataPointEntity[]): Map<string, MetricDataPointEntity[]> {
    const groups = new Map<string, MetricDataPointEntity[]>();

    for (const dp of dataPoints) {
      const dateStr = dp.timestamp.toISOString().substring(0, 10);
      const existing = groups.get(dateStr);
      if (existing) {
        existing.push(dp);
      } else {
        groups.set(dateStr, [dp]);
      }
    }

    return groups;
  }

  /**
   * Upsert a utilization summary record.
   */
  private async upsertSummary(summary: {
    trackedResourceId: string;
    summaryDate: Date;
    metricName: string;
    avgUtilization: number;
    maxUtilization: number;
    minUtilization: number;
    p95Utilization: number | null;
    sampleCount: number;
    timeGrain: TimeGrain;
    isUnderused: boolean;
    underuseThreshold: number | null;
  }): Promise<UtilizationSummaryEntity | null> {
    try {
      let existing = await this.summaryRepo.findOne({
        where: {
          trackedResourceId: summary.trackedResourceId,
          summaryDate: summary.summaryDate,
          metricName: summary.metricName,
        },
      });

      if (existing) {
        existing.avgUtilization = summary.avgUtilization;
        existing.maxUtilization = summary.maxUtilization;
        existing.minUtilization = summary.minUtilization;
        existing.p95Utilization = summary.p95Utilization;
        existing.sampleCount = summary.sampleCount;
        existing.timeGrain = summary.timeGrain;
        existing.isUnderused = summary.isUnderused;
        existing.underuseThreshold = summary.underuseThreshold;
        existing = await this.summaryRepo.save(existing);
        return existing;
      }

      const entity = this.summaryRepo.create(summary);
      return await this.summaryRepo.save(entity);
    } catch (error: unknown) {
      const message = error instanceof Error ? error.message : String(error);
      this.logger.error(
        `Failed to upsert summary for ${summary.trackedResourceId} ` +
          `on ${summary.summaryDate}: ${message}`,
      );
      return null;
    }
  }

  /**
   * Find tracked resources matching the filter criteria.
   */
  private async findTrackedResources(
    params: UtilizationSummaryParams,
  ): Promise<TrackedResourceEntity[]> {
    const queryBuilder = this.trackedResourceRepo
      .createQueryBuilder('tr')
      .where('tr.is_active = :isActive', { isActive: true });

    if (params.trackedResourceIds && params.trackedResourceIds.length > 0) {
      queryBuilder.andWhere('tr.id IN (:...ids)', { ids: params.trackedResourceIds });
    }

    if (params.resourceTypes && params.resourceTypes.length > 0) {
      queryBuilder.andWhere('tr.resource_type IN (:...types)', {
        types: params.resourceTypes,
      });
    }

    return queryBuilder.getMany();
  }
}
