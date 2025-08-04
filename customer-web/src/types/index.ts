// Customer types
export interface Customer {
  id: number;
  first_name: string;
  last_name: string;
  email: string;
  phone?: string;
  loyalty_tier?: string;
  loyalty_points?: number;
  created_at: string;
  updated_at: string;
}

// Menu types
export interface MenuCategory {
  id: number;
  name: string;
  description?: string;
  display_order: number;
  is_active: boolean;
  icon?: string;
}

export interface MenuItem {
  id: number;
  category_id: number;
  name: string;
  description?: string;
  price: number;
  image_url?: string;
  dietary_tags?: string[];
  allergens?: string[];
  preparation_time?: number;
  is_active: boolean;
  is_available: boolean;
  display_order: number;
}

export interface MenuItemWithDetails extends MenuItem {
  category?: MenuCategory;
  modifiers?: ModifierGroup[];
}

export interface ModifierGroup {
  id: number;
  name: string;
  min_selections?: number;
  max_selections?: number;
  modifiers: Modifier[];
}

export interface Modifier {
  id: number;
  name: string;
  price_adjustment: number;
  is_available: boolean;
}

// Order types
export interface OrderItem {
  id?: number;
  menu_item_id: number;
  menu_item: MenuItem;
  quantity: number;
  price: number;
  modifiers?: number[];
  special_instructions?: string;
}

export interface Order {
  id: number;
  order_number?: string;
  customer_id: number;
  status: string;
  order_type?: string;
  payment_status?: string;
  total_amount: number;
  items: OrderItem[];
  special_instructions?: string;
  created_at: string;
  updated_at: string;
  estimated_completion?: string;
}

export enum OrderStatus {
  PENDING = 'pending',
  CONFIRMED = 'confirmed',
  PREPARING = 'preparing',
  READY = 'ready',
  COMPLETED = 'completed',
  CANCELLED = 'cancelled'
}

// Reservation types
export interface Reservation {
  id: number;
  customer_id: number;
  date: string;
  time: string;
  party_size: number;
  status: ReservationStatus;
  special_requests?: string;
  table_preference?: string;
  created_at: string;
  updated_at: string;
}

export enum ReservationStatus {
  PENDING = 'pending',
  CONFIRMED = 'confirmed',
  SEATED = 'seated',
  COMPLETED = 'completed',
  CANCELLED = 'cancelled',
  NO_SHOW = 'no_show'
}

// Cart types
export interface CartItem {
  menuItem: MenuItem;
  quantity: number;
  modifiers?: Modifier[];
  specialInstructions?: string;
  subtotal: number;
}

export interface Cart {
  items: CartItem[];
  total: number;
}