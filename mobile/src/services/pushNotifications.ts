import messaging from '@react-native-firebase/messaging';
import notifee, { 
  AndroidImportance, 
  AndroidCategory,
  AndroidGroupAlertBehavior,
  EventType,
  TriggerType,
} from '@notifee/react-native';
import AsyncStorage from '@react-native-async-storage/async-storage';
import { Platform } from 'react-native';

interface NotificationPreferences {
  enabled: boolean;
  orderUpdates: boolean;
  staffAlerts: boolean;
  inventoryAlerts: boolean;
  promotions: boolean;
  sound: boolean;
  vibration: boolean;
  groupSimilar: boolean;
  quietHours: {
    enabled: boolean;
    start: string;
    end: string;
  };
  priority: {
    orders: 'high' | 'medium' | 'low';
    staff: 'high' | 'medium' | 'low';
    inventory: 'high' | 'medium' | 'low';
  };
}

interface NotificationChannel {
  id: string;
  name: string;
  importance: AndroidImportance;
  sound?: string;
  vibration?: boolean;
  category: AndroidCategory;
}

class PushNotificationService {
  private preferences: NotificationPreferences | null = null;
  private channels: Map<string, NotificationChannel> = new Map();
  private notificationGroups: Map<string, string[]> = new Map();

  constructor() {
    this.initializeChannels();
    this.loadPreferences();
    this.setupNotificationHandlers();
  }

  private async initializeChannels() {
    // Create notification channels for Android
    if (Platform.OS === 'android') {
      // High priority channel for orders
      await notifee.createChannel({
        id: 'orders-high',
        name: 'Order Notifications',
        importance: AndroidImportance.HIGH,
        sound: 'order_notification',
        vibration: true,
        category: AndroidCategory.MESSAGE,
      });

      // Medium priority channel for staff
      await notifee.createChannel({
        id: 'staff-medium',
        name: 'Staff Notifications',
        importance: AndroidImportance.DEFAULT,
        sound: 'default',
        vibration: true,
        category: AndroidCategory.REMINDER,
      });

      // Low priority channel for inventory
      await notifee.createChannel({
        id: 'inventory-low',
        name: 'Inventory Notifications',
        importance: AndroidImportance.LOW,
        sound: 'default',
        vibration: false,
        category: AndroidCategory.STATUS,
      });

      // Silent channel for promotions
      await notifee.createChannel({
        id: 'promotions-silent',
        name: 'Promotional Notifications',
        importance: AndroidImportance.MIN,
        vibration: false,
        category: AndroidCategory.PROMO,
      });
    }
  }

  private async loadPreferences() {
    try {
      const prefs = await AsyncStorage.getItem('notification_preferences');
      if (prefs) {
        this.preferences = JSON.parse(prefs);
      } else {
        // Default preferences
        this.preferences = {
          enabled: true,
          orderUpdates: true,
          staffAlerts: true,
          inventoryAlerts: true,
          promotions: false,
          sound: true,
          vibration: true,
          groupSimilar: true,
          quietHours: {
            enabled: false,
            start: '22:00',
            end: '07:00',
          },
          priority: {
            orders: 'high',
            staff: 'medium',
            inventory: 'low',
          },
        };
      }
    } catch (error) {
      console.error('Error loading notification preferences:', error);
    }
  }

  private setupNotificationHandlers() {
    // Handle background messages
    messaging().setBackgroundMessageHandler(async remoteMessage => {
      await this.handleNotification(remoteMessage);
    });

    // Handle foreground messages
    messaging().onMessage(async remoteMessage => {
      await this.handleNotification(remoteMessage);
    });

    // Handle notification interactions
    notifee.onBackgroundEvent(async ({ type, detail }) => {
      if (type === EventType.PRESS) {
        await this.handleNotificationPress(detail.notification);
      }
    });
  }

