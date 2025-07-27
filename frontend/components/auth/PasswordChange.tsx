import React, { useState } from 'react';
import { apiClient } from '../../utils/apiClient';
import { useRBAC } from '../../hooks/useRBAC';
import './PasswordChange.css';

interface PasswordChangeProps {
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

const PasswordChange: React.FC<PasswordChangeProps> = ({ onSuccess, onCancel }) => {
  const { user } = useRBAC();
  const [currentPassword, setCurrentPassword] = useState('');
  const [newPassword, setNewPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const [passwordStrength, setPasswordStrength] = useState<PasswordStrengthResult | null>(null);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    
    if (newPassword !== confirmPassword) {
      setError('New passwords do not match');
      return;
    }

    if (!passwordStrength?.is_valid) {
      setError('Please choose a stronger password');
      return;
    }

    setLoading(true);
    setError(null);

    try {
      const response = await apiClient.post('/auth/password/change', {
        current_password: currentPassword,
        new_password: newPassword,
        confirm_password: confirmPassword
      });

      setSuccess(response.data.message);
      
      // Clear form
      setCurrentPassword('');
      setNewPassword('');
      setConfirmPassword('');
      setPasswordStrength(null);
      
      // Call success callback after a short delay
      setTimeout(() => {
        if (onSuccess) {
          onSuccess();
        }
      }, 1500);
      
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to change password');
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
        email: user?.email
      });

      setPasswordStrength(response.data);
    } catch (err) {
      console.error('Password validation failed:', err);
    }
  };

  const generateSecurePassword = async () => {
    try {
      const response = await apiClient.post('/auth/password/generate', {
        length: 16
      });

      setNewPassword(response.data.password);
      setConfirmPassword(response.data.password);
      await validatePassword(response.data.password);
      
    } catch (err) {
      console.error('Failed to generate password:', err);
      setError('Failed to generate secure password');
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

  return (
    <div className="password-change">
      <div className="password-change-card">
        <h2>Change Password</h2>
        <p>Update your password to keep your account secure.</p>

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

        <form onSubmit={handleSubmit}>
          <div className="form-group">
            <label htmlFor="currentPassword">Current Password</label>
            <input
              type="password"
              id="currentPassword"
              value={currentPassword}
              onChange={(e) => setCurrentPassword(e.target.value)}
              required
              disabled={loading}
              placeholder="Enter your current password"
            />
          </div>

          <div className="form-group">
            <label htmlFor="newPassword">New Password</label>
            <div className="password-input-group">
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
              <button
                type="button"
                className="btn-generate"
                onClick={generateSecurePassword}
                disabled={loading}
                title="Generate secure password"
              >
                🎲
              </button>
            </div>
            
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

          <div className="password-requirements">
            <h4>Password Requirements:</h4>
            <ul>
              <li>At least 8 characters long</li>
              <li>Include uppercase and lowercase letters</li>
              <li>Include at least one number</li>
              <li>Include at least one special character</li>
              <li>Avoid using personal information</li>
              <li>Cannot reuse recent passwords</li>
            </ul>
          </div>

          <div className="form-actions">
            <button
              type="submit"
              className="btn btn-primary"
              disabled={loading || !currentPassword || !newPassword || !confirmPassword || 
                       newPassword !== confirmPassword || !passwordStrength?.is_valid}
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

        <div className="security-tips">
          <h4>Security Tips:</h4>
          <ul>
            <li>Use a unique password for this account</li>
            <li>Consider using a password manager</li>
            <li>Enable two-factor authentication when available</li>
            <li>Never share your password with anyone</li>
          </ul>
        </div>
      </div>
    </div>
  );
};

export default PasswordChange;