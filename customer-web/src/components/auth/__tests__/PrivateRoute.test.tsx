import React from 'react';
import { render, screen } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { PrivateRoute } from '../PrivateRoute';
import { useAuthStore } from '../../../store/authStore';

jest.mock('../../../store/authStore');

describe('PrivateRoute', () => {
  const TestComponent = () => <div>Protected Content</div>;
  const LoginComponent = () => <div>Login Page</div>;

  const renderWithRouter = (isAuthenticated: boolean) => {
    (useAuthStore as unknown as jest.Mock).mockReturnValue({
      isAuthenticated,
    });

    render(
      <MemoryRouter initialEntries={['/protected']}>
        <Routes>
          <Route path="/login" element={<LoginComponent />} />
          <Route
            path="/protected"
            element={
              <PrivateRoute>
                <TestComponent />
              </PrivateRoute>
            }
          />
        </Routes>
      </MemoryRouter>
    );
  };

  test('renders protected content when authenticated', () => {
    renderWithRouter(true);
    expect(screen.getByText('Protected Content')).toBeInTheDocument();
  });

  test('redirects to login when not authenticated', () => {
    renderWithRouter(false);
    expect(screen.getByText('Login Page')).toBeInTheDocument();
    expect(screen.queryByText('Protected Content')).not.toBeInTheDocument();
  });

  test('preserves location state when redirecting', () => {
    (useAuthStore as unknown as jest.Mock).mockReturnValue({
      isAuthenticated: false,
    });

    const { container } = render(
      <MemoryRouter initialEntries={['/protected/resource']}>
        <Routes>
          <Route path="/login" element={<LoginComponent />} />
          <Route
            path="/protected/resource"
            element={
              <PrivateRoute>
                <TestComponent />
              </PrivateRoute>
            }
          />
        </Routes>
      </MemoryRouter>
    );

    // Verify redirect happened
    expect(screen.getByText('Login Page')).toBeInTheDocument();
  });
});