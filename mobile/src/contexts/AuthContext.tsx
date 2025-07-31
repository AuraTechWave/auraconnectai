import React, {
  createContext,
  useContext,
  useState,
  useEffect,
  ReactNode,
} from 'react';
import { MMKV } from 'react-native-mmkv';
import * as Keychain from 'react-native-keychain';

import { authService } from '@services/auth.service';
import { User } from '@types/user';

interface AuthContextType {
  user: User | null;
  isAuthenticated: boolean;
  isLoading: boolean;
  login: (username: string, password: string) => Promise<void>;
  logout: () => Promise<void>;
  refreshToken: () => Promise<void>;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

const storage = new MMKV();

export const AuthProvider: React.FC<{ children: ReactNode }> = ({
  children,
}) => {
  const [user, setUser] = useState<User | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    checkAuthState();
  }, []);

  const checkAuthState = async () => {
    try {
      const token = await getStoredToken();
      if (token) {
        const userData = await authService.validateToken(token);
        setUser(userData);
      }
    } catch (error) {
      // Token invalid or expired
      await clearAuthData();
    } finally {
      setIsLoading(false);
    }
  };

  const login = async (username: string, password: string) => {
    const response = await authService.login(username, password);
    
    // Store token securely
    await Keychain.setInternetCredentials(
      'auraconnect.api',
      'access_token',
      response.access_token,
    );
    
    // Store refresh token
    if (response.refresh_token) {
      await Keychain.setInternetCredentials(
        'auraconnect.api',
        'refresh_token',
        response.refresh_token,
      );
    }
    
    // Store user data
    storage.set('user', JSON.stringify(response.user));
    setUser(response.user);
  };

  const logout = async () => {
    await clearAuthData();
    setUser(null);
  };

  const refreshToken = async () => {
    try {
      const credentials = await Keychain.getInternetCredentials(
        'auraconnect.api',
      );
      if (credentials && credentials.password) {
        const response = await authService.refreshToken(credentials.password);
        
        // Update tokens
        await Keychain.setInternetCredentials(
          'auraconnect.api',
          'access_token',
          response.access_token,
        );
        
        if (response.refresh_token) {
          await Keychain.setInternetCredentials(
            'auraconnect.api',
            'refresh_token',
            response.refresh_token,
          );
        }
      }
    } catch (error) {
      // If refresh fails, logout
      await logout();
      throw error;
    }
  };

  const getStoredToken = async (): Promise<string | null> => {
    try {
      const credentials = await Keychain.getInternetCredentials(
        'auraconnect.api',
      );
      return credentials ? credentials.password : null;
    } catch {
      return null;
    }
  };

  const clearAuthData = async () => {
    await Keychain.resetInternetCredentials('auraconnect.api');
    storage.delete('user');
  };

  const value: AuthContextType = {
    user,
    isAuthenticated: !!user,
    isLoading,
    login,
    logout,
    refreshToken,
  };

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
};

export const useAuth = () => {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used within AuthProvider');
  }
  return context;
};