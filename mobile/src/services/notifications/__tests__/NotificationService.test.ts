import { NotificationService } from '../NotificationService';
import messaging from '@react-native-firebase/messaging';
import notifee from '@notifee/react-native';
import PushNotification from 'react-native-push-notification';
import { Platform } from 'react-native';
import { NotificationFactory } from '../NotificationFactory';
import { NotificationErrorHandler } from '../NotificationErrorHandler';
import { SecureNotificationStorage } from '../SecureNotificationStorage';
import { logger } from '@utils/logger';

jest.mock('@react-native-firebase/messaging');
jest.mock('@notifee/react-native');
jest.mock('react-native-push-notification');
jest.mock('../NotificationFactory');
jest.mock('../NotificationErrorHandler');
jest.mock('../SecureNotificationStorage');
jest.mock('@utils/logger');

describe('NotificationService', () => {
  let service: NotificationService;

  beforeEach(() => {
    jest.clearAllMocks();
    service = NotificationService.getInstance();
    
    // Setup default mocks
    (messaging as jest.MockedFunction<any>).mockReturnValue({
      requestPermission: jest.fn().mockResolvedValue(messaging.AuthorizationStatus.AUTHORIZED),
      getToken: jest.fn().mockResolvedValue('test-fcm-token'),
      onMessage: jest.fn(),
      setBackgroundMessageHandler: jest.fn(),
      onTokenRefresh: jest.fn(),
    });

    (notifee.createChannel as jest.Mock).mockResolvedValue(undefined);
    (notifee.displayNotification as jest.Mock).mockResolvedValue(undefined);
    (notifee.onForegroundEvent as jest.Mock).mockReturnValue(jest.fn());
    (notifee.onBackgroundEvent as jest.Mock).mockResolvedValue(undefined);

    (NotificationErrorHandler.withRetry as jest.Mock).mockImplementation(
      async (operation) => operation()
    );

    (SecureNotificationStorage.getPreferences as jest.Mock).mockResolvedValue(null);
    (SecureNotificationStorage.saveFCMToken as jest.Mock).mockResolvedValue(undefined);
    (SecureNotificationStorage.getNotificationHistory as jest.Mock).mockResolvedValue([]);
    (SecureNotificationStorage.saveNotificationHistory as jest.Mock).mockResolvedValue(undefined);
  });

  describe('initialization', () => {
    it('should initialize successfully with permissions', async () => {
      Platform.OS = 'ios';
      
      await service.initialize();

      expect(messaging().requestPermission).toHaveBeenCalled();
      expect(messaging().getToken).toHaveBeenCalled();
      expect(SecureNotificationStorage.saveFCMToken).toHaveBeenCalledWith('test-fcm-token');
      expect(logger.info).toHaveBeenCalledWith('Notification service initialized successfully');
    });

    it('should not initialize twice', async () => {
      await service.initialize();
      jest.clearAllMocks();
      
      await service.initialize();

      expect(messaging().requestPermission).not.toHaveBeenCalled();
      expect(logger.debug).toHaveBeenCalledWith('Notification service already initialized');
    });

    it('should handle permission denial gracefully', async () => {
      Platform.OS = 'ios';
      (messaging as jest.MockedFunction<any>).mockReturnValue({
        requestPermission: jest.fn().mockResolvedValue(messaging.AuthorizationStatus.DENIED),
      });

      await service.initialize();

      expect(logger.warn).toHaveBeenCalledWith('Notification permission denied');
      expect(messaging().getToken).not.toHaveBeenCalled();
    });

    it('should create Android notification channels', async () => {
      Platform.OS = 'android';
      
      await service.initialize();

      expect(notifee.createChannel).toHaveBeenCalledTimes(3);
      expect(notifee.createChannel).toHaveBeenCalledWith(
        expect.objectContaining({
          id: 'order_updates',
          name: 'Order Updates',
        })
      );
    });
  });

  describe('notification display', () => {
    beforeEach(async () => {
      await service.initialize();
    });

    it('should display notification and store it', async () => {
      const notification = {
        id: 'test-123',
        title: 'Test',
        body: 'Test notification',
        data: {},
      };

      await service.displayNotification(notification);

      expect(notifee.displayNotification).toHaveBeenCalledWith(notification);
      expect(SecureNotificationStorage.saveNotificationHistory).toHaveBeenCalled();
      expect(SecureNotificationStorage.trimNotificationHistory).toHaveBeenCalled();
    });

    it('should emit notificationDisplayed event', async () => {
      const notification = { id: 'test-123', title: 'Test', body: 'Body' };
      const listener = jest.fn();
      service.on('notificationDisplayed', listener);

      await service.displayNotification(notification);

      expect(listener).toHaveBeenCalledWith(notification);
    });

    it('should handle display errors gracefully', async () => {
      const error = new Error('Display failed');
      (notifee.displayNotification as jest.Mock).mockRejectedValue(error);

      const notification = { id: 'test-123', title: 'Test', body: 'Body' };
      await service.displayNotification(notification);

      expect(logger.error).toHaveBeenCalledWith('Failed to display notification', error);
    });
  });

  describe('foreground notifications', () => {
    beforeEach(async () => {
      await service.initialize();
    });

    it('should handle order notifications using factory', async () => {
      const remoteMessage = {
        messageId: 'msg-123',
        notification: { title: 'New Order', body: 'Order #123' },
        data: { type: 'order_created', orderId: '123' },
      };

      const factoryNotification = { id: 'order_123', title: 'New Order' };
      (NotificationFactory.createOrderNotification as jest.Mock).mockReturnValue(factoryNotification);

      const handler = (messaging().onMessage as jest.Mock).mock.calls[0][0];
      await handler(remoteMessage);

      expect(NotificationFactory.createOrderNotification).toHaveBeenCalledWith(
        'order_created',
        { type: 'order_created', orderId: '123' },
        expect.objectContaining({ title: 'New Order' })
      );
      expect(notifee.displayNotification).toHaveBeenCalledWith(factoryNotification);
    });

    it('should respect notification preferences', async () => {
      await service.savePreferences({ orderUpdates: false });

      const remoteMessage = {
        messageId: 'msg-123',
        notification: { title: 'Order Update', body: 'Your order is ready' },
        data: { type: 'order_update' },
      };

      const handler = (messaging().onMessage as jest.Mock).mock.calls[0][0];
      await handler(remoteMessage);

      expect(notifee.displayNotification).not.toHaveBeenCalled();
    });

    it('should respect do not disturb settings', async () => {
      const now = new Date();
      now.setHours(22, 30); // 10:30 PM
      jest.spyOn(global, 'Date').mockImplementation(() => now as any);

      await service.savePreferences({
        doNotDisturb: {
          enabled: true,
          startTime: '22:00',
          endTime: '08:00',
        },
      });

      const remoteMessage = {
        messageId: 'msg-123',
        notification: { title: 'Test', body: 'Test' },
        data: { type: 'order_update' },
      };

      const handler = (messaging().onMessage as jest.Mock).mock.calls[0][0];
      await handler(remoteMessage);

      expect(notifee.displayNotification).not.toHaveBeenCalled();
    });
  });

  describe('notification interactions', () => {
    beforeEach(async () => {
      await service.initialize();
    });

    it('should handle notification press and navigate to order', async () => {
      const listener = jest.fn();
      service.on('navigateToOrder', listener);

      const handler = (notifee.onForegroundEvent as jest.Mock).mock.calls[0][0];
      await handler({
        type: notifee.EventType.PRESS,
        detail: {
          notification: {
            data: { type: 'order_update', orderId: '123' },
          },
        },
      });

      expect(listener).toHaveBeenCalledWith('123');
    });

    it('should handle notification actions', async () => {
      const actionListener = jest.fn();
      service.on('notificationAction', actionListener);

      const orderListener = jest.fn();
      service.on('navigateToOrder', orderListener);

      const handler = (notifee.onForegroundEvent as jest.Mock).mock.calls[0][0];
      await handler({
        type: notifee.EventType.ACTION_PRESS,
        detail: {
          notification: {
            data: { orderId: '123' },
          },
          pressAction: { id: 'view_order' },
        },
      });

      expect(actionListener).toHaveBeenCalled();
      expect(orderListener).toHaveBeenCalledWith('123');
    });
  });

  describe('preferences', () => {
    it('should save and emit preferences update', async () => {
      const listener = jest.fn();
      service.on('preferencesUpdated', listener);

      await service.savePreferences({ sound: false, vibration: false });

      expect(SecureNotificationStorage.savePreferences).toHaveBeenCalledWith(
        expect.objectContaining({ sound: false, vibration: false })
      );
      expect(listener).toHaveBeenCalled();
    });

    it('should return current preferences', () => {
      const prefs = service.getPreferences();
      
      expect(prefs).toEqual(expect.objectContaining({
        enabled: true,
        orderUpdates: true,
        promotions: false,
      }));
    });
  });

  describe('token management', () => {
    beforeEach(async () => {
      await service.initialize();
    });

    it('should handle token refresh', async () => {
      const listener = jest.fn();
      service.on('tokenRefresh', listener);

      const refreshHandler = (messaging().onTokenRefresh as jest.Mock).mock.calls[0][0];
      await refreshHandler('new-token');

      expect(SecureNotificationStorage.saveFCMToken).toHaveBeenCalledWith('new-token');
      expect(listener).toHaveBeenCalledWith('new-token');
    });

    it('should retry token registration on failure', async () => {
      const tokenListener = jest.fn();
      service.on('registerToken', tokenListener);

      (NotificationErrorHandler.withRetry as jest.Mock).mockImplementation(
        async (operation, options) => {
          await operation();
          return true;
        }
      );

      await service.initialize();

      expect(NotificationErrorHandler.withRetry).toHaveBeenCalled();
      expect(tokenListener).toHaveBeenCalledWith('test-fcm-token');
    });
  });

  describe('notification history', () => {
    it('should mark notification as read', async () => {
      const notifications = [
        { id: '1', read: false },
        { id: '2', read: false },
      ];
      (SecureNotificationStorage.getNotificationHistory as jest.Mock).mockResolvedValue(notifications);

      await service.markNotificationAsRead('1');

      expect(SecureNotificationStorage.saveNotificationHistory).toHaveBeenCalledWith([
        { id: '1', read: true },
        { id: '2', read: false },
      ]);
    });

    it('should clear notification history', async () => {
      await service.clearNotificationHistory();

      expect(SecureNotificationStorage.saveNotificationHistory).toHaveBeenCalledWith([]);
      expect(logger.info).toHaveBeenCalledWith('Notification history cleared');
    });
  });
});