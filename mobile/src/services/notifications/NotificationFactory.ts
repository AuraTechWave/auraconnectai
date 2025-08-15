import {
  Notification,
  AndroidStyle,
  AndroidImportance,
} from '@notifee/react-native';
import { NOTIFICATION_CONFIG } from '@constants/config';
import { NotificationType, OrderNotificationData } from './types';

export class NotificationFactory {
  static createOrderNotification(
    type: NotificationType,
    data: OrderNotificationData,
    options: {
      title: string;
      body: string;
      actions?: any[];
      sound?: string;
      vibrationPattern?: number[];
    },
  ): Notification {
    const { title, body, actions, sound, vibrationPattern } = options;

    return {
      id: `order_${data.orderId}_${type}`,
      title,
      body,
      data: {
        type,
        ...data,
      },
      android: {
        channelId: NOTIFICATION_CONFIG.CHANNELS.ORDER_UPDATES,
        importance: AndroidImportance.HIGH,
        sound: sound || NOTIFICATION_CONFIG.SOUNDS.ORDER_NOTIFICATION,
        vibrationPattern:
          vibrationPattern || NOTIFICATION_CONFIG.VIBRATION_PATTERNS.DEFAULT,
        pressAction: {
          id: 'default',
          launchActivity: 'default',
        },
        actions: actions || this.getDefaultOrderActions(type),
        style: this.getOrderNotificationStyle(data),
      },
      ios: {
        categoryId: 'ORDER_ACTIONS',
        sound: sound || NOTIFICATION_CONFIG.SOUNDS.ORDER_NOTIFICATION,
      },
    };
  }

  static createPromotionNotification(
    id: string,
    title: string,
    body: string,
    data?: any,
  ): Notification {
    return {
      id,
      title,
      body,
      data: {
        type: NotificationType.PROMOTION,
        ...data,
      },
      android: {
        channelId: NOTIFICATION_CONFIG.CHANNELS.PROMOTIONS,
        importance: AndroidImportance.DEFAULT,
        sound: NOTIFICATION_CONFIG.SOUNDS.DEFAULT,
        vibrationPattern: false,
        pressAction: {
          id: 'default',
          launchActivity: 'default',
        },
      },
      ios: {
        categoryId: 'PROMOTION',
      },
    };
  }

  static createSystemNotification(
    id: string,
    title: string,
    body: string,
    data?: any,
  ): Notification {
    return {
      id,
      title,
      body,
      data: {
        type: NotificationType.SYSTEM_UPDATE,
        ...data,
      },
      android: {
        channelId: NOTIFICATION_CONFIG.CHANNELS.SYSTEM,
        importance: AndroidImportance.HIGH,
        sound: NOTIFICATION_CONFIG.SOUNDS.DEFAULT,
        vibrationPattern: NOTIFICATION_CONFIG.VIBRATION_PATTERNS.DEFAULT,
        pressAction: {
          id: 'default',
          launchActivity: 'default',
        },
      },
      ios: {
        categoryId: 'SYSTEM',
      },
    };
  }

  private static getDefaultOrderActions(type: NotificationType): any[] {
    const actions = [
      {
        title: 'View Order',
        pressAction: {
          id: NOTIFICATION_CONFIG.ACTIONS.VIEW_ORDER,
          launchActivity: 'default',
        },
      },
    ];

    switch (type) {
      case NotificationType.ORDER_CREATED:
        actions.push(
          {
            title: 'Accept',
            pressAction: {
              id: NOTIFICATION_CONFIG.ACTIONS.ACCEPT_ORDER,
            },
          },
          {
            title: 'Reject',
            pressAction: {
              id: NOTIFICATION_CONFIG.ACTIONS.REJECT_ORDER,
            },
          },
        );
        break;
      case NotificationType.ORDER_READY:
        actions.push({
          title: 'Notify Customer',
          pressAction: {
            id: NOTIFICATION_CONFIG.ACTIONS.NOTIFY_CUSTOMER,
          },
        });
        break;
    }

    return actions;
  }

  private static getOrderNotificationStyle(
    data: OrderNotificationData,
  ): AndroidStyle | undefined {
    if (data.items) {
      return {
        type: AndroidStyle.BIGTEXT,
        text: data.items,
      };
    }
    return undefined;
  }

  static getChannelFromType(type: string): string {
    if (type.includes('order')) {
      return NOTIFICATION_CONFIG.CHANNELS.ORDER_UPDATES;
    } else if (type === NotificationType.PROMOTION) {
      return NOTIFICATION_CONFIG.CHANNELS.PROMOTIONS;
    }
    return NOTIFICATION_CONFIG.CHANNELS.SYSTEM;
  }

  static getStatusMessages(): Record<
    string,
    { title: string; body: (order: any) => string }
  > {
    return {
      created: {
        title: 'New Order Received',
        body: order =>
          `Order #${order.orderNumber} from ${order.customerName || 'Walk-in Customer'}`,
      },
      accepted: {
        title: 'Order Accepted',
        body: order =>
          `Order #${order.orderNumber} has been accepted and will be prepared soon`,
      },
      preparing: {
        title: 'Order Being Prepared',
        body: order => `Order #${order.orderNumber} is now being prepared`,
      },
      ready: {
        title: '🔔 Order Ready!',
        body: order =>
          `Order #${order.orderNumber} for ${order.customerName || 'Walk-in Customer'} is ready`,
      },
      completed: {
        title: 'Order Completed',
        body: order => `Order #${order.orderNumber} has been completed`,
      },
      cancelled: {
        title: 'Order Cancelled',
        body: order => `Order #${order.orderNumber} has been cancelled`,
      },
    };
  }
}
