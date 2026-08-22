import { dataSourceOptions } from './data-source';

describe('DataSource Configuration', () => {
  it('should have postgres as the database type', () => {
    expect(dataSourceOptions.type).toBe('postgres');
  });

  it('should have synchronize disabled by default', () => {
    expect(dataSourceOptions.synchronize).toBe(false);
  });

  it('should have entities path configured', () => {
    expect(dataSourceOptions.entities).toBeDefined();
    expect(Array.isArray(dataSourceOptions.entities)).toBe(true);
  });

  it('should have migrations path configured', () => {
    expect(dataSourceOptions.migrations).toBeDefined();
    expect(Array.isArray(dataSourceOptions.migrations)).toBe(true);
  });

  it('should have a migrations table name', () => {
    expect(dataSourceOptions.migrationsTableName).toBe('typeorm_migrations');
  });
});
