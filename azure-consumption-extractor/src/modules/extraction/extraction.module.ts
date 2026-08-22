import { Module } from '@nestjs/common';
import { CostModule } from '@modules/cost';
import { DatabaseModule } from '@modules/database';
import { ConsumptionExtractorService } from './consumption-extractor.service';

/**
 * Module for consumption data extraction from Azure Cost Management.
 *
 * Wires together the Azure Cost Client (for API calls), the Database module
 * (for TypeORM repositories), and the ConsumptionExtractorService (orchestration).
 */
@Module({
  imports: [CostModule, DatabaseModule],
  providers: [ConsumptionExtractorService],
  exports: [ConsumptionExtractorService],
})
export class ExtractionModule {}
