import { debounce } from './debounce';

describe('debounce', () => {
  beforeEach(() => {
    jest.useFakeTimers();
  });

  afterEach(() => {
    jest.clearAllTimers();
    jest.useRealTimers();
  });

  test('delays function execution', () => {
    const mockFn = jest.fn();
    const debouncedFn = debounce(mockFn, 100);

    debouncedFn('test');
    
    // Function should not be called immediately
    expect(mockFn).not.toHaveBeenCalled();
    
    // Fast-forward time by 100ms
    jest.advanceTimersByTime(100);
    
    // Function should now be called
    expect(mockFn).toHaveBeenCalledTimes(1);
    expect(mockFn).toHaveBeenCalledWith('test');
  });

  test('cancels previous calls when called multiple times', () => {
    const mockFn = jest.fn();
    const debouncedFn = debounce(mockFn, 100);

    debouncedFn('first');
    jest.advanceTimersByTime(50);
    debouncedFn('second');
    jest.advanceTimersByTime(50);
    debouncedFn('third');
    
    // Function should not be called yet
    expect(mockFn).not.toHaveBeenCalled();
    
    jest.advanceTimersByTime(100);
    
    // Function should only be called once with the last argument
    expect(mockFn).toHaveBeenCalledTimes(1);
    expect(mockFn).toHaveBeenCalledWith('third');
  });

  test('preserves multiple arguments', () => {
    const mockFn = jest.fn();
    const debouncedFn = debounce(mockFn, 100);

    debouncedFn('arg1', 'arg2', 'arg3');
    
    jest.advanceTimersByTime(100);
    
    expect(mockFn).toHaveBeenCalledWith('arg1', 'arg2', 'arg3');
  });

  test('handles different delay values', () => {
    const mockFn = jest.fn();
    const shortDebounce = debounce(mockFn, 50);
    const longDebounce = debounce(mockFn, 200);

    shortDebounce('short');
    longDebounce('long');
    
    jest.advanceTimersByTime(50);
    expect(mockFn).toHaveBeenCalledTimes(1);
    expect(mockFn).toHaveBeenCalledWith('short');
    
    jest.advanceTimersByTime(150);
    expect(mockFn).toHaveBeenCalledTimes(2);
    expect(mockFn).toHaveBeenCalledWith('long');
  });

  test('works with functions that return values', () => {
    const mockFn = jest.fn().mockReturnValue('result');
    const debouncedFn = debounce(mockFn, 100);

    const result = debouncedFn();
    
    // Note: debounced functions don't return values synchronously
    expect(result).toBeUndefined();
    
    jest.advanceTimersByTime(100);
    
    expect(mockFn).toHaveBeenCalled();
  });

  test('handles rapid successive calls', () => {
    const mockFn = jest.fn();
    const debouncedFn = debounce(mockFn, 100);

    // Simulate rapid calls
    for (let i = 0; i < 10; i++) {
      debouncedFn(i);
      jest.advanceTimersByTime(10);
    }
    
    // Function should not be called yet
    expect(mockFn).not.toHaveBeenCalled();
    
    // Advance past the debounce delay
    jest.advanceTimersByTime(100);
    
    // Should only be called once with the last value
    expect(mockFn).toHaveBeenCalledTimes(1);
    expect(mockFn).toHaveBeenCalledWith(9);
  });
});