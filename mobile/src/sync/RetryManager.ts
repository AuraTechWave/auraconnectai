import { logger } from '@utils/logger';
import { SYNC_CONFIG } from '@constants/config';
import { NetworkStateManager } from './NetworkStateManager';

export interface RetryOptions {
  maxAttempts?: number;
  baseDelay?: number;
  maxDelay?: number;
  backoffFactor?: number;
  jitter?: boolean;
  retryOnNetworkError?: boolean;
  retryCondition?: (error: any) => boolean;
  onRetryAttempt?: (attempt: number, delay: number, error: any) => void;
}

export interface RetryResult<T> {
  success: boolean;
  data?: T;
  error?: any;
  attempts: number;
  totalDelay: number;
}

interface RetryState {
  attempts: number;
  totalDelay: number;
  lastError: any;
  startTime: number;
}

export class RetryManager {
  private static instance: RetryManager;
  private networkManager: NetworkStateManager;
  private activeRetries: Map<string, RetryState> = new Map();

  private constructor() {
    this.networkManager = NetworkStateManager.getInstance();
  }

  static getInstance(): RetryManager {
    if (!RetryManager.instance) {
      RetryManager.instance = new RetryManager();
    }
    return RetryManager.instance;
  }

  async retry<T>(
    operation: () => Promise<T>,
    options?: RetryOptions,
    operationId?: string,
  ): Promise<RetryResult<T>> {
    const config = this.mergeOptions(options);
    const id = operationId || this.generateOperationId();

    const state: RetryState = {
      attempts: 0,
      totalDelay: 0,
      lastError: null,
      startTime: Date.now(),
    };

    this.activeRetries.set(id, state);

    try {
      while (state.attempts < config.maxAttempts!) {
        state.attempts++;

        try {
          // Check network state before attempting
          if (config.retryOnNetworkError && !this.networkManager.isOnline()) {
            logger.debug(
              `Retry ${id}: Waiting for network connection (attempt ${state.attempts})`,
            );
            const connected =
              await this.networkManager.waitForConnection(10000);
            if (!connected) {
              throw new Error('Network unavailable');
            }
          }

          // Execute the operation
          const result = await operation();

          // Success!
          logger.debug(
            `Retry ${id}: Operation succeeded on attempt ${state.attempts}`,
          );
          return {
            success: true,
            data: result,
            attempts: state.attempts,
            totalDelay: state.totalDelay,
          };
        } catch (error) {
          state.lastError = error;

          // Check if we should retry
          if (!this.shouldRetry(error, config, state)) {
            logger.warn(`Retry ${id}: Not retrying after error`, {
              attempt: state.attempts,
              error,
            });
            break;
          }

          // Check if we have more attempts
          if (state.attempts >= config.maxAttempts!) {
            logger.error(`Retry ${id}: Max attempts reached`, {
              attempts: state.attempts,
              error,
            });
            break;
          }

          // Calculate delay with exponential backoff
          const delay = this.calculateDelay(state.attempts, config);
          state.totalDelay += delay;

          // Notify callback if provided
          if (config.onRetryAttempt) {
            config.onRetryAttempt(state.attempts, delay, error);
          }

          logger.debug(
            `Retry ${id}: Waiting ${delay}ms before attempt ${state.attempts + 1}`,
            {
              error: error instanceof Error ? error.message : error,
            },
          );

          // Wait before next attempt
          await this.delay(delay);
        }
      }

      // All attempts failed
      return {
        success: false,
        error: state.lastError,
        attempts: state.attempts,
        totalDelay: state.totalDelay,
      };
    } finally {
      this.activeRetries.delete(id);
    }
  }

  async retryWithCircuitBreaker<T>(
    operation: () => Promise<T>,
    options?: RetryOptions & {
      circuitBreakerThreshold?: number;
      circuitBreakerTimeout?: number;
    },
  ): Promise<RetryResult<T>> {
    const threshold = options?.circuitBreakerThreshold || 5;
    const timeout = options?.circuitBreakerTimeout || 60000;

    // Check if circuit is open
    const circuitKey = `circuit_${operation.toString()}`;
    const circuitState = this.getCircuitState(circuitKey);

    if (circuitState.isOpen) {
      const elapsed = Date.now() - circuitState.openedAt;
      if (elapsed < timeout) {
        return {
          success: false,
          error: new Error('Circuit breaker is open'),
          attempts: 0,
          totalDelay: 0,
        };
      }
      // Half-open state - allow one attempt
      this.resetCircuit(circuitKey);
    }

    const result = await this.retry(operation, options);

    // Update circuit state
    if (!result.success) {
      circuitState.failures++;
      if (circuitState.failures >= threshold) {
        this.openCircuit(circuitKey);
      }
    } else {
      this.resetCircuit(circuitKey);
    }

    return result;
  }

  private calculateDelay(attempt: number, config: RetryOptions): number {
    const { baseDelay, maxDelay, backoffFactor, jitter } = config;

    // Calculate exponential backoff
    let delay = Math.min(
      baseDelay! * Math.pow(backoffFactor!, attempt - 1),
      maxDelay!,
    );

    // Add jitter if enabled
    if (jitter) {
      const jitterAmount = delay * 0.2; // 20% jitter
      delay = delay + (Math.random() * jitterAmount * 2 - jitterAmount);
    }

    return Math.round(delay);
  }

