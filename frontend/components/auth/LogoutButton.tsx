/**
 * Logout Button Component
 * 
 * Provides logout functionality with confirmation dialog
 */

import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../../contexts/AuthContext';
import './LogoutButton.css';

interface LogoutButtonProps {
  showConfirmation?: boolean;
  redirectTo?: string;
  variant?: 'button' | 'link' | 'icon';
  className?: string;
  onLogoutComplete?: () => void;
}

const LogoutButton: React.FC<LogoutButtonProps> = ({
  showConfirmation = true,
  redirectTo = '/auth/login',
  variant = 'button',
  className = '',
  onLogoutComplete,
}) => {
  const navigate = useNavigate();
  const { logout, isLoading } = useAuth();
  const [showDialog, setShowDialog] = useState(false);

  const handleLogout = async () => {
    if (showConfirmation && !showDialog) {
      setShowDialog(true);
      return;
    }

    try {
      await logout();
      
      if (onLogoutComplete) {
        onLogoutComplete();
      }
      
      navigate(redirectTo, {
        state: { message: 'You have been successfully logged out' }
      });
    } catch (error) {
      console.error('Logout failed:', error);
    }
  };

  const handleCancel = () => {
    setShowDialog(false);
  };

  const renderButton = () => {
    switch (variant) {
      case 'icon':
        return (
          <button
            onClick={handleLogout}
            className={`logout-icon-button ${className}`}
            disabled={isLoading}
            aria-label="Logout"
            title="Logout"
          >
            <svg
              width="20"
              height="20"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="2"
              strokeLinecap="round"
              strokeLinejoin="round"
            >
              <path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4" />
              <polyline points="16 17 21 12 16 7" />
              <line x1="21" y1="12" x2="9" y2="12" />
            </svg>
            {isLoading && <span className="spinner-small"></span>}
          </button>
        );

      case 'link':
        return (
          <a
            onClick={handleLogout}
            className={`logout-link ${className}`}
            role="button"
            tabIndex={0}
            onKeyDown={(e) => {
              if (e.key === 'Enter' || e.key === ' ') {
                e.preventDefault();
                handleLogout();
              }
            }}
          >
            {isLoading ? 'Logging out...' : 'Logout'}
          </a>
        );

      case 'button':
      default:
        return (
          <button
            onClick={handleLogout}
            className={`logout-button ${className}`}
            disabled={isLoading}
          >
            {isLoading ? (
              <>
                <span className="spinner-small"></span>
                Logging out...
              </>
            ) : (
              <>
                <svg
                  className="logout-icon"
                  width="16"
                  height="16"
                  viewBox="0 0 24 24"
                  fill="none"
                  stroke="currentColor"
                  strokeWidth="2"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                >
                  <path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4" />
                  <polyline points="16 17 21 12 16 7" />
                  <line x1="21" y1="12" x2="9" y2="12" />
                </svg>
                Logout
              </>
            )}
          </button>
        );
    }
  };

  return (
    <>
      {renderButton()}

      {/* Confirmation Dialog */}
      {showDialog && (
        <div className="logout-dialog-overlay" onClick={handleCancel}>
          <div
            className="logout-dialog"
            onClick={(e) => e.stopPropagation()}
            role="dialog"
            aria-labelledby="logout-dialog-title"
            aria-describedby="logout-dialog-description"
          >
            <div className="logout-dialog-header">
              <h2 id="logout-dialog-title">Confirm Logout</h2>
              <button
                className="dialog-close"
                onClick={handleCancel}
                aria-label="Close dialog"
              >
                <svg
                  width="20"
                  height="20"
                  viewBox="0 0 24 24"
                  fill="none"
                  stroke="currentColor"
                  strokeWidth="2"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                >
                  <line x1="18" y1="6" x2="6" y2="18" />
                  <line x1="6" y1="6" x2="18" y2="18" />
                </svg>
              </button>
            </div>

            <div className="logout-dialog-body">
              <p id="logout-dialog-description">
                Are you sure you want to log out? You'll need to sign in again to access your account.
              </p>
            </div>

            <div className="logout-dialog-footer">
              <button
                className="dialog-button dialog-button-cancel"
                onClick={handleCancel}
              >
                Cancel
              </button>
              <button
                className="dialog-button dialog-button-confirm"
                onClick={() => {
                  setShowDialog(false);
                  handleLogout();
                }}
                disabled={isLoading}
              >
                {isLoading ? (
                  <>
                    <span className="spinner-small"></span>
                    Logging out...
                  </>
                ) : (
                  'Yes, Logout'
                )}
              </button>
            </div>
          </div>
        </div>
      )}
    </>
  );
};

export default LogoutButton;

/**
 * Hook for programmatic logout
 */
export const useLogout = () => {
  const navigate = useNavigate();
  const { logout, isLoading } = useAuth();

  const performLogout = async (redirectTo: string = '/auth/login') => {
    try {
      await logout();
      navigate(redirectTo, {
        state: { message: 'You have been successfully logged out' }
      });
      return true;
    } catch (error) {
      console.error('Logout failed:', error);
      return false;
    }
  };

  return { performLogout, isLoading };
};