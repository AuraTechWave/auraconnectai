import { useState, useEffect, useCallback } from 'react';
import offlineSyncService from '@services/offlineSync';
import AsyncStorage from '@react-native-async-storage/async-storage';
import NetInfo from '@react-native-community/netinfo';

interface OfflineState {
  isOffline: boolean;
  syncStatus: {
    lastSync: string | null;
    pendingChanges: number;
    failedSyncs: number;
    isCurrentlySyncing: boolean;
    nextScheduledSync: string | null;
  };
  capabilities: {
    orders: boolean;
    inventory: boolean;
    staff: boolean;
    menu: boolean;
  };
}

interface OfflinePreferences {
  autoSync: boolean;
  syncInterval: number;
  wifiOnly: boolean;
  backgroundSync: boolean;
  conflictResolution: 'local' | 'server';
  queueActions: boolean;
  offlineFeatures: {
    orders: boolean;
    inventory: boolean;
    staff: boolean;
    menu: boolean;
  };
}

export const useEnhancedOffline = () => {
  const [offlineState, setOfflineState] = useState<OfflineState>({
    isOffline: false,
    syncStatus: {
      lastSync: null,
      pendingChanges: 0,
      failedSyncs: 0,
      isCurrentlySyncing: false,
      nextScheduledSync: null,
    },
    capabilities: {
      orders: true,
      inventory: true,
      staff: true,
      menu: true,
    },
  });

  const [preferences, setPreferences] = useState<OfflinePreferences>({
    autoSync: true,
    syncInterval: 15,
    wifiOnly: false,
    backgroundSync: true,
    conflictResolution: 'server',
    queueActions: true,
    offlineFeatures: {
      orders: true,
      inventory: true,
      staff: true,
      menu: true,
    },
  });

  useEffect(() => {
    // Load preferences
    loadPreferences();

    // Subscribe to network state
    const unsubscribeNetInfo = NetInfo.addEventListener(state => {
      setOfflineState(prev => ({
        ...prev,
        isOffline: !state.isConnected,
      }));
    });

    // Subscribe to sync status
    const unsubscribeSyncStatus = offlineSyncService.subscribeToStatus(status => {
      setOfflineState(prev => ({
        ...prev,
        syncStatus: status,
      }));
    });

    // Start auto sync if enabled
    if (preferences.autoSync) {
      offlineSyncService.startAutoSync(preferences.syncInterval);
    }

    return () => {
      unsubscribeNetInfo();
      unsubscribeSyncStatus();
      offlineSyncService.stopAutoSync();
    };
  }, [preferences.autoSync, preferences.syncInterval]);

  const loadPreferences = async () => {
    try {
      const savedPrefs = await AsyncStorage.getItem('offline_preferences');
      if (savedPrefs) {
        setPreferences(JSON.parse(savedPrefs));
      }
    } catch (error) {
      console.error('Error loading offline preferences:', error);
    }
  };

  const updatePreferences = useCallback(async (newPrefs: Partial<OfflinePreferences>) => {
    const updated = { ...preferences, ...newPrefs };
    setPreferences(updated);
    await AsyncStorage.setItem('offline_preferences', JSON.stringify(updated));

    // Restart auto sync if interval changed
    if (newPrefs.syncInterval || newPrefs.autoSync !== undefined) {
      offlineSyncService.stopAutoSync();
      if (updated.autoSync) {
        offlineSyncService.startAutoSync(updated.syncInterval);
      }
    }
  }, [preferences]);

  const queueAction = useCallback(async (
    type: 'order' | 'inventory' | 'staff' | 'menu',
    action: 'create' | 'update' | 'delete',
    data: any,
  ) => {
    if (!preferences.queueActions) {
      throw new Error('Offline actions are disabled');
    }

    if (!preferences.offlineFeatures[type]) {
      throw new Error(`Offline ${type} operations are disabled`);
    }

    try {
      const queueId = await offlineSyncService.addToQueue(type, action, data);
      return { success: true, queueId };
    } catch (error) {
      return { success: false, error: error.message };
    }
  }, [preferences]);

  const syncNow = useCallback(async () => {
    if (offlineState.isOffline) {
      throw new Error('Cannot sync while offline');
    }

    const netState = await NetInfo.fetch();
    if (preferences.wifiOnly && netState.type !== 'wifi') {
      throw new Error('WiFi-only sync is enabled');
    }

    await offlineSyncService.performSync();
  }, [offlineState.isOffline, preferences.wifiOnly]);

  const retryFailedSyncs = useCallback(async () => {
    await offlineSyncService.retryFailedSyncs();
  }, []);

  const clearOfflineData = useCallback(async () => {
    await offlineSyncService.clearOfflineData();
  }, []);

  const getOfflineData = useCallback(async (type: string) => {
    try {
      const data = await AsyncStorage.getItem(`offline_${type}`);
      return data ? JSON.parse(data) : null;
    } catch (error) {
      console.error(`Error getting offline ${type} data:`, error);
      return null;
    }
  }, []);

  const saveOfflineData = useCallback(async (type: string, data: any) => {
    try {
      await AsyncStorage.setItem(`offline_${type}`, JSON.stringify(data));
    } catch (error) {
      console.error(`Error saving offline ${type} data:`, error);
      throw error;
    }
  }, []);

  const getPendingChanges = useCallback(async () => {
    return await offlineSyncService.getPendingChanges();
  }, []);

  const exportSyncQueue = useCallback(async () => {
    return await offlineSyncService.exportSyncQueue();
  }, []);

  const checkCapacity = useCallback(async (type: string) => {
    const capabilities = offlineSyncService.getOfflineCapabilities();
    const typeData = await getOfflineData(type);
    
    if (!typeData) return { used: 0, max: 100, percentage: 0 };

    const count = Array.isArray(typeData) ? typeData.length : Object.keys(typeData).length;
    let max = 100;

    switch (type) {
      case 'orders':
        max = capabilities.orders.maxItems;
        break;
      case 'inventory':
        max = capabilities.inventory.maxItems;
        break;
      case 'menu':
        max = capabilities.menu.maxItems;
        break;
    }

    return {
      used: count,
      max,
      percentage: (count / max) * 100,
    };
  }, [getOfflineData]);

  return {
    // State
    isOffline: offlineState.isOffline,
    syncStatus: offlineState.syncStatus,
    capabilities: offlineState.capabilities,
    preferences,

    // Actions
    updatePreferences,
    queueAction,
    syncNow,
    retryFailedSyncs,
    clearOfflineData,
    
    // Data management
    getOfflineData,
    saveOfflineData,
    getPendingChanges,
    exportSyncQueue,
    checkCapacity,
  };
};