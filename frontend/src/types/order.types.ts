// Order type definitions aligned with backend API

export enum OrderStatus {
  PENDING = 'pending',
  CONFIRMED = 'confirmed',
  IN_PROGRESS = 'in_progress',
  READY = 'ready',
  COMPLETED = 'completed',
  CANCELLED = 'cancelled',
  DELAYED = 'delayed'
}

export enum PaymentStatus {
  PENDING = 'pending',
  PAID = 'paid',
  PARTIAL = 'partial',
  FAILED = 'failed',
  REFUNDED = 'refunded'
}

export enum PaymentMethod {
  CASH = 'cash',
  CARD = 'card',
  DIGITAL = 'digital',
  SPLIT = 'split'
}

export enum OrderType {
  DINE_IN = 'dine_in',
  TAKEOUT = 'takeout',
  DELIVERY = 'delivery',
  PICKUP = 'pickup'
}

export enum OrderPriority {
  LOW = 'low',
  NORMAL = 'normal',
  HIGH = 'high',
  URGENT = 'urgent'
}

export interface OrderItem {
  id: number;
  menu_item_id: number;
  menu_item_name: string;
  quantity: number;
  unit_price: number;
  total_price: number;
  modifiers?: OrderModifier[];
  special_instructions?: string;
  status: string;
  kitchen_status?: string;
  station_id?: number;
  started_at?: string;
  completed_at?: string;
}

export interface OrderModifier {
  id: number;
  name: string;
  price: number;
  quantity: number;
}

export interface Customer {
  id?: number;
  name: string;
  phone: string;
  email?: string;
  address?: string;
}

export interface OrderTag {
  id: number;
  name: string;
  color: string;
}

export interface Order {
  id: number;
  order_number: string;
  customer?: Customer;
  table_no?: number;
  status: OrderStatus;
  payment_status: PaymentStatus;
  payment_method?: PaymentMethod;
  order_type: OrderType;
  priority: OrderPriority;
  items: OrderItem[];
  subtotal: number;
  tax: number;
  discount: number;
  total: number;
  notes?: string;
  customer_notes?: string;
  tags?: OrderTag[];
  category_id?: number;
  created_at: string;
  updated_at: string;
  completed_at?: string;
  estimated_completion?: string;
  delay_minutes?: number;
  staff_id?: number;
  staff_name?: string;
  restaurant_id: number;
  external_order_id?: string;
  pos_integration_id?: number;
}

// API Request/Response types
export interface OrderListParams {
  status?: OrderStatus | OrderStatus[];
  payment_status?: PaymentStatus | PaymentStatus[];
  payment_method?: PaymentMethod | PaymentMethod[];
  order_type?: OrderType | OrderType[];
  staff_id?: number;
  table_no?: number;
  tag_ids?: number[];
  category_id?: number;
  date_from?: string; // ISO date string
  date_to?: string; // ISO date string
  limit?: number;
  offset?: number;
  include_items?: boolean;
  search?: string; // For free text search
}

export interface OrderCreateRequest {
  customer?: Customer;
  table_no?: number;
  order_type: OrderType;
  items: Array<{
    menu_item_id: number;
    quantity: number;
    modifiers?: Array<{
      modifier_id: number;
      quantity: number;
    }>;
    special_instructions?: string;
  }>;
  notes?: string;
  payment_method?: PaymentMethod;
}

export interface OrderUpdateRequest {
  status?: OrderStatus;
  payment_status?: PaymentStatus;
  payment_method?: PaymentMethod;
  priority?: OrderPriority;
  notes?: string;
  customer_notes?: string;
  table_no?: number;
  estimated_completion?: string;
}

export interface RefundRequest {
  amount: number;
  reason: string;
  items?: Array<{
    order_item_id: number;
    quantity: number;
  }>;
}

export interface RefundResponse {
  refund_id: string;
  status: 'pending' | 'completed' | 'failed';
  amount: number;
  gateway_response?: any;
  error_message?: string;
}

// Analytics types
export interface OrderAnalytics {
  total_orders: number;
  total_revenue: number;
  average_order_value: number;
  orders_by_status: Record<OrderStatus, number>;
  orders_by_type: Record<OrderType, number>;
  revenue_by_hour: Array<{
    hour: number;
    revenue: number;
    orders: number;
  }>;
  top_items: Array<{
    item_id: number;
    item_name: string;
    quantity: number;
    revenue: number;
  }>;
  payment_methods: Record<PaymentMethod, {
    count: number;
    amount: number;
  }>;
}

// WebSocket event types
export interface OrderEvent {
  type: 'order_created' | 'order_updated' | 'order_status_changed' | 'payment_updated';
  order_id: number;
  data: Partial<Order>;
  timestamp: string;
}

// Pagination
export interface PaginatedResponse<T> {
  items: T[];
  total: number;
  limit: number;
  offset: number;
  has_more: boolean;
}

// Error response
export interface ApiError {
  error: string;
  message: string;
  details?: any;
  timestamp: string;
}