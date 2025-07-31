import messaging, { FirebaseMessagingTypes } from '@react-native-firebase/messaging';
import notifee, { 
  AndroidImportance, 
  AndroidStyle,
  EventType,
  Notification,
  NotificationAndroid,
  NotificationIOS,
  TimestampTrigger,
  TriggerType
} from '@notifee/react-native';
import PushNotification from 'react-native-push-notification';
import { Platform } from 'react-native';
import AsyncStorage from '@react-native-async-storage/async-storage';
import { logger } from '@utils/logger';
import { NOTIFICATION_CONFIG, STORAGE_KEYS } from '@constants/config';
import { NotificationPreferences, NotificationChannel } from './types';
import { NotificationHandler } from './NotificationHandler';
import { EventEmitter } from 'events';

export class NotificationService extends EventEmitter {
  private static instance: NotificationService;
  private notificationHandler: NotificationHandler;
  private fcmToken: string | null = null;
  private isInitialized = false;
  private preferences: NotificationPreferences = {
    enabled: true,
    orderUpdates: true,
    promotions: false,
    sound: true,
    vibration: true,
    doNotDisturb: {
      enabled: false,
      startTime: '22:00',
      endTime: '07:00',
    },
  };

  private constructor() {
    super();
    this.notificationHandler = new NotificationHandler();
  }

  static getInstance(): NotificationService {
    if (!NotificationService.instance) {
      NotificationService.instance = new NotificationService();
    }
    return NotificationService.instance;
  }

  async initialize(): Promise<void> {
    if (this.isInitialized) {
      logger.debug('Notification service already initialized');
      return;
    }

    try {
      // Load preferences
      await this.loadPreferences();

      // Request permissions
      const hasPermission = await this.requestPermission();
      if (!hasPermission) {
        logger.warn('Notification permission denied');
        return;
      }

      // Initialize Firebase messaging
      await this.initializeFirebase();

      // Create notification channels (Android)
      await this.createNotificationChannels();

      // Configure local notifications
      this.configureLocalNotifications();

      // Set up notification handlers
      this.setupNotificationHandlers();

      // Register device token
      await this.registerDeviceToken();

      this.isInitialized = true;
      logger.info('Notification service initialized successfully');
    } catch (error) {
      logger.error('Failed to initialize notification service', error);
      throw error;
    }
  }

  private async requestPermission(): Promise<boolean> {
    try {
      if (Platform.OS === 'ios') {
        const authStatus = await messaging().requestPermission();
        const enabled =
          authStatus === messaging.AuthorizationStatus.AUTHORIZED ||
          authStatus === messaging.AuthorizationStatus.PROVISIONAL;
        return enabled;
      } else {
        // Android permissions are handled differently
        return true;
      }
    } catch (error) {
      logger.error('Failed to request notification permission', error);
      return false;
    }
  }

  private async initializeFirebase(): Promise<void> {
    try {
      // Get FCM token
      this.fcmToken = await messaging().getToken();
      logger.debug('FCM token obtained', { token: this.fcmToken });

      // Listen for token refresh
      messaging().onTokenRefresh(token => {
        this.fcmToken = token;
        this.emit('tokenRefresh', token);
        this.registerDeviceToken();
      });
    } catch (error) {
      logger.error('Failed to initialize Firebase messaging', error);
    }
  }

  private async createNotificationChannels(): Promise<void> {
    if (Platform.OS !== 'android') return;

    try {
      // Order updates channel
      await notifee.createChannel({
        id: NotificationChannel.ORDER_UPDATES,
        name: 'Order Updates',
        description: 'Notifications for order status changes',
        importance: AndroidImportance.HIGH,
        sound: 'order_notification',
        vibration: true,
        badge: true,
      });

      // Promotions channel
      await notifee.createChannel({
        id: NotificationChannel.PROMOTIONS,
        name: 'Promotions',
        description: 'Promotional offers and announcements',
        importance: AndroidImportance.DEFAULT,
        sound: 'default',
        vibration: false,
        badge: false,
      });

      // System channel
      await notifee.createChannel({
        id: NotificationChannel.SYSTEM,
        name: 'System',
        description: 'Important system notifications',
        importance: AndroidImportance.HIGH,
        sound: 'default',
        vibration: true,
        badge: true,
      });

      logger.info('Notification channels created');
    } catch (error) {
      logger.error('Failed to create notification channels', error);
    }
  }

