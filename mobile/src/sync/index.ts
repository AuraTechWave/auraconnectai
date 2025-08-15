export { SyncEngine } from './SyncEngine';
export { SyncManager, type SyncState, type SyncStatus } from './SyncManager';
export {
  ConflictResolver,
  type ConflictInfo,
  type ConflictResult,
} from './ConflictResolver';
export { SyncQueue, type QueueItem } from './SyncQueue';
export {
  NetworkStateManager,
  type NetworkState,
  type NetworkType,
  type NetworkQuality,
} from './NetworkStateManager';
export {
  RetryManager,
  type RetryOptions,
  type RetryResult,
} from './RetryManager';

// Export singleton instances for easy access
import { SyncManager } from './SyncManager';
import { NetworkStateManager } from './NetworkStateManager';
import { RetryManager } from './RetryManager';

export const syncManager = SyncManager.getInstance();
export const networkManager = NetworkStateManager.getInstance();
export const retryManager = RetryManager.getInstance();
