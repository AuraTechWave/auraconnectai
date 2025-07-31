export const generateId = (): string => {
  const timestamp = Date.now().toString(36);
  const randomStr = Math.random().toString(36).substring(2, 9);
  return `${timestamp}-${randomStr}`.toUpperCase();
};

export const formatOrderNumber = (orderNumber: string): string => {
  return `#${orderNumber}`;
};

export const getOrderStatusColor = (status: string) => {
  const colors = {
    pending: '#FFA500',
    preparing: '#2196F3',
    ready: '#4CAF50',
    completed: '#9E9E9E',
    cancelled: '#F44336',
  };
  return colors[status.toLowerCase()] || '#000000';
};

export const calculateOrderProgress = (status: string): number => {
  const progress = {
    pending: 0.2,
    preparing: 0.5,
    ready: 0.8,
    completed: 1.0,
    cancelled: 0,
  };
  return progress[status.toLowerCase()] || 0;
};