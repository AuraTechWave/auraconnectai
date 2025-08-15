import { logger } from '@utils/logger';
import { showToast } from '@utils/toast';
import { SyncError, SyncErrorCode } from '@types/sync.types';

export class SyncErrorHandler {
  private static readonly ERROR_MESSAGES: Record<SyncErrorCode, string> = {
    SYNC_NETWORK_ERROR:
      'Network connection lost. Changes will sync when online.',
    SYNC_AUTH_ERROR: 'Authentication failed. Please log in again.',
    SYNC_SERVER_ERROR: 'Server error occurred. Please try again later.',
    SYNC_CLIENT_ERROR: 'Local data error. Please contact support.',
    SYNC_CONFLICT_ERROR: 'Data conflicts detected. Manual resolution required.',
    SYNC_QUEUE_FULL: 'Too many pending changes. Please sync before continuing.',
    SYNC_INVALID_DATA: 'Invalid data detected. Please check your entries.',
  };

  private static readonly RETRY_DELAYS: Record<SyncErrorCode, number> = {
    SYNC_NETWORK_ERROR: 5000,
    SYNC_AUTH_ERROR: 0, // Don't retry auth errors
    SYNC_SERVER_ERROR: 30000,
    SYNC_CLIENT_ERROR: 0,
    SYNC_CONFLICT_ERROR: 0,
    SYNC_QUEUE_FULL: 10000,
    SYNC_INVALID_DATA: 0,
  };

  static createError(
    code: SyncErrorCode,
    message?: string,
    details?: Record<string, any>,
  ): SyncError {
    const error: SyncError = {
      code,
      message: message || this.ERROR_MESSAGES[code],
      details,
      retryable: this.isRetryable(code),
      retryAfter: this.RETRY_DELAYS[code],
    };

    logger.error('Sync error created', error);
    return error;
  }

  static handleError(error: any): SyncError {
    // Network errors
    if (error.code === 'NETWORK_ERROR' || !navigator.onLine) {
      return this.createError('SYNC_NETWORK_ERROR');
    }

    // Auth errors
    if (error.response?.status === 401 || error.response?.status === 403) {
      return this.createError('SYNC_AUTH_ERROR', error.response?.data?.message);
    }

    // Server errors
    if (error.response?.status >= 500) {
      return this.createError(
        'SYNC_SERVER_ERROR',
        error.response?.data?.message,
        { status: error.response.status },
      );
    }

    // Client errors
    if (error.response?.status >= 400) {
      return this.createError(
        'SYNC_CLIENT_ERROR',
        error.response?.data?.message,
        { status: error.response.status },
      );
    }

    // Default error
    return this.createError(
      'SYNC_CLIENT_ERROR',
      error.message || 'An unexpected error occurred',
    );
  }

  static isRetryable(code: SyncErrorCode): boolean {
    return [
      'SYNC_NETWORK_ERROR',
      'SYNC_SERVER_ERROR',
      'SYNC_QUEUE_FULL',
    ].includes(code);
  }

  static async showErrorToUser(error: SyncError): Promise<void> {
    const toastType = error.retryable ? 'warning' : 'error';
    const title = error.retryable ? 'Sync Issue' : 'Sync Failed';

    showToast(toastType, title, error.message);
  }

  static async recoverFromError(error: SyncError): Promise<boolean> {
    switch (error.code) {
      case 'SYNC_NETWORK_ERROR':
        // Will automatically retry when network is available
        return true;

      case 'SYNC_AUTH_ERROR':
        // Trigger re-authentication
        // TODO: Implement re-auth flow
        return false;

      case 'SYNC_QUEUE_FULL':
        // Try to clean up old queue items
        logger.info('Attempting to clean up sync queue');
        // TODO: Implement queue cleanup
        return true;

      case 'SYNC_CONFLICT_ERROR':
        // Navigate to conflict resolution screen
        // TODO: Implement conflict resolution UI
        return false;

      default:
        return false;
    }
  }

  static formatErrorForLogging(error: SyncError): string {
    return `[${error.code}] ${error.message}${
      error.details ? ` - Details: ${JSON.stringify(error.details)}` : ''
    }`;
  }

  static createErrorReport(errors: SyncError[]): {
    summary: string;
    byCode: Record<SyncErrorCode, number>;
    retryableCount: number;
  } {
    const byCode = errors.reduce(
      (acc, error) => {
        acc[error.code] = (acc[error.code] || 0) + 1;
        return acc;
      },
      {} as Record<SyncErrorCode, number>,
    );

    const retryableCount = errors.filter(e => e.retryable).length;

    return {
      summary: `${errors.length} sync errors (${retryableCount} retryable)`,
      byCode,
      retryableCount,
    };
  }
}