  private configureLocalNotifications(): void {
    PushNotification.configure({
      onRegister: (token) => {
        logger.debug('Local notification token', token);
      },

      onNotification: (notification) => {
        logger.debug('Local notification received', notification);
        this.notificationHandler.handleLocalNotification(notification);
      },

      onAction: (notification) => {
        logger.debug('Notification action', notification);
        this.notificationHandler.handleNotificationAction(notification);
      },

      permissions: {
        alert: true,
        badge: true,
        sound: true,
      },

      popInitialNotification: true,
      requestPermissions: Platform.OS === 'ios',
    });
  }

  private setupNotificationHandlers(): void {
    // Foreground notifications
    messaging().onMessage(async remoteMessage => {
      logger.debug('Foreground notification received', remoteMessage);
      await this.handleForegroundNotification(remoteMessage);
    });

    // Background notifications
    messaging().setBackgroundMessageHandler(async remoteMessage => {
      logger.debug('Background notification received', remoteMessage);
      await this.handleBackgroundNotification(remoteMessage);
    });

    // Notification interactions
    notifee.onForegroundEvent(({ type, detail }) => {
      switch (type) {
        case EventType.DISMISSED:
          logger.debug('Notification dismissed', detail.notification);
          break;
        case EventType.PRESS:
          logger.debug('Notification pressed', detail.notification);
          this.handleNotificationPress(detail.notification);
          break;
        case EventType.ACTION_PRESS:
          logger.debug('Notification action pressed', detail);
          this.handleActionPress(detail.notification, detail.pressAction);
          break;
      }
    });

    // Background event handler
    notifee.onBackgroundEvent(async ({ type, detail }) => {
      logger.debug('Background notification event', { type, detail });
      if (type === EventType.PRESS) {
        await this.handleNotificationPress(detail.notification);
      }
    });
  }

  private async handleForegroundNotification(
    remoteMessage: FirebaseMessagingTypes.RemoteMessage,
  ): Promise<void> {
    if (!this.shouldShowNotification(remoteMessage)) {
      return;
    }

    const notification = this.createNotificationFromRemoteMessage(remoteMessage);
    await this.displayNotification(notification);
  }

  private async handleBackgroundNotification(
    remoteMessage: FirebaseMessagingTypes.RemoteMessage,
  ): Promise<void> {
    // Background notifications are automatically displayed by the OS
    // Just log and store for history
    await this.storeNotification(remoteMessage);
  }

  private createNotificationFromRemoteMessage(
    remoteMessage: FirebaseMessagingTypes.RemoteMessage,
  ): Notification {
    const { notification, data } = remoteMessage;
    const channel = this.getChannelFromData(data);

    const notificationPayload: Notification = {
      id: remoteMessage.messageId || Date.now().toString(),
      title: notification?.title || 'AuraConnect',
      body: notification?.body || '',
      data: data || {},
      android: {
        channelId: channel,
        importance: AndroidImportance.HIGH,
        pressAction: {
          id: 'default',
          launchActivity: 'default',
        },
        style: this.getNotificationStyle(data),
        actions: this.getNotificationActions(data),
      },
      ios: {
        categoryId: data?.category || 'default',
        attachments: notification?.ios?.attachments || [],
      },
    };

    return notificationPayload;
  }

