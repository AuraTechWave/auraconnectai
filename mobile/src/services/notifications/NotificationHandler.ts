import { logger } from '@utils/logger';
import { NotificationType, OrderNotificationData } from './types';
import { showToast } from '@utils/toast';
import { EventEmitter } from 'events';
import database from '@database/index';
import { Q } from '@nozbe/watermelondb';
import { syncManager } from '@sync';

export class NotificationHandler {
  private eventEmitter: EventEmitter;

  constructor() {
    this.eventEmitter = new EventEmitter();
  }

  async handleLocalNotification(notification: any): Promise<void> {
    try {
      const { data } = notification;
      if (!data) return;

      switch (data.type) {
        case NotificationType.ORDER_CREATED:
        case NotificationType.ORDER_ACCEPTED:
        case NotificationType.ORDER_PREPARING:
        case NotificationType.ORDER_READY:
        case NotificationType.ORDER_COMPLETED:
        case NotificationType.ORDER_CANCELLED:
          await this.handleOrderNotification(data);
          break;
        case NotificationType.PROMOTION:
          await this.handlePromotionNotification(data);
          break;
        case NotificationType.SYSTEM_UPDATE:
          await this.handleSystemNotification(data);
          break;
        default:
          logger.warn('Unknown notification type', data.type);
      }
    } catch (error) {
      logger.error('Failed to handle local notification', error);
    }
  }

  async handleNotificationAction(notification: any): Promise<void> {
    try {
      const { action, data } = notification;
      logger.info('Handling notification action', { action, data });

      switch (action) {
        case 'view_order':
          this.eventEmitter.emit('navigateToOrder', data.orderId);
          break;
        case 'notify_customer':
          await this.notifyCustomer(data.orderId);
          break;
        case 'accept_order':
          await this.acceptOrder(data.orderId);
          break;
        case 'reject_order':
          await this.rejectOrder(data.orderId);
          break;
        default:
          logger.warn('Unknown notification action', action);
      }
    } catch (error) {
      logger.error('Failed to handle notification action', error);
    }
  }

  private async handleOrderNotification(
    data: OrderNotificationData,
  ): Promise<void> {
    try {
      // Update local database if order exists
      const ordersCollection = database.collections.get('orders');
      const orders = await ordersCollection
        .query(Q.where('server_id', data.orderId))
        .fetch();

      if (orders.length > 0) {
        const order = orders[0];
        await database.write(async () => {
          await order.update(o => {
            o.status = data.status;
            o.syncStatus = 'pending';
            o.lastModified = Date.now();
          });
        });

        // Trigger sync
        if (syncManager.getState().isOnline) {
          syncManager.sync().catch(error => {
            logger.error('Failed to sync after order notification', error);
          });
        }
      }

      // Show appropriate toast based on status
      this.showOrderStatusToast(data);

      // Emit event for UI updates
      this.eventEmitter.emit('orderUpdate', {
        orderId: data.orderId,
        status: data.status,
      });
    } catch (error) {
      logger.error('Failed to handle order notification', error);
    }
  }

  private showOrderStatusToast(data: OrderNotificationData): void {
    const messages: Record<
      string,
      { title: string; message: string; type: any }
    > = {
      [NotificationType.ORDER_CREATED]: {
        title: 'New Order',
        message: `Order #${data.orderNumber} from ${data.customerName}`,
        type: 'info',
      },
      [NotificationType.ORDER_ACCEPTED]: {
        title: 'Order Accepted',
        message: `Order #${data.orderNumber} has been accepted`,
        type: 'success',
      },
      [NotificationType.ORDER_PREPARING]: {
        title: 'Order Preparing',
        message: `Order #${data.orderNumber} is being prepared`,
        type: 'info',
      },
      [NotificationType.ORDER_READY]: {
        title: 'Order Ready',
        message: `Order #${data.orderNumber} is ready for pickup`,
        type: 'success',
      },
      [NotificationType.ORDER_COMPLETED]: {
        title: 'Order Completed',
        message: `Order #${data.orderNumber} has been completed`,
        type: 'success',
      },
      [NotificationType.ORDER_CANCELLED]: {
        title: 'Order Cancelled',
        message: `Order #${data.orderNumber} has been cancelled`,
        type: 'warning',
      },
    };

    const statusMessage = messages[data.status as NotificationType];
    if (statusMessage) {
      showToast(statusMessage.type, statusMessage.title, statusMessage.message);
    }
  }

  private async handlePromotionNotification(data: any): Promise<void> {
    logger.info('Handling promotion notification', data);
    // Implement promotion handling logic
  }

  private async handleSystemNotification(data: any): Promise<void> {
    logger.info('Handling system notification', data);
    // Implement system notification handling logic
  }

  private async notifyCustomer(orderId: string): Promise<void> {
    try {
      // Implement customer notification logic
      logger.info('Notifying customer for order', orderId);
      showToast(
        'success',
        'Customer Notified',
        'Notification sent to customer',
      );
    } catch (error) {
      logger.error('Failed to notify customer', error);
      showToast('error', 'Error', 'Failed to notify customer');
    }
  }

  private async acceptOrder(orderId: string): Promise<void> {
    try {
      const ordersCollection = database.collections.get('orders');
      const orders = await ordersCollection
        .query(Q.where('server_id', orderId))
        .fetch();

      if (orders.length > 0) {
        const order = orders[0];
        await database.write(async () => {
          await order.update(o => {
            o.status = 'accepted';
            o.syncStatus = 'pending';
            o.lastModified = Date.now();
          });
        });

        showToast(
          'success',
          'Order Accepted',
          `Order #${order.orderNumber} accepted`,
        );
      }
    } catch (error) {
      logger.error('Failed to accept order', error);
      showToast('error', 'Error', 'Failed to accept order');
    }
  }

  private async rejectOrder(orderId: string): Promise<void> {
    try {
      const ordersCollection = database.collections.get('orders');
      const orders = await ordersCollection
        .query(Q.where('server_id', orderId))
        .fetch();

      if (orders.length > 0) {
        const order = orders[0];
        await database.write(async () => {
          await order.update(o => {
            o.status = 'cancelled';
            o.syncStatus = 'pending';
            o.lastModified = Date.now();
          });
        });

        showToast(
          'warning',
          'Order Rejected',
          `Order #${order.orderNumber} rejected`,
        );
      }
    } catch (error) {
      logger.error('Failed to reject order', error);
      showToast('error', 'Error', 'Failed to reject order');
    }
  }

  onOrderUpdate(callback: (data: any) => void): void {
    this.eventEmitter.on('orderUpdate', callback);
  }

  onNavigateToOrder(callback: (orderId: string) => void): void {
    this.eventEmitter.on('navigateToOrder', callback);
  }

  removeAllListeners(): void {
    this.eventEmitter.removeAllListeners();
  }
}
