import { Module } from '@nestjs/common';
import { ConfigModule } from '@nestjs/config';
import { AzureCostClientService } from './azure-cost-client.service';
import { azureConfig } from '@config/index';

@Module({
  imports: [ConfigModule.forFeature(azureConfig)],
  providers: [AzureCostClientService],
  exports: [AzureCostClientService],
})
export class CostModule {}
