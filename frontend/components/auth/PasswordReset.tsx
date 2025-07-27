import React, { useState } from 'react';
import { apiClient } from '../../utils/apiClient';
import './PasswordReset.css';

interface PasswordResetProps {
  onSuccess?: () => void;
  onCancel?: () => void;
}

interface PasswordStrengthResult {
  is_valid: boolean;
  strength: string;
  score: number;
  errors: string[];
  suggestions: string[];
}

const PasswordReset: React.FC<PasswordResetProps> = ({ onSuccess, onCancel }) => {
  const [step, setStep] = useState<'request' | 'confirm'>('request');
  const [email, setEmail] = useState('');
  const [token, setToken] = useState('');
  const [newPassword, setNewPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const [passwordStrength, setPasswordStrength] = useState<PasswordStrengthResult | null>(null);

  // Get token from URL if present
  React.useEffect(() => {
    const urlParams = new URLSearchParams(window.location.search);
    const urlToken = urlParams.get('token');
    if (urlToken) {
      setToken(urlToken);
      setStep('confirm');
    }
  }, []);

  const handleRequestReset = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError(null);

    try {
      const response = await apiClient.post('/auth/password/reset/request', {
        email: email.trim().toLowerCase()
      });

      setSuccess(response.data.message);
      
      // Don't automatically switch steps for security reasons
      // User should check their email
      
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to request password reset');
    } finally {
      setLoading(false);
    }
  };

  const handleConfirmReset = async (e: React.FormEvent) => {
    e.preventDefault();
    
    if (newPassword !== confirmPassword) {
      setError('Passwords do not match');
      return;
    }

    if (!passwordStrength?.is_valid) {
      setError('Please choose a stronger password');
      return;
    }

    setLoading(true);
    setError(null);

    try {
      const response = await apiClient.post('/auth/password/reset/confirm', {
        token: token,
        new_password: newPassword,
        confirm_password: confirmPassword
      });

      setSuccess(response.data.message);
      
      // Redirect to login after successful reset
      setTimeout(() => {
        if (onSuccess) {
          onSuccess();
        } else {
          window.location.href = '/login';
        }
      }, 2000);
      
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to reset password');
    } finally {
      setLoading(false);
    }
  };

  const validatePassword = async (password: string) => {
    if (!password || password.length < 8) {
      setPasswordStrength(null);
      return;
    }

    try {
      const response = await apiClient.post('/auth/password/validate', {
        password: password,
        email: email
      });

      setPasswordStrength(response.data);
    } catch (err) {
      console.error('Password validation failed:', err);
    }
  };

  const getStrengthColor = (strength: string) => {
    switch (strength) {
      case 'very_weak': return '#dc3545';
      case 'weak': return '#fd7e14';
      case 'fair': return '#ffc107';
      case 'good': return '#198754';
      case 'strong': return '#0d6efd';
      default: return '#6c757d';
    }
  };

  const getStrengthText = (strength: string) => {
    switch (strength) {
      case 'very_weak': return 'Very Weak';
      case 'weak': return 'Weak';
      case 'fair': return 'Fair';
      case 'good': return 'Good';
      case 'strong': return 'Strong';
      default: return 'Unknown';
    }
  };

  if (step === 'request') {
    return (
      <div className="password-reset">
        <div className="password-reset-card">
          <h2>Reset Your Password</h2>
          <p>Enter your email address and we'll send you a link to reset your password.</p>

          {error && (
            <div className="alert alert-error">
              {error}
            </div>
          )}

          {success && (
            <div className="alert alert-success">
              {success}
            </div>
          )}

          <form onSubmit={handleRequestReset}>
            <div className="form-group">
              <label htmlFor="email">Email Address</label>
              <input
                type="email"
                id="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                required
                disabled={loading}
                placeholder="Enter your email address"
              />
            </div>

            <div className="form-actions">
              <button
                type="submit"
                className="btn btn-primary"
                disabled={loading || !email.trim()}
              >
                {loading ? 'Sending...' : 'Send Reset Link'}
              </button>

              {onCancel && (
                <button
                  type="button"
                  className="btn btn-secondary"
                  onClick={onCancel}
                  disabled={loading}
                >
                  Cancel
                </button>
              )}
            </div>
          </form>

          <div className="additional-links">
            <p>
              Remember your password? <a href="/login">Sign In</a>
            </p>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="password-reset">
      <div className="password-reset-card">
        <h2>Set New Password</h2>
        <p>Please enter your new password below.</p>

        {error && (
          <div className="alert alert-error">
            {error}
          </div>
        )}

        {success && (
          <div className="alert alert-success">
            {success}
          </div>
        )}

        <form onSubmit={handleConfirmReset}>
          <div className="form-group">
            <label htmlFor="newPassword">New Password</label>
            <input
              type="password"
              id="newPassword"
              value={newPassword}
              onChange={(e) => {
                setNewPassword(e.target.value);
                validatePassword(e.target.value);
              }}
              required
              disabled={loading}
              placeholder="Enter new password"
            />
            
            {passwordStrength && (
              <div className="password-strength">
                <div className="strength-bar">
                  <div 
                    className="strength-fill"
                    style={{
                      width: `${passwordStrength.score}%`,
                      backgroundColor: getStrengthColor(passwordStrength.strength)
                    }}
                  />
                </div>
                <div className="strength-info">
                  <span 
                    className="strength-label"
                    style={{ color: getStrengthColor(passwordStrength.strength) }}
                  >
                    {getStrengthText(passwordStrength.strength)} ({passwordStrength.score}/100)
                  </span>
                </div>
                
                {passwordStrength.errors.length > 0 && (
                  <div className="password-errors">
                    {passwordStrength.errors.map((error, index) => (
                      <div key={index} className="password-error">
                        ❌ {error}
                      </div>
                    ))}
                  </div>
                )}
                
                {passwordStrength.suggestions.length > 0 && (
                  <div className="password-suggestions">
                    {passwordStrength.suggestions.map((suggestion, index) => (
                      <div key={index} className="password-suggestion">
                        💡 {suggestion}
                      </div>
                    ))}
                  </div>
                )}
              </div>
            )}
          </div>

          <div className="form-group">
            <label htmlFor="confirmPassword">Confirm New Password</label>
            <input
              type="password"
              id="confirmPassword"
              value={confirmPassword}
              onChange={(e) => setConfirmPassword(e.target.value)}
              required
              disabled={loading}
              placeholder="Confirm new password"
            />
            {confirmPassword && newPassword !== confirmPassword && (
              <div className="password-error">
                ❌ Passwords do not match
              </div>
            )}
          </div>

          <div className="form-actions">
            <button
              type="submit"
              className="btn btn-primary"
              disabled={loading || !newPassword || !confirmPassword || newPassword !== confirmPassword || !passwordStrength?.is_valid}
            >
              {loading ? 'Updating...' : 'Update Password'}
            </button>

            {onCancel && (
              <button
                type="button"
                className="btn btn-secondary"
                onClick={onCancel}
                disabled={loading}
              >
                Cancel
              </button>
            )}
          </div>
        </form>
      </div>
    </div>
  );
};

export default PasswordReset;