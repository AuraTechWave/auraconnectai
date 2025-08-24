export enum OrderStatus {
  PENDING = 'pending',
  CONFIRMED = 'confirmed',
  PREPARING = 'preparing',
  READY = 'ready',
  DELIVERED = 'delivered',
  CANCELLED = 'cancelled',
  REFUNDED = 'refunded'
}

export enum PaymentStatus {
  PENDING = 'pending',
  PAID = 'paid',
  FAILED = 'failed',
  REFUNDED = 'refunded'
}

export enum PaymentMethod {
  CASH = 'cash',
  CREDIT_CARD = 'credit_card',
  DEBIT_CARD = 'debit_card',
  MOBILE_PAYMENT = 'mobile_payment',
  GIFT_CARD = 'gift_card'
}

export interface OrderItem {
  id: string;
  menu_item_id: string;
  menu_item_name: string;
  quantity: number;
  unit_price: number;
  total_price: number;
  special_instructions?: string;
  modifiers?: OrderModifier[];
}

export interface OrderModifier {
  id: string;
  name: string;
  price: number;
}

export interface Customer {
  id: string;
  name: string;
  email?: string;
  phone?: string;
}

export interface Order {
  id: string;
  order_number: string;
  customer?: Customer;
  customer_name?: string;
  customer_phone?: string;
  customer_email?: string;
  table_number?: string;
  order_type: 'dine_in' | 'takeout' | 'delivery';
  status: OrderStatus;
  payment_status: PaymentStatus;
  payment_method?: PaymentMethod;
  items: OrderItem[];
  subtotal: number;
  tax: number;
  tip?: number;
  discount?: number;
  total: number;
  notes?: string;
  created_at: string;
  updated_at: string;
  confirmed_at?: string;
  prepared_at?: string;
  delivered_at?: string;
  cancelled_at?: string;
  restaurant_id: string;
  location_id?: string;
  staff_id?: string;
  staff_name?: string;
}

export interface OrderFilter {
  status?: OrderStatus[];
  payment_status?: PaymentStatus[];
  order_type?: string[];
  date_from?: string;
  date_to?: string;
  search?: string;
  restaurant_id?: string;
  location_id?: string;
}

export interface OrderAnalytics {
  total_orders: number;
  total_revenue: number;
  average_order_value: number;
  orders_by_status: Record<OrderStatus, number>;
  orders_by_type: Record<string, number>;
  hourly_orders: Array<{ hour: string; count: number; revenue: number }>;
  top_items: Array<{ name: string; quantity: number; revenue: number }>;
  payment_methods: Record<PaymentMethod, number>;
}