import React, { useState } from 'react';
import { AuthService } from '../utils/authInterceptor';

const Login = ({ onLoginSuccess }) => {
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  const handleSubmit = async (e) => {
    e.preventDefault();
    setLoading(true);
    setError('');

    const result = await AuthService.login(username, password);
    
    if (result.success) {
      onLoginSuccess(result.user);
    } else {
      setError(result.error || 'Login failed');
    }
    
    setLoading(false);
  };

  return (
    <div style={{ 
      display: 'flex', 
      justifyContent: 'center', 
      alignItems: 'center', 
      minHeight: '100vh',
      backgroundColor: '#f5f5f5'
    }}>
      <div style={{
        backgroundColor: 'white',
        padding: '30px',
        borderRadius: '8px',
        boxShadow: '0 2px 10px rgba(0,0,0,0.1)',
        width: '100%',
        maxWidth: '400px'
      }}>
        <h2 style={{ textAlign: 'center', marginBottom: '30px' }}>
          AuraConnect Login
        </h2>
        
        <form onSubmit={handleSubmit}>
          {error && (
            <div style={{
              backgroundColor: '#fee',
              color: '#c00',
              padding: '10px',
              borderRadius: '4px',
              marginBottom: '20px'
            }}>
              {error}
            </div>
          )}
          
          <div style={{ marginBottom: '20px' }}>
            <label style={{ display: 'block', marginBottom: '5px' }}>
              Username
            </label>
            <input
              type="text"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              required
              style={{
                width: '100%',
                padding: '10px',
                borderRadius: '4px',
                border: '1px solid #ddd',
                fontSize: '16px'
              }}
            />
          </div>
          
          <div style={{ marginBottom: '20px' }}>
            <label style={{ display: 'block', marginBottom: '5px' }}>
              Password
            </label>
            <input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
              style={{
                width: '100%',
                padding: '10px',
                borderRadius: '4px',
                border: '1px solid #ddd',
                fontSize: '16px'
              }}
            />
          </div>
          
          <button
            type="submit"
            disabled={loading}
            style={{
              width: '100%',
              padding: '12px',
              backgroundColor: '#007bff',
              color: 'white',
              border: 'none',
              borderRadius: '4px',
              fontSize: '16px',
              cursor: loading ? 'not-allowed' : 'pointer',
              opacity: loading ? 0.7 : 1
            }}
          >
            {loading ? 'Logging in...' : 'Login'}
          </button>
        </form>
        
        <div style={{ marginTop: '20px', fontSize: '14px', color: '#666' }}>
          <p><strong>Test Credentials:</strong></p>
          <ul style={{ marginTop: '10px', paddingLeft: '20px' }}>
            <li>Admin: admin / secret</li>
            <li>Manager: manager / secret</li>
            <li>Payroll Clerk: payroll_clerk / secret</li>
          </ul>
        </div>
      </div>
    </div>
  );
};

export default Login;