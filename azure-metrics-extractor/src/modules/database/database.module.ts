import { Module } from '@nestjs/common';
import { TypeOrmModule } from '@nestjs/typeorm';
import { ConfigModule, ConfigService } from '@nestjs/config';
import { databaseConfig } from '@config/index';
import { SubscriptionEntity } from './entities/subscription.entity';
import { ResourceGroupEntity } from './entities/resource-group.entity';
import { TrackedResourceEntity } from './entities/tracked-resource.entity';
import { MetricDefinitionEntity } from './entities/metric-definition.entity';
import { MetricDataPointEntity } from './entities/metric-data-point.entity';
import { UtilizationSummaryEntity } from './entities/utilization-summary.entity';

const entities = [
  SubscriptionEntity,
  ResourceGroupEntity,
  TrackedResourceEntity,
  MetricDefinitionEntity,
  MetricDataPointEntity,
  UtilizationSummaryEntity,
];

/**
 * Database module for the Azure Metrics Extractor.
 *
 * Configures TypeORM connection to PostgreSQL using the `finops` schema
 * and registers all entities needed for metrics data extraction and storage.
 *
 * Entity definitions mirror the shared `database` package schema.
 * Migrations are managed exclusively by the `database` project.
 */
@Module({
  imports: [
    ConfigModule.forFeature(databaseConfig),
    TypeOrmModule.forRootAsync({
      imports: [ConfigModule],
      inject: [ConfigService],
      useFactory: (configService: ConfigService) => ({
        type: 'postgres' as const,
        host: configService.get<string>('database.host', 'localhost'),
        port: configService.get<number>('database.port', 5432),
        username: configService.get<string>('database.username', 'postgres'),
        password: configService.get<string>('database.password', ''),
        database: configService.get<string>('database.database', 'cloud_finops'),
        schema: configService.get<string>('database.schema', 'finops'),
        synchronize: false,
        logging: configService.get<boolean>('database.logging', false),
        entities,
      }),
    }),
    TypeOrmModule.forFeature(entities),
  ],
  exports: [TypeOrmModule],
})
export class DatabaseModule {}
