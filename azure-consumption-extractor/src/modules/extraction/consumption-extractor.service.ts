import { Injectable, Logger } from '@nestjs/common';
import { InjectRepository } from '@nestjs/typeorm';
import { Repository, DataSource } from 'typeorm';
import { AzureCostClientService } from '@modules/cost';
import { CostRecord } from '@modules/cost';
import {
  SubscriptionEntity,
  ResourceGroupEntity,
  ConsumptionRecordEntity,
} from '@modules/database';
import {
  ExtractionParams,
  ExtractionResult,
  ExtractionError,
  MappedConsumptionRecord,
} from './interfaces';

/** Default batch size for database inserts. */
const DEFAULT_BATCH_SIZE = 500;

/** Maximum date range span in days per API call to avoid memory issues. */
const MAX_DAYS_PER_CHUNK = 31;

/**
 * Service that orchestrates consumption data extraction from Azure Cost Management API
 * and persists it to the database.
 *
 * Responsibilities:
 * - Fetch cost data from Azure via AzureCostClientService
 * - Map API responses to ConsumptionRecordEntity instances
 * - Ensure subscriptions and resource groups exist (upsert)
 * - Persist records in batches with transaction handling
 * - Support idempotent re-runs (upsert on conflict)
 */
@Injectable()
export class ConsumptionExtractorService {
  private readonly logger = new Logger(ConsumptionExtractorService.name);

  constructor(
    private readonly costClient: AzureCostClientService,
    private readonly dataSource: DataSource,
    @InjectRepository(SubscriptionEntity)
    private readonly subscriptionRepo: Repository<SubscriptionEntity>,
    @InjectRepository(ResourceGroupEntity)
    private readonly resourceGroupRepo: Repository<ResourceGroupEntity>,
  ) {}

  /**
   * Execute a full consumption data extraction for the given parameters.
   *
   * 1. Chunks the date range into manageable periods
   * 2. Fetches cost data grouped by ResourceGroup and MeterCategory
   * 3. Ensures subscription and resource group entities exist
   * 4. Maps and persists consumption records in batches
   *
   * @param params - Extraction parameters (date range, subscription, batch size)
   * @returns Extraction result with counts and timing
   */
  async extract(params: ExtractionParams): Promise<ExtractionResult> {
    const startTime = Date.now();
    const batchSize = params.batchSize ?? DEFAULT_BATCH_SIZE;
    const errors: ExtractionError[] = [];

    let totalFetched = 0;
    let totalPersisted = 0;
    let totalInserted = 0;
    let totalUpdated = 0;
    let batchesProcessed = 0;

    this.logger.log(
      `Starting extraction: ${params.startDate.toISOString()} to ${params.endDate.toISOString()}` +
        `${params.subscriptionId ? ` for subscription ${params.subscriptionId}` : ''}`,
    );

    // Chunk the date range to avoid large API responses
    const dateChunks = this.chunkDateRange(params.startDate, params.endDate);
    this.logger.log(`Date range split into ${dateChunks.length} chunk(s)`);

    for (const chunk of dateChunks) {
      try {
        // Fetch cost data grouped by ResourceGroup and MeterCategory
        const result = await this.costClient.queryCostData({
          startDate: chunk.start,
          endDate: chunk.end,
          subscriptionId: params.subscriptionId,
          granularity: 'Daily',
          groupBy: ['ResourceGroup', 'MeterCategory'],
        });

        totalFetched += result.totalRecords;
        this.logger.log(
          `Fetched ${result.totalRecords} records for ` +
            `${chunk.start.toISOString()} to ${chunk.end.toISOString()}`,
        );

        if (result.records.length === 0) {
          continue;
        }

        // Map API records to intermediate format
        const mapped = this.mapCostRecords(result.records, params.subscriptionId ?? '');

        // Ensure subscription exists
        const subscription = await this.ensureSubscription(params.subscriptionId ?? '');

        // Ensure resource groups exist and build a lookup map
        const rgNames = [...new Set(mapped.map((r) => r.resourceGroupName).filter(Boolean))];
        const rgMap = await this.ensureResourceGroups(rgNames, subscription.id);

        // Persist in batches
        const batches = this.createBatches(mapped, batchSize);
        for (const batch of batches) {
          try {
            const { inserted, updated } = await this.persistBatch(batch, subscription.id, rgMap);
            totalInserted += inserted;
            totalUpdated += updated;
            totalPersisted += batch.length;
            batchesProcessed++;
          } catch (error) {
            const message = error instanceof Error ? error.message : String(error);
            this.logger.error(`Failed to persist batch: ${message}`);
            errors.push({
              phase: 'persist',
              message,
              recordsAffected: batch.length,
            });
          }
        }
      } catch (error) {
        const message = error instanceof Error ? error.message : String(error);
        this.logger.error(
          `Failed to fetch data for chunk ` +
            `${chunk.start.toISOString()} to ${chunk.end.toISOString()}: ${message}`,
        );
        errors.push({
          phase: 'fetch',
          message,
        });
      }
    }

    const durationMs = Date.now() - startTime;
    const result: ExtractionResult = {
      recordsFetched: totalFetched,
      recordsPersisted: totalPersisted,
      recordsUpdated: totalUpdated,
      recordsInserted: totalInserted,
      batchesProcessed,
      durationMs,
      errors,
    };

    this.logger.log(
      `Extraction complete: ${totalPersisted} records persisted ` +
        `(${totalInserted} inserted, ${totalUpdated} updated) ` +
        `in ${durationMs}ms with ${errors.length} error(s)`,
    );

    return result;
  }

