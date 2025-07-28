import React, { useState, useEffect } from 'react';
import './Notification.css';

export type NotificationType = 'success' | 'error' | 'warning' | 'info';

interface NotificationProps {
  type: NotificationType;
  title?: string;
  message: string;
  duration?: number;
  onClose: () => void;
  persistent?: boolean;
}

const Notification: React.FC<NotificationProps> = ({
  type,
  title,
  message,
  duration = 5000,
  onClose,
  persistent = false
}) => {
  const [isVisible, setIsVisible] = useState(true);
  const [isClosing, setIsClosing] = useState(false);

  useEffect(() => {
    if (!persistent && duration > 0) {
      const timer = setTimeout(() => {
        handleClose();
      }, duration);

      return () => clearTimeout(timer);
    }
  }, [duration, persistent]);

  const handleClose = () => {
    setIsClosing(true);
    setTimeout(() => {
      setIsVisible(false);
      onClose();
    }, 300); // Match CSS animation duration
  };

  const getIcon = () => {
    switch (type) {
      case 'success':
        return '✅';
      case 'error':
        return '❌';
      case 'warning':
        return '⚠️';
      case 'info':
        return 'ℹ️';
      default:
        return 'ℹ️';
    }
  };

  if (!isVisible) return null;

  return (
    <div 
      className={`notification notification-${type} ${isClosing ? 'notification-closing' : ''}`}
      role="alert"
      aria-live="polite"
    >
      <div className="notification-icon">
        {getIcon()}
      </div>
      
      <div className="notification-content">
        {title && <div className="notification-title">{title}</div>}
        <div className="notification-message">{message}</div>
      </div>
      
      <button 
        className="notification-close"
        onClick={handleClose}
        aria-label="Close notification"
      >
        ×
      </button>

      {!persistent && duration > 0 && (
        <div 
          className="notification-progress"
          style={{ animationDuration: `${duration}ms` }}
        />
      )}
    </div>
  );
};

// Hook for managing notifications
export interface NotificationData {
  id: string;
  type: NotificationType;
  title?: string;
  message: string;
  duration?: number;
  persistent?: boolean;
}

export const useNotifications = () => {
  const [notifications, setNotifications] = useState<NotificationData[]>([]);

  const addNotification = (notification: Omit<NotificationData, 'id'>) => {
    const id = Date.now().toString() + Math.random().toString(36).substr(2, 9);
    setNotifications(prev => [...prev, { ...notification, id }]);
    return id;
  };

  const removeNotification = (id: string) => {
    setNotifications(prev => prev.filter(n => n.id !== id));
  };

  const clearAll = () => {
    setNotifications([]);
  };

  // Convenience methods
  const success = (message: string, title?: string, options?: Partial<NotificationData>) => 
    addNotification({ type: 'success', message, title, ...options });

  const error = (message: string, title?: string, options?: Partial<NotificationData>) => 
    addNotification({ type: 'error', message, title, persistent: true, ...options });

  const warning = (message: string, title?: string, options?: Partial<NotificationData>) => 
    addNotification({ type: 'warning', message, title, ...options });

  const info = (message: string, title?: string, options?: Partial<NotificationData>) => 
    addNotification({ type: 'info', message, title, ...options });

  return {
    notifications,
    addNotification,
    removeNotification,
    clearAll,
    success,
    error,
    warning,
    info
  };
};

// Container component for displaying notifications
export const NotificationContainer: React.FC<{
  notifications: NotificationData[];
  onRemove: (id: string) => void;
}> = ({ notifications, onRemove }) => {
  if (notifications.length === 0) return null;

  return (
    <div className="notification-container">
      {notifications.map((notification) => (
        <Notification
          key={notification.id}
          {...notification}
          onClose={() => onRemove(notification.id)}
        />
      ))}
    </div>
  );
};

export default Notification;