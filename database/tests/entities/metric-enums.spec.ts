import { MetricUnit, AggregationType, TimeGrain } from '../../src/entities/enums';

describe('MetricUnit Enum', () => {
  it('should have all expected unit values', () => {
    const expectedValues = [
      'Count',
      'Bytes',
      'Seconds',
      'CountPerSecond',
      'BytesPerSecond',
      'Percent',
      'MilliSeconds',
      'ByteSeconds',
      'Cores',
      'MilliCores',
      'NanoCores',
      'BitsPerSecond',
      'Unspecified',
    ];

    const actualValues = Object.values(MetricUnit);
    expect(actualValues).toEqual(expect.arrayContaining(expectedValues));
    expect(actualValues).toHaveLength(expectedValues.length);
  });

  it('should have string values matching the Azure Monitor specification', () => {
    expect(MetricUnit.Count).toBe('Count');
    expect(MetricUnit.Bytes).toBe('Bytes');
    expect(MetricUnit.Percent).toBe('Percent');
    expect(MetricUnit.Cores).toBe('Cores');
    expect(MetricUnit.Unspecified).toBe('Unspecified');
  });

  it('should include byte-rate units', () => {
    expect(MetricUnit.BytesPerSecond).toBe('BytesPerSecond');
    expect(MetricUnit.BitsPerSecond).toBe('BitsPerSecond');
    expect(MetricUnit.ByteSeconds).toBe('ByteSeconds');
  });

  it('should include sub-core granularity units', () => {
    expect(MetricUnit.MilliCores).toBe('MilliCores');
    expect(MetricUnit.NanoCores).toBe('NanoCores');
  });
});

describe('AggregationType Enum', () => {
  it('should have all expected aggregation values', () => {
    const expectedValues = ['Average', 'Minimum', 'Maximum', 'Total', 'Count', 'None'];

    const actualValues = Object.values(AggregationType);
    expect(actualValues).toEqual(expect.arrayContaining(expectedValues));
    expect(actualValues).toHaveLength(expectedValues.length);
  });

  it('should have string values matching Azure Monitor aggregation types', () => {
    expect(AggregationType.Average).toBe('Average');
    expect(AggregationType.Minimum).toBe('Minimum');
    expect(AggregationType.Maximum).toBe('Maximum');
    expect(AggregationType.Total).toBe('Total');
    expect(AggregationType.Count).toBe('Count');
    expect(AggregationType.None).toBe('None');
  });
});

describe('TimeGrain Enum', () => {
  it('should have all expected ISO 8601 duration values', () => {
    const expectedValues = ['PT1M', 'PT5M', 'PT15M', 'PT30M', 'PT1H', 'PT6H', 'PT12H', 'P1D'];

    const actualValues = Object.values(TimeGrain);
    expect(actualValues).toEqual(expect.arrayContaining(expectedValues));
    expect(actualValues).toHaveLength(expectedValues.length);
  });

  it('should use ISO 8601 duration format', () => {
    // Minutes
    expect(TimeGrain.PT1M).toBe('PT1M');
    expect(TimeGrain.PT5M).toBe('PT5M');
    expect(TimeGrain.PT15M).toBe('PT15M');
    expect(TimeGrain.PT30M).toBe('PT30M');

    // Hours
    expect(TimeGrain.PT1H).toBe('PT1H');
    expect(TimeGrain.PT6H).toBe('PT6H');
    expect(TimeGrain.PT12H).toBe('PT12H');

    // Days
    expect(TimeGrain.P1D).toBe('P1D');
  });

  it('should have values ordered from finest to coarsest grain', () => {
    const grainOrder = [
      TimeGrain.PT1M,
      TimeGrain.PT5M,
      TimeGrain.PT15M,
      TimeGrain.PT30M,
      TimeGrain.PT1H,
      TimeGrain.PT6H,
      TimeGrain.PT12H,
      TimeGrain.P1D,
    ];

    expect(Object.values(TimeGrain)).toEqual(grainOrder);
  });
});
