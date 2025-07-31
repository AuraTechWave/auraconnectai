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
import { AUTH_CONFIG, STORAGE_KEYS } from '@constants/config';
import { logger } from '@utils/logger';

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
        logger.debug('Validating stored token');
        const userData = await authService.validateToken(token);
        setUser(userData);
        logger.info('User authenticated', { userId: userData.id, username: userData.username });
      }
    } catch (error) {
      logger.warn('Token validation failed', error);
      await clearAuthData();
    } finally {
      setIsLoading(false);
    }
  };

  const login = async (username: string, password: string) => {
    logger.info('User login attempt', { username });
    const response = await authService.login(username, password);
    
    // Store token securely
    await Keychain.setInternetCredentials(
      AUTH_CONFIG.TOKEN_STORAGE_SERVICE,
      AUTH_CONFIG.TOKEN_KEY,
      response.access_token,
    );
    
    // Store refresh token
    if (response.refresh_token) {
      await Keychain.setInternetCredentials(
        AUTH_CONFIG.TOKEN_STORAGE_SERVICE,
        AUTH_CONFIG.REFRESH_TOKEN_KEY,
        response.refresh_token,
      );
    }
    
    // Store user data
    storage.set(STORAGE_KEYS.USER, JSON.stringify(response.user));
    setUser(response.user);
    logger.info('User login successful', { userId: response.user.id, username: response.user.username });
  };

  const logout = async () => {
    logger.info('User logout', { userId: user?.id });
    await clearAuthData();
    setUser(null);
  };

  const refreshToken = async () => {
    try {
      const credentials = await Keychain.getInternetCredentials(
        AUTH_CONFIG.TOKEN_STORAGE_SERVICE,
      );
      if (credentials && credentials.password) {
        logger.debug('Refreshing auth token');
        const response = await authService.refreshToken(credentials.password);
        
        // Update tokens
        await Keychain.setInternetCredentials(
          AUTH_CONFIG.TOKEN_STORAGE_SERVICE,
          AUTH_CONFIG.TOKEN_KEY,
          response.access_token,
        );
        
        if (response.refresh_token) {
          await Keychain.setInternetCredentials(
            AUTH_CONFIG.TOKEN_STORAGE_SERVICE,
            AUTH_CONFIG.REFRESH_TOKEN_KEY,
            response.refresh_token,
          );
        }
        logger.debug('Token refresh successful');
      }
    } catch (error) {
      logger.error('Token refresh failed', error);
      // If refresh fails, logout
      await logout();
      throw error;
    }
  };

  const getStoredToken = async (): Promise<string | null> => {
    try {
      const credentials = await Keychain.getInternetCredentials(
        AUTH_CONFIG.TOKEN_STORAGE_SERVICE,
      );
      return credentials ? credentials.password : null;
    } catch (error) {
      logger.error('Failed to retrieve stored token', error);
      return null;
    }
  };

  const clearAuthData = async () => {
    await Keychain.resetInternetCredentials(AUTH_CONFIG.TOKEN_STORAGE_SERVICE);
    storage.delete(STORAGE_KEYS.USER);
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