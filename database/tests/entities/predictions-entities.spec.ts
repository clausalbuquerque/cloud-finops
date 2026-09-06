import { CostForecastEntity } from '../../src/entities/cost-forecast.entity';
import { CostAnomalyEntity } from '../../src/entities/cost-anomaly.entity';

describe('Predictions Entities', () => {
  describe('CostForecastEntity', () => {
    it('should create a valid CostForecastEntity instance', () => {
      const forecast = new CostForecastEntity();
      forecast.id = 'b1b2b3b4-c5c6-7d8e-9f0a-1b2c3d4e5f6a';
      forecast.dimension = 'service:Compute';
      forecast.providerName = 'Google';
      forecast.forecastDate = new Date('2026-08-31');
      forecast.expectedCost = 1450.5;
      forecast.lowerBound = 1380.0;
      forecast.upperBound = 1520.0;
      forecast.confidenceLevel = 0.95;
      forecast.modelName = 'ridge_seasonal';
      forecast.mape = 0.042;
      forecast.generatedAt = new Date();

      expect(forecast.id).toBeDefined();
      expect(forecast.dimension).toBe('service:Compute');
      expect(forecast.expectedCost).toBe(1450.5);
      expect(forecast.mape).toBe(0.042);
    });
  });

  describe('CostAnomalyEntity', () => {
    it('should create a valid CostAnomalyEntity instance', () => {
      const anomaly = new CostAnomalyEntity();
      anomaly.id = 'a1a2a3a4-b5b6-7c8d-9e0f-1a2b3c4d5e6f';
      anomaly.anomalyId = 'anom-20260815-analytics-worker-02';
      anomaly.providerName = 'Google';
      anomaly.resourceId =
        'projects/prod-analytics/zones/us-central1-a/instances/analytics-worker-02';
      anomaly.dimension = 'resourceId';
      anomaly.dimensionValue = 'analytics-worker-02';
      anomaly.detectedDate = new Date('2026-08-15');
      anomaly.actualCost = 284.5;
      anomaly.expectedCost = 142.25;
      anomaly.costDelta = 142.25;
      anomaly.percentageDelta = 100.0;
      anomaly.zScore = 4.2;
      anomaly.severity = 'critical';
      anomaly.anomalyType = 'spike';
      anomaly.status = 'detected';
      anomaly.details = { root_cause: 'upsize to n2-standard-16' };

      expect(anomaly.anomalyId).toBe('anom-20260815-analytics-worker-02');
      expect(anomaly.severity).toBe('critical');
      expect(anomaly.percentageDelta).toBe(100.0);
      expect(anomaly.details).toEqual({ root_cause: 'upsize to n2-standard-16' });
    });
  });
});