  /**
   * Map raw CostRecord objects from the API to intermediate MappedConsumptionRecord format.
   */
  mapCostRecords(records: CostRecord[], subscriptionId: string): MappedConsumptionRecord[] {
    return records.map((record) => ({
      subscriptionId,
      resourceGroupName: record.groupings['ResourceGroup'] || 'unknown',
      usageDate: this.parseUsageDate(record.usageDate),
      cost: record.cost,
      currency: record.currency,
      resourceGroup: record.groupings['ResourceGroup'],
      meterCategory: record.groupings['MeterCategory'],
      serviceName: record.groupings['ServiceName'],
      resourceType: record.groupings['ResourceType'],
    }));
  }

  /**
   * Ensure a subscription entity exists in the database.
   * Creates it if not found (upsert by subscriptionId).
   */
  private async ensureSubscription(subscriptionId: string): Promise<SubscriptionEntity> {
    let subscription = await this.subscriptionRepo.findOne({
      where: { subscriptionId },
    });

    if (!subscription) {
      this.logger.log(`Creating subscription record for ${subscriptionId}`);
      subscription = this.subscriptionRepo.create({
        subscriptionId,
        displayName: subscriptionId, // Will be updated when we have ARM metadata
        state: 'Enabled',
      });
      subscription = await this.subscriptionRepo.save(subscription);
    }

    return subscription;
  }

  /**
   * Ensure all required resource group entities exist.
   * Returns a map of resource group name → entity ID.
   */
  private async ensureResourceGroups(
    names: string[],
    subscriptionEntityId: string,
  ): Promise<Map<string, string>> {
    const rgMap = new Map<string, string>();

    for (const name of names) {
      let rg = await this.resourceGroupRepo.findOne({
        where: { name, subscriptionId: subscriptionEntityId },
      });

      if (!rg) {
        rg = this.resourceGroupRepo.create({
          name,
          subscriptionId: subscriptionEntityId,
        });
        rg = await this.resourceGroupRepo.save(rg);
      }

      rgMap.set(name, rg.id);
    }

    return rgMap;
  }

  /**
   * Persist a batch of mapped records using a database transaction.
   *
   * Uses upsert (ON CONFLICT) to handle idempotent re-runs:
   * if a record with the same subscription, resource group, usage date,
   * and meter category already exists, it gets updated.
   */
  private async persistBatch(
    batch: MappedConsumptionRecord[],
    subscriptionEntityId: string,
    rgMap: Map<string, string>,
  ): Promise<{ inserted: number; updated: number }> {
    let inserted = 0;
    let updated = 0;

    await this.dataSource.transaction(async (manager) => {
      const repo = manager.getRepository(ConsumptionRecordEntity);

      for (const record of batch) {
        const resourceGroupId = rgMap.get(record.resourceGroupName);
        if (!resourceGroupId) {
          continue;
        }

        // Check for existing record (idempotent upsert)
        const existing = await repo.findOne({
          where: {
            subscriptionId: subscriptionEntityId,
            resourceGroupId,
            usageDate: record.usageDate,
            meterCategory: record.meterCategory ?? undefined,
          },
        });

        if (existing) {
          // Update existing record
          existing.effectiveCost = record.cost;
          existing.billingCurrency = record.currency;
          if (record.meterCategory) existing.meterCategory = record.meterCategory;
          if (record.serviceName) existing.serviceName = record.serviceName;
          if (record.resourceType) existing.resourceType = record.resourceType;
          await repo.save(existing);
          updated++;
        } else {
          // Insert new record
          const entity = repo.create({
            subscriptionId: subscriptionEntityId,
            resourceGroupId,
            usageDate: record.usageDate,
            effectiveCost: record.cost,
            billingCurrency: record.currency,
            meterCategory: record.meterCategory,
            serviceName: record.serviceName,
            resourceType: record.resourceType,
          });
          await repo.save(entity);
          inserted++;
        }
      }
    });

    return { inserted, updated };
  }

  /**
   * Split a date range into chunks of MAX_DAYS_PER_CHUNK days.
   */
  chunkDateRange(startDate: Date, endDate: Date): Array<{ start: Date; end: Date }> {
    const chunks: Array<{ start: Date; end: Date }> = [];
    let current = new Date(startDate);

    while (current < endDate) {
      const chunkEnd = new Date(current);
      chunkEnd.setDate(chunkEnd.getDate() + MAX_DAYS_PER_CHUNK);

      chunks.push({
        start: new Date(current),
        end: chunkEnd > endDate ? new Date(endDate) : chunkEnd,
      });

      current = new Date(chunkEnd);
      current.setDate(current.getDate() + 1);
    }

    // Edge case: if start === end, ensure we have one chunk
    if (chunks.length === 0) {
      chunks.push({ start: new Date(startDate), end: new Date(endDate) });
    }

    return chunks;
  }

  /**
   * Parse Azure usage date (YYYYMMDD number) into a Date object.
   */
  parseUsageDate(usageDate: number | null): Date {
    if (!usageDate) {
      return new Date();
    }

    const dateStr = String(usageDate);
    const year = parseInt(dateStr.substring(0, 4), 10);
    const month = parseInt(dateStr.substring(4, 6), 10) - 1;
    const day = parseInt(dateStr.substring(6, 8), 10);
    return new Date(Date.UTC(year, month, day));
  }

  /**
   * Split an array into batches of a given size.
   */
  private createBatches<T>(items: T[], batchSize: number): T[][] {
    const batches: T[][] = [];
    for (let i = 0; i < items.length; i += batchSize) {
      batches.push(items.slice(i, i + batchSize));
    }
    return batches;
  }
}
