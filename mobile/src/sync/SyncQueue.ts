import { Q } from '@nozbe/watermelondb';
import database from '@database/index';
import { logger } from '@utils/logger';
import AsyncStorage from '@react-native-async-storage/async-storage';
import NetInfo from '@react-native-community/netinfo';
import { SYNC_CONFIG } from '@constants/config';
import { encrypt, decrypt } from '@utils/encryption';

export interface QueueItem {
  id: string;
  collection: string;
  operation: 'create' | 'update' | 'delete';
  recordId: string;
  data?: any;
  timestamp: number;
  retryCount: number;
  priority: 'high' | 'normal' | 'low';
}

export class SyncQueue {
  private static QUEUE_KEY = 'auraconnect.sync.queue';
  private queue: QueueItem[] = [];
  private isProcessing = false;

  constructor() {
    this.loadQueue();
    this.setupNetworkListener();
  }

  async add(
    item: Omit<QueueItem, 'id' | 'timestamp' | 'retryCount'>,
  ): Promise<void> {
    const queueItem: QueueItem = {
      ...item,
      id: this.generateId(),
      timestamp: Date.now(),
      retryCount: 0,
    };

    this.queue.push(queueItem);
    await this.saveQueue();

    logger.debug('Added item to sync queue', { item: queueItem });

    // Try to process immediately if online
    this.processQueue();
  }

  async addBatch(
    items: Omit<QueueItem, 'id' | 'timestamp' | 'retryCount'>[],
  ): Promise<void> {
    const queueItems = items.map(item => ({
      ...item,
      id: this.generateId(),
      timestamp: Date.now(),
      retryCount: 0,
    }));

    this.queue.push(...queueItems);
    await this.saveQueue();

    logger.debug('Added batch to sync queue', { count: items.length });

    // Try to process immediately if online
    this.processQueue();
  }

  async processQueue(): Promise<void> {
    if (this.isProcessing) {
      logger.debug('Queue already processing, skipping');
      return;
    }

    const isOnline = await this.isOnline();
    if (!isOnline) {
      logger.debug('Device offline, skipping queue processing');
      return;
    }

    this.isProcessing = true;

    try {
      // Sort queue by priority and timestamp
      this.sortQueue();

      while (this.queue.length > 0) {
        const item = this.queue[0];

        try {
          await this.processItem(item);
          // Remove successfully processed item
          this.queue.shift();
          await this.saveQueue();
        } catch (error) {
          logger.error('Failed to process queue item', { item, error });

          // Increment retry count
          item.retryCount++;

          if (item.retryCount >= SYNC_CONFIG.MAX_RETRY_COUNT) {
            logger.error('Max retries reached, removing item from queue', {
              item,
            });
            this.queue.shift();
            await this.saveQueue();
            // TODO: Store in dead letter queue
          } else {
            // Move to end of queue
            this.queue.shift();
            this.queue.push(item);
            await this.saveQueue();

            // Wait before retrying with exponential backoff
            const delay = Math.min(
              SYNC_CONFIG.RETRY_BASE_DELAY *
                Math.pow(SYNC_CONFIG.RETRY_BACKOFF_FACTOR, item.retryCount - 1),
              SYNC_CONFIG.RETRY_MAX_DELAY,
            );
            await this.delay(delay);
          }
        }
      }
    } finally {
      this.isProcessing = false;
    }
  }

  private async processItem(item: QueueItem): Promise<void> {
    logger.debug('Processing queue item', { item });

    const collection = database.collections.get(item.collection);

    switch (item.operation) {
      case 'create':
        await database.write(async () => {
          await collection.create(record => {
            Object.assign(record._raw, item.data);
          });
        });
        break;

      case 'update':
        await database.write(async () => {
          const record = await collection.find(item.recordId);
          await record.update(r => {
            Object.assign(r._raw, item.data);
          });
        });
        break;

      case 'delete':
        await database.write(async () => {
          const record = await collection.find(item.recordId);
          await record.markAsDeleted();
        });
        break;
    }
  }

  private sortQueue(): void {
    this.queue.sort((a, b) => {
      // Priority order: high > normal > low
      const priorityOrder = { high: 0, normal: 1, low: 2 };
      const priorityDiff =
        priorityOrder[a.priority] - priorityOrder[b.priority];

      if (priorityDiff !== 0) return priorityDiff;

      // If same priority, sort by timestamp (older first)
      return a.timestamp - b.timestamp;
    });
  }