  private getChannelFromData(data: any): string {
    if (data?.type === 'order_update') {
      return NotificationChannel.ORDER_UPDATES;
    } else if (data?.type === 'promotion') {
      return NotificationChannel.PROMOTIONS;
    }
    return NotificationChannel.SYSTEM;
  }

  private getNotificationStyle(data: any): AndroidStyle | undefined {
    if (data?.type === 'order_update' && data?.items) {
      return {
        type: AndroidStyle.BIGTEXT,
        text: data.items,
      };
    }
    return undefined;
  }

  private getNotificationActions(data: any): NotificationAndroid['actions'] {
    const actions = [];

    if (data?.type === 'order_update') {
      actions.push({
        title: 'View Order',
        pressAction: {
          id: 'view_order',
          launchActivity: 'default',
        },
      });

      if (data?.status === 'ready') {
        actions.push({
          title: 'Notify Customer',
          pressAction: {
            id: 'notify_customer',
          },
        });
      }
    }

    return actions;
  }

  async displayNotification(notification: Notification): Promise<void> {
    try {
      await notifee.displayNotification(notification);
      await this.storeNotificationLocally(notification);
      this.emit('notificationDisplayed', notification);
    } catch (error) {
      logger.error('Failed to display notification', error);
    }
  }

  async scheduleNotification(
    notification: Notification,
    timestamp: number,
  ): Promise<void> {
    try {
      const trigger: TimestampTrigger = {
        type: TriggerType.TIMESTAMP,
        timestamp,
      };

      await notifee.createTriggerNotification(notification, trigger);
      logger.info('Notification scheduled', { id: notification.id, timestamp });
    } catch (error) {
      logger.error('Failed to schedule notification', error);
    }
  }

  async cancelNotification(notificationId: string): Promise<void> {
    try {
      await notifee.cancelNotification(notificationId);
      logger.info('Notification cancelled', { id: notificationId });
    } catch (error) {
      logger.error('Failed to cancel notification', error);
    }
  }

  async cancelAllNotifications(): Promise<void> {
    try {
      await notifee.cancelAllNotifications();
      logger.info('All notifications cancelled');
    } catch (error) {
      logger.error('Failed to cancel all notifications', error);
    }
  }

  private async handleNotificationPress(notification?: Notification): Promise<void> {
    if (!notification) return;

    const { data } = notification;
    this.emit('notificationPress', notification);

    // Navigate based on notification type
    if (data?.type === 'order_update' && data?.orderId) {
      this.emit('navigateToOrder', data.orderId);
    }
  }

  private async handleActionPress(
    notification: Notification | undefined,
    action: any,
  ): Promise<void> {
    if (!notification || !action) return;

    this.emit('notificationAction', { notification, action });

    switch (action.id) {
      case 'view_order':
        if (notification.data?.orderId) {
          this.emit('navigateToOrder', notification.data.orderId);
        }
        break;
      case 'notify_customer':
        if (notification.data?.orderId) {
          this.emit('notifyCustomer', notification.data.orderId);
        }
        break;
    }
  }

  private shouldShowNotification(remoteMessage: FirebaseMessagingTypes.RemoteMessage): boolean {
    if (!this.preferences.enabled) return false;

    const { data } = remoteMessage;
    if (data?.type === 'order_update' && !this.preferences.orderUpdates) return false;
    if (data?.type === 'promotion' && !this.preferences.promotions) return false;

    // Check do not disturb
    if (this.preferences.doNotDisturb.enabled) {
      const now = new Date();
      const currentTime = `${now.getHours().toString().padStart(2, '0')}:${now.getMinutes().toString().padStart(2, '0')}`;
      const { startTime, endTime } = this.preferences.doNotDisturb;
      
      if (startTime <= endTime) {
        if (currentTime >= startTime && currentTime <= endTime) return false;
      } else {
        if (currentTime >= startTime || currentTime <= endTime) return false;
      }
    }

    return true;
  }

