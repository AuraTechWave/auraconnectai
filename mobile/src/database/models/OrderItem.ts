import { field, relation, json } from '@nozbe/watermelondb/decorators';
import BaseModel from './BaseModel';

export type OrderItemStatus = 'pending' | 'preparing' | 'ready' | 'served' | 'cancelled';

interface Modifier {
  id: string;
  name: string;
  price: number;
}

export default class OrderItem extends BaseModel {
  static table = 'order_items';
  static associations = {
    orders: { type: 'belongs_to', key: 'order_id' },
    menu_items: { type: 'belongs_to', key: 'menu_item_id' },
  } as const;

  @field('order_id') orderId!: string;
  @field('menu_item_id') menuItemId!: string;
  @field('name') name!: string;
  @field('quantity') quantity!: number;
  @field('unit_price') unitPrice!: number;
  @field('total_price') totalPrice!: number;
  @json('modifiers', json => json) modifiers?: Modifier[];
  @field('special_instructions') specialInstructions?: string;
  @field('status') status!: OrderItemStatus;

  @relation('orders', 'order_id') order!: any;
  @relation('menu_items', 'menu_item_id') menuItem!: any;

  get modifiersCost(): number {
    if (!this.modifiers) return 0;
    return this.modifiers.reduce((sum, mod) => sum + mod.price, 0);
  }

  get totalWithModifiers(): number {
    return (this.unitPrice + this.modifiersCost) * this.quantity;
  }
}