import {
  OptimizationRecommendationEntity,
  AnomalyResolutionEntity,
  InfrastructureBaselineEntity,
  AgentInteractionMemoryEntity,
} from '../../src/entities';

describe('Agent Memory Entities', () => {
  describe('OptimizationRecommendationEntity', () => {
    it('should instantiate with default and custom values', () => {
      const entity = new OptimizationRecommendationEntity();
      entity.id = 'b9b329a1-7789-4d6b-9519-74d119c83693';
      entity.providerName = 'GCP';
      entity.resourceId = 'projects/prod-123/zones/us-central1-a/instances/worker-01';
      entity.resourceType = 'compute/instance';
      entity.recommendationType = 'rightsize';
      entity.currentState = { sku: 'n2-standard-8', monthlyCost: 284.5 };
      entity.proposedState = { sku: 'n2-standard-4', estimatedMonthlyCost: 142.25 };
      entity.estimatedMonthlySavings = 142.25;
      entity.actualMonthlySavings = null;
      entity.confidenceScore = 0.95;
      entity.sreAssessment = { safeToModify: true, dependencies: [] };
      entity.status = 'proposed';
      entity.scopeTeam = 'data-platform';
      entity.flowId = 'flow-abc-123';
      entity.proposedAt = new Date('2026-08-22T00:00:00Z');

      expect(entity.id).toBe('b9b329a1-7789-4d6b-9519-74d119c83693');
      expect(entity.providerName).toBe('GCP');
      expect(entity.resourceId).toBe('projects/prod-123/zones/us-central1-a/instances/worker-01');
      expect(entity.recommendationType).toBe('rightsize');
      expect(entity.estimatedMonthlySavings).toBe(142.25);
      expect(entity.confidenceScore).toBe(0.95);
      expect(entity.sreAssessment?.safeToModify).toBe(true);
      expect(entity.status).toBe('proposed');
      expect(entity.scopeTeam).toBe('data-platform');
      expect(entity.flowId).toBe('flow-abc-123');
    });
  });

  describe('AnomalyResolutionEntity', () => {
    it('should instantiate with default and custom values', () => {
      const entity = new AnomalyResolutionEntity();
      entity.id = 'c1c329a1-7789-4d6b-9519-74d119c83694';
      entity.anomalyId = 'anom-20260822-01';
      entity.providerName = 'GCP';
      entity.resourceId = 'projects/prod-123/zones/us-central1-a/instances/worker-01';
      entity.dimension = 'serviceCategory';
      entity.rootCauseType = 'sku_change';
      entity.rootCauseDescription = 'Instance was upgraded from n2-standard-4 to n2-standard-8';
      entity.resolutionAction = 'reverted';
      entity.isRecurring = false;
      entity.recurrenceCount = 1;
      entity.investigationTrace = { steps: 4, toolsCalled: ['query_cost_by_service'] };
      entity.resolvedBy = 'claus';

      expect(entity.anomalyId).toBe('anom-20260822-01');
      expect(entity.rootCauseType).toBe('sku_change');
      expect(entity.resolutionAction).toBe('reverted');
      expect(entity.isRecurring).toBe(false);
      expect(entity.recurrenceCount).toBe(1);
      expect(entity.resolvedBy).toBe('claus');
    });
  });

  describe('InfrastructureBaselineEntity', () => {
    it('should instantiate with default and custom values', () => {
      const entity = new InfrastructureBaselineEntity();
      entity.id = 'd2d329a1-7789-4d6b-9519-74d119c83695';
      entity.resourceId = 'projects/prod-123/zones/us-central1-a/instances/batch-worker';
      entity.providerName = 'GCP';
      entity.metricName = 'cpu_utilization';
      entity.baselineType = 'workload_pattern';
      entity.expectedPattern = {
        schedule: 'weekday_nights',
        expectedUtilization: { low: 5, high: 85 },
        description: 'Nightly batch processing',
      };
      entity.suppressUnderuseAlerts = true;
      entity.confidenceScore = 0.98;
      entity.establishedBy = 'user_confirmed';

      expect(entity.metricName).toBe('cpu_utilization');
      expect(entity.baselineType).toBe('workload_pattern');
      expect(entity.suppressUnderuseAlerts).toBe(true);
      expect(entity.confidenceScore).toBe(0.98);
      expect(entity.establishedBy).toBe('user_confirmed');
    });
  });

  describe('AgentInteractionMemoryEntity', () => {
    it('should instantiate with default and custom values', () => {
      const entity = new AgentInteractionMemoryEntity();
      entity.id = 'e3e329a1-7789-4d6b-9519-74d119c83696';
      entity.sessionId = 'session-123';
      entity.userId = 'user-456';
      entity.agentType = 'finops';
      entity.interactionSummary = 'Discussed compute cost spike in prod-analytics';
      entity.keyFindings = { totalSpikeUsd: 450.0, topResource: 'worker-01' };
      entity.scopeContext = { team: 'data-platform', provider: 'GCP' };

      expect(entity.sessionId).toBe('session-123');
      expect(entity.userId).toBe('user-456');
      expect(entity.agentType).toBe('finops');
      expect(entity.interactionSummary).toContain('prod-analytics');
      expect(entity.keyFindings?.totalSpikeUsd).toBe(450.0);
    });
  });
});
