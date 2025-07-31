import { NotificationFactory } from '../NotificationFactory';
import { NotificationType } from '../types';
import { NOTIFICATION_CONFIG } from '@constants/config';
import { AndroidImportance, AndroidStyle } from '@notifee/react-native';

describe('NotificationFactory', () => {
  describe('createOrderNotification', () => {
    it('should create a properly formatted order notification', () => {
      const notification = NotificationFactory.createOrderNotification(
        NotificationType.ORDER_CREATED,
        {
          orderId: '123',
          orderNumber: 'ORD-001',
          customerName: 'John Doe',
        },
        {
          title: 'New Order',
          body: 'You have a new order',
        }
      );

      expect(notification.id).toBe('order_123_order_created');
      expect(notification.title).toBe('New Order');
      expect(notification.body).toBe('You have a new order');
      expect(notification.data?.type).toBe(NotificationType.ORDER_CREATED);
      expect(notification.android?.channelId).toBe(NOTIFICATION_CONFIG.CHANNELS.ORDER_UPDATES);
      expect(notification.android?.importance).toBe(AndroidImportance.HIGH);
    });

    it('should include custom actions for specific order types', () => {
      const createdNotification = NotificationFactory.createOrderNotification(
        NotificationType.ORDER_CREATED,
        { orderId: '123' },
        { title: 'Test', body: 'Test' }
      );

      const actions = createdNotification.android?.actions || [];
      const actionIds = actions.map(a => a.pressAction?.id);
      
      expect(actionIds).toContain(NOTIFICATION_CONFIG.ACTIONS.VIEW_ORDER);
      expect(actionIds).toContain(NOTIFICATION_CONFIG.ACTIONS.ACCEPT_ORDER);
      expect(actionIds).toContain(NOTIFICATION_CONFIG.ACTIONS.REJECT_ORDER);
    });

    it('should apply big text style when items are provided', () => {
      const notification = NotificationFactory.createOrderNotification(
        NotificationType.ORDER_READY,
        {
          orderId: '123',
          items: '2x Burger, 1x Fries, 1x Coke',
        },
        { title: 'Test', body: 'Test' }
      );

      expect(notification.android?.style?.type).toBe(AndroidStyle.BIGTEXT);
      expect(notification.android?.style?.text).toBe('2x Burger, 1x Fries, 1x Coke');
    });
  });

  describe('createPromotionNotification', () => {
    it('should create a promotion notification with correct channel', () => {
      const notification = NotificationFactory.createPromotionNotification(
        'promo-123',
        'Special Offer',
        '50% off today!',
        { promoCode: 'SAVE50' }
      );

      expect(notification.id).toBe('promo-123');
      expect(notification.title).toBe('Special Offer');
      expect(notification.body).toBe('50% off today!');
      expect(notification.data?.type).toBe(NotificationType.PROMOTION);
      expect(notification.data?.promoCode).toBe('SAVE50');
      expect(notification.android?.channelId).toBe(NOTIFICATION_CONFIG.CHANNELS.PROMOTIONS);
      expect(notification.android?.vibrationPattern).toBe(false);
    });
  });

  describe('createSystemNotification', () => {
    it('should create a system notification with high importance', () => {
      const notification = NotificationFactory.createSystemNotification(
        'sys-123',
        'System Update',
        'New version available',
        { version: '2.0.0' }
      );

      expect(notification.id).toBe('sys-123');
      expect(notification.title).toBe('System Update');
      expect(notification.body).toBe('New version available');
      expect(notification.data?.type).toBe(NotificationType.SYSTEM_UPDATE);
      expect(notification.data?.version).toBe('2.0.0');
      expect(notification.android?.channelId).toBe(NOTIFICATION_CONFIG.CHANNELS.SYSTEM);
      expect(notification.android?.importance).toBe(AndroidImportance.HIGH);
    });
  });

  describe('getChannelFromType', () => {
    it('should return order channel for order-related types', () => {
      expect(NotificationFactory.getChannelFromType('order_created')).toBe(NOTIFICATION_CONFIG.CHANNELS.ORDER_UPDATES);
      expect(NotificationFactory.getChannelFromType('order_ready')).toBe(NOTIFICATION_CONFIG.CHANNELS.ORDER_UPDATES);
      expect(NotificationFactory.getChannelFromType('order_anything')).toBe(NOTIFICATION_CONFIG.CHANNELS.ORDER_UPDATES);
    });

    it('should return promotion channel for promotion type', () => {
      expect(NotificationFactory.getChannelFromType(NotificationType.PROMOTION)).toBe(NOTIFICATION_CONFIG.CHANNELS.PROMOTIONS);
    });

    it('should return system channel as default', () => {
      expect(NotificationFactory.getChannelFromType('unknown')).toBe(NOTIFICATION_CONFIG.CHANNELS.SYSTEM);
      expect(NotificationFactory.getChannelFromType('')).toBe(NOTIFICATION_CONFIG.CHANNELS.SYSTEM);
    });
  });

  describe('getStatusMessages', () => {
    it('should return correct messages for all order statuses', () => {
      const messages = NotificationFactory.getStatusMessages();
      const order = { orderNumber: 'ORD-001', customerName: 'John Doe' };

      expect(messages.created.title).toBe('New Order Received');
      expect(messages.created.body(order)).toBe('Order #ORD-001 from John Doe');
      
      expect(messages.ready.title).toBe('🔔 Order Ready!');
      expect(messages.ready.body(order)).toBe('Order #ORD-001 for John Doe is ready');
      
      expect(messages.cancelled.title).toBe('Order Cancelled');
      expect(messages.cancelled.body(order)).toBe('Order #ORD-001 has been cancelled');
    });

    it('should handle walk-in customers', () => {
      const messages = NotificationFactory.getStatusMessages();
      const order = { orderNumber: 'ORD-002' };

      expect(messages.created.body(order)).toBe('Order #ORD-002 from Walk-in Customer');
      expect(messages.ready.body(order)).toBe('Order #ORD-002 for Walk-in Customer is ready');
    });
  });
});