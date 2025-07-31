import AsyncStorage from '@react-native-async-storage/async-storage';
import { encrypt, decrypt } from '@utils/encryption';
import { NOTIFICATION_CONFIG, STORAGE_KEYS } from '@constants/config';
import { logger } from '@utils/logger';
import { StoredNotification, NotificationPreferences } from './types';

export class SecureNotificationStorage {
  // Notification History
  static async saveNotificationHistory(notifications: StoredNotification[]): Promise<void> {
    try {
      const data = JSON.stringify(notifications);
      const toStore = NOTIFICATION_CONFIG.NOTIFICATION_HISTORY_ENCRYPT
        ? await encrypt(data)
        : data;
      
      await AsyncStorage.setItem(STORAGE_KEYS.NOTIFICATION_HISTORY, toStore);
    } catch (error) {
      logger.error('Failed to save notification history', error);
      throw error;
    }
  }

  static async getNotificationHistory(): Promise<StoredNotification[]> {
    try {
      const stored = await AsyncStorage.getItem(STORAGE_KEYS.NOTIFICATION_HISTORY);
      if (!stored) return [];

      let data: string;
      if (NOTIFICATION_CONFIG.NOTIFICATION_HISTORY_ENCRYPT) {
        try {
          data = await decrypt(stored);
        } catch (decryptError) {
          // Handle migration from unencrypted to encrypted
          logger.warn('Failed to decrypt notification history, trying plain text');
          data = stored;
        }
      } else {
        data = stored;
      }

      return JSON.parse(data);
    } catch (error) {
      logger.error('Failed to get notification history', error);
      return [];
    }
  }

  // Notification Preferences
  static async savePreferences(preferences: NotificationPreferences): Promise<void> {
    try {
      const data = JSON.stringify(preferences);
      const toStore = NOTIFICATION_CONFIG.NOTIFICATION_PREFS_ENCRYPT
        ? await encrypt(data)
        : data;
      
      await AsyncStorage.setItem(STORAGE_KEYS.NOTIFICATION_PREFERENCES, toStore);
    } catch (error) {
      logger.error('Failed to save notification preferences', error);
      throw error;
    }
  }

  static async getPreferences(): Promise<NotificationPreferences | null> {
    try {
      const stored = await AsyncStorage.getItem(STORAGE_KEYS.NOTIFICATION_PREFERENCES);
      if (!stored) return null;

      let data: string;
      if (NOTIFICATION_CONFIG.NOTIFICATION_PREFS_ENCRYPT) {
        try {
          data = await decrypt(stored);
        } catch (decryptError) {
          logger.warn('Failed to decrypt preferences, trying plain text');
          data = stored;
        }
      } else {
        data = stored;
      }

      return JSON.parse(data);
    } catch (error) {
      logger.error('Failed to get notification preferences', error);
      return null;
    }
  }

  // FCM Token (never log in production)
  static async saveFCMToken(token: string): Promise<void> {
    try {
      // Always encrypt FCM tokens
      const encrypted = await encrypt(token);
      await AsyncStorage.setItem(STORAGE_KEYS.FCM_TOKEN, encrypted);
      
      if (__DEV__) {
        logger.debug('FCM token saved (encrypted)');
      }
    } catch (error) {
      logger.error('Failed to save FCM token', error);
      throw error;
    }
  }

  static async getFCMToken(): Promise<string | null> {
    try {
      const stored = await AsyncStorage.getItem(STORAGE_KEYS.FCM_TOKEN);
      if (!stored) return null;

      const token = await decrypt(stored);
      return token;
    } catch (error) {
      logger.error('Failed to get FCM token', error);
      return null;
    }
  }

  static async removeFCMToken(): Promise<void> {
    try {
      await AsyncStorage.removeItem(STORAGE_KEYS.FCM_TOKEN);
    } catch (error) {
      logger.error('Failed to remove FCM token', error);
    }
  }

  // Batch operations for performance
  static async trimNotificationHistory(maxSize: number = NOTIFICATION_CONFIG.MAX_STORED_NOTIFICATIONS): Promise<void> {
    try {
      const notifications = await this.getNotificationHistory();
      
      if (notifications.length > maxSize) {
        // Trim in batches to avoid performance issues
        const batchSize = NOTIFICATION_CONFIG.HISTORY_TRIM_BATCH_SIZE;
        const toRemove = notifications.length - maxSize;
        
        for (let i = 0; i < toRemove; i += batchSize) {
          const trimmed = notifications.slice(0, -Math.min(batchSize, toRemove - i));
          await this.saveNotificationHistory(trimmed);
        }
      }
    } catch (error) {
      logger.error('Failed to trim notification history', error);
    }
  }

  // Clear all notification data (for logout)
  static async clearAll(): Promise<void> {
    try {
      await AsyncStorage.multiRemove([
        STORAGE_KEYS.NOTIFICATION_HISTORY,
        STORAGE_KEYS.NOTIFICATION_PREFERENCES,
        STORAGE_KEYS.FCM_TOKEN,
      ]);
    } catch (error) {
      logger.error('Failed to clear notification data', error);
    }
  }
}