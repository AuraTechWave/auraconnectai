import { SyncEngine } from './SyncEngine';
import { SyncQueue } from './SyncQueue';
import BackgroundFetch from 'react-native-background-fetch';
import BackgroundTimer from 'react-native-background-timer';
import NetInfo from '@react-native-community/netinfo';
import { logger } from '@utils/logger';
import { showToast } from '@utils/toast';
import { EventEmitter } from 'events';
import { SYNC_CONFIG } from '@constants/config';
import database from '@database/index';
import SyncLog from '@database/models/SyncLog';
import { Q } from '@nozbe/watermelondb';

export type SyncStatus = 'idle' | 'syncing' | 'error' | 'offline';

export interface SyncState {
  status: SyncStatus;
  lastSync: number | null;
  pendingChanges: number;
  queueSize: number;
  isOnline: boolean;
  error: Error | null;
  progress: {
    current: number;
    total: number;
    message: string;
  } | null;
}

export class SyncManager extends EventEmitter {
  private static instance: SyncManager;
  private syncEngine: SyncEngine;
  private syncQueue: SyncQueue;
  private syncTimer: number | null = null;
  private networkListener: (() => void) | null = null;
  private state: SyncState = {
    status: 'idle',
    lastSync: null,
    pendingChanges: 0,
    queueSize: 0,
    isOnline: true,
    error: null,
    progress: null,
  };

  private constructor() {
    super();
    this.syncEngine = SyncEngine.getInstance();
    this.syncQueue = new SyncQueue();
    this.setupNetworkListener();
    this.setupBackgroundSync();
    this.loadState();
  }

  static getInstance(): SyncManager {
    if (!SyncManager.instance) {
      SyncManager.instance = new SyncManager();
    }
    return SyncManager.instance;
  }

  async initialize(): Promise<void> {
    logger.info('Initializing sync manager');

    // Check initial network state
    const netState = await NetInfo.fetch();
    this.updateState({ isOnline: netState.isConnected ?? false });

    // Start periodic sync if online
    if (this.state.isOnline) {
      this.startPeriodicSync();
    }

    // Update pending changes count
    await this.updatePendingChangesCount();
  }

  async sync(options?: {
    force?: boolean;
    syncType?: 'push' | 'pull' | 'full';
  }): Promise<void> {
    if (this.state.status === 'syncing' && !options?.force) {
      logger.warn('Sync already in progress');
      return;
    }

    if (!this.state.isOnline) {
      logger.warn('Cannot sync while offline');
      showToast('warning', 'Offline', 'Changes will sync when online');
      return;
    }

    this.updateState({
      status: 'syncing',
      error: null,
      progress: { current: 0, total: 100, message: 'Starting sync...' },
    });

    try {
      // First, process any queued operations
      await this.syncQueue.processQueue();

      // Then perform the sync
      const stats = await this.syncEngine.sync(options || {});

      // Update state with results
      this.updateState({
        status: 'idle',
        lastSync: Date.now(),
        error: null,
        progress: null,
      });

      // Update pending changes count
      await this.updatePendingChangesCount();

      logger.info('Sync completed', stats);
      this.emit('syncComplete', stats);
    } catch (error) {
      logger.error('Sync failed', error);
      this.updateState({
        status: 'error',
        error: error as Error,
        progress: null,
      });
      this.emit('syncError', error);
      throw error;
    }
  }

  async queueOperation(operation: {
    collection: string;
    operation: 'create' | 'update' | 'delete';
    recordId: string;
    data?: any;
    priority?: 'high' | 'normal' | 'low';
  }): Promise<void> {
    await this.syncQueue.add({
      ...operation,
      priority: operation.priority || 'normal',
    });

    this.updateState({ queueSize: this.syncQueue.getQueueSize() });

    // Try to sync immediately if online
    if (this.state.isOnline && this.state.status === 'idle') {
      this.sync().catch(error => {
        logger.warn('Auto-sync after queue operation failed', error);
      });
    }
  }

