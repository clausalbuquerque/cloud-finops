/**
 * Entity barrel export.
 *
 * All entity classes should be re-exported from here.
 */

// Enums
export { MetricUnit, AggregationType, TimeGrain } from './enums';

// Core entities
export { SubscriptionEntity } from './subscription.entity';
export { ResourceGroupEntity } from './resource-group.entity';
export { ConsumptionRecordEntity } from './consumption-record.entity';

// Metrics entities
export { TrackedResourceEntity } from './tracked-resource.entity';
export { MetricDefinitionEntity } from './metric-definition.entity';
export { MetricDataPointEntity } from './metric-data-point.entity';
export { UtilizationSummaryEntity } from './utilization-summary.entity';

// Knowledge base retrieval entities
export { KbDocumentEntity } from './kb-document.entity';
export { KbChunkEntity } from './kb-chunk.entity';
export { KbEmbeddingEntity } from './kb-embedding.entity';
export { KbIngestionRunEntity } from './kb-ingestion-run.entity';

// Agent long-term memory entities
export { OptimizationRecommendationEntity } from './optimization-recommendation.entity';
export { AnomalyResolutionEntity } from './anomaly-resolution.entity';
export { InfrastructureBaselineEntity } from './infrastructure-baseline.entity';
export { AgentInteractionMemoryEntity } from './agent-interaction-memory.entity';

// Predictions entities
export { CostForecastEntity } from './cost-forecast.entity';
export {
  CostAnomalyEntity,
  AnomalySeverity,
  AnomalyType,
  AnomalyStatus,
} from './cost-anomaly.entity';
