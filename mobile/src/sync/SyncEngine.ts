import { synchronize } from '@nozbe/watermelondb/sync';
import { Q } from '@nozbe/watermelondb';
import database from '@database/index';
import { apiClient } from '@services/api.client';
import { logger } from '@utils/logger';
import { showToast } from '@utils/toast';
import SyncLog from '@database/models/SyncLog';
import { ConflictResolver } from './ConflictResolver';
import { SyncQueue } from './SyncQueue';
import { SyncErrorHandler } from './errors/SyncErrorHandler';
import type {
  PullRequest,
  PullResponse,
  PushRequest,
  PushResponse,
  SyncError,
  SyncResult,
  SyncCollectionChanges,
  SyncAcceptedItem,
  SyncRejectedItem,
} from '@types/sync.types';

export interface SyncConfig {
  pullUrl: string;
  pushUrl: string;
  batchSize: number;
  conflictStrategy:
    | 'server_wins'
    | 'client_wins'
    | 'last_write_wins'
    | 'manual';
}

export interface SyncStats {
  pushed: number;
  pulled: number;
  conflicts: number;
  errors: number;
  duration: number;
}

export class SyncEngine {
  private static instance: SyncEngine;
  private isSyncing = false;
  private lastSyncTimestamp = 0;
  private conflictResolver: ConflictResolver;
  private syncQueue: SyncQueue;

  private config: SyncConfig = {
    pullUrl: '/api/sync/pull',
    pushUrl: '/api/sync/push',
    batchSize: 100,
    conflictStrategy: 'last_write_wins',
  };

  private constructor() {
    this.conflictResolver = new ConflictResolver();
    this.syncQueue = new SyncQueue();
    this.loadLastSyncTimestamp();
  }

  static getInstance(): SyncEngine {
    if (!SyncEngine.instance) {
      SyncEngine.instance = new SyncEngine();
    }
    return SyncEngine.instance;
  }

  async sync(
    options: { force?: boolean; syncType?: 'push' | 'pull' | 'full' } = {},
  ): Promise<SyncStats> {
    const { force = false, syncType = 'full' } = options;

    if (this.isSyncing && !force) {
      logger.warn('Sync already in progress');
      return { pushed: 0, pulled: 0, conflicts: 0, errors: 0, duration: 0 };
    }

    this.isSyncing = true;
    const startTime = Date.now();

    // Create sync log
    const syncLog = await this.createSyncLog(syncType);

    const stats: SyncStats = {
      pushed: 0,
      pulled: 0,
      conflicts: 0,
      errors: 0,
      duration: 0,
    };

    try {
      logger.info('Starting sync', {
        syncType,
        lastSync: this.lastSyncTimestamp,
      });

      if (syncType === 'pull' || syncType === 'full') {
        const pullStats = await this.pull();
        stats.pulled = pullStats.pulled;
        stats.conflicts += pullStats.conflicts;
      }

      if (syncType === 'push' || syncType === 'full') {
        const pushStats = await this.push();
        stats.pushed = pushStats.pushed;
        stats.conflicts += pushStats.conflicts;
      }

      // Update last sync timestamp
      this.lastSyncTimestamp = Date.now();
      await this.saveLastSyncTimestamp();

      // Update sync log
      await this.completeSyncLog(syncLog, stats);

      logger.info('Sync completed successfully', stats);
      showToast(
        'success',
        'Sync Complete',
        `↓${stats.pulled} ↑${stats.pushed}`,
      );
    } catch (error) {
      stats.errors++;
      logger.error('Sync failed', error);
      await this.failSyncLog(syncLog, error, stats);
      showToast('error', 'Sync Failed', 'Please try again later');
      throw error;
    } finally {
      this.isSyncing = false;
      stats.duration = Date.now() - startTime;
    }

    return stats;
  }

