import { Module } from '@nestjs/common';
import { ConfigModule } from '@nestjs/config';
import { MetricsModule } from '@modules/metrics';
import { DatabaseModule } from '@modules/database';
import { ExtractionModule } from '@modules/extraction';
import { azureConfig, databaseConfig, underuseThresholdsConfig } from '@config/index';

@Module({
  imports: [
    ConfigModule.forRoot({
      isGlobal: true,
      envFilePath: '.env',
      load: [azureConfig, databaseConfig, underuseThresholdsConfig],
    }),
    MetricsModule,
    DatabaseModule,
    ExtractionModule,
  ],
  controllers: [],
  providers: [],
})
export class AppModule {}
