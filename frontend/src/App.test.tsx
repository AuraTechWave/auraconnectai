import React from 'react';
import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import App from './App';

// Mock child components
jest.mock('./pages/admin/OrderManagementPage', () => {
  return function OrderManagementPage() {
    return <div>Order Management Page</div>;
  };
});

jest.mock('./components/AdminSettings', () => {
  return function AdminSettings() {
    return <div>Admin Settings</div>;
  };
});

jest.mock('./components/staff/scheduling', () => ({
  StaffSchedulingInterface: function StaffSchedulingInterface() {
    return <div>Staff Scheduling Interface</div>;
  }
}));

jest.mock('./components/auth/AuthWrapper', () => ({
  AuthWrapper: function AuthWrapper({ children }: { children: React.ReactNode }) {
    return <>{children}</>;
  }
}));

jest.mock('./pages/customer/LoginPage', () => {
  return function LoginPage() {
    return <div>Login Page</div>;
  };
});

describe('App Component', () => {
  test('renders without crashing', () => {
    render(<App />);
  });

  test('renders login page on /login route', () => {
    window.history.pushState({}, '', '/login');
    render(<App />);
    expect(screen.getByText('Login Page')).toBeInTheDocument();
  });

  test('renders order management page on /admin/orders route', () => {
    window.history.pushState({}, '', '/admin/orders');
    render(<App />);
    expect(screen.getByText('Order Management Page')).toBeInTheDocument();
  });

  test('renders admin settings on /admin/settings route', () => {
    window.history.pushState({}, '', '/admin/settings');
    render(<App />);
    expect(screen.getByText('Admin Settings')).toBeInTheDocument();
  });

  test('renders staff scheduling on /staff/scheduling route', () => {
    window.history.pushState({}, '', '/staff/scheduling');
    render(<App />);
    expect(screen.getByText('Staff Scheduling Interface')).toBeInTheDocument();
  });

  test('redirects from / to /admin/orders', () => {
    window.history.pushState({}, '', '/');
    render(<App />);
    expect(screen.getByText('Order Management Page')).toBeInTheDocument();
  });

  test('redirects from /admin to /admin/orders', () => {
    window.history.pushState({}, '', '/admin');
    render(<App />);
    expect(screen.getByText('Order Management Page')).toBeInTheDocument();
  });
});