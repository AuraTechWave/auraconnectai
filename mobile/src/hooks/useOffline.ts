import { useEffect, useState } from 'react';
import { offlineService } from '@services/offline.service';

export const useOffline = () => {
  const [isOnline, setIsOnline] = useState(offlineService.isNetworkOnline());
  const [queueSize, setQueueSize] = useState(offlineService.getQueueSize());

  useEffect(() => {
    // Subscribe to network changes
    const unsubscribe = offlineService.subscribe(online => {
      setIsOnline(online);
      setQueueSize(offlineService.getQueueSize());
    });

    return unsubscribe;
  }, []);

  const syncQueue = async () => {
    await offlineService.syncOfflineQueue();
    setQueueSize(offlineService.getQueueSize());
  };

  const clearQueue = () => {
    offlineService.clearQueue();
    setQueueSize(0);
  };

  return {
    isOnline,
    queueSize,
    syncQueue,
    clearQueue,
  };
};
