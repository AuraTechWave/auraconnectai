import { useEffect, useState, useCallback } from 'react';
import { syncManager, type SyncState } from '@sync';
import database from '@database/index';
import { Q } from '@nozbe/watermelondb';
import { withObservables } from '@nozbe/with-observables';

export interface UseOfflineSyncResult {
  syncState: SyncState;
  sync: () => Promise<void>;
  forceSync: () => Promise<void>;
  queueOperation: (operation: any) => Promise<void>;
  clearQueue: () => Promise<void>;
  isOffline: boolean;
  hasPendingChanges: boolean;
}

export const useOfflineSync = (): UseOfflineSyncResult => {
  const [syncState, setSyncState] = useState<SyncState>(syncManager.getState());

  useEffect(() => {
    const handleStateChange = (newState: SyncState) => {
      setSyncState(newState);
    };

    syncManager.on('stateChange', handleStateChange);

    return () => {
      syncManager.off('stateChange', handleStateChange);
    };
  }, []);

  const sync = useCallback(async () => {
    await syncManager.sync();
  }, []);

  const forceSync = useCallback(async () => {
    await syncManager.forceSync();
  }, []);

  const queueOperation = useCallback(async (operation: any) => {
    await syncManager.queueOperation(operation);
  }, []);

  const clearQueue = useCallback(async () => {
    await syncManager.clearQueue();
  }, []);

  return {
    syncState,
    sync,
    forceSync,
    queueOperation,
    clearQueue,
    isOffline: !syncState.isOnline,
    hasPendingChanges: syncState.pendingChanges > 0,
  };
};

// Higher-order component to observe collection changes
export const withOfflineSync = withObservables(
  ['collection'],
  ({ collection }: { collection: string }) => {
    const dbCollection = database.collections.get(collection);
    return {
      pendingRecords: dbCollection
        .query(Q.where('sync_status', Q.oneOf(['pending', 'conflict'])))
        .observeCount(),
    };
  },
);

// Hook to observe specific record sync status
export const useRecordSyncStatus = (collection: string, recordId: string) => {
  const [syncStatus, setSyncStatus] = useState<string>('synced');

  useEffect(() => {
    const dbCollection = database.collections.get(collection);
    
    const subscription = dbCollection
      .findAndObserve(recordId)
      .subscribe(
        record => {
          setSyncStatus(record.syncStatus);
        },
        error => {
          console.error('Error observing record sync status:', error);
        },
      );

    return () => subscription.unsubscribe();
  }, [collection, recordId]);

  return syncStatus;
};

// Hook to track collection sync progress
export const useCollectionSync = (collection: string) => {
  const [stats, setStats] = useState({
    total: 0,
    pending: 0,
    synced: 0,
    conflicts: 0,
  });

  useEffect(() => {
    const dbCollection = database.collections.get(collection);
    
    const updateStats = async () => {
      const [total, pending, conflicts] = await Promise.all([
        dbCollection.query().fetchCount(),
        dbCollection.query(Q.where('sync_status', 'pending')).fetchCount(),
        dbCollection.query(Q.where('sync_status', 'conflict')).fetchCount(),
      ]);
      
      setStats({
        total,
        pending,
        conflicts,
        synced: total - pending - conflicts,
      });
    };

    updateStats();
    
    // Update stats when sync state changes
    const handleSyncComplete = () => {
      updateStats();
    };
    
    syncManager.on('syncComplete', handleSyncComplete);
    
    return () => {
      syncManager.off('syncComplete', handleSyncComplete);
    };
  }, [collection]);

  return stats;
};