  public async requestPermission(): Promise<boolean> {
    try {
      const authStatus = await messaging().requestPermission();
      const enabled =
        authStatus === messaging.AuthorizationStatus.AUTHORIZED ||
        authStatus === messaging.AuthorizationStatus.PROVISIONAL;

      if (enabled) {
        await this.registerDevice();
      }

      return enabled;
    } catch (error) {
      console.error('Error requesting permission:', error);
      return false;
    }
  }

  private async registerDevice() {
    try {
      const token = await messaging().getToken();
      // Send token to backend
      await this.sendTokenToBackend(token);
      
      // Listen for token refreshes
      messaging().onTokenRefresh(async newToken => {
        await this.sendTokenToBackend(newToken);
      });
    } catch (error) {
      console.error('Error registering device:', error);
    }
  }

  private async sendTokenToBackend(token: string) {
    // Send FCM token to backend API
    try {
      await fetch('https://api.auraconnect.ai/v1/devices/register', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          token,
          platform: Platform.OS,
          preferences: this.preferences,
        }),
      });
    } catch (error) {
      console.error('Error sending token to backend:', error);
    }
  }

  private async handleNotification(remoteMessage: any) {
    if (!this.preferences?.enabled) {
      return;
    }

    const { data, notification } = remoteMessage;
    const notificationType = data?.type || 'general';

    // Check if this notification type is enabled
    if (!this.shouldShowNotification(notificationType)) {
      return;
    }

    // Check quiet hours
    if (this.isInQuietHours()) {
      return;
    }

    // Get appropriate channel based on type and priority
    const channelId = this.getChannelId(notificationType);

    // Create notification display options
    const notificationOptions: any = {
      title: notification?.title || data?.title,
      body: notification?.body || data?.body,
      android: {
        channelId,
        smallIcon: 'ic_notification',
        color: '#0066CC',
        category: this.getCategory(notificationType),
        importance: this.getImportance(notificationType),
        pressAction: {
          id: 'default',
          launchActivity: 'default',
        },
      },
      ios: {
        categoryId: notificationType,
        sound: this.preferences.sound ? 'default' : undefined,
      },
    };

    // Add data payload
    if (data) {
      notificationOptions.data = data;
    }

    // Handle grouping
    if (this.preferences.groupSimilar) {
      notificationOptions.android.groupId = notificationType;
      notificationOptions.android.groupAlertBehavior = AndroidGroupAlertBehavior.CHILDREN;
      
      // Create or update summary notification
      await this.updateGroupSummary(notificationType);
    }

    // Handle large text
    if (notification?.body && notification.body.length > 50) {
      notificationOptions.android.style = {
        type: 1, // BigTextStyle
        text: notification.body,
      };
    }

    // Display the notification
    await notifee.displayNotification(notificationOptions);
  }

  private shouldShowNotification(type: string): boolean {
    if (!this.preferences) return false;

    switch (type) {
      case 'order':
        return this.preferences.orderUpdates;
      case 'staff':
        return this.preferences.staffAlerts;
      case 'inventory':
        return this.preferences.inventoryAlerts;
      case 'promotion':
        return this.preferences.promotions;
      default:
        return true;
    }
  }

  private isInQuietHours(): boolean {
    if (!this.preferences?.quietHours.enabled) return false;

    const now = new Date();
    const currentTime = `${now.getHours().toString().padStart(2, '0')}:${now.getMinutes().toString().padStart(2, '0')}`;
    
    const { start, end } = this.preferences.quietHours;
    
    // Handle overnight quiet hours
    if (start > end) {
      return currentTime >= start || currentTime < end;
    } else {
      return currentTime >= start && currentTime < end;
    }
  }

  private getChannelId(type: string): string {
    const priority = this.preferences?.priority[type as keyof typeof this.preferences.priority] || 'medium';
    return `${type}-${priority}`;
  }

  private getCategory(type: string): AndroidCategory {
    switch (type) {
      case 'order':
        return AndroidCategory.MESSAGE;
      case 'staff':
        return AndroidCategory.REMINDER;
      case 'inventory':
        return AndroidCategory.STATUS;
      case 'promotion':
        return AndroidCategory.PROMO;
      default:
        return AndroidCategory.SERVICE;
    }
  }

  private getImportance(type: string): AndroidImportance {
    const priority = this.preferences?.priority[type as keyof typeof this.preferences.priority] || 'medium';
    
    switch (priority) {
      case 'high':
        return AndroidImportance.HIGH;
      case 'low':
        return AndroidImportance.LOW;
      default:
        return AndroidImportance.DEFAULT;
    }
  }

  private async updateGroupSummary(groupId: string) {
    // Track notifications per group
    const currentNotifications = this.notificationGroups.get(groupId) || [];
    currentNotifications.push(new Date().toISOString());
    this.notificationGroups.set(groupId, currentNotifications);

    const count = currentNotifications.length;
    if (count > 1) {
      await notifee.displayNotification({
        id: `${groupId}-summary`,
        title: this.getGroupTitle(groupId),
        body: `${count} new notifications`,
        android: {
          channelId: this.getChannelId(groupId),
          groupId,
          groupSummary: true,
          groupAlertBehavior: AndroidGroupAlertBehavior.SUMMARY,
        },
      });
    }
  }

  private getGroupTitle(groupId: string): string {
    switch (groupId) {
      case 'order':
        return 'Order Updates';
      case 'staff':
        return 'Staff Alerts';
      case 'inventory':
        return 'Inventory Notifications';
      case 'promotion':
        return 'Promotions';
      default:
        return 'Notifications';
    }
  }

  private async handleNotificationPress(notification: any) {
    const { data } = notification;
    
    // Navigate based on notification type
    if (data?.navigateTo) {
      // Handle navigation using the navigation service
      // navigationService.navigate(data.navigateTo, data.params);
    }

    // Clear group if it was a summary
    if (notification.android?.groupSummary) {
      this.notificationGroups.delete(notification.android.groupId);
    }
  }

  public async updatePreferences(preferences: Partial<NotificationPreferences>) {
    this.preferences = { ...this.preferences, ...preferences } as NotificationPreferences;
    await AsyncStorage.setItem('notification_preferences', JSON.stringify(this.preferences));
    
    // Update backend with new preferences
    const token = await messaging().getToken();
    await this.sendTokenToBackend(token);
  }

  public async scheduleNotification(
    title: string,
    body: string,
    scheduledTime: Date,
    type: string = 'general',
    data?: any,
  ) {
    const trigger = {
      type: TriggerType.TIMESTAMP,
      timestamp: scheduledTime.getTime(),
    };

    await notifee.createTriggerNotification(
      {
        title,
        body,
        data: { ...data, type },
        android: {
          channelId: this.getChannelId(type),
        },
      },
      trigger,
    );
  }

  public async cancelScheduledNotifications(type?: string) {
    const notifications = await notifee.getTriggerNotifications();
    
    for (const notification of notifications) {
      if (!type || notification.notification.data?.type === type) {
        await notifee.cancelTriggerNotification(notification.notification.id!);
      }
    }
  }

  public async getNotificationHistory(): Promise<any[]> {
    const displayed = await notifee.getDisplayedNotifications();
    return displayed.map(item => ({
      id: item.id,
      title: item.notification.title,
      body: item.notification.body,
      timestamp: item.date,
      type: item.notification.data?.type,
    }));
  }

  public async clearAllNotifications() {
    await notifee.cancelAllNotifications();
    this.notificationGroups.clear();
  }

  public async clearNotificationsByType(type: string) {
    const displayed = await notifee.getDisplayedNotifications();
    
    for (const item of displayed) {
      if (item.notification.data?.type === type) {
        await notifee.cancelNotification(item.id);
      }
    }
    
    this.notificationGroups.delete(type);
  }
}

export default new PushNotificationService();