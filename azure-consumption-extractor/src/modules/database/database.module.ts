import { Module } from '@nestjs/common';
import { TypeOrmModule } from '@nestjs/typeorm';
import { ConfigModule, ConfigService } from '@nestjs/config';
import { databaseConfig } from '@config/index';
import { SubscriptionEntity } from './entities/subscription.entity';
import { ResourceGroupEntity } from './entities/resource-group.entity';
import { ConsumptionRecordEntity } from './entities/consumption-record.entity';

const entities = [SubscriptionEntity, ResourceGroupEntity, ConsumptionRecordEntity];

/**
 * Database module for the Azure Consumption Extractor.
 *
 * Configures TypeORM connection to PostgreSQL using the `finops` schema
 * and registers all entities needed for consumption data extraction.
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
