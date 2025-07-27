/**
 * Login Form Component with Token Management
 * 
 * Demonstrates:
 * - Login with JWT tokens
 * - Token storage
 * - Error handling
 * - Redirect after login
 */

import React, { useState, useEffect } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import { useAuth } from '../../hooks/useAuth';
import { useToast } from '../ui/Toast';
import './LoginForm.css';

interface LocationState {
  from?: string;
  message?: string;
}

export const LoginForm: React.FC = () => {
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [rememberMe, setRememberMe] = useState(false);
  
  const { login, isAuthenticated } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const { showError, showSuccess, showInfo } = useToast();
  
  const state = location.state as LocationState;
  const from = state?.from || '/dashboard';
  
  // Show any messages from navigation state
  useEffect(() => {
    if (state?.message) {
      showInfo('Session Expired', state.message);
    }
  }, [state, showInfo]);
  
  // Redirect if already authenticated
  useEffect(() => {
    if (isAuthenticated) {
      navigate(from, { replace: true });
    }
  }, [isAuthenticated, navigate, from]);
  
  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    
    if (!username || !password) {
      showError('Validation Error', 'Please enter both username and password');
      return;
    }
    
    setIsLoading(true);
    
    try {
      const success = await login(username, password);
      
      if (success) {
        showSuccess('Login Successful', 'Welcome back!');
        navigate(from, { replace: true });
      } else {
        showError('Login Failed', 'Invalid username or password');
      }
    } catch (error) {
      showError('Login Error', 'An unexpected error occurred. Please try again.');
    } finally {
      setIsLoading(false);
    }
  };
  
  return (
    <div className="login-container">
      <div className="login-card">
        <div className="login-header">
          <h1>AuraConnect AI</h1>
          <p>Restaurant Management Platform</p>
        </div>
        
        <form onSubmit={handleSubmit} className="login-form">
          <div className="form-group">
            <label htmlFor="username">Username</label>
            <input
              id="username"
              type="text"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              placeholder="Enter your username"
              disabled={isLoading}
              autoComplete="username"
              required
            />
          </div>
          
          <div className="form-group">
            <label htmlFor="password">Password</label>
            <input
              id="password"
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="Enter your password"
              disabled={isLoading}
              autoComplete="current-password"
              required
            />
          </div>
          
          <div className="form-group checkbox-group">
            <label>
              <input
                type="checkbox"
                checked={rememberMe}
                onChange={(e) => setRememberMe(e.target.checked)}
                disabled={isLoading}
              />
              Remember me
            </label>
          </div>
          
          <button
            type="submit"
            className="login-button"
            disabled={isLoading}
          >
            {isLoading ? 'Logging in...' : 'Login'}
          </button>
        </form>
        
        <div className="login-footer">
          <div className="test-credentials">
            <h3>Test Credentials</h3>
            <ul>
              <li><strong>Admin:</strong> admin / secret</li>
              <li><strong>Payroll:</strong> payroll_clerk / secret</li>
              <li><strong>Manager:</strong> manager / secret</li>
            </ul>
          </div>
        </div>
      </div>
    </div>
  );
};

// Session Monitor Component - shows token status
export const SessionMonitor: React.FC = () => {
  const { user, logout } = useAuth();
  const [sessionInfo, setSessionInfo] = useState<any>(null);
  const { showInfo } = useToast();
  
  useEffect(() => {
    const checkTokenStatus = () => {
      const accessToken = localStorage.getItem('access_token');
      const refreshToken = localStorage.getItem('refresh_token');
      
      if (accessToken) {
        try {
          // Decode token to check expiration
          const base64Url = accessToken.split('.')[1];
          const base64 = base64Url.replace(/-/g, '+').replace(/_/g, '/');
          const jsonPayload = decodeURIComponent(
            atob(base64)
              .split('')
              .map(c => '%' + ('00' + c.charCodeAt(0).toString(16)).slice(-2))
              .join('')
          );
          
          const payload = JSON.parse(jsonPayload);
          const exp = new Date(payload.exp * 1000);
          const now = new Date();
          const timeLeft = Math.floor((exp.getTime() - now.getTime()) / 1000);
          
          setSessionInfo({
            accessTokenExpires: exp.toLocaleString(),
            timeLeft: timeLeft > 0 ? `${Math.floor(timeLeft / 60)}m ${timeLeft % 60}s` : 'Expired',
            isExpired: timeLeft <= 0,
            hasRefreshToken: !!refreshToken
          });
        } catch (error) {
          console.error('Failed to decode token:', error);
        }
      }
    };
    
    // Check immediately and then every 10 seconds
    checkTokenStatus();
    const interval = setInterval(checkTokenStatus, 10000);
    
    return () => clearInterval(interval);
  }, []);
  
  if (!user || !sessionInfo) return null;
  
  return (
    <div className="session-monitor">
      <div className="session-info">
        <span className="username">{user.username}</span>
        <span className={`token-status ${sessionInfo.isExpired ? 'expired' : 'active'}`}>
          Token: {sessionInfo.timeLeft}
        </span>
        {sessionInfo.isExpired && sessionInfo.hasRefreshToken && (
          <span className="refresh-available">
            (Will auto-refresh on next request)
          </span>
        )}
      </div>
      
      <div className="session-actions">
        <button
          onClick={() => logout(false)}
          className="logout-button"
          title="Logout from this device"
        >
          Logout
        </button>
        <button
          onClick={() => {
            showInfo('Logging out', 'Logging out from all devices...');
            logout(true);
          }}
          className="logout-all-button"
          title="Logout from all devices"
        >
          Logout All
        </button>
      </div>
    </div>
  );
};