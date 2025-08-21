/**
 * Icon configuration for react-native-vector-icons
 * Ensures icons are properly loaded and available across the app
 */

// Common icon names used throughout the app
export const ICON_NAMES = {
  // Order status icons
  orderPending: 'clock-outline',
  orderPreparing: 'chef-hat',
  orderReady: 'check-circle',
  orderServed: 'food',
  orderCompleted: 'check-all',
  orderCancelled: 'close-circle',
  
  // Payment method icons
  cash: 'cash',
  card: 'credit-card',
  digital: 'cellphone',
  check: 'checkbook',
  
  // Navigation icons
  back: 'arrow-left',
  menu: 'menu',
  search: 'magnify',
  filter: 'filter-variant',
  sort: 'sort',
  
  // Action icons
  add: 'plus',
  edit: 'pencil',
  delete: 'delete',
  share: 'share-variant',
  print: 'printer',
  download: 'download',
  
  // Status icons
  online: 'circle',
  offline: 'circle-outline',
  busy: 'minus-circle',
  away: 'clock',
  
  // User/Account icons
  account: 'account',
  accountGroup: 'account-group',
  settings: 'cog',
  logout: 'logout',
  
  // Communication icons
  phone: 'phone',
  email: 'email',
  message: 'message-text',
  
  // UI elements
  close: 'close',
  check: 'check',
  info: 'information',
  warning: 'alert',
  error: 'alert-circle',
  success: 'check-circle',
} as const;

// Icon size constants
export const ICON_SIZES = {
  xs: 12,
  sm: 16,
  md: 20,
  lg: 24,
  xl: 32,
  xxl: 48,
} as const;

// Helper to ensure icon exists
export const getIconName = (name: keyof typeof ICON_NAMES): string => {
  return ICON_NAMES[name] || 'help-circle-outline';
};