  private async loadQueue(): Promise<void> {
    try {
      const stored = await AsyncStorage.getItem(SyncQueue.QUEUE_KEY);
      if (stored) {
        // Decrypt queue if it was encrypted
        let queueData: string;
        try {
          // Try to parse directly first (for backward compatibility)
          JSON.parse(stored);
          queueData = stored;
        } catch {
          // If parse fails, assume it's encrypted
          queueData = await decrypt(stored);
        }

        this.queue = JSON.parse(queueData);

        // Clean up expired items
        const now = Date.now();
        this.queue = this.queue.filter(item => {
          const age = now - item.timestamp;
          if (age > SYNC_CONFIG.QUEUE_ITEM_TTL) {
            logger.debug('Removing expired queue item', { id: item.id, age });
            return false;
          }
          return true;
        });

        logger.debug('Loaded sync queue', { count: this.queue.length });
      }
    } catch (error) {
      logger.error('Failed to load sync queue', error);
      // Reset queue on corruption
      this.queue = [];
    }
  }

  private async saveQueue(): Promise<void> {
    try {
      // Check queue size
      if (this.queue.length > SYNC_CONFIG.MAX_QUEUE_SIZE) {
        // Remove oldest low-priority items
        const lowPriorityItems = this.queue
          .filter(item => item.priority === 'low')
          .sort((a, b) => a.timestamp - b.timestamp);

        const itemsToRemove = this.queue.length - SYNC_CONFIG.MAX_QUEUE_SIZE;
        if (lowPriorityItems.length >= itemsToRemove) {
          const idsToRemove = lowPriorityItems
            .slice(0, itemsToRemove)
            .map(item => item.id);
          this.queue = this.queue.filter(
            item => !idsToRemove.includes(item.id),
          );
          logger.warn('Queue size limit reached, removed low priority items', {
            removed: itemsToRemove,
          });
        }
      }

      // Encrypt queue if configured
      const dataToStore = SYNC_CONFIG.ENCRYPT_QUEUE
        ? await encrypt(JSON.stringify(this.queue))
        : JSON.stringify(this.queue);

      await AsyncStorage.setItem(SyncQueue.QUEUE_KEY, dataToStore);
    } catch (error) {
      logger.error('Failed to save sync queue', error);
    }
  }

  private setupNetworkListener(): void {
    NetInfo.addEventListener(state => {
      if (state.isConnected && !this.isProcessing && this.queue.length > 0) {
        logger.info('Network connected, processing sync queue');
        this.processQueue();
      }
    });
  }

  private async isOnline(): Promise<boolean> {
    const state = await NetInfo.fetch();
    return state.isConnected ?? false;
  }

  private generateId(): string {
    return `${Date.now()}-${Math.random().toString(36).substr(2, 9)}`;
  }

  private delay(ms: number): Promise<void> {
    return new Promise(resolve => setTimeout(resolve, ms));
  }

  // Public methods
  getQueueSize(): number {
    return this.queue.length;
  }

  getQueueItems(): QueueItem[] {
    return [...this.queue];
  }

  async clear(): Promise<void> {
    this.queue = [];
    await this.saveQueue();
    logger.info('Sync queue cleared');
  }

  async removeItem(id: string): Promise<void> {
    this.queue = this.queue.filter(item => item.id !== id);
    await this.saveQueue();
  }

  async prioritizeItem(id: string): Promise<void> {
    const item = this.queue.find(item => item.id === id);
    if (item) {
      item.priority = 'high';
      item.timestamp = Date.now(); // Reset timestamp to move to front
      await this.saveQueue();
    }
  }

  getStats(): {
    total: number;
    byPriority: Record<string, number>;
    byOperation: Record<string, number>;
    byCollection: Record<string, number>;
    oldestItem: number | null;
  } {
    const stats = {
      total: this.queue.length,
      byPriority: { high: 0, normal: 0, low: 0 },
      byOperation: { create: 0, update: 0, delete: 0 },
      byCollection: {} as Record<string, number>,
      oldestItem: null as number | null,
    };

    for (const item of this.queue) {
      stats.byPriority[item.priority]++;
      stats.byOperation[item.operation]++;
      stats.byCollection[item.collection] =
        (stats.byCollection[item.collection] || 0) + 1;

      if (!stats.oldestItem || item.timestamp < stats.oldestItem) {
        stats.oldestItem = item.timestamp;
      }
    }

    return stats;
  }
}
