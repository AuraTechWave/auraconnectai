import { NotificationService } from './NotificationService';
import { NotificationType, OrderNotificationData } from './types';
import database from '@database/index';
import Order from '@database/models/Order';
import { logger } from '@utils/logger';
import notifee, { AndroidImportance } from '@notifee/react-native';

export class OrderNotificationService {
  private static instance: OrderNotificationService;
  private notificationService: NotificationService;

  private constructor() {
    this.notificationService = NotificationService.getInstance();
  }

  static getInstance(): OrderNotificationService {
    if (!OrderNotificationService.instance) {
      OrderNotificationService.instance = new OrderNotificationService();
    }
    return OrderNotificationService.instance;
  }

  async notifyOrderCreated(order: Order): Promise<void> {
    try {
      const notification = {
        id: `order_${order.id}`,
        title: 'New Order Received',
        body: `Order #${order.orderNumber} from ${order.customerName || 'Walk-in Customer'}`,
        data: {
          type: NotificationType.ORDER_CREATED,
          orderId: order.id,
          orderNumber: order.orderNumber,
          customerName: order.customerName || 'Walk-in Customer',
          status: 'created',
          totalAmount: order.totalAmount,
          tableNumber: order.tableNumber,
        } as OrderNotificationData,
        android: {
          channelId: 'order_updates',
          importance: AndroidImportance.HIGH,
          pressAction: {
            id: 'default',
            launchActivity: 'default',
          },
          actions: [
            {
              title: 'View Order',
              pressAction: {
                id: 'view_order',
                launchActivity: 'default',
              },
            },
            {
              title: 'Accept',
              pressAction: {
                id: 'accept_order',
              },
            },
            {
              title: 'Reject',
              pressAction: {
                id: 'reject_order',
              },
            },
          ],
        },
      };

      await this.notificationService.displayNotification(notification);
    } catch (error) {
      logger.error('Failed to send order created notification', error);
    }
  }

  async notifyOrderStatusChange(
    order: Order,
    previousStatus: string,
  ): Promise<void> {
    try {
      const statusMessages: Record<string, { title: string; body: string }> = {
        accepted: {
          title: 'Order Accepted',
          body: `Order #${order.orderNumber} has been accepted and will be prepared soon`,
        },
        preparing: {
          title: 'Order Being Prepared',
          body: `Order #${order.orderNumber} is now being prepared`,
        },
        ready: {
          title: 'Order Ready!',
          body: `Order #${order.orderNumber} is ready for pickup`,
        },
        completed: {
          title: 'Order Completed',
          body: `Order #${order.orderNumber} has been completed`,
        },
        cancelled: {
          title: 'Order Cancelled',
          body: `Order #${order.orderNumber} has been cancelled`,
        },
      };

      const message = statusMessages[order.status];
      if (!message) return;

      const notification = {
        id: `order_${order.id}_${order.status}`,
        title: message.title,
        body: message.body,
        data: {
          type: this.getNotificationTypeForStatus(order.status),
          orderId: order.id,
          orderNumber: order.orderNumber,
          customerName: order.customerName || 'Walk-in Customer',
          status: order.status,
          previousStatus,
        } as OrderNotificationData,
        android: {
          channelId: 'order_updates',
          importance: AndroidImportance.HIGH,
          pressAction: {
            id: 'default',
            launchActivity: 'default',
          },
          actions: this.getActionsForStatus(order.status),
        },
      };

      await this.notificationService.displayNotification(notification);
    } catch (error) {
      logger.error('Failed to send order status notification', error);
    }
  }

