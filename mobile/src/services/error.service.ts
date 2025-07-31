import { AxiosError } from 'axios';
import { showToast } from '@utils/toast';

export interface AppError {
  code: string;
  message: string;
  details?: any;
  statusCode?: number;
}

export type ErrorHandler = (error: AppError) => void;

class ErrorService {
  private errorHandlers: Map<string, ErrorHandler[]> = new Map();
  private globalHandlers: ErrorHandler[] = [];

  /**
   * Register a global error handler
   */
  registerGlobalHandler(handler: ErrorHandler): () => void {
    this.globalHandlers.push(handler);
    return () => {
      this.globalHandlers = this.globalHandlers.filter(h => h !== handler);
    };
  }

  /**
   * Register an error handler for specific error codes
   */
  registerHandler(errorCode: string, handler: ErrorHandler): () => void {
    const handlers = this.errorHandlers.get(errorCode) || [];
    handlers.push(handler);
    this.errorHandlers.set(errorCode, handlers);

    return () => {
      const updatedHandlers = (this.errorHandlers.get(errorCode) || []).filter(
        h => h !== handler,
      );
      if (updatedHandlers.length > 0) {
        this.errorHandlers.set(errorCode, updatedHandlers);
      } else {
        this.errorHandlers.delete(errorCode);
      }
    };
  }

  /**
   * Handle API errors from Axios
   */
  handleApiError(error: AxiosError): AppError {
    let appError: AppError;

    if (!error.response) {
      // Network error
      if (error.message === 'No internet connection') {
        appError = {
          code: 'NETWORK_OFFLINE',
          message: 'No internet connection',
          details: error,
        };
      } else {
        appError = {
          code: 'NETWORK_ERROR',
          message: 'Network error occurred',
          details: error,
        };
      }
    } else {
      // Server error
      const { status, data } = error.response;
      
      switch (status) {
        case 400:
          appError = {
            code: 'BAD_REQUEST',
            message: data.detail || 'Invalid request',
            statusCode: status,
            details: data,
          };
          break;
        case 401:
          appError = {
            code: 'UNAUTHORIZED',
            message: 'Authentication required',
            statusCode: status,
            details: data,
          };
          break;
        case 403:
          appError = {
            code: 'FORBIDDEN',
            message: 'You do not have permission',
            statusCode: status,
            details: data,
          };
          break;
        case 404:
          appError = {
            code: 'NOT_FOUND',
            message: 'Resource not found',
            statusCode: status,
            details: data,
          };
          break;
        case 429:
          appError = {
            code: 'RATE_LIMITED',
            message: 'Too many requests',
            statusCode: status,
            details: data,
          };
          break;
        case 500:
        case 502:
        case 503:
          appError = {
            code: 'SERVER_ERROR',
            message: 'Server error occurred',
            statusCode: status,
            details: data,
          };
          break;
        default:
          appError = {
            code: 'UNKNOWN_ERROR',
            message: data.detail || 'An error occurred',
            statusCode: status,
            details: data,
          };
      }
    }

    this.notifyHandlers(appError);
    return appError;
  }

  /**
   * Handle generic errors
   */
  handleError(error: Error | AppError): AppError {
    let appError: AppError;

    if ('code' in error && 'message' in error) {
      appError = error as AppError;
    } else {
      appError = {
        code: 'APP_ERROR',
        message: error.message || 'An error occurred',
        details: error,
      };
    }

    this.notifyHandlers(appError);
    return appError;
  }

  /**
   * Show error toast (can be disabled by specific handlers)
   */
  showErrorToast(error: AppError, options?: { silent?: boolean }) {
    if (options?.silent) return;

    const title = this.getErrorTitle(error.code);
    showToast('error', title, error.message);
  }

  /**
   * Notify all relevant handlers
   */
  private notifyHandlers(error: AppError) {
    // Notify specific handlers
    const specificHandlers = this.errorHandlers.get(error.code) || [];
    specificHandlers.forEach(handler => handler(error));

    // Notify global handlers
    this.globalHandlers.forEach(handler => handler(error));
  }

  /**
   * Get user-friendly error title
   */
  private getErrorTitle(code: string): string {
    const titles: Record<string, string> = {
      NETWORK_OFFLINE: 'Offline',
      NETWORK_ERROR: 'Connection Error',
      BAD_REQUEST: 'Invalid Request',
      UNAUTHORIZED: 'Authentication Error',
      FORBIDDEN: 'Access Denied',
      NOT_FOUND: 'Not Found',
      RATE_LIMITED: 'Too Many Requests',
      SERVER_ERROR: 'Server Error',
      APP_ERROR: 'Application Error',
      UNKNOWN_ERROR: 'Error',
    };

    return titles[code] || 'Error';
  }

  /**
   * Check if error is recoverable
   */
  isRecoverableError(error: AppError): boolean {
    const recoverableCodes = [
      'NETWORK_ERROR',
      'NETWORK_OFFLINE',
      'SERVER_ERROR',
      'RATE_LIMITED',
    ];
    return recoverableCodes.includes(error.code);
  }

  /**
   * Check if error requires reauthentication
   */
  isAuthError(error: AppError): boolean {
    return error.code === 'UNAUTHORIZED' || error.statusCode === 401;
  }
}

export const errorService = new ErrorService();