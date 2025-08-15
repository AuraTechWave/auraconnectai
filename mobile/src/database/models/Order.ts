import {
  field,
  children,
  relation,
  writer,
} from '@nozbe/watermelondb/decorators';
import { Q } from '@nozbe/watermelondb';
import BaseModel from './BaseModel';

export type OrderStatus =
  | 'pending'
  | 'confirmed'
  | 'preparing'
  | 'ready'
  | 'delivered'
  | 'cancelled';
export type OrderType = 'dine_in' | 'takeout' | 'delivery';
export type PaymentStatus = 'pending' | 'paid' | 'partial' | 'refunded';

export default class Order extends BaseModel {
  static table = 'orders';
  static associations = {
    order_items: { type: 'has_many', foreignKey: 'order_id' },
    customers: { type: 'belongs_to', key: 'customer_id' },
    staff: { type: 'belongs_to', key: 'staff_id' },
  } as const;

  @field('order_number') orderNumber!: string;
  @field('customer_id') customerId?: string;
  @field('staff_id') staffId?: string;
  @field('status') status!: OrderStatus;
  @field('order_type') orderType!: OrderType;
  @field('table_number') tableNumber?: string;
  @field('subtotal') subtotal!: number;
  @field('tax_amount') taxAmount!: number;
  @field('discount_amount') discountAmount!: number;
  @field('tip_amount') tipAmount!: number;
  @field('total_amount') totalAmount!: number;
  @field('payment_status') paymentStatus!: PaymentStatus;
  @field('notes') notes?: string;

  @children('order_items') items!: any;
  @relation('customers', 'customer_id') customer!: any;
  @relation('staff', 'staff_id') staff!: any;

  // Computed properties
  get itemCount() {
    return this.items.length;
  }

  get isPaid() {
    return this.paymentStatus === 'paid';
  }

  get isActive() {
    return !['delivered', 'cancelled'].includes(this.status);
  }

  // Actions
  @writer async updateStatus(newStatus: OrderStatus) {
    await this.update(order => {
      order.status = newStatus;
      order.syncStatus = 'pending';
      order.lastModified = Date.now();
    });
  }

  @writer async updatePaymentStatus(newStatus: PaymentStatus) {
    await this.update(order => {
      order.paymentStatus = newStatus;
      order.syncStatus = 'pending';
      order.lastModified = Date.now();
    });
  }

  @writer async addItem(itemData: any) {
    const { orderItems } = this.collections.get('order_items');
    await orderItems.create(item => {
      Object.assign(item, {
        ...itemData,
        orderId: this.id,
        syncStatus: 'pending',
        lastModified: Date.now(),
      });
    });
  }

  // Query helpers
  static activeOrders() {
    return this.query(
      Q.where('status', Q.notIn(['delivered', 'cancelled'])),
      Q.where('is_deleted', false),
      Q.sortBy('created_at', Q.desc),
    );
  }

  static pendingSync() {
    return this.query(Q.where('sync_status', Q.oneOf(['pending', 'conflict'])));
  }

  static forDate(date: Date) {
    const startOfDay = new Date(date);
    startOfDay.setHours(0, 0, 0, 0);
    const endOfDay = new Date(date);
    endOfDay.setHours(23, 59, 59, 999);

    return this.query(
      Q.where(
        'created_at',
        Q.between(startOfDay.getTime(), endOfDay.getTime()),
      ),
      Q.where('is_deleted', false),
    );
  }
}
