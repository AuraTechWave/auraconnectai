import { NotificationErrorHandler } from '../NotificationErrorHandler';
import { logger } from '@utils/logger';
import { showToast } from '@utils/toast';
import { NOTIFICATION_CONFIG } from '@constants/config';

jest.mock('@utils/logger');
jest.mock('@utils/toast');

describe('NotificationErrorHandler', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    jest.useFakeTimers();
  });

  afterEach(() => {
    jest.useRealTimers();
  });

  describe('withRetry', () => {
    it('should return result on successful operation', async () => {
      const operation = jest.fn().mockResolvedValue('success');
      
      const result = await NotificationErrorHandler.withRetry(operation);
      
      expect(result).toBe('success');
      expect(operation).toHaveBeenCalledTimes(1);
    });

    it('should retry on failure with exponential backoff', async () => {
      const operation = jest.fn()
        .mockRejectedValueOnce(new Error('Fail 1'))
        .mockRejectedValueOnce(new Error('Fail 2'))
        .mockResolvedValue('success');
      
      const onRetry = jest.fn();
      
      const promise = NotificationErrorHandler.withRetry(operation, {
        maxRetries: 3,
        retryDelay: 1000,
        onRetry,
      });

      // First attempt fails immediately
      await jest.advanceTimersByTimeAsync(0);
      expect(operation).toHaveBeenCalledTimes(1);

      // Second attempt after 1000ms
      await jest.advanceTimersByTimeAsync(1000);
      expect(operation).toHaveBeenCalledTimes(2);
      expect(onRetry).toHaveBeenCalledWith(1);

      // Third attempt after 2000ms (exponential backoff)
      await jest.advanceTimersByTimeAsync(2000);
      expect(operation).toHaveBeenCalledTimes(3);
      expect(onRetry).toHaveBeenCalledWith(2);

      const result = await promise;
      expect(result).toBe('success');
    });

    it('should return null after all retries fail', async () => {
      const error = new Error('Always fails');
      const operation = jest.fn().mockRejectedValue(error);
      const onError = jest.fn();
      
      const promise = NotificationErrorHandler.withRetry(operation, {
        maxRetries: 2,
        retryDelay: 100,
        onError,
      });

      // Advance through all retries
      await jest.advanceTimersByTimeAsync(0);    // First attempt
      await jest.advanceTimersByTimeAsync(100);  // Second attempt
      await jest.advanceTimersByTimeAsync(200);  // Third attempt

      const result = await promise;
      
      expect(result).toBeNull();
      expect(operation).toHaveBeenCalledTimes(3);
      expect(onError).toHaveBeenCalledWith(error);
    });

    it('should use default config values', async () => {
      const operation = jest.fn().mockRejectedValue(new Error('Fail'));
      
      const promise = NotificationErrorHandler.withRetry(operation);
      
      // Advance through all default retries
      for (let i = 0; i <= NOTIFICATION_CONFIG.TOKEN_MAX_RETRIES; i++) {
        await jest.advanceTimersByTimeAsync(
          NOTIFICATION_CONFIG.TOKEN_RETRY_DELAY * Math.pow(2, i)
        );
      }

      await promise;
      
      expect(operation).toHaveBeenCalledTimes(NOTIFICATION_CONFIG.TOKEN_MAX_RETRIES + 1);
    });
  });

  describe('handleTokenRegistrationError', () => {
    it('should log error without showing user toast in production', () => {
      const originalDev = __DEV__;
      (global as any).__DEV__ = false;
      
      const error = new Error('Token registration failed');
      NotificationErrorHandler.handleTokenRegistrationError(error);
      
      expect(logger.error).toHaveBeenCalledWith('FCM token registration failed', error);
      expect(showToast).not.toHaveBeenCalled();
      
      (global as any).__DEV__ = originalDev;
    });

    it('should show warning toast in development', () => {
      const originalDev = __DEV__;
      (global as any).__DEV__ = true;
      
      const error = new Error('Token registration failed');
      NotificationErrorHandler.handleTokenRegistrationError(error);
      
      expect(logger.error).toHaveBeenCalledWith('FCM token registration failed', error);
      expect(showToast).toHaveBeenCalledWith(
        'warning',
        'Notification Setup',
        'Push notifications may be delayed'
      );
      
      (global as any).__DEV__ = originalDev;
    });
  });

  describe('handleNotificationError', () => {
    it('should log error with context', () => {
      const error = new Error('Test error');
      NotificationErrorHandler.handleNotificationError(error, 'testContext');
      
      expect(logger.error).toHaveBeenCalledWith('Notification error in testContext', error);
    });

    it('should show toast for critical errors', () => {
      const error = new Error('PERMISSION_DENIED: User denied permission');
      NotificationErrorHandler.handleNotificationError(error);
      
      expect(showToast).toHaveBeenCalledWith(
        'error',
        'Notification Error',
        'Some notifications may not work properly'
      );
    });

    it('should not show toast for non-critical errors', () => {
      const error = new Error('Network timeout');
      NotificationErrorHandler.handleNotificationError(error);
      
      expect(logger.error).toHaveBeenCalled();
      expect(showToast).not.toHaveBeenCalled();
    });
  });

  describe('handlePermissionDenied', () => {
    it('should log warning and show info toast', () => {
      NotificationErrorHandler.handlePermissionDenied();
      
      expect(logger.warn).toHaveBeenCalledWith('Notification permission denied');
      expect(showToast).toHaveBeenCalledWith(
        'info',
        'Notifications Disabled',
        'Enable notifications in settings to receive order updates'
      );
    });
  });

  describe('sanitizeErrorForLogging', () => {
    it('should remove tokens from error messages', () => {
      const error = {
        message: 'Failed with token: abc123def456ghi789jkl012mno345pqr678stu901vwx234yz567890abcdefghijklmnopqrstuvwxyz1234567890',
        stack: 'Error at line with token abc123def456ghi789jkl012mno345pqr678stu901vwx234yz567890abcdefghijklmnopqrstuvwxyz1234567890',
      };
      
      const sanitized = NotificationErrorHandler.sanitizeErrorForLogging(error);
      
      expect(sanitized.message).toBe('Failed with token: [REDACTED]');
      expect(sanitized.stack).toContain('[TOKEN_REDACTED]');
      expect(sanitized.stack).not.toContain('abc123def456');
    });

    it('should handle null error', () => {
      expect(NotificationErrorHandler.sanitizeErrorForLogging(null)).toBeNull();
      expect(NotificationErrorHandler.sanitizeErrorForLogging(undefined)).toBeUndefined();
    });

    it('should handle errors without message or stack', () => {
      const error = { code: 'ERROR_CODE' };
      const sanitized = NotificationErrorHandler.sanitizeErrorForLogging(error);
      
      expect(sanitized.code).toBe('ERROR_CODE');
    });
  });
});