  private async pull(): Promise<{ pulled: number; conflicts: number }> {
    let pulled = 0;
    let conflicts = 0;

    try {
      const params: PullRequest = {
        lastPulledAt: this.lastSyncTimestamp,
        schemaVersion: 1,
      };

      const response = await apiClient.get<PullResponse>(this.config.pullUrl, {
        params,
      });
      const { changes, timestamp } = response.data;

      // Process changes through WatermelonDB sync
      await synchronize({
        database,
        pullChanges: async () => {
          // Transform server data to WatermelonDB format
          const transformedChanges = this.transformServerChanges(changes);

          // Detect and resolve conflicts
          const conflictResults =
            await this.conflictResolver.detectConflicts(transformedChanges);
          conflicts = conflictResults.conflicts.length;

          return {
            changes: conflictResults.resolved,
            timestamp,
          };
        },
        pushChanges: async () => {
          // Not used in pull-only sync
          return {};
        },
      });

      pulled = this.countChanges(changes);
    } catch (error) {
      const syncError = SyncErrorHandler.handleError(error);
      logger.error('Pull sync failed', syncError);

      if (syncError.retryable) {
        await SyncErrorHandler.recoverFromError(syncError);
      }

      throw syncError;
    }

    return { pulled, conflicts };
  }

  private async push(): Promise<{ pushed: number; conflicts: number }> {
    let pushed = 0;
    let conflicts = 0;

    try {
      // Get all pending changes
      const pendingChanges = await this.collectPendingChanges();

      if (Object.keys(pendingChanges).length === 0) {
        logger.debug('No pending changes to push');
        return { pushed: 0, conflicts: 0 };
      }

      // Push in batches
      const batches = this.createBatches(pendingChanges, this.config.batchSize);

      for (const batch of batches) {
        const request: PushRequest = {
          changes: batch,
          lastPulledAt: this.lastSyncTimestamp,
        };

        const response = await apiClient.post<PushResponse>(
          this.config.pushUrl,
          request,
        );
        const {
          accepted,
          rejected,
          conflicts: serverConflicts,
        } = response.data;

        // Update local records with server IDs
        await this.updateSyncedRecords(accepted);

        // Handle rejections and conflicts
        if (rejected.length > 0) {
          await this.handleRejections(rejected);
        }

        if (serverConflicts.length > 0) {
          conflicts += serverConflicts.length;
          await this.conflictResolver.resolveConflicts(serverConflicts);
        }

        pushed += accepted.length;
      }
    } catch (error) {
      const syncError = SyncErrorHandler.handleError(error);
      logger.error('Push sync failed', syncError);

      if (syncError.retryable) {
        await SyncErrorHandler.recoverFromError(syncError);
      }

      throw syncError;
    }

    return { pushed, conflicts };
  }

  private async collectPendingChanges(): Promise<SyncCollectionChanges> {
    const changes: SyncCollectionChanges = {};
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
        .fetch();

      if (pendingRecords.length > 0) {
        changes[collectionName] = {
          created: [],
          updated: [],
          deleted: [],
        };

        for (const record of pendingRecords) {
          const data = this.serializeRecord(record);

          if (record.isDeleted) {
            changes[collectionName].deleted.push(data);
          } else if (record.serverId) {
            changes[collectionName].updated.push(data);
          } else {
            changes[collectionName].created.push(data);
          }
        }
      }
    }