  async notifyOrderReady(order: Order): Promise<void> {
    try {
      // Special notification for order ready with sound and vibration
      const notification = {
        id: `order_${order.id}_ready`,
        title: '🔔 Order Ready for Pickup!',
        body: `Order #${order.orderNumber} for ${order.customerName || 'Walk-in Customer'} is ready`,
        data: {
          type: NotificationType.ORDER_READY,
          orderId: order.id,
          orderNumber: order.orderNumber,
          customerName: order.customerName || 'Walk-in Customer',
          status: 'ready',
          priority: 'high',
        } as OrderNotificationData,
        android: {
          channelId: 'order_updates',
          importance: AndroidImportance.HIGH,
          sound: 'order_ready',
          vibrationPattern: [0, 500, 250, 500],
          pressAction: {
            id: 'default',
            launchActivity: 'default',
          },
          actions: [
            {
              title: 'View Order',
              pressAction: {
                id: 'view_order',
                launchActivity: 'default',
              },
            },
            {
              title: 'Notify Customer',
              pressAction: {
                id: 'notify_customer',
              },
            },
          ],
        },
      };

      await this.notificationService.displayNotification(notification);
    } catch (error) {
      logger.error('Failed to send order ready notification', error);
    }
  }

  async notifyOrderDelayed(order: Order, delayReason?: string): Promise<void> {
    try {
      const notification = {
        id: `order_${order.id}_delayed`,
        title: '⏰ Order Delayed',
        body: `Order #${order.orderNumber} is delayed${delayReason ? `: ${delayReason}` : ''}`,
        data: {
          type: 'order_delayed',
          orderId: order.id,
          orderNumber: order.orderNumber,
          customerName: order.customerName || 'Walk-in Customer',
          delayReason,
        },
        android: {
          channelId: 'order_updates',
          importance: AndroidImportance.DEFAULT,
          pressAction: {
            id: 'default',
            launchActivity: 'default',
          },
        },
      };

      await this.notificationService.displayNotification(notification);
    } catch (error) {
      logger.error('Failed to send order delayed notification', error);
    }
  }

  async scheduleOrderReminder(
    order: Order,
    reminderTime: number,
  ): Promise<void> {
    try {
      const notification = {
        id: `order_${order.id}_reminder`,
        title: '⏰ Order Reminder',
        body: `Don't forget about Order #${order.orderNumber}`,
        data: {
          type: 'order_reminder',
          orderId: order.id,
          orderNumber: order.orderNumber,
        },
      };

      await this.notificationService.scheduleNotification(
        notification,
        reminderTime,
      );
    } catch (error) {
      logger.error('Failed to schedule order reminder', error);
    }
  }

  async cancelOrderNotifications(orderId: string): Promise<void> {
    try {
      // Cancel all notifications related to this order
      const notificationIds = [
        `order_${orderId}`,
        `order_${orderId}_ready`,
        `order_${orderId}_delayed`,
        `order_${orderId}_reminder`,
      ];

      for (const id of notificationIds) {
        await this.notificationService.cancelNotification(id);
      }
    } catch (error) {
      logger.error('Failed to cancel order notifications', error);
    }
  }

  private getNotificationTypeForStatus(status: string): NotificationType {
    const statusMap: Record<string, NotificationType> = {
      created: NotificationType.ORDER_CREATED,
      accepted: NotificationType.ORDER_ACCEPTED,
      preparing: NotificationType.ORDER_PREPARING,
      ready: NotificationType.ORDER_READY,
      completed: NotificationType.ORDER_COMPLETED,
      cancelled: NotificationType.ORDER_CANCELLED,
    };

    return statusMap[status] || NotificationType.ORDER_CREATED;
  }

  private getActionsForStatus(status: string): any[] {
    const actions = [
      {
        title: 'View Order',
        pressAction: {
          id: 'view_order',
          launchActivity: 'default',
        },
      },
    ];

    switch (status) {
      case 'created':
        actions.push(
          {
            title: 'Accept',
            pressAction: {
              id: 'accept_order',
            },
          },
          {
            title: 'Reject',
            pressAction: {
              id: 'reject_order',
            },
          },
        );
        break;
      case 'ready':
        actions.push({
          title: 'Notify Customer',
          pressAction: {
            id: 'notify_customer',
          },
        });
        break;
    }

    return actions;
  }

  // Subscribe to order changes and send notifications
  subscribeToOrderChanges(): void {
    const ordersCollection = database.collections.get('orders');

    ordersCollection
      .query()
      .observe()
      .subscribe(orders => {
        // This would need more sophisticated logic to track actual changes
        // For now, this is a placeholder
        logger.debug('Order collection changed', { count: orders.length });
      });
  }
}
