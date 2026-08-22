/**
 * Cloud FinOps Database
 *
 * Barrel export for all shared entities and the DataSource configuration.
 * Consumer projects should import from this file.
 */
export { default as AppDataSource, dataSourceOptions } from './data-source';
export * from './entities';
