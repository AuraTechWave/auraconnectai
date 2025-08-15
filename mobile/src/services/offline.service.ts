import NetInfo from '@react-native-community/netinfo';
import { MMKV } from 'react-native-mmkv';
import { apiClient } from './api.client';
import { showToast } from '@utils/toast';
import { encryptionService } from '@utils/encryption';
import { OFFLINE_CONFIG, STORAGE_KEYS } from '@constants/config';

const storage = new MMKV();

interface QueuedRequest {
  id: string;
  timestamp: string;
  config: {
    method: string;
    url: string;
    data?: any;
    params?: any;
  };
  retryCount: number;
}

class OfflineService {
  private isOnline = true;
  private syncInProgress = false;
  private listeners: Array<(isOnline: boolean) => void> = [];

  constructor() {
    this.setupNetworkListener();
  }

  private setupNetworkListener() {
    NetInfo.addEventListener(state => {
      const wasOffline = !this.isOnline;
      this.isOnline = state.isConnected || false;

      // Notify listeners
      this.listeners.forEach(listener => listener(this.isOnline));

      // If we just came online, sync queued requests
      if (wasOffline && this.isOnline) {
        this.syncOfflineQueue();
      }
    });
  }

  public subscribe(listener: (isOnline: boolean) => void) {
    this.listeners.push(listener);
    // Return unsubscribe function
    return () => {
      this.listeners = this.listeners.filter(l => l !== listener);
    };
  }

  public async queueRequest(
    request: Omit<QueuedRequest, 'id' | 'timestamp' | 'retryCount'>,
  ) {
    const queue = this.getQueue();

    // Check queue size limit
    if (queue.length >= OFFLINE_CONFIG.MAX_QUEUE_SIZE) {
      showToast(
        'warning',
        'Queue Full',
        'Offline queue is full. Please sync when online.',
      );
      return;
    }

    const queuedRequest: QueuedRequest = {
      id: Date.now().toString(),
      timestamp: new Date().toISOString(),
      retryCount: 0,
      ...request,
    };

    // Encrypt sensitive data if enabled
    if (OFFLINE_CONFIG.ENCRYPT_QUEUE && queuedRequest.config.data) {
      queuedRequest.config.data = encryptionService.encrypt(
        queuedRequest.config.data,
      );
    }

    queue.push(queuedRequest);
    this.saveQueue(queue);

    showToast(
      'info',
      'Offline',
      `Request queued (${queue.length}/${OFFLINE_CONFIG.MAX_QUEUE_SIZE})`,
    );
  }

  public async syncOfflineQueue() {
    if (this.syncInProgress || !this.isOnline) {
      return;
    }

    this.syncInProgress = true;
    const queue = this.getQueue();

    if (queue.length === 0) {
      this.syncInProgress = false;
      return;
    }

    showToast('info', 'Syncing', `Syncing ${queue.length} offline requests`);

    const failedRequests: QueuedRequest[] = [];
    const batchSize = OFFLINE_CONFIG.SYNC_BATCH_SIZE;

    // Process in batches
    for (let i = 0; i < queue.length; i += batchSize) {
      const batch = queue.slice(i, i + batchSize);

      await Promise.all(
        batch.map(async request => {
          try {
            await this.executeRequest(request);
          } catch (error) {
            request.retryCount++;

            // Keep request in queue if retry count is below threshold
            if (request.retryCount < OFFLINE_CONFIG.MAX_RETRY_COUNT) {
              failedRequests.push(request);
            }
          }
        }),
      );
    }

    // Update queue with failed requests
    this.saveQueue(failedRequests);

    if (failedRequests.length === 0) {
      showToast('success', 'Sync Complete', 'All offline requests synced');
    } else {
      showToast(
        'warning',
        'Sync Partial',
        `${failedRequests.length} requests failed`,
      );
    }

    this.syncInProgress = false;
  }

  private async executeRequest(request: QueuedRequest) {
    const { method, url, data, params } = request.config;

    // Decrypt data if it was encrypted
    let decryptedData = data;
    if (OFFLINE_CONFIG.ENCRYPT_QUEUE && data) {
      try {
        decryptedData = encryptionService.decrypt(data);
      } catch (error) {
        console.error('Failed to decrypt request data:', error);
        throw error;
      }
    }

    switch (method.toLowerCase()) {
      case 'get':
        await apiClient.get(url, { params });
        break;
      case 'post':
        await apiClient.post(url, decryptedData, { params });
        break;
      case 'put':
        await apiClient.put(url, decryptedData, { params });
        break;
      case 'patch':
        await apiClient.patch(url, decryptedData, { params });
        break;
      case 'delete':
        await apiClient.delete(url, { params });
        break;
    }
  }

  private getQueue(): QueuedRequest[] {
    const queueString = storage.getString(STORAGE_KEYS.OFFLINE_QUEUE);
    return queueString ? JSON.parse(queueString) : [];
  }

  private saveQueue(queue: QueuedRequest[]) {
    storage.set(STORAGE_KEYS.OFFLINE_QUEUE, JSON.stringify(queue));
  }

  public clearQueue() {
    storage.delete(STORAGE_KEYS.OFFLINE_QUEUE);
  }

  public getQueueSize(): number {
    return this.getQueue().length;
  }

  public isNetworkOnline(): boolean {
    return this.isOnline;
  }
}

export const offlineService = new OfflineService();
