import { QueryRunner } from 'typeorm';
import { AddPredictionsSchema1732656400000 } from '../../migrations/1732656400000-AddPredictionsSchema';

describe('AddPredictionsSchema1732656400000 Migration', () => {
  let migration: AddPredictionsSchema1732656400000;
  let mockQueryRunner: Partial<QueryRunner>;
  let executedQueries: string[];

  beforeEach(() => {
    executedQueries = [];
    mockQueryRunner = {
      query: jest.fn().mockImplementation(async (query: string) => {
        executedQueries.push(query);
        return [];
      }),
    };
    migration = new AddPredictionsSchema1732656400000();
  });

  it('should have the correct migration name', () => {
    expect(migration.name).toBe('AddPredictionsSchema1732656400000');
  });

  it('should create cost_forecasts and cost_anomalies tables on up()', async () => {
    await migration.up(mockQueryRunner as QueryRunner);

    const hasForecastsTable = executedQueries.some((q) =>
      q.includes('CREATE TABLE "finops"."cost_forecasts"'),
    );
    const hasAnomaliesTable = executedQueries.some((q) =>
      q.includes('CREATE TABLE "finops"."cost_anomalies"'),
    );
    const hasForecastIndex = executedQueries.some((q) =>
      q.includes('IDX_cost_forecasts_dimension_forecast_date'),
    );
    const hasAnomalyIndex = executedQueries.some((q) =>
      q.includes('IDX_cost_anomalies_dim_val_date'),
    );

    expect(hasForecastsTable).toBe(true);
    expect(hasAnomaliesTable).toBe(true);
    expect(hasForecastIndex).toBe(true);
    expect(hasAnomalyIndex).toBe(true);
  });

  it('should drop cost_anomalies and cost_forecasts tables on down()', async () => {
    await migration.down(mockQueryRunner as QueryRunner);

    const hasDropAnomaliesTable = executedQueries.some((q) =>
      q.includes('DROP TABLE "finops"."cost_anomalies"'),
    );
    const hasDropForecastsTable = executedQueries.some((q) =>
      q.includes('DROP TABLE "finops"."cost_forecasts"'),
    );

    expect(hasDropAnomaliesTable).toBe(true);
    expect(hasDropForecastsTable).toBe(true);
  });
});
