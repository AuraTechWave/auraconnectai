import NetInfo from '@react-native-community/netinfo';
import { MMKV } from 'react-native-mmkv';
import { apiClient } from './api.client';
import { showToast } from '@utils/toast';

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

  public async queueRequest(request: Omit<QueuedRequest, 'id' | 'timestamp' | 'retryCount'>) {
    const queue = this.getQueue();
    
    const queuedRequest: QueuedRequest = {
      id: Date.now().toString(),
      timestamp: new Date().toISOString(),
      retryCount: 0,
      ...request,
    };

    queue.push(queuedRequest);
    this.saveQueue(queue);

    showToast('info', 'Offline', 'Request queued for sync');
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

    for (const request of queue) {
      try {
        await this.executeRequest(request);
      } catch (error) {
        request.retryCount++;
        
        // Keep request in queue if retry count is below threshold
        if (request.retryCount < 3) {
          failedRequests.push(request);
        }
      }
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

    switch (method.toLowerCase()) {
      case 'get':
        await apiClient.get(url, { params });
        break;
      case 'post':
        await apiClient.post(url, data, { params });
        break;
      case 'put':
        await apiClient.put(url, data, { params });
        break;
      case 'patch':
        await apiClient.patch(url, data, { params });
        break;
      case 'delete':
        await apiClient.delete(url, { params });
        break;
    }
  }

  private getQueue(): QueuedRequest[] {
    const queueString = storage.getString('offlineQueue');
    return queueString ? JSON.parse(queueString) : [];
  }

  private saveQueue(queue: QueuedRequest[]) {
    storage.set('offlineQueue', JSON.stringify(queue));
  }

  public clearQueue() {
    storage.delete('offlineQueue');
  }

  public getQueueSize(): number {
    return this.getQueue().length;
  }

  public isNetworkOnline(): boolean {
    return this.isOnline;
  }
}

export const offlineService = new OfflineService();