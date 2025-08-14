/**
 * User Menu Component
 * 
 * Displays user information and navigation options including logout
 */

import React, { useState, useRef, useEffect } from 'react';
import { Link } from 'react-router-dom';
import { useAuth } from '../../contexts/AuthContext';
import LogoutButton from '../auth/LogoutButton';
import './UserMenu.css';

interface UserMenuProps {
  showAvatar?: boolean;
  showName?: boolean;
  className?: string;
}

const UserMenu: React.FC<UserMenuProps> = ({
  showAvatar = true,
  showName = true,
  className = '',
}) => {
  const { user, isAuthenticated } = useAuth();
  const [isOpen, setIsOpen] = useState(false);
  const menuRef = useRef<HTMLDivElement>(null);

  // Close menu when clicking outside
  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (menuRef.current && !menuRef.current.contains(event.target as Node)) {
        setIsOpen(false);
      }
    };

    if (isOpen) {
      document.addEventListener('mousedown', handleClickOutside);
    }

    return () => {
      document.removeEventListener('mousedown', handleClickOutside);
    };
  }, [isOpen]);

  // Close menu on escape key
  useEffect(() => {
    const handleEscape = (event: KeyboardEvent) => {
      if (event.key === 'Escape') {
        setIsOpen(false);
      }
    };

    if (isOpen) {
      document.addEventListener('keydown', handleEscape);
    }

    return () => {
      document.removeEventListener('keydown', handleEscape);
    };
  }, [isOpen]);

  if (!isAuthenticated || !user) {
    return null;
  }

  const toggleMenu = () => {
    setIsOpen(!isOpen);
  };

  const getUserInitials = () => {
    if (!user.email) return '?';
    const parts = user.email.split('@')[0].split('.');
    if (parts.length >= 2) {
      return (parts[0][0] + parts[1][0]).toUpperCase();
    }
    return user.email[0].toUpperCase();
  };

  const getUserDisplayName = () => {
    if (user.name) return user.name;
    if (user.email) return user.email.split('@')[0];
    return 'User';
  };

  const getRoleLabel = () => {
    const roleLabels: Record<string, string> = {
      admin: 'Administrator',
      manager: 'Manager',
      staff: 'Staff',
      cashier: 'Cashier',
      kitchen: 'Kitchen Staff',
      server: 'Server',
    };
    return roleLabels[user.role] || user.role;
  };

  return (
    <div className={`user-menu ${className}`} ref={menuRef}>
      <button
        className="user-menu-trigger"
        onClick={toggleMenu}
        aria-expanded={isOpen}
        aria-haspopup="menu"
      >
        {showAvatar && (
          <div className="user-avatar">
            {user.avatar ? (
              <img src={user.avatar} alt={getUserDisplayName()} />
            ) : (
              <span className="user-initials">{getUserInitials()}</span>
            )}
          </div>
        )}
        
        {showName && (
          <div className="user-info">
            <span className="user-name">{getUserDisplayName()}</span>
            <span className="user-role">{getRoleLabel()}</span>
          </div>
        )}

        <svg
          className={`menu-chevron ${isOpen ? 'open' : ''}`}
          width="16"
          height="16"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          strokeWidth="2"
          strokeLinecap="round"
          strokeLinejoin="round"
        >
          <polyline points="6 9 12 15 18 9" />
        </svg>
      </button>

      {isOpen && (
        <div className="user-menu-dropdown" role="menu">
          <div className="menu-header">
            <div className="menu-user-info">
              <div className="menu-user-name">{getUserDisplayName()}</div>
              <div className="menu-user-email">{user.email}</div>
              <div className="menu-user-role">{getRoleLabel()}</div>
            </div>
          </div>

          <div className="menu-divider" />

          <nav className="menu-nav">
            <Link
              to="/profile"
              className="menu-item"
              onClick={() => setIsOpen(false)}
              role="menuitem"
            >
              <svg
                className="menu-icon"
                width="16"
                height="16"
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                strokeWidth="2"
                strokeLinecap="round"
                strokeLinejoin="round"
              >
                <path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2" />
                <circle cx="12" cy="7" r="4" />
              </svg>
              My Profile
            </Link>

            <Link
              to="/settings"
              className="menu-item"
              onClick={() => setIsOpen(false)}
              role="menuitem"
            >
              <svg
                className="menu-icon"
                width="16"
                height="16"
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                strokeWidth="2"
                strokeLinecap="round"
                strokeLinejoin="round"
              >
                <circle cx="12" cy="12" r="3" />
                <path d="M12 1v6m0 6v6m4.22-13.22l4.24 4.24M1.54 9.96l4.24 4.24M18.46 14.04l4.24 4.24M1.54 14.04l4.24-4.24" />
              </svg>
              Settings
            </Link>

            {user.role === 'admin' && (
              <>
                <div className="menu-divider" />
                <Link
                  to="/admin"
                  className="menu-item"
                  onClick={() => setIsOpen(false)}
                  role="menuitem"
                >
                  <svg
                    className="menu-icon"
                    width="16"
                    height="16"
                    viewBox="0 0 24 24"
                    fill="none"
                    stroke="currentColor"
                    strokeWidth="2"
                    strokeLinecap="round"
                    strokeLinejoin="round"
                  >
                    <rect x="3" y="3" width="18" height="18" rx="2" ry="2" />
                    <line x1="9" y1="9" x2="15" y2="9" />
                    <line x1="9" y1="15" x2="15" y2="15" />
                  </svg>
                  Admin Dashboard
                </Link>
              </>
            )}

            <div className="menu-divider" />

            <Link
              to="/help"
              className="menu-item"
              onClick={() => setIsOpen(false)}
              role="menuitem"
            >
              <svg
                className="menu-icon"
                width="16"
                height="16"
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                strokeWidth="2"
                strokeLinecap="round"
                strokeLinejoin="round"
              >
                <circle cx="12" cy="12" r="10" />
                <path d="M9.09 9a3 3 0 0 1 5.83 1c0 2-3 3-3 3" />
                <line x1="12" y1="17" x2="12.01" y2="17" />
              </svg>
              Help & Support
            </Link>
          </nav>

          <div className="menu-divider" />

          <div className="menu-footer">
            <LogoutButton
              variant="button"
              className="menu-logout"
              onLogoutComplete={() => setIsOpen(false)}
            />
          </div>
        </div>
      )}
    </div>
  );
};

export default UserMenu;