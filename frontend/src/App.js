import React, { useState, useEffect } from 'react';
import AdminSettings from './components/AdminSettings';
import Login from './components/Login';
import { AuthService, TokenStorage } from './utils/authInterceptor';
import './App.css';

function App() {
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    // Check if user is already logged in
    const checkAuth = async () => {
      if (TokenStorage.hasTokens()) {
        const currentUser = await AuthService.getCurrentUser();
        setUser(currentUser);
      }
      setLoading(false);
    };

    checkAuth();

    // Listen for logout events
    const handleLogout = () => {
      setUser(null);
    };

    window.addEventListener('auth:logout', handleLogout);
    return () => window.removeEventListener('auth:logout', handleLogout);
  }, []);

  const handleLoginSuccess = (userData) => {
    setUser(userData);
  };

  const handleLogout = async () => {
    await AuthService.logout();
    setUser(null);
  };

  if (loading) {
    return (
      <div style={{ 
        display: 'flex', 
        justifyContent: 'center', 
        alignItems: 'center', 
        minHeight: '100vh' 
      }}>
        Loading...
      </div>
    );
  }

  if (!user) {
    return <Login onLoginSuccess={handleLoginSuccess} />;
  }

  return (
    <div className="App">
      <header className="App-header" style={{ 
        backgroundColor: '#282c34', 
        padding: '20px', 
        color: 'white',
        display: 'flex',
        justifyContent: 'space-between',
        alignItems: 'center'
      }}>
        <h1>AuraConnect Admin Panel</h1>
        <div style={{ display: 'flex', alignItems: 'center', gap: '20px' }}>
          <span>Welcome, {user.username}</span>
          <button 
            onClick={handleLogout}
            style={{
              padding: '8px 16px',
              backgroundColor: '#dc3545',
              color: 'white',
              border: 'none',
              borderRadius: '4px',
              cursor: 'pointer'
            }}
          >
            Logout
          </button>
        </div>
      </header>
      <main>
        <AdminSettings />
      </main>
    </div>
  );
}

export default App;
