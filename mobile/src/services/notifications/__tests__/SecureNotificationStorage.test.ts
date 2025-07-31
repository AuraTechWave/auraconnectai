import AsyncStorage from '@react-native-async-storage/async-storage';
import { SecureNotificationStorage } from '../SecureNotificationStorage';
import { encrypt, decrypt } from '@utils/encryption';
import { NOTIFICATION_CONFIG, STORAGE_KEYS } from '@constants/config';
import { logger } from '@utils/logger';

jest.mock('@react-native-async-storage/async-storage');
jest.mock('@utils/encryption');
jest.mock('@utils/logger');

describe('SecureNotificationStorage', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    (encrypt as jest.Mock).mockImplementation((data) => Promise.resolve(`encrypted:${data}`));
    (decrypt as jest.Mock).mockImplementation((data) => Promise.resolve(data.replace('encrypted:', '')));
  });

  describe('saveNotificationHistory', () => {
    it('should encrypt and save notification history when encryption is enabled', async () => {
      const notifications = [
        { id: '1', title: 'Test', body: 'Test body', data: {}, timestamp: Date.now(), read: false },
      ];

      await SecureNotificationStorage.saveNotificationHistory(notifications);

      expect(encrypt).toHaveBeenCalledWith(JSON.stringify(notifications));
      expect(AsyncStorage.setItem).toHaveBeenCalledWith(
        STORAGE_KEYS.NOTIFICATION_HISTORY,
        `encrypted:${JSON.stringify(notifications)}`
      );
    });

    it('should save without encryption when disabled', async () => {
      const originalEncrypt = NOTIFICATION_CONFIG.NOTIFICATION_HISTORY_ENCRYPT;
      (NOTIFICATION_CONFIG as any).NOTIFICATION_HISTORY_ENCRYPT = false;

      const notifications = [{ id: '1', title: 'Test', body: 'Test body', data: {}, timestamp: Date.now(), read: false }];
      await SecureNotificationStorage.saveNotificationHistory(notifications);

      expect(encrypt).not.toHaveBeenCalled();
      expect(AsyncStorage.setItem).toHaveBeenCalledWith(
        STORAGE_KEYS.NOTIFICATION_HISTORY,
        JSON.stringify(notifications)
      );

      (NOTIFICATION_CONFIG as any).NOTIFICATION_HISTORY_ENCRYPT = originalEncrypt;
    });

    it('should throw and log error on failure', async () => {
      const error = new Error('Storage error');
      (AsyncStorage.setItem as jest.Mock).mockRejectedValue(error);

      await expect(SecureNotificationStorage.saveNotificationHistory([])).rejects.toThrow(error);
      expect(logger.error).toHaveBeenCalledWith('Failed to save notification history', error);
    });
  });

  describe('getNotificationHistory', () => {
    it('should decrypt stored notifications', async () => {
      const notifications = [{ id: '1', title: 'Test' }];
      const encrypted = `encrypted:${JSON.stringify(notifications)}`;
      (AsyncStorage.getItem as jest.Mock).mockResolvedValue(encrypted);

      const result = await SecureNotificationStorage.getNotificationHistory();

      expect(decrypt).toHaveBeenCalledWith(encrypted);
      expect(result).toEqual(notifications);
    });

    it('should handle migration from unencrypted data', async () => {
      const notifications = [{ id: '1', title: 'Test' }];
      const plainData = JSON.stringify(notifications);
      (AsyncStorage.getItem as jest.Mock).mockResolvedValue(plainData);
      (decrypt as jest.Mock).mockRejectedValue(new Error('Decryption failed'));

      const result = await SecureNotificationStorage.getNotificationHistory();

      expect(logger.warn).toHaveBeenCalledWith('Failed to decrypt notification history, trying plain text');
      expect(result).toEqual(notifications);
    });

    it('should return empty array when no data exists', async () => {
      (AsyncStorage.getItem as jest.Mock).mockResolvedValue(null);

      const result = await SecureNotificationStorage.getNotificationHistory();

      expect(result).toEqual([]);
    });

    it('should return empty array on error', async () => {
      (AsyncStorage.getItem as jest.Mock).mockRejectedValue(new Error('Storage error'));

      const result = await SecureNotificationStorage.getNotificationHistory();

      expect(result).toEqual([]);
      expect(logger.error).toHaveBeenCalled();
    });
  });

  describe('saveFCMToken', () => {
    it('should always encrypt FCM tokens', async () => {
      const token = 'test-fcm-token';

      await SecureNotificationStorage.saveFCMToken(token);

      expect(encrypt).toHaveBeenCalledWith(token);
      expect(AsyncStorage.setItem).toHaveBeenCalledWith(
        STORAGE_KEYS.FCM_TOKEN,
        'encrypted:test-fcm-token'
      );
    });

    it('should log in development mode only', async () => {
      const originalDev = __DEV__;
      (global as any).__DEV__ = true;

      await SecureNotificationStorage.saveFCMToken('token');

      expect(logger.debug).toHaveBeenCalledWith('FCM token saved (encrypted)');

      (global as any).__DEV__ = false;
      jest.clearAllMocks();

      await SecureNotificationStorage.saveFCMToken('token');

      expect(logger.debug).not.toHaveBeenCalled();

      (global as any).__DEV__ = originalDev;
    });
  });

  describe('getFCMToken', () => {
    it('should decrypt stored token', async () => {
      const token = 'test-fcm-token';
      (AsyncStorage.getItem as jest.Mock).mockResolvedValue(`encrypted:${token}`);

      const result = await SecureNotificationStorage.getFCMToken();

      expect(decrypt).toHaveBeenCalledWith(`encrypted:${token}`);
      expect(result).toBe(token);
    });

    it('should return null when no token exists', async () => {
      (AsyncStorage.getItem as jest.Mock).mockResolvedValue(null);

      const result = await SecureNotificationStorage.getFCMToken();

      expect(result).toBeNull();
    });
  });

  describe('trimNotificationHistory', () => {
    it('should trim notifications when exceeding max size', async () => {
      const notifications = Array.from({ length: 150 }, (_, i) => ({
        id: `${i}`,
        title: `Notification ${i}`,
        body: 'Body',
        data: {},
        timestamp: Date.now(),
        read: false,
      }));

      (AsyncStorage.getItem as jest.Mock).mockResolvedValue(
        `encrypted:${JSON.stringify(notifications)}`
      );

      await SecureNotificationStorage.trimNotificationHistory(100);

      // Should trim in batches
      expect(AsyncStorage.setItem).toHaveBeenCalled();
    });

    it('should not trim when under max size', async () => {
      const notifications = Array.from({ length: 50 }, (_, i) => ({
        id: `${i}`,
        title: `Notification ${i}`,
        body: 'Body',
        data: {},
        timestamp: Date.now(),
        read: false,
      }));

      (AsyncStorage.getItem as jest.Mock).mockResolvedValue(
        `encrypted:${JSON.stringify(notifications)}`
      );

      jest.clearAllMocks();

      await SecureNotificationStorage.trimNotificationHistory(100);

      expect(AsyncStorage.setItem).not.toHaveBeenCalled();
    });
  });

  describe('clearAll', () => {
    it('should remove all notification-related keys', async () => {
      await SecureNotificationStorage.clearAll();

      expect(AsyncStorage.multiRemove).toHaveBeenCalledWith([
        STORAGE_KEYS.NOTIFICATION_HISTORY,
        STORAGE_KEYS.NOTIFICATION_PREFERENCES,
        STORAGE_KEYS.FCM_TOKEN,
      ]);
    });

    it('should log error on failure', async () => {
      const error = new Error('Clear failed');
      (AsyncStorage.multiRemove as jest.Mock).mockRejectedValue(error);

      await SecureNotificationStorage.clearAll();

      expect(logger.error).toHaveBeenCalledWith('Failed to clear notification data', error);
    });
  });
});