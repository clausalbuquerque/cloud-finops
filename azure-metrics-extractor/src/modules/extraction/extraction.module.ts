import { Module } from '@nestjs/common';
import { ConfigModule } from '@nestjs/config';
import { DatabaseModule } from '@modules/database';
import { MetricsModule } from '@modules/metrics';
import { underuseThresholdsConfig } from '@config/index';
import { MetricsExtractorService } from './metrics-extractor.service';
import { UtilizationSummaryService } from './utilization-summary.service';

/**
 * Module for metrics extraction and utilization summary computation.
 *
 * Orchestrates the full pipeline:
 * - MetricsExtractorService: discover → sync → fetch → persist
 * - UtilizationSummaryService: aggregate → threshold → flag underuse
 */
@Module({
  imports: [ConfigModule.forFeature(underuseThresholdsConfig), DatabaseModule, MetricsModule],
  providers: [MetricsExtractorService, UtilizationSummaryService],
  exports: [MetricsExtractorService, UtilizationSummaryService],
})
export class ExtractionModule {}
