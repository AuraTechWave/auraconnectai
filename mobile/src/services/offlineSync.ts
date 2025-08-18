import AsyncStorage from '@react-native-async-storage/async-storage';
import NetInfo from '@react-native-community/netinfo';
import { Alert } from 'react-native';

interface SyncQueue {
  id: string;
  type: 'order' | 'inventory' | 'staff' | 'menu';
  action: 'create' | 'update' | 'delete';
  data: any;
  timestamp: string;
  retries: number;
  status: 'pending' | 'syncing' | 'failed' | 'completed';
}

interface SyncStatus {
  lastSync: string | null;
  pendingChanges: number;
  failedSyncs: number;
  isCurrentlySyncing: boolean;
  nextScheduledSync: string | null;
}

interface OfflineCapabilities {
  orders: {
    create: boolean;
    update: boolean;
    maxItems: number;
  };
  inventory: {
    count: boolean;
    adjust: boolean;
    maxItems: number;
  };
  staff: {
    viewSchedule: boolean;
    checkIn: boolean;
    maxDays: number;
  };
  menu: {
    browse: boolean;
    search: boolean;
    maxItems: number;
  };
}

class OfflineSyncService {
  private syncQueue: SyncQueue[] = [];
  private syncInterval: NodeJS.Timeout | null = null;
  private syncListeners: Set<(status: SyncStatus) => void> = new Set();
  private isOnline: boolean = true;
  private capabilities: OfflineCapabilities = {
    orders: {
      create: true,
      update: true,
      maxItems: 100,
    },
    inventory: {
      count: true,
      adjust: true,
      maxItems: 500,
    },
    staff: {
      viewSchedule: true,
      checkIn: true,
      maxDays: 7,
    },
    menu: {
      browse: true,
      search: true,
      maxItems: 200,
    },
  };

  constructor() {
    this.initializeNetworkListener();
    this.loadSyncQueue();
  }

  private async initializeNetworkListener() {
    // Monitor network status
    NetInfo.addEventListener(state => {
      const wasOffline = !this.isOnline;
      this.isOnline = state.isConnected ?? false;

      if (wasOffline && this.isOnline) {
        // Just came online, trigger sync
        this.performSync();
      }

      this.notifyStatusChange();
    });

    // Get initial network state
    const state = await NetInfo.fetch();
    this.isOnline = state.isConnected ?? false;
  }

  private async loadSyncQueue() {
    try {
      const queueData = await AsyncStorage.getItem('sync_queue');
      if (queueData) {
        this.syncQueue = JSON.parse(queueData);
      }
    } catch (error) {
      console.error('Error loading sync queue:', error);
    }
  }

  private async saveSyncQueue() {
    try {
      await AsyncStorage.setItem('sync_queue', JSON.stringify(this.syncQueue));
    } catch (error) {
      console.error('Error saving sync queue:', error);
    }
  }

  public async addToQueue(
    type: SyncQueue['type'],
    action: SyncQueue['action'],
    data: any,
  ): Promise<string> {
    const queueItem: SyncQueue = {
      id: `${type}_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`,
      type,
      action,
      data,
      timestamp: new Date().toISOString(),
      retries: 0,
      status: 'pending',
    };

    // Check capacity limits
    if (!this.checkCapacity(type)) {
      throw new Error(`Offline capacity exceeded for ${type}`);
    }

    this.syncQueue.push(queueItem);
    await this.saveSyncQueue();
    this.notifyStatusChange();

    // Try immediate sync if online
    if (this.isOnline) {
      this.performSync();
    }

    return queueItem.id;
  }

  private checkCapacity(type: SyncQueue['type']): boolean {
    const typeCount = this.syncQueue.filter(
      item => item.type === type && item.status === 'pending',
    ).length;

    switch (type) {
      case 'order':
        return typeCount < this.capabilities.orders.maxItems;
      case 'inventory':
        return typeCount < this.capabilities.inventory.maxItems;
      case 'menu':
        return typeCount < this.capabilities.menu.maxItems;
      case 'staff':
        return typeCount < this.capabilities.staff.maxDays * 10; // Arbitrary limit
      default:
        return true;
    }
  }

  public async performSync(): Promise<void> {
    if (!this.isOnline || this.syncQueue.length === 0) {
      return;
    }

    const pendingItems = this.syncQueue.filter(item => item.status === 'pending');
    
    for (const item of pendingItems) {
      try {
        item.status = 'syncing';
        await this.saveSyncQueue();
        
        // Perform the actual sync based on type and action
        await this.syncItem(item);
        
        // Mark as completed
        item.status = 'completed';
        await this.saveSyncQueue();
      } catch (error) {
        item.retries += 1;
        item.status = item.retries > 3 ? 'failed' : 'pending';
        await this.saveSyncQueue();
        
        if (item.status === 'failed') {
          this.handleSyncFailure(item, error);
        }
      }
    }

    // Clean up completed items
    this.cleanupCompletedItems();
    this.notifyStatusChange();
  }

