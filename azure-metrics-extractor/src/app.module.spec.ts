import { AppModule } from './app.module';

describe('AppModule', () => {
  it('should be defined', () => {
    expect(AppModule).toBeDefined();
  });

  it('should be a valid NestJS module (decorated class)', () => {
    const metadata = Reflect.getMetadata('imports', AppModule);
    expect(metadata).toBeDefined();
    expect(Array.isArray(metadata)).toBe(true);
    expect(metadata.length).toBeGreaterThanOrEqual(4);
  });
});
