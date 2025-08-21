import { NavigatorScreenParams } from '@react-navigation/native';
import { OrdersStackParamList } from '../navigation/OrdersNavigator';

// Root navigation types
export type RootStackParamList = {
  Auth: undefined;
  Main: undefined;
};

// Main tab navigation types
export type MainTabParamList = {
  Home: undefined;
  Orders: NavigatorScreenParams<OrdersStackParamList>;
  Menu: undefined;
  Customers: undefined;
  Reports: undefined;
};

// Re-export stack param lists
export type { OrdersStackParamList };

// Type helpers for consistent ID handling
export const normalizeOrderId = (id: string | number): string => {
  return typeof id === 'number' ? id.toString() : id;
};

export const parseOrderId = (id: string): number | null => {
  const parsed = parseInt(id, 10);
  return isNaN(parsed) ? null : parsed;
};