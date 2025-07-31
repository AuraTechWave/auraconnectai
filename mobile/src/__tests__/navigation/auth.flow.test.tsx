import React from 'react';
import { render, waitFor, act } from '@testing-library/react-native';
import { NavigationContainer } from '@react-navigation/native';
import * as Keychain from 'react-native-keychain';
import { MMKV } from 'react-native-mmkv';

import { AppNavigator } from '@navigation/AppNavigator';
import { AuthProvider } from '@contexts/AuthContext';
import { authService } from '@services/auth.service';
import { AUTH_CONFIG, STORAGE_KEYS } from '@constants/config';

jest.mock('react-native-keychain');
jest.mock('react-native-mmkv');
jest.mock('@services/auth.service');
jest.mock('react-native-screens', () => ({
  enableScreens: jest.fn(),
}));

// Mock screens
jest.mock('@screens/LoadingScreen', () => ({
  LoadingScreen: () => 'LoadingScreen',
}));
jest.mock('@navigation/AuthNavigator', () => ({
  AuthNavigator: () => 'AuthNavigator',
}));
jest.mock('@navigation/MainNavigator', () => ({
  MainNavigator: () => 'MainNavigator',
}));

describe('Authentication Flow', () => {
  let mockStorage: any;

  beforeEach(() => {
    jest.clearAllMocks();
    
    // Mock MMKV
    mockStorage = {
      getString: jest.fn(),
      set: jest.fn(),
      delete: jest.fn(),
    };
    (MMKV as jest.MockedClass<typeof MMKV>).mockImplementation(() => mockStorage);
  });

  const renderApp = () => {
    return render(
      <NavigationContainer>
        <AuthProvider>
          <AppNavigator />
        </AuthProvider>
      </NavigationContainer>,
    );
  };

  describe('Initial Load', () => {
    it('should show loading screen while checking auth state', async () => {
      // Mock slow token validation
      (Keychain.getInternetCredentials as jest.Mock).mockImplementation(
        () => new Promise(resolve => setTimeout(() => resolve(null), 100)),
      );

      const { getByText } = renderApp();

      expect(getByText('LoadingScreen')).toBeTruthy();
    });

    it('should navigate to auth screen when no token exists', async () => {
      (Keychain.getInternetCredentials as jest.Mock).mockResolvedValue(null);

      const { getByText } = renderApp();

      await waitFor(() => {
        expect(getByText('AuthNavigator')).toBeTruthy();
      });
    });

    it('should navigate to main screen when valid token exists', async () => {
      const mockUser = {
        id: 1,
        username: 'testuser',
        email: 'test@example.com',
        full_name: 'Test User',
      };

      (Keychain.getInternetCredentials as jest.Mock).mockResolvedValue({
        username: 'refresh-token',
        password: 'access-token',
      });
      (authService.validateToken as jest.Mock).mockResolvedValue(mockUser);
      mockStorage.getString.mockReturnValue(JSON.stringify(mockUser));

      const { getByText } = renderApp();

      await waitFor(() => {
        expect(getByText('MainNavigator')).toBeTruthy();
      });
    });

    it('should navigate to auth screen when token validation fails', async () => {
      (Keychain.getInternetCredentials as jest.Mock).mockResolvedValue({
        username: 'refresh-token',
        password: 'invalid-token',
      });
      (authService.validateToken as jest.Mock).mockRejectedValue(
        new Error('Invalid token'),
      );

      const { getByText } = renderApp();

      await waitFor(() => {
        expect(getByText('AuthNavigator')).toBeTruthy();
      });

      // Should clear auth data
      expect(Keychain.resetInternetCredentials).toHaveBeenCalledWith(
        AUTH_CONFIG.TOKEN_STORAGE_SERVICE,
      );
      expect(mockStorage.delete).toHaveBeenCalledWith(STORAGE_KEYS.USER);
    });
  });

  describe('Login Flow', () => {
    it('should transition from auth to main after successful login', async () => {
      const mockUser = {
        id: 1,
        username: 'testuser',
        email: 'test@example.com',
        full_name: 'Test User',
      };

      const mockLoginResponse = {
        access_token: 'new-access-token',
        refresh_token: 'new-refresh-token',
        user: mockUser,
      };

      (Keychain.getInternetCredentials as jest.Mock).mockResolvedValue(null);
      (authService.login as jest.Mock).mockResolvedValue(mockLoginResponse);

      const { getByText, rerender } = renderApp();

      // Initially on auth screen
      await waitFor(() => {
        expect(getByText('AuthNavigator')).toBeTruthy();
      });

      // Simulate login
      await act(async () => {
        const { useAuth } = require('@contexts/AuthContext');
        const authContext = useAuth();
        await authContext.login('testuser', 'password');
      });

      // Force re-render to see navigation change
      rerender(
        <NavigationContainer>
          <AuthProvider>
            <AppNavigator />
          </AuthProvider>
        </NavigationContainer>,
      );

      // Should now be on main screen
      await waitFor(() => {
        expect(getByText('MainNavigator')).toBeTruthy();
      });

      // Should store tokens
      expect(Keychain.setInternetCredentials).toHaveBeenCalledWith(
        AUTH_CONFIG.TOKEN_STORAGE_SERVICE,
        AUTH_CONFIG.TOKEN_KEY,
        'new-access-token',
      );
      expect(Keychain.setInternetCredentials).toHaveBeenCalledWith(
        AUTH_CONFIG.TOKEN_STORAGE_SERVICE,
        AUTH_CONFIG.REFRESH_TOKEN_KEY,
        'new-refresh-token',
      );

      // Should store user
      expect(mockStorage.set).toHaveBeenCalledWith(
        STORAGE_KEYS.USER,
        JSON.stringify(mockUser),
      );
    });
  });

  describe('Logout Flow', () => {
    it('should transition from main to auth after logout', async () => {
      const mockUser = {
        id: 1,
        username: 'testuser',
        email: 'test@example.com',
        full_name: 'Test User',
      };

      // Start authenticated
      (Keychain.getInternetCredentials as jest.Mock).mockResolvedValue({
        username: 'refresh-token',
        password: 'access-token',
      });
      (authService.validateToken as jest.Mock).mockResolvedValue(mockUser);
      mockStorage.getString.mockReturnValue(JSON.stringify(mockUser));

      const { getByText, rerender } = renderApp();

      // Initially on main screen
      await waitFor(() => {
        expect(getByText('MainNavigator')).toBeTruthy();
      });

      // Simulate logout
      await act(async () => {
        const { useAuth } = require('@contexts/AuthContext');
        const authContext = useAuth();
        await authContext.logout();
      });

      // Mock no credentials after logout
      (Keychain.getInternetCredentials as jest.Mock).mockResolvedValue(null);

      // Force re-render
      rerender(
        <NavigationContainer>
          <AuthProvider>
            <AppNavigator />
          </AuthProvider>
        </NavigationContainer>,
      );

      // Should now be on auth screen
      await waitFor(() => {
        expect(getByText('AuthNavigator')).toBeTruthy();
      });

      // Should clear auth data
      expect(Keychain.resetInternetCredentials).toHaveBeenCalledWith(
        AUTH_CONFIG.TOKEN_STORAGE_SERVICE,
      );
      expect(mockStorage.delete).toHaveBeenCalledWith(STORAGE_KEYS.USER);
    });
  });

  describe('Token Refresh Flow', () => {
    it('should maintain authenticated state after token refresh', async () => {
      const mockUser = {
        id: 1,
        username: 'testuser',
        email: 'test@example.com',
        full_name: 'Test User',
      };

      (Keychain.getInternetCredentials as jest.Mock).mockResolvedValue({
        username: 'refresh-token',
        password: 'access-token',
      });
      (authService.validateToken as jest.Mock).mockResolvedValue(mockUser);
      (authService.refreshToken as jest.Mock).mockResolvedValue({
        access_token: 'new-access-token',
        refresh_token: 'new-refresh-token',
      });
      mockStorage.getString.mockReturnValue(JSON.stringify(mockUser));

      const { getByText } = renderApp();

      // Should stay on main screen
      await waitFor(() => {
        expect(getByText('MainNavigator')).toBeTruthy();
      });

      // Simulate token refresh
      await act(async () => {
        const { useAuth } = require('@contexts/AuthContext');
        const authContext = useAuth();
        await authContext.refreshToken();
      });

      // Should still be on main screen
      expect(getByText('MainNavigator')).toBeTruthy();

      // Should update tokens
      expect(Keychain.setInternetCredentials).toHaveBeenCalledWith(
        AUTH_CONFIG.TOKEN_STORAGE_SERVICE,
        AUTH_CONFIG.TOKEN_KEY,
        'new-access-token',
      );
    });

    it('should navigate to auth screen if refresh fails', async () => {
      const mockUser = {
        id: 1,
        username: 'testuser',
        email: 'test@example.com',
        full_name: 'Test User',
      };

      (Keychain.getInternetCredentials as jest.Mock).mockResolvedValue({
        username: 'refresh-token',
        password: 'access-token',
      });
      (authService.validateToken as jest.Mock).mockResolvedValue(mockUser);
      (authService.refreshToken as jest.Mock).mockRejectedValue(
        new Error('Refresh failed'),
      );
      mockStorage.getString.mockReturnValue(JSON.stringify(mockUser));

      const { getByText, rerender } = renderApp();

      // Initially on main screen
      await waitFor(() => {
        expect(getByText('MainNavigator')).toBeTruthy();
      });

      // Simulate failed token refresh
      await act(async () => {
        try {
          const { useAuth } = require('@contexts/AuthContext');
          const authContext = useAuth();
          await authContext.refreshToken();
        } catch (error) {
          // Expected to fail
        }
      });

      // Mock no credentials after failed refresh
      (Keychain.getInternetCredentials as jest.Mock).mockResolvedValue(null);

      // Force re-render
      rerender(
        <NavigationContainer>
          <AuthProvider>
            <AppNavigator />
          </AuthProvider>
        </NavigationContainer>,
      );

      // Should navigate to auth screen
      await waitFor(() => {
        expect(getByText('AuthNavigator')).toBeTruthy();
      });
    });
  });
});