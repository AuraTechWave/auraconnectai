import { logger } from '@utils/logger';
import { showToast } from '@utils/toast';
import { NOTIFICATION_CONFIG } from '@constants/config';

export interface RetryOptions {
  maxRetries?: number;
  retryDelay?: number;
  onRetry?: (attempt: number) => void;
  onError?: (error: Error) => void;
}

export class NotificationErrorHandler {
  static async withRetry<T>(
    operation: () => Promise<T>,
    options: RetryOptions = {},
  ): Promise<T | null> {
    const {
      maxRetries = NOTIFICATION_CONFIG.TOKEN_MAX_RETRIES,
      retryDelay = NOTIFICATION_CONFIG.TOKEN_RETRY_DELAY,
      onRetry,
      onError,
    } = options;

    let lastError: Error | null = null;

    for (let attempt = 0; attempt <= maxRetries; attempt++) {
      try {
        return await operation();
      } catch (error) {
        lastError = error as Error;
        logger.warn(
          `Operation failed, attempt ${attempt + 1}/${maxRetries + 1}`,
          error,
        );

        if (attempt < maxRetries) {
          onRetry?.(attempt + 1);
          await this.delay(retryDelay * Math.pow(2, attempt)); // Exponential backoff
        }
      }
    }

    // All retries failed
    if (onError && lastError) {
      onError(lastError);
    }

    return null;
  }

  static handleTokenRegistrationError(error: Error): void {
    logger.error('FCM token registration failed', error);

    // Don't show user-facing error for token registration
    // as it might recover on next app launch
    if (__DEV__) {
      showToast(
        'warning',
        'Notification Setup',
        'Push notifications may be delayed',
      );
    }
  }

  static handleNotificationError(error: Error, context?: string): void {
    logger.error(`Notification error ${context ? `in ${context}` : ''}`, error);

    // Only show user-facing errors for critical failures
    if (this.isCriticalError(error)) {
      showToast(
        'error',
        'Notification Error',
        'Some notifications may not work properly',
      );
    }
  }

  static handlePermissionDenied(): void {
    logger.warn('Notification permission denied');
    showToast(
      'info',
      'Notifications Disabled',
      'Enable notifications in settings to receive order updates',
    );
  }

  private static isCriticalError(error: Error): boolean {
    // Define what constitutes a critical error
    const criticalMessages = [
      'PERMISSION_DENIED',
      'INVALID_TOKEN',
      'SERVICE_NOT_AVAILABLE',
    ];

    return criticalMessages.some(msg =>
      error.message?.toUpperCase().includes(msg),
    );
  }

  private static delay(ms: number): Promise<void> {
    return new Promise(resolve => setTimeout(resolve, ms));
  }

  static sanitizeErrorForLogging(error: any): any {
    if (!error) return error;

    // Remove sensitive data from errors
    const sanitized = { ...error };

    // Remove tokens from error messages
    if (sanitized.message) {
      sanitized.message = sanitized.message.replace(
        /token:\s*[^\s]+/gi,
        'token: [REDACTED]',
      );
    }

    // Remove FCM tokens from stack traces
    if (sanitized.stack) {
      sanitized.stack = sanitized.stack.replace(
        /[a-zA-Z0-9_-]{100,}/g,
        '[TOKEN_REDACTED]',
      );
    }

    return sanitized;
  }
}
