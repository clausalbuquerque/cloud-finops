import { Module } from '@nestjs/common';
import { ConfigModule } from '@nestjs/config';
import { azureConfig } from '@config/index';
import { AzureResourceClientService } from './azure-resource-client.service';
import { AzureMonitorClientService } from './azure-monitor-client.service';
import { UtilizationMetricsRegistry } from './utilization-metrics-registry.service';

/**
 * Module for Azure Monitor metrics collection.
 *
 * Provides three injectable services:
 * - AzureResourceClientService — discover resources via ARM
 * - AzureMonitorClientService — query metric data from Azure Monitor
 * - UtilizationMetricsRegistry — registry of target utilization metrics per resource type
 */
@Module({
  imports: [ConfigModule.forFeature(azureConfig)],
  providers: [AzureResourceClientService, AzureMonitorClientService, UtilizationMetricsRegistry],
  exports: [AzureResourceClientService, AzureMonitorClientService, UtilizationMetricsRegistry],
})
export class MetricsModule {}
