export { NotificationService } from './NotificationService';
export { NotificationHandler } from './NotificationHandler';
export * from './types';

// Export singleton instance
import { NotificationService } from './NotificationService';
export const notificationService = NotificationService.getInstance();