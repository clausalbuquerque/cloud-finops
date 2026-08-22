import { Module } from '@nestjs/common';
import { ConfigModule } from '@nestjs/config';
import { CostModule } from '@modules/cost';
import { DatabaseModule } from '@modules/database';
import { ExtractionModule } from '@modules/extraction';
import { azureConfig, databaseConfig } from '@config/index';

@Module({
  imports: [
    ConfigModule.forRoot({
      isGlobal: true,
      envFilePath: '.env',
      load: [azureConfig, databaseConfig],
    }),
    DatabaseModule,
    CostModule,
    ExtractionModule,
  ],
  controllers: [],
  providers: [],
})
export class AppModule {}