  private setupNetworkListener(): void {
    this.networkListener = NetInfo.addEventListener(state => {
      const wasOffline = !this.state.isOnline;
      const isOnline = state.isConnected ?? false;

      this.updateState({ isOnline });

      if (wasOffline && isOnline) {
        logger.info('Network reconnected, triggering sync');
        showToast('success', 'Online', 'Syncing changes...');
        this.sync().catch(error => {
          logger.error('Auto-sync on reconnect failed', error);
        });
        this.startPeriodicSync();
      } else if (!isOnline) {
        this.stopPeriodicSync();
        this.updateState({ status: 'offline' });
        showToast('info', 'Offline', 'Working in offline mode');
      }
    });
  }

  private setupBackgroundSync(): void {
    BackgroundFetch.configure(
      {
        minimumFetchInterval: 15, // 15 minutes
        forceAlarmManager: false,
        stopOnTerminate: false,
        startOnBoot: true,
        enableHeadless: true,
      },
      async taskId => {
        logger.info('Background sync triggered', { taskId });

        try {
          await this.sync();
          BackgroundFetch.finish(taskId);
        } catch (error) {
          logger.error('Background sync failed', error);
          BackgroundFetch.finish(taskId);
        }
      },
      taskId => {
        logger.error('Background fetch failed to start', { taskId });
        BackgroundFetch.finish(taskId);
      },
    );
  }

  private startPeriodicSync(): void {
    if (this.syncTimer) {
      return;
    }

    logger.info('Starting periodic sync');

    this.syncTimer = BackgroundTimer.setInterval(() => {
      if (this.state.isOnline && this.state.status === 'idle') {
        this.sync().catch(error => {
          logger.error('Periodic sync failed', error);
        });
      }
    }, SYNC_CONFIG.SYNC_INTERVAL);
  }

  private stopPeriodicSync(): void {
    if (this.syncTimer) {
      BackgroundTimer.clearInterval(this.syncTimer);
      this.syncTimer = null;
      logger.info('Stopped periodic sync');
    }
  }

  private async updatePendingChangesCount(): Promise<void> {
    let count = 0;
    const collections = [
      'orders',
      'order_items',
      'staff',
      'shifts',
      'menu_items',
      'customers',
    ];

    for (const collectionName of collections) {
      const collection = database.collections.get(collectionName);
      const pendingRecords = await collection
        .query(Q.where('sync_status', Q.oneOf(['pending', 'conflict'])))
        .fetchCount();
      count += pendingRecords;
    }

    this.updateState({ pendingChanges: count });
  }

  private updateState(updates: Partial<SyncState>): void {
    const previousState = { ...this.state };
    this.state = { ...this.state, ...updates };

    // Emit state change event
    this.emit('stateChange', this.state, previousState);
  }

  private async loadState(): Promise<void> {
    try {
      // Load last sync timestamp from sync logs
      const lastSync = await SyncLog.lastSuccessfulSync();
      if (lastSync && lastSync.length > 0) {
        this.updateState({ lastSync: lastSync[0].completedAt || null });
      }

      // Load queue size
      this.updateState({ queueSize: this.syncQueue.getQueueSize() });
    } catch (error) {
      logger.error('Failed to load sync state', error);
    }
  }

  // Public methods
  getState(): SyncState {
    return { ...this.state };
  }

  async forceSync(): Promise<void> {
    return this.sync({ force: true });
  }

  async syncPull(): Promise<void> {
    return this.sync({ syncType: 'pull' });
  }

  async syncPush(): Promise<void> {
    return this.sync({ syncType: 'push' });
  }

  async clearQueue(): Promise<void> {
    await this.syncQueue.clear();
    this.updateState({ queueSize: 0 });
  }

  getQueueStats() {
    return this.syncQueue.getStats();
  }

  async getSyncHistory(limit = 10): Promise<SyncLog[]> {
    return await SyncLog.recentSyncs(limit).fetch();
  }

  destroy(): void {
    this.stopPeriodicSync();

    if (this.networkListener) {
      this.networkListener();
      this.networkListener = null;
    }

    BackgroundFetch.stop();
    this.removeAllListeners();
  }

  // Event emitter methods are inherited
  // Events: 'stateChange', 'syncComplete', 'syncError'
}
