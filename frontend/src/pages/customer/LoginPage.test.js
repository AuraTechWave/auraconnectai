import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { BrowserRouter } from 'react-router-dom';
import LoginPage from './LoginPage';
import useCustomerStore from '../../stores/useCustomerStore';

// Mock the customer store
jest.mock('../../stores/useCustomerStore');
const mockUseCustomerStore = useCustomerStore;

// Mock react-router-dom
const mockNavigate = jest.fn();
jest.mock('react-router-dom', () => ({
  ...jest.requireActual('react-router-dom'),
  useNavigate: () => mockNavigate,
  useLocation: () => ({ state: null })
}));

const renderWithRouter = (component) => {
  return render(
    <BrowserRouter>
      {component}
    </BrowserRouter>
  );
};

describe('LoginPage', () => {
  const mockLogin = jest.fn();

  beforeEach(() => {
    mockUseCustomerStore.mockReturnValue({
      login: mockLogin
    });
    mockLogin.mockClear();
    mockNavigate.mockClear();
  });

  describe('Rendering', () => {
    test('renders login form elements', () => {
      renderWithRouter(<LoginPage />);
      
      expect(screen.getByText('Welcome Back')).toBeInTheDocument();
      expect(screen.getByText('Sign in to your account')).toBeInTheDocument();
      expect(screen.getByLabelText(/email/i)).toBeInTheDocument();
      expect(screen.getByLabelText(/password/i)).toBeInTheDocument();
      expect(screen.getByRole('button', { name: /sign in/i })).toBeInTheDocument();
    });

    test('renders sign up link', () => {
      renderWithRouter(<LoginPage />);
      
      const signUpLink = screen.getByRole('link', { name: /sign up/i });
      expect(signUpLink).toBeInTheDocument();
      expect(signUpLink).toHaveAttribute('href', '/register');
    });

    test('renders with correct form structure', () => {
      renderWithRouter(<LoginPage />);
      
      const form = screen.getByRole('form');
      expect(form).toBeInTheDocument();
      
      const emailInput = screen.getByPlaceholderText(/enter your email/i);
      const passwordInput = screen.getByPlaceholderText(/enter your password/i);
      
      expect(emailInput).toBeRequired();
      expect(passwordInput).toBeRequired();
      expect(emailInput).toHaveAttribute('type', 'email');
      expect(passwordInput).toHaveAttribute('type', 'password');
    });
  });

  describe('User Interactions', () => {
    test('updates email input value', async () => {
      const user = userEvent.setup();
      renderWithRouter(<LoginPage />);
      
      const emailInput = screen.getByLabelText(/email/i);
      await user.type(emailInput, 'test@example.com');
      
      expect(emailInput).toHaveValue('test@example.com');
    });

    test('updates password input value', async () => {
      const user = userEvent.setup();
      renderWithRouter(<LoginPage />);
      
      const passwordInput = screen.getByLabelText(/password/i);
      await user.type(passwordInput, 'password123');
      
      expect(passwordInput).toHaveValue('password123');
    });

    test('handles form submission with valid data', async () => {
      const user = userEvent.setup();
      mockLogin.mockResolvedValueOnce({ success: true });
      
      renderWithRouter(<LoginPage />);
      
      const emailInput = screen.getByLabelText(/email/i);
      const passwordInput = screen.getByLabelText(/password/i);
      const submitButton = screen.getByRole('button', { name: /sign in/i });
      
      await user.type(emailInput, 'test@example.com');
      await user.type(passwordInput, 'password123');
      await user.click(submitButton);
      
      expect(mockLogin).toHaveBeenCalledWith({
        email: 'test@example.com',
        password: 'password123'
      });
    });

    test('prevents form submission when loading', async () => {
      const user = userEvent.setup();
      let resolveLogin;
      mockLogin.mockReturnValue(new Promise(resolve => { resolveLogin = resolve; }));
      
      renderWithRouter(<LoginPage />);
      
      const emailInput = screen.getByLabelText(/email/i);
      const passwordInput = screen.getByLabelText(/password/i);
      const submitButton = screen.getByRole('button', { name: /sign in/i });
      
      await user.type(emailInput, 'test@example.com');
      await user.type(passwordInput, 'password123');
      await user.click(submitButton);
      
      // Button should show loading state
      expect(screen.getByText(/signing in/i)).toBeInTheDocument();
      expect(submitButton).toBeDisabled();
      
      // Resolve the login
      resolveLogin({ success: true });
    });

    test('clears error message when form is resubmitted', async () => {
      const user = userEvent.setup();
      mockLogin
        .mockResolvedValueOnce({ success: false, error: 'Invalid credentials' })
        .mockResolvedValueOnce({ success: true });
      
      renderWithRouter(<LoginPage />);
      
      const emailInput = screen.getByLabelText(/email/i);
      const passwordInput = screen.getByLabelText(/password/i);
      const submitButton = screen.getByRole('button', { name: /sign in/i });
      
      // First submission fails
      await user.type(emailInput, 'wrong@example.com');
      await user.type(passwordInput, 'wrongpassword');
      await user.click(submitButton);
      
      await waitFor(() => {
        expect(screen.getByText(/invalid credentials/i)).toBeInTheDocument();
      });
      
      // Second submission should clear error
      await user.clear(emailInput);
      await user.clear(passwordInput);
      await user.type(emailInput, 'test@example.com');
      await user.type(passwordInput, 'password123');
      await user.click(submitButton);
      
      await waitFor(() => {
        expect(screen.queryByText(/invalid credentials/i)).not.toBeInTheDocument();
      });
    });
  });

  describe('Login Success', () => {
    test('navigates to home page on successful login', async () => {
      const user = userEvent.setup();
      mockLogin.mockResolvedValueOnce({ success: true });
      
      renderWithRouter(<LoginPage />);
      
      const emailInput = screen.getByLabelText(/email/i);
      const passwordInput = screen.getByLabelText(/password/i);
      const submitButton = screen.getByRole('button', { name: /sign in/i });
      
      await user.type(emailInput, 'test@example.com');
      await user.type(passwordInput, 'password123');
      await user.click(submitButton);
      
      await waitFor(() => {
        expect(mockNavigate).toHaveBeenCalledWith('/', { replace: true });
      });
    });

    test('navigates to intended page after login', async () => {
      const user = userEvent.setup();
      mockLogin.mockResolvedValueOnce({ success: true });
      
      // Mock useLocation to return a previous location
      jest.doMock('react-router-dom', () => ({
        ...jest.requireActual('react-router-dom'),
        useNavigate: () => mockNavigate,
        useLocation: () => ({ 
          state: { from: { pathname: '/protected-page' } } 
        })
      }));
      
      // Re-import to get updated mock
      const { default: LoginPageWithLocation } = require('./LoginPage');
      
      renderWithRouter(<LoginPageWithLocation />);
      
      const emailInput = screen.getByLabelText(/email/i);
      const passwordInput = screen.getByLabelText(/password/i);
      const submitButton = screen.getByRole('button', { name: /sign in/i });
      
      await user.type(emailInput, 'test@example.com');
      await user.type(passwordInput, 'password123');
      await user.click(submitButton);
      
      await waitFor(() => {
        expect(mockNavigate).toHaveBeenCalledWith('/protected-page', { replace: true });
      });
    });
  });

  describe('Login Failure', () => {
    test('displays error message on login failure', async () => {
      const user = userEvent.setup();
      mockLogin.mockResolvedValueOnce({ 
        success: false, 
        error: 'Invalid email or password' 
      });
      
      renderWithRouter(<LoginPage />);
      
      const emailInput = screen.getByLabelText(/email/i);
      const passwordInput = screen.getByLabelText(/password/i);
      const submitButton = screen.getByRole('button', { name: /sign in/i });
      
      await user.type(emailInput, 'wrong@example.com');
      await user.type(passwordInput, 'wrongpassword');
      await user.click(submitButton);
      
      await waitFor(() => {
        expect(screen.getByText(/invalid email or password/i)).toBeInTheDocument();
      });
      
      // Should not navigate
      expect(mockNavigate).not.toHaveBeenCalled();
    });

    test('displays generic error message when no specific error provided', async () => {
      const user = userEvent.setup();
      mockLogin.mockResolvedValueOnce({ success: false });
      
      renderWithRouter(<LoginPage />);
      
      const emailInput = screen.getByLabelText(/email/i);
      const passwordInput = screen.getByLabelText(/password/i);
      const submitButton = screen.getByRole('button', { name: /sign in/i });
      
      await user.type(emailInput, 'test@example.com');
      await user.type(passwordInput, 'password123');
      await user.click(submitButton);
      
      await waitFor(() => {
        expect(screen.getByText(/login failed\. please try again/i)).toBeInTheDocument();
      });
    });

    test('re-enables button after failed login', async () => {
      const user = userEvent.setup();
      mockLogin.mockResolvedValueOnce({ 
        success: false, 
        error: 'Network error' 
      });
      
      renderWithRouter(<LoginPage />);
      
      const emailInput = screen.getByLabelText(/email/i);
      const passwordInput = screen.getByLabelText(/password/i);
      const submitButton = screen.getByRole('button', { name: /sign in/i });
      
      await user.type(emailInput, 'test@example.com');
      await user.type(passwordInput, 'password123');
      await user.click(submitButton);
      
      await waitFor(() => {
        expect(screen.getByText(/network error/i)).toBeInTheDocument();
      });
      
      expect(submitButton).not.toBeDisabled();
      expect(submitButton).toHaveTextContent('Sign In');
    });
  });

  describe('Form Validation', () => {
    test('prevents submission with empty fields', async () => {
      const user = userEvent.setup();
      renderWithRouter(<LoginPage />);
      
      const submitButton = screen.getByRole('button', { name: /sign in/i });
      await user.click(submitButton);
      
      // Should not call login with empty fields
      expect(mockLogin).not.toHaveBeenCalled();
    });

    test('email input accepts valid email format', async () => {
      const user = userEvent.setup();
      renderWithRouter(<LoginPage />);
      
      const emailInput = screen.getByLabelText(/email/i);
      await user.type(emailInput, 'valid@email.com');
      
      expect(emailInput).toBeValid();
    });
  });

  describe('Loading States', () => {
    test('shows loading state during login', async () => {
      const user = userEvent.setup();
      let resolveLogin;
      mockLogin.mockReturnValue(new Promise(resolve => { resolveLogin = resolve; }));
      
      renderWithRouter(<LoginPage />);
      
      const emailInput = screen.getByLabelText(/email/i);
      const passwordInput = screen.getByLabelText(/password/i);
      const submitButton = screen.getByRole('button', { name: /sign in/i });
      
      await user.type(emailInput, 'test@example.com');
      await user.type(passwordInput, 'password123');
      await user.click(submitButton);
      
      expect(screen.getByText(/signing in/i)).toBeInTheDocument();
      expect(submitButton).toBeDisabled();
      
      // Resolve login
      resolveLogin({ success: true });
      
      await waitFor(() => {
        expect(screen.queryByText(/signing in/i)).not.toBeInTheDocument();
      });
    });
  });
});