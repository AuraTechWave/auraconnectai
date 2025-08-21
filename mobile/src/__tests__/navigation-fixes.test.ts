import { normalizeOrderId, parseOrderId } from '../types/navigation';
import { 
  redactCardNumber, 
  redactPhoneNumber, 
  redactEmail,
  containsSensitiveData 
} from '../utils/privacy';
import { debounce, throttle } from '../utils/performance';

describe('Navigation Type Helpers', () => {
  describe('normalizeOrderId', () => {
    it('should convert number to string', () => {
      expect(normalizeOrderId(123)).toBe('123');
    });

    it('should return string as-is', () => {
      expect(normalizeOrderId('123')).toBe('123');
    });
  });

  describe('parseOrderId', () => {
    it('should parse valid numeric string', () => {
      expect(parseOrderId('123')).toBe(123);
    });

    it('should return null for non-numeric string', () => {
      expect(parseOrderId('abc')).toBeNull();
    });
  });
});

describe('Privacy Utilities', () => {
  describe('redactCardNumber', () => {
    it('should redact card number showing last 4 digits', () => {
      expect(redactCardNumber('1234567890123456')).toBe('**** **** **** 3456');
    });

    it('should handle card numbers with spaces', () => {
      expect(redactCardNumber('1234 5678 9012 3456')).toBe('**** **** **** 3456');
    });
  });

  describe('redactPhoneNumber', () => {
    it('should redact phone number showing last 4 digits', () => {
      expect(redactPhoneNumber('1234567890')).toBe('******7890');
    });

    it('should handle formatted phone numbers', () => {
      expect(redactPhoneNumber('(123) 456-7890')).toBe('******7890');
    });
  });

  describe('redactEmail', () => {
    it('should redact email address', () => {
      expect(redactEmail('john.doe@example.com')).toBe('jo*******@example.com');
    });

    it('should handle short email addresses', () => {
      expect(redactEmail('ab@example.com')).toBe('a*@example.com');
    });
  });

  describe('containsSensitiveData', () => {
    it('should detect credit card patterns', () => {
      expect(containsSensitiveData('My card is 1234567890123456')).toBe(true);
    });

    it('should detect email addresses', () => {
      expect(containsSensitiveData('Contact me at test@example.com')).toBe(true);
    });

    it('should return false for safe text', () => {
      expect(containsSensitiveData('This is safe text')).toBe(false);
    });
  });
});

describe('Performance Utilities', () => {
  beforeEach(() => {
    jest.useFakeTimers();
  });

  afterEach(() => {
    jest.useRealTimers();
  });

  describe('debounce', () => {
    it('should delay function execution', () => {
      const mockFn = jest.fn();
      const debouncedFn = debounce(mockFn, 300);

      debouncedFn('test');
      expect(mockFn).not.toHaveBeenCalled();

      jest.advanceTimersByTime(300);
      expect(mockFn).toHaveBeenCalledWith('test');
    });

    it('should cancel previous calls', () => {
      const mockFn = jest.fn();
      const debouncedFn = debounce(mockFn, 300);

      debouncedFn('first');
      jest.advanceTimersByTime(100);
      debouncedFn('second');
      jest.advanceTimersByTime(300);

      expect(mockFn).toHaveBeenCalledTimes(1);
      expect(mockFn).toHaveBeenCalledWith('second');
    });
  });

  describe('throttle', () => {
    it('should limit function execution', () => {
      const mockFn = jest.fn();
      const throttledFn = throttle(mockFn, 300);

      throttledFn('first');
      throttledFn('second');
      throttledFn('third');

      expect(mockFn).toHaveBeenCalledTimes(1);
      expect(mockFn).toHaveBeenCalledWith('first');

      jest.advanceTimersByTime(300);
      throttledFn('fourth');
      expect(mockFn).toHaveBeenCalledTimes(2);
      expect(mockFn).toHaveBeenCalledWith('fourth');
    });
  });
});