  private async registerDeviceToken(): Promise<void> {
    if (!this.fcmToken) return;

    try {
      // Send token to backend
      this.emit('registerToken', this.fcmToken);
      logger.info('Device token registered');
    } catch (error) {
      logger.error('Failed to register device token', error);
    }
  }

  private async loadPreferences(): Promise<void> {
    try {
      const stored = await AsyncStorage.getItem(STORAGE_KEYS.NOTIFICATION_PREFERENCES);
      if (stored) {
        this.preferences = { ...this.preferences, ...JSON.parse(stored) };
      }
    } catch (error) {
      logger.error('Failed to load notification preferences', error);
    }
  }

  async savePreferences(preferences: Partial<NotificationPreferences>): Promise<void> {
    try {
      this.preferences = { ...this.preferences, ...preferences };
      await AsyncStorage.setItem(
        STORAGE_KEYS.NOTIFICATION_PREFERENCES,
        JSON.stringify(this.preferences),
      );
      this.emit('preferencesUpdated', this.preferences);
    } catch (error) {
      logger.error('Failed to save notification preferences', error);
    }
  }

  private async storeNotification(
    remoteMessage: FirebaseMessagingTypes.RemoteMessage,
  ): Promise<void> {
    try {
      const notifications = await this.getStoredNotifications();
      notifications.unshift({
        id: remoteMessage.messageId || Date.now().toString(),
        title: remoteMessage.notification?.title || '',
        body: remoteMessage.notification?.body || '',
        data: remoteMessage.data || {},
        timestamp: Date.now(),
        read: false,
      });

      // Keep only last N notifications
      const trimmed = notifications.slice(0, NOTIFICATION_CONFIG.MAX_STORED_NOTIFICATIONS);
      await AsyncStorage.setItem(
        STORAGE_KEYS.NOTIFICATION_HISTORY,
        JSON.stringify(trimmed),
      );
    } catch (error) {
      logger.error('Failed to store notification', error);
    }
  }

  private async storeNotificationLocally(notification: Notification): Promise<void> {
    try {
      const notifications = await this.getStoredNotifications();
      notifications.unshift({
        id: notification.id || Date.now().toString(),
        title: notification.title || '',
        body: notification.body || '',
        data: notification.data || {},
        timestamp: Date.now(),
        read: false,
      });

      const trimmed = notifications.slice(0, NOTIFICATION_CONFIG.MAX_STORED_NOTIFICATIONS);
      await AsyncStorage.setItem(
        STORAGE_KEYS.NOTIFICATION_HISTORY,
        JSON.stringify(trimmed),
      );
    } catch (error) {
      logger.error('Failed to store notification locally', error);
    }
  }

  async getStoredNotifications(): Promise<any[]> {
    try {
      const stored = await AsyncStorage.getItem(STORAGE_KEYS.NOTIFICATION_HISTORY);
      return stored ? JSON.parse(stored) : [];
    } catch (error) {
      logger.error('Failed to get stored notifications', error);
      return [];
    }
  }

  async markNotificationAsRead(notificationId: string): Promise<void> {
    try {
      const notifications = await this.getStoredNotifications();
      const updated = notifications.map(n => 
        n.id === notificationId ? { ...n, read: true } : n
      );
      await AsyncStorage.setItem(
        STORAGE_KEYS.NOTIFICATION_HISTORY,
        JSON.stringify(updated),
      );
    } catch (error) {
      logger.error('Failed to mark notification as read', error);
    }
  }

  async clearNotificationHistory(): Promise<void> {
    try {
      await AsyncStorage.removeItem(STORAGE_KEYS.NOTIFICATION_HISTORY);
      logger.info('Notification history cleared');
    } catch (error) {
      logger.error('Failed to clear notification history', error);
    }
  }

  getPreferences(): NotificationPreferences {
    return { ...this.preferences };
  }

  getFCMToken(): string | null {
    return this.fcmToken;
  }

  isInitialized(): boolean {
    return this.isInitialized;
  }
}