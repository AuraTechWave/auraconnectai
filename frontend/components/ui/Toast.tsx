/**
 * Toast notification system for better error and success messaging
 * Replaces console errors with user-friendly notifications
 */

import React, { createContext, useContext, useState, useCallback, useEffect } from 'react';
import './Toast.css';

export interface Toast {
  id: string;
  type: 'success' | 'error' | 'warning' | 'info';
  title: string;
  message?: string;
  duration?: number;
  action?: {
    label: string;
    onClick: () => void;
  };
}

interface ToastContextType {
  toasts: Toast[];
  showToast: (toast: Omit<Toast, 'id'>) => void;
  hideToast: (id: string) => void;
  showSuccess: (title: string, message?: string) => void;
  showError: (title: string, message?: string) => void;
  showWarning: (title: string, message?: string) => void;
  showInfo: (title: string, message?: string) => void;
}

const ToastContext = createContext<ToastContextType | undefined>(undefined);

export const useToast = (): ToastContextType => {
  const context = useContext(ToastContext);
  if (!context) {
    throw new Error('useToast must be used within a ToastProvider');
  }
  return context;
};

interface ToastProviderProps {
  children: React.ReactNode;
  maxToasts?: number;
}

export const ToastProvider: React.FC<ToastProviderProps> = ({ 
  children, 
  maxToasts = 5 
}) => {
  const [toasts, setToasts] = useState<Toast[]>([]);

  const showToast = useCallback((toast: Omit<Toast, 'id'>) => {
    const id = `toast-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`;
    const newToast: Toast = {
      ...toast,
      id,
      duration: toast.duration ?? 5000,
    };

    setToasts(prev => {
      const updated = [newToast, ...prev];
      return updated.slice(0, maxToasts);
    });

    // Auto-hide after duration
    if (newToast.duration && newToast.duration > 0) {
      setTimeout(() => {
        hideToast(id);
      }, newToast.duration);
    }
  }, [maxToasts]);

  const hideToast = useCallback((id: string) => {
    setToasts(prev => prev.filter(toast => toast.id !== id));
  }, []);

  const showSuccess = useCallback((title: string, message?: string) => {
    showToast({ type: 'success', title, message });
  }, [showToast]);

  const showError = useCallback((title: string, message?: string) => {
    showToast({ type: 'error', title, message, duration: 8000 });
  }, [showToast]);

  const showWarning = useCallback((title: string, message?: string) => {
    showToast({ type: 'warning', title, message, duration: 6000 });
  }, [showToast]);

  const showInfo = useCallback((title: string, message?: string) => {
    showToast({ type: 'info', title, message });
  }, [showToast]);

  const value: ToastContextType = {
    toasts,
    showToast,
    hideToast,
    showSuccess,
    showError,
    showWarning,
    showInfo,
  };

  return (
    <ToastContext.Provider value={value}>
      {children}
      <ToastContainer toasts={toasts} onHide={hideToast} />
    </ToastContext.Provider>
  );
};

interface ToastContainerProps {
  toasts: Toast[];
  onHide: (id: string) => void;
}

const ToastContainer: React.FC<ToastContainerProps> = ({ toasts, onHide }) => {
  if (toasts.length === 0) return null;

  return (
    <div className="toast-container" aria-live="polite" aria-label="Notifications">
      {toasts.map(toast => (
        <ToastItem key={toast.id} toast={toast} onHide={onHide} />
      ))}
    </div>
  );
};

interface ToastItemProps {
  toast: Toast;
  onHide: (id: string) => void;
}

const ToastItem: React.FC<ToastItemProps> = ({ toast, onHide }) => {
  const [isExiting, setIsExiting] = useState(false);

  const handleClose = () => {
    setIsExiting(true);
    setTimeout(() => onHide(toast.id), 300);
  };

  const handleAction = () => {
    if (toast.action) {
      toast.action.onClick();
      handleClose();
    }
  };

  useEffect(() => {
    const timer = setTimeout(() => setIsExiting(false), 100);
    return () => clearTimeout(timer);
  }, []);

  const getIcon = () => {
    switch (toast.type) {
      case 'success':
        return '✓';
      case 'error':
        return '✕';
      case 'warning':
        return '⚠';
      case 'info':
        return 'ℹ';
      default:
        return '';
    }
  };

  return (
    <div
      className={`toast toast--${toast.type} ${isExiting ? 'toast--exiting' : 'toast--entering'}`}
      role="alert"
      aria-labelledby={`toast-title-${toast.id}`}
      aria-describedby={toast.message ? `toast-message-${toast.id}` : undefined}
    >
      <div className="toast__icon" aria-hidden="true">
        {getIcon()}
      </div>
      
      <div className="toast__content">
        <div id={`toast-title-${toast.id}`} className="toast__title">
          {toast.title}
        </div>
        {toast.message && (
          <div id={`toast-message-${toast.id}`} className="toast__message">
            {toast.message}
          </div>
        )}
      </div>

      <div className="toast__actions">
        {toast.action && (
          <button
            className="toast__action-button"
            onClick={handleAction}
            type="button"
          >
            {toast.action.label}
          </button>
        )}
        <button
          className="toast__close-button"
          onClick={handleClose}
          type="button"
          aria-label="Close notification"
        >
          ×
        </button>
      </div>
    </div>
  );
};

// Utility hook for payroll-specific toasts
export const usePayrollToast = () => {
  const { showSuccess, showError, showWarning, showInfo } = useToast();

  return {
    payrollSuccess: (message: string) => showSuccess('Payroll Success', message),
    payrollError: (message: string, details?: string) => 
      showError('Payroll Error', details ? `${message}: ${details}` : message),
    payrollWarning: (message: string) => showWarning('Payroll Warning', message),
    payrollInfo: (message: string) => showInfo('Payroll Info', message),
    
    // Specific payroll operations
    runPayrollSuccess: (staffCount: number) => 
      showSuccess('Payroll Started', `Processing payroll for ${staffCount} staff member${staffCount > 1 ? 's' : ''}`),
    runPayrollError: (error: string) => 
      showError('Failed to Run Payroll', error),
    
    exportSuccess: (format: string) => 
      showSuccess('Export Ready', `Your ${format} export is ready for download`),
    exportError: (error: string) => 
      showError('Export Failed', error),
    
    loadError: (operation: string) => 
      showError('Failed to Load Data', `Could not load ${operation}. Please try again.`),
    
    saveSuccess: () => 
      showSuccess('Changes Saved', 'Your payroll settings have been updated'),
    saveError: (error: string) => 
      showError('Save Failed', error),
  };
};