import { registerAs } from '@nestjs/config';

/**
 * Configurable underuse thresholds per metric type.
 *
 * Defaults per TASK-011 specification:
 * - CPU: avg < 10% → underused
 * - Memory: avg < 20% → underused
 * - DTU/RU: avg < 15% → underused
 * - Storage: used < 10% of provisioned → underused
 *
 * Override via environment variables with prefix UNDERUSE_THRESHOLD_.
 */
export interface UnderuseThresholdsConfig {
  /** CPU utilization threshold (percentage). */
  cpu: number;
  /** Memory utilization threshold (percentage). */
  memory: number;
  /** DTU consumption threshold (percentage). */
  dtu: number;
  /** RU consumption threshold (percentage). */
  ru: number;
  /** Storage utilization threshold (percentage). */
  storage: number;
  /** Default threshold for any metric not explicitly configured. */
  default: number;
}

export default registerAs(
  'underuseThresholds',
  (): UnderuseThresholdsConfig => ({
    cpu: parseFloat(process.env.UNDERUSE_THRESHOLD_CPU || '10'),
    memory: parseFloat(process.env.UNDERUSE_THRESHOLD_MEMORY || '20'),
    dtu: parseFloat(process.env.UNDERUSE_THRESHOLD_DTU || '15'),
    ru: parseFloat(process.env.UNDERUSE_THRESHOLD_RU || '15'),
    storage: parseFloat(process.env.UNDERUSE_THRESHOLD_STORAGE || '10'),
    default: parseFloat(process.env.UNDERUSE_THRESHOLD_DEFAULT || '10'),
  }),
);
