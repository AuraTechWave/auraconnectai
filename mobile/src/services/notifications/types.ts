export interface NotificationPreferences {
  enabled: boolean;
  orderUpdates: boolean;
  promotions: boolean;
  sound: boolean;
  vibration: boolean;
  doNotDisturb: {
    enabled: boolean;
    startTime: string; // HH:MM format
    endTime: string; // HH:MM format
  };
}

export enum NotificationChannel {
  ORDER_UPDATES = 'order_updates',
  PROMOTIONS = 'promotions',
  SYSTEM = 'system',
}

export enum NotificationType {
  ORDER_CREATED = 'order_created',
  ORDER_ACCEPTED = 'order_accepted',
  ORDER_PREPARING = 'order_preparing',
  ORDER_READY = 'order_ready',
  ORDER_COMPLETED = 'order_completed',
  ORDER_CANCELLED = 'order_cancelled',
  PROMOTION = 'promotion',
  SYSTEM_UPDATE = 'system_update',
}

export interface OrderNotificationData {
  orderId: string;
  orderNumber: string;
  customerName: string;
  status: string;
  items?: string;
  totalAmount?: number;
  estimatedTime?: number;
  tableNumber?: string;
}

export interface NotificationData {
  type: NotificationType | string;
  category?: string;
  priority?: 'high' | 'normal' | 'low';
  orderId?: string;
  [key: string]: any;
}

export interface StoredNotification {
  id: string;
  title: string;
  body: string;
  data: NotificationData;
  timestamp: number;
  read: boolean;
}

export interface NotificationAction {
  id: string;
  title: string;
  icon?: string;
  input?: boolean;
  choices?: string[];
}

export interface NotificationStats {
  total: number;
  unread: number;
  orderUpdates: number;
  promotions: number;
  lastNotificationTime?: number;
}