    return changes;
  }

  private serializeRecord(record: any) {
    const data = record._raw;
    // Remove WatermelonDB specific fields
    const { _status, _changed, ...cleanData } = data;
    return {
      ...cleanData,
      localId: record.id,
    };
  }

  private transformServerChanges(changes: any) {
    const transformed: any = {};

    for (const [collection, records] of Object.entries(changes)) {
      transformed[collection] = {
        created:
          records.created?.map((r: any) => ({
            ...r,
            id: r.localId || r.id,
            serverId: r.id,
          })) || [],
        updated:
          records.updated?.map((r: any) => ({
            ...r,
            id: r.localId || r.id,
            serverId: r.id,
          })) || [],
        deleted: records.deleted || [],
      };
    }

    return transformed;
  }

  private createBatches(changes: any, batchSize: number) {
    const batches = [];
    let currentBatch: any = {};
    let currentSize = 0;

    for (const [collection, data] of Object.entries(changes)) {
      const allRecords = [...data.created, ...data.updated, ...data.deleted];

      for (const record of allRecords) {
        if (!currentBatch[collection]) {
          currentBatch[collection] = {
            created: [],
            updated: [],
            deleted: [],
          };
        }

        // Add to appropriate array
        if (data.created.includes(record)) {
          currentBatch[collection].created.push(record);
        } else if (data.updated.includes(record)) {
          currentBatch[collection].updated.push(record);
        } else if (data.deleted.includes(record)) {
          currentBatch[collection].deleted.push(record);
        }

        currentSize++;

        if (currentSize >= batchSize) {
          batches.push(currentBatch);
          currentBatch = {};
          currentSize = 0;
        }
      }
    }

    if (currentSize > 0) {
      batches.push(currentBatch);
    }

    return batches;
  }

  private async updateSyncedRecords(accepted: SyncAcceptedItem[]) {
    await database.write(async () => {
      for (const item of accepted) {
        const { collection: collectionName, localId, serverId } = item;
        const collection = database.collections.get(collectionName);

        try {
          const record = await collection.find(localId);
          await record.markAsSynced(serverId);
        } catch (error) {
          logger.warn('Failed to update synced record', { localId, error });
        }
      }
    });
  }

  private async handleRejections(rejected: SyncRejectedItem[]) {
    for (const rejection of rejected) {
      logger.warn('Server rejected record', rejection);
      // Mark as conflict for manual resolution
      const { collection: collectionName, localId, reason } = rejection;
      const collection = database.collections.get(collectionName);

      try {
        const record = await collection.find(localId);
        await record.markAsConflict();
      } catch (error) {
        logger.error('Failed to mark rejection as conflict', {
          localId,
          error,
        });
      }
    }
  }

  private countChanges(changes: any): number {
    let count = 0;
    for (const records of Object.values(changes)) {
      const { created = [], updated = [], deleted = [] } = records as any;
      count += created.length + updated.length + deleted.length;
    }
    return count;
  }

  private async createSyncLog(syncType: string) {
    const syncLogs = database.collections.get('sync_logs');
    return await database.write(async () => {
      return await syncLogs.create((log: SyncLog) => {
        log.syncType = syncType as any;
        log.status = 'started';
        log.startedAt = Date.now();
        log.recordsPushed = 0;
        log.recordsPulled = 0;
        log.conflictsResolved = 0;
      });
    });
  }

  private async completeSyncLog(syncLog: SyncLog, stats: SyncStats) {
    await database.write(async () => {
      await syncLog.update(log => {
        log.status = 'completed';
        log.completedAt = Date.now();
        log.recordsPushed = stats.pushed;
        log.recordsPulled = stats.pulled;
        log.conflictsResolved = stats.conflicts;
      });
    });
  }

  private async failSyncLog(syncLog: SyncLog, error: any, stats: SyncStats) {
    await database.write(async () => {
      await syncLog.update(log => {
        log.status = 'failed';
        log.completedAt = Date.now();
        log.recordsPushed = stats.pushed;
        log.recordsPulled = stats.pulled;
        log.conflictsResolved = stats.conflicts;
        log.errors = [
          {
            message: error.message || 'Unknown error',
            code: error.code,
            timestamp: Date.now(),
          },
        ];
      });
    });
  }

  private async loadLastSyncTimestamp() {
    try {
      const lastSync = await SyncLog.lastSuccessfulSync();
      if (lastSync && lastSync.length > 0) {
        this.lastSyncTimestamp = lastSync[0].completedAt || 0;
      }
    } catch (error) {
      logger.warn('Failed to load last sync timestamp', error);
    }
  }

  private async saveLastSyncTimestamp() {
    // Timestamp is saved in sync log
  }

  // Public methods
  get isSyncInProgress(): boolean {
    return this.isSyncing;
  }

  get lastSync(): number {
    return this.lastSyncTimestamp;
  }

  async forcePush() {
    return this.sync({ syncType: 'push', force: true });
  }

  async forcePull() {
    return this.sync({ syncType: 'pull', force: true });
  }
}