  private shouldRetry(
    error: any,
    config: RetryOptions,
    state: RetryState,
  ): boolean {
    // Check custom retry condition
    if (config.retryCondition) {
      return config.retryCondition(error);
    }

    // Default retry conditions
    if (error instanceof Error) {
      const message = error.message.toLowerCase();

      // Network errors
      if (config.retryOnNetworkError) {
        if (
          message.includes('network') ||
          message.includes('timeout') ||
          message.includes('fetch') ||
          message.includes('connection')
        ) {
          return true;
        }
      }

      // Rate limiting
      if (
        message.includes('rate limit') ||
        message.includes('too many requests')
      ) {
        return true;
      }

      // Server errors (5xx)
      if (error.name === 'HTTPError' && (error as any).status >= 500) {
        return true;
      }

      // Temporary failures
      if (
        message.includes('temporary') ||
        message.includes('unavailable') ||
        message.includes('busy')
      ) {
        return true;
      }
    }

    return false;
  }

  private mergeOptions(options?: RetryOptions): Required<RetryOptions> {
    return {
      maxAttempts: options?.maxAttempts || SYNC_CONFIG.MAX_RETRY_COUNT,
      baseDelay: options?.baseDelay || SYNC_CONFIG.RETRY_BASE_DELAY,
      maxDelay: options?.maxDelay || SYNC_CONFIG.RETRY_MAX_DELAY,
      backoffFactor: options?.backoffFactor || SYNC_CONFIG.RETRY_BACKOFF_FACTOR,
      jitter: options?.jitter !== undefined ? options.jitter : true,
      retryOnNetworkError:
        options?.retryOnNetworkError !== undefined
          ? options.retryOnNetworkError
          : true,
      retryCondition: options?.retryCondition || (() => true),
      onRetryAttempt: options?.onRetryAttempt || (() => {}),
    };
  }

  private delay(ms: number): Promise<void> {
    return new Promise(resolve => setTimeout(resolve, ms));
  }

  private generateOperationId(): string {
    return `op_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
  }

  // Circuit breaker helpers
  private circuitStates: Map<
    string,
    {
      isOpen: boolean;
      failures: number;
      openedAt: number;
    }
  > = new Map();

  private getCircuitState(key: string) {
    if (!this.circuitStates.has(key)) {
      this.circuitStates.set(key, {
        isOpen: false,
        failures: 0,
        openedAt: 0,
      });
    }
    return this.circuitStates.get(key)!;
  }

  private openCircuit(key: string): void {
    const state = this.getCircuitState(key);
    state.isOpen = true;
    state.openedAt = Date.now();
    logger.warn(`Circuit breaker opened for ${key}`);
  }

  private resetCircuit(key: string): void {
    const state = this.getCircuitState(key);
    state.isOpen = false;
    state.failures = 0;
    state.openedAt = 0;
  }

  // Public utility methods
  getActiveRetries(): string[] {
    return Array.from(this.activeRetries.keys());
  }

  getRetryState(operationId: string): RetryState | undefined {
    return this.activeRetries.get(operationId);
  }

  cancelRetry(operationId: string): boolean {
    return this.activeRetries.delete(operationId);
  }

  clearAllRetries(): void {
    this.activeRetries.clear();
  }

  // Batch retry with different strategies
  async retryBatch<T>(
    operations: Array<() => Promise<T>>,
    options?: RetryOptions & {
      concurrency?: number;
      stopOnFirstSuccess?: boolean;
      stopOnFirstFailure?: boolean;
    },
  ): Promise<RetryResult<T[]>> {
    const concurrency = options?.concurrency || 3;
    const results: T[] = [];
    const errors: any[] = [];
    let totalAttempts = 0;
    let totalDelay = 0;

    // Process in batches
    for (let i = 0; i < operations.length; i += concurrency) {
      const batch = operations.slice(i, i + concurrency);
      const batchPromises = batch.map(op => this.retry(op, options));
      const batchResults = await Promise.allSettled(batchPromises);

      for (const result of batchResults) {
        if (result.status === 'fulfilled') {
          const retryResult = result.value;
          totalAttempts += retryResult.attempts;
          totalDelay += retryResult.totalDelay;

          if (retryResult.success) {
            results.push(retryResult.data!);
            if (options?.stopOnFirstSuccess) {
              return {
                success: true,
                data: results,
                attempts: totalAttempts,
                totalDelay,
              };
            }
          } else {
            errors.push(retryResult.error);
            if (options?.stopOnFirstFailure) {
              return {
                success: false,
                error: retryResult.error,
                attempts: totalAttempts,
                totalDelay,
              };
            }
          }
        }
      }
    }

    return {
      success: errors.length === 0,
      data: results,
      error: errors.length > 0 ? errors : undefined,
      attempts: totalAttempts,
      totalDelay,
    };
  }
}
