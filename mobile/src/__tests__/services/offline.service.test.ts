import NetInfo from '@react-native-community/netinfo';
import { MMKV } from 'react-native-mmkv';

import { offlineService } from '@services/offline.service';
import { apiClient } from '@services/api.client';
import { encryptionService } from '@utils/encryption';
import { OFFLINE_CONFIG, STORAGE_KEYS } from '@constants/config';
import * as toastUtils from '@utils/toast';

jest.mock('@react-native-community/netinfo');
jest.mock('react-native-mmkv');
jest.mock('@services/api.client');
jest.mock('@utils/encryption');
jest.mock('@utils/toast');

describe('Offline Service', () => {
  let mockStorage: any;
  let mockNetInfo: any;

  beforeEach(() => {
    jest.clearAllMocks();

    // Mock MMKV storage
    mockStorage = {
      getString: jest.fn(),
      set: jest.fn(),
      delete: jest.fn(),
    };
    (MMKV as jest.MockedClass<typeof MMKV>).mockImplementation(
      () => mockStorage,
    );

    // Mock NetInfo
    mockNetInfo = {
      isConnected: true,
    };
    (NetInfo.addEventListener as jest.Mock).mockImplementation(callback => {
      // Store the callback for later use
      mockNetInfo.callback = callback;
      return jest.fn(); // unsubscribe function
    });
  });

  describe('Queue Management', () => {
    it('should queue request when offline', async () => {
      const request = {
        config: {
          method: 'POST',
          url: '/api/test',
          data: { test: 'data' },
          params: {},
        },
      };

      mockStorage.getString.mockReturnValue(null);
      (encryptionService.encrypt as jest.Mock).mockReturnValue(
        'encrypted-data',
      );

      await offlineService.queueRequest(request);

      expect(mockStorage.set).toHaveBeenCalledWith(
        STORAGE_KEYS.OFFLINE_QUEUE,
        expect.stringContaining('encrypted-data'),
      );
      expect(toastUtils.showToast).toHaveBeenCalledWith(
        'info',
        'Offline',
        expect.stringContaining('Request queued'),
      );
    });

    it('should enforce queue size limit', async () => {
      // Create a full queue
      const fullQueue = Array.from(
        { length: OFFLINE_CONFIG.MAX_QUEUE_SIZE },
        (_, i) => ({
          id: i.toString(),
          timestamp: new Date().toISOString(),
          config: { method: 'GET', url: `/test${i}` },
          retryCount: 0,
        }),
      );

      mockStorage.getString.mockReturnValue(JSON.stringify(fullQueue));

      const request = {
        config: {
          method: 'POST',
          url: '/api/test',
          data: { test: 'data' },
        },
      };

      await offlineService.queueRequest(request);

      expect(mockStorage.set).not.toHaveBeenCalled();
      expect(toastUtils.showToast).toHaveBeenCalledWith(
        'warning',
        'Queue Full',
        expect.any(String),
      );
    });

    it('should encrypt sensitive data when enabled', async () => {
      const sensitiveData = { password: 'secret123', token: 'abc123' };
      const request = {
        config: {
          method: 'POST',
          url: '/api/auth',
          data: sensitiveData,
        },
      };

      mockStorage.getString.mockReturnValue(null);
      (encryptionService.encrypt as jest.Mock).mockReturnValue(
        'encrypted-sensitive-data',
      );

      await offlineService.queueRequest(request);

      expect(encryptionService.encrypt).toHaveBeenCalledWith(sensitiveData);

      const savedQueue = JSON.parse(mockStorage.set.mock.calls[0][1]);
      expect(savedQueue[0].config.data).toBe('encrypted-sensitive-data');
    });

    it('should clear queue', () => {
      offlineService.clearQueue();

      expect(mockStorage.delete).toHaveBeenCalledWith(
        STORAGE_KEYS.OFFLINE_QUEUE,
      );
    });

    it('should return correct queue size', () => {
      const queue = [
        { id: '1', config: {} },
        { id: '2', config: {} },
      ];
      mockStorage.getString.mockReturnValue(JSON.stringify(queue));

      const size = offlineService.getQueueSize();

      expect(size).toBe(2);
    });
  });

  describe('Sync Process', () => {
    it('should sync queued requests when online', async () => {
      const queue = [
        {
          id: '1',
          timestamp: new Date().toISOString(),
          config: { method: 'POST', url: '/api/test1', data: 'encrypted1' },
          retryCount: 0,
        },
        {
          id: '2',
          timestamp: new Date().toISOString(),
          config: { method: 'GET', url: '/api/test2', params: { id: 1 } },
          retryCount: 0,
        },
      ];

      mockStorage.getString.mockReturnValue(JSON.stringify(queue));
      (encryptionService.decrypt as jest.Mock).mockReturnValueOnce({
        original: 'data1',
      });
      (apiClient.post as jest.Mock).mockResolvedValue({ data: 'success' });
      (apiClient.get as jest.Mock).mockResolvedValue({ data: 'success' });

      await offlineService.syncOfflineQueue();

      expect(apiClient.post).toHaveBeenCalledWith(
        '/api/test1',
        { original: 'data1' },
        { params: undefined },
      );
      expect(apiClient.get).toHaveBeenCalledWith('/api/test2', {
        params: { id: 1 },
      });
      expect(mockStorage.set).toHaveBeenCalledWith(
        STORAGE_KEYS.OFFLINE_QUEUE,
        '[]',
      );
      expect(toastUtils.showToast).toHaveBeenCalledWith(
        'success',
        'Sync Complete',
        expect.any(String),
      );
    });

    it('should handle sync failures and retry', async () => {
      const queue = [
        {
          id: '1',
          timestamp: new Date().toISOString(),
          config: { method: 'POST', url: '/api/test1', data: {} },
          retryCount: 0,
        },
      ];

      mockStorage.getString.mockReturnValue(JSON.stringify(queue));
      (apiClient.post as jest.Mock).mockRejectedValue(
        new Error('Network error'),
      );

      await offlineService.syncOfflineQueue();

      // Should save failed request with incremented retry count
      const savedQueue = JSON.parse(mockStorage.set.mock.calls[0][1]);
      expect(savedQueue).toHaveLength(1);
      expect(savedQueue[0].retryCount).toBe(1);
      expect(toastUtils.showToast).toHaveBeenCalledWith(
        'warning',
        'Sync Partial',
        expect.any(String),
      );
    });

    it('should remove requests that exceed retry limit', async () => {
      const queue = [
        {
          id: '1',
          timestamp: new Date().toISOString(),
          config: { method: 'POST', url: '/api/test1', data: {} },
          retryCount: OFFLINE_CONFIG.MAX_RETRY_COUNT - 1,
        },
      ];

      mockStorage.getString.mockReturnValue(JSON.stringify(queue));
      (apiClient.post as jest.Mock).mockRejectedValue(
        new Error('Network error'),
      );

      await offlineService.syncOfflineQueue();

      // Should not save request that exceeds retry limit
      const savedQueue = JSON.parse(mockStorage.set.mock.calls[0][1]);
      expect(savedQueue).toHaveLength(0);
    });

    it('should process requests in batches', async () => {
      // Create queue larger than batch size
      const queueSize = OFFLINE_CONFIG.SYNC_BATCH_SIZE * 2 + 3;
      const queue = Array.from({ length: queueSize }, (_, i) => ({
        id: i.toString(),
        timestamp: new Date().toISOString(),
        config: { method: 'GET', url: `/api/test${i}` },
        retryCount: 0,
      }));

      mockStorage.getString.mockReturnValue(JSON.stringify(queue));
      (apiClient.get as jest.Mock).mockResolvedValue({ data: 'success' });

      await offlineService.syncOfflineQueue();

      // Verify all requests were made
      expect(apiClient.get).toHaveBeenCalledTimes(queueSize);

      // Verify empty queue was saved
      expect(mockStorage.set).toHaveBeenCalledWith(
        STORAGE_KEYS.OFFLINE_QUEUE,
        '[]',
      );
    });

    it('should not sync when already in progress', async () => {
      const queue = [{ id: '1', config: {} }];
      mockStorage.getString.mockReturnValue(JSON.stringify(queue));

      // Start first sync
      const firstSync = offlineService.syncOfflineQueue();

      // Try to start second sync immediately
      await offlineService.syncOfflineQueue();

      // Wait for first sync
      await firstSync;

      // API should only be called once
      expect(apiClient.get).toHaveBeenCalledTimes(0);
      expect(apiClient.post).toHaveBeenCalledTimes(0);
    });
  });

  describe('Network Monitoring', () => {
    it('should trigger sync when coming online', async () => {
      const queue = [
        { id: '1', config: { method: 'GET', url: '/test' }, retryCount: 0 },
      ];
      mockStorage.getString.mockReturnValue(JSON.stringify(queue));
      (apiClient.get as jest.Mock).mockResolvedValue({ data: 'success' });

      // Simulate going offline then online
      const service = require('@services/offline.service').offlineService;

      // Trigger network change to offline
      mockNetInfo.callback({ isConnected: false });

      // Then back online
      mockNetInfo.callback({ isConnected: true });

      // Give time for sync to complete
      await new Promise(resolve => setTimeout(resolve, 100));

      expect(apiClient.get).toHaveBeenCalled();
    });

    it('should notify subscribers of network changes', () => {
      const subscriber = jest.fn();
      const unsubscribe = offlineService.subscribe(subscriber);

      // Trigger network change
      mockNetInfo.callback({ isConnected: false });

      expect(subscriber).toHaveBeenCalledWith(false);

      // Unsubscribe and verify no more calls
      unsubscribe();
      mockNetInfo.callback({ isConnected: true });

      expect(subscriber).toHaveBeenCalledTimes(1);
    });
  });
});
