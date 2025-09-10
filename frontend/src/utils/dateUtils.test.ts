import { toISOString, formatDate, getDateRange } from './dateUtils';

describe('dateUtils', () => {
  describe('toISOString', () => {
    test('converts Date object to ISO string', () => {
      const date = new Date('2024-01-15T10:30:00Z');
      const result = toISOString(date);
      expect(result).toBe('2024-01-15T10:30:00.000Z');
    });

    test('converts valid date string to ISO string', () => {
      const dateStr = '2024-01-15';
      const result = toISOString(dateStr);
      expect(result).toContain('2024-01-15');
    });

    test('returns undefined for undefined input', () => {
      const result = toISOString(undefined);
      expect(result).toBeUndefined();
    });

    test('returns undefined for invalid date string', () => {
      const result = toISOString('invalid-date');
      expect(result).toBeUndefined();
    });
  });

  describe('formatDate', () => {
    test('formats Date object with default format', () => {
      const date = new Date('2024-01-15T10:30:00Z');
      const result = formatDate(date);
      expect(result).toBe('2024-01-15');
    });

    test('formats Date object with custom format', () => {
      const date = new Date('2024-01-15T10:30:00Z');
      const result = formatDate(date, 'MM/dd/yyyy');
      expect(result).toBe('01/15/2024');
    });

    test('formats date string with default format', () => {
      const dateStr = '2024-01-15T10:30:00Z';
      const result = formatDate(dateStr);
      expect(result).toBe('2024-01-15');
    });

    test('formats date string with custom format', () => {
      const dateStr = '2024-01-15T10:30:00Z';
      const result = formatDate(dateStr, 'dd MMM yyyy');
      expect(result).toBe('15 Jan 2024');
    });

    test('returns empty string for invalid date', () => {
      const result = formatDate('invalid-date');
      expect(result).toBe('');
    });
  });

  describe('getDateRange', () => {
    test('returns start and end of day for date range', () => {
      const startDate = new Date('2024-01-15T14:30:00Z');
      const endDate = new Date('2024-01-20T09:15:00Z');
      
      const result = getDateRange(startDate, endDate);
      
      // Check that start is at beginning of day
      expect(result.start).toContain('T00:00:00');
      
      // Check that end is at end of day
      expect(result.end).toContain('T23:59:59');
      
      // Check dates are correct
      const startResult = new Date(result.start);
      const endResult = new Date(result.end);
      
      expect(startResult.getDate()).toBe(15);
      expect(endResult.getDate()).toBe(20);
    });

    test('handles same day range', () => {
      const date = new Date('2024-01-15T14:30:00Z');
      const result = getDateRange(date, date);
      
      const startResult = new Date(result.start);
      const endResult = new Date(result.end);
      
      expect(startResult.getDate()).toBe(endResult.getDate());
      expect(result.start).toContain('T00:00:00');
      expect(result.end).toContain('T23:59:59');
    });
  });
});