  private async syncItem(item: SyncQueue): Promise<void> {
    // This would make actual API calls based on the item type and action
    const endpoint = this.getEndpoint(item.type, item.action);
    
    // Simulated API call
    const response = await fetch(endpoint, {
      method: item.action === 'delete' ? 'DELETE' : 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(item.data),
    });

    if (!response.ok) {
      throw new Error(`Sync failed: ${response.statusText}`);
    }
  }

  private getEndpoint(type: SyncQueue['type'], action: SyncQueue['action']): string {
    // Map to actual API endpoints
    const baseUrl = 'https://api.auraconnect.ai/v1';
    const endpoints = {
      order: {
        create: `${baseUrl}/orders`,
        update: `${baseUrl}/orders`,
        delete: `${baseUrl}/orders`,
      },
      inventory: {
        create: `${baseUrl}/inventory`,
        update: `${baseUrl}/inventory`,
        delete: `${baseUrl}/inventory`,
      },
      staff: {
        create: `${baseUrl}/staff`,
        update: `${baseUrl}/staff`,
        delete: `${baseUrl}/staff`,
      },
      menu: {
        create: `${baseUrl}/menu`,
        update: `${baseUrl}/menu`,
        delete: `${baseUrl}/menu`,
      },
    };

    return endpoints[type][action];
  }

  private handleSyncFailure(item: SyncQueue, error: any) {
    Alert.alert(
      'Sync Failed',
      `Failed to sync ${item.type} after multiple attempts. Data will be preserved for manual sync.`,
      [
        { text: 'OK' },
        {
          text: 'Retry',
          onPress: () => {
            item.status = 'pending';
            item.retries = 0;
            this.saveSyncQueue();
            this.performSync();
          },
        },
      ],
    );
  }

  private async cleanupCompletedItems() {
    const cutoffDate = new Date();
    cutoffDate.setHours(cutoffDate.getHours() - 24); // Keep for 24 hours

    this.syncQueue = this.syncQueue.filter(
      item =>
        item.status !== 'completed' ||
        new Date(item.timestamp) > cutoffDate,
    );

    await this.saveSyncQueue();
  }

  public startAutoSync(intervalMinutes: number = 15) {
    this.stopAutoSync();
    
    this.syncInterval = setInterval(() => {
      this.performSync();
    }, intervalMinutes * 60 * 1000);

    // Perform initial sync
    this.performSync();
  }

  public stopAutoSync() {
    if (this.syncInterval) {
      clearInterval(this.syncInterval);
      this.syncInterval = null;
    }
  }

  public getSyncStatus(): SyncStatus {
    const pendingItems = this.syncQueue.filter(item => item.status === 'pending');
    const failedItems = this.syncQueue.filter(item => item.status === 'failed');
    const lastSyncItem = this.syncQueue
      .filter(item => item.status === 'completed')
      .sort((a, b) => new Date(b.timestamp).getTime() - new Date(a.timestamp).getTime())[0];

    return {
      lastSync: lastSyncItem?.timestamp || null,
      pendingChanges: pendingItems.length,
      failedSyncs: failedItems.length,
      isCurrentlySyncing: this.syncQueue.some(item => item.status === 'syncing'),
      nextScheduledSync: this.syncInterval ? new Date(Date.now() + 15 * 60 * 1000).toISOString() : null,
    };
  }

  public subscribeToStatus(callback: (status: SyncStatus) => void) {
    this.syncListeners.add(callback);
    callback(this.getSyncStatus());
    
    return () => {
      this.syncListeners.delete(callback);
    };
  }

  private notifyStatusChange() {
    const status = this.getSyncStatus();
    this.syncListeners.forEach(listener => listener(status));
  }

  public async clearOfflineData() {
    this.syncQueue = [];
    await AsyncStorage.multiRemove([
      'sync_queue',
      'offline_orders',
      'offline_inventory',
      'offline_staff',
      'offline_menu',
    ]);
    this.notifyStatusChange();
  }

  public getOfflineCapabilities(): OfflineCapabilities {
    return { ...this.capabilities };
  }

  public async getPendingChanges(): Promise<SyncQueue[]> {
    return this.syncQueue.filter(item => item.status === 'pending');
  }

  public async retryFailedSyncs() {
    const failedItems = this.syncQueue.filter(item => item.status === 'failed');
    
    failedItems.forEach(item => {
      item.status = 'pending';
      item.retries = 0;
    });

    await this.saveSyncQueue();
    this.performSync();
  }

  public async exportSyncQueue(): Promise<string> {
    const data = {
      exportDate: new Date().toISOString(),
      deviceInfo: {
        isOnline: this.isOnline,
        capabilities: this.capabilities,
      },
      syncQueue: this.syncQueue,
    };

    return JSON.stringify(data, null, 2);
  }
}

export default new OfflineSyncService();