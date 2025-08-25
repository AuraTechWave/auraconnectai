import React from 'react';
import { Outlet, Link, useNavigate } from 'react-router-dom';
import useCustomerStore from '../../stores/useCustomerStore';
import useCartStore from '../../stores/useCartStore';
import './Layout.css';

function Layout() {
  const navigate = useNavigate();
  const { isAuthenticated, customer, logout } = useCustomerStore();
  const { getItemCount } = useCartStore();
  const cartCount = getItemCount();

  const handleLogout = () => {
    logout();
    navigate('/');
  };

  return (
    <div className="customer-layout">
      <header className="customer-header">
        <div className="header-content">
          <Link to="/" className="logo">
            AuraConnect
          </Link>
          
          <nav className="main-nav">
            <Link to="/menu">Menu</Link>
            <Link to="/orders">Orders</Link>
            {isAuthenticated && <Link to="/profile">Profile</Link>}
          </nav>

          <div className="header-actions">
            <Link to="/cart" className="cart-link">
              <span className="cart-icon">🛒</span>
              {cartCount > 0 && <span className="cart-badge">{cartCount}</span>}
            </Link>
            
            {isAuthenticated ? (
              <div className="user-menu">
                <span className="user-name">Hi, {customer?.name || 'Guest'}</span>
                <button onClick={handleLogout} className="logout-btn">
                  Logout
                </button>
              </div>
            ) : (
              <Link to="/login" className="login-btn">
                Login
              </Link>
            )}
          </div>
        </div>
      </header>

      <main className="customer-main">
        <Outlet />
      </main>

      <footer className="customer-footer">
        <div className="footer-content">
          <p>&copy; 2025 AuraConnect. All rights reserved.</p>
          <div className="footer-links">
            <a href="/privacy">Privacy Policy</a>
            <a href="/terms">Terms of Service</a>
            <a href="/contact">Contact Us</a>
          </div>
        </div>
      </footer>
    </div>
  );
}

export default Layout;