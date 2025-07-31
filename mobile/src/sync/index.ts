export { SyncEngine } from './SyncEngine';
export { SyncManager, type SyncState, type SyncStatus } from './SyncManager';
export { ConflictResolver, type ConflictInfo, type ConflictResult } from './ConflictResolver';
export { SyncQueue, type QueueItem } from './SyncQueue';

// Export singleton instance for easy access
import { SyncManager } from './SyncManager';
export const syncManager = SyncManager.getInstance();