import axios, { AxiosInstance, AxiosError } from 'axios';
import Config from 'react-native-config';
import * as Keychain from 'react-native-keychain';
import NetInfo from '@react-native-community/netinfo';
import { MMKV } from 'react-native-mmkv';

import { showToast } from '@utils/toast';

const storage = new MMKV();

class ApiClient {
  private client: AxiosInstance;
  private isRefreshing = false;
  private refreshSubscribers: Array<(token: string) => void> = [];

  constructor() {
    this.client = axios.create({
      baseURL: Config.API_URL || 'https://api.auraconnect.ai/api',
      timeout: 30000,
      headers: {
        'Content-Type': 'application/json',
      },
    });

    this.setupInterceptors();
  }

  private setupInterceptors() {
    // Request interceptor
    this.client.interceptors.request.use(
      async config => {
        // Check network connectivity
        const netInfo = await NetInfo.fetch();
        if (!netInfo.isConnected) {
          // Queue request for offline sync
          this.queueOfflineRequest(config);
          throw new Error('No internet connection');
        }

        // Add auth token
        const token = await this.getAuthToken();
        if (token) {
          config.headers.Authorization = `Bearer ${token}`;
        }

        return config;
      },
      error => {
        return Promise.reject(error);
      },
    );

    // Response interceptor
    this.client.interceptors.response.use(
      response => response,
      async error => {
        const originalRequest = error.config;

        if (error.response?.status === 401 && !originalRequest._retry) {
          if (this.isRefreshing) {
            return new Promise(resolve => {
              this.refreshSubscribers.push((token: string) => {
                originalRequest.headers.Authorization = `Bearer ${token}`;
                resolve(this.client(originalRequest));
              });
            });
          }

          originalRequest._retry = true;
          this.isRefreshing = true;

          try {
            const newToken = await this.refreshAuthToken();
            this.onRefreshed(newToken);
            originalRequest.headers.Authorization = `Bearer ${newToken}`;
            return this.client(originalRequest);
          } catch (refreshError) {
            // Refresh failed, redirect to login
            this.onRefreshFailed();
            throw refreshError;
          } finally {
            this.isRefreshing = false;
            this.refreshSubscribers = [];
          }
        }

        // Handle other errors
        this.handleError(error);
        return Promise.reject(error);
      },
    );
  }

  private async getAuthToken(): Promise<string | null> {
    try {
      const credentials = await Keychain.getInternetCredentials(
        'auraconnect.api',
      );
      return credentials ? credentials.password : null;
    } catch {
      return null;
    }
  }

  private async refreshAuthToken(): Promise<string> {
    const refreshToken = await this.getRefreshToken();
    if (!refreshToken) {
      throw new Error('No refresh token available');
    }

    const response = await this.client.post('/auth/refresh', {
      refresh_token: refreshToken,
    });

    const { access_token, refresh_token: newRefreshToken } = response.data;

    // Store new tokens
    await Keychain.setInternetCredentials(
      'auraconnect.api',
      'access_token',
      access_token,
    );

    if (newRefreshToken) {
      await Keychain.setInternetCredentials(
        'auraconnect.api',
        'refresh_token',
        newRefreshToken,
      );
    }

    return access_token;
  }

  private async getRefreshToken(): Promise<string | null> {
    try {
      const credentials = await Keychain.getInternetCredentials(
        'auraconnect.api',
      );
      return credentials ? credentials.username : null;
    } catch {
      return null;
    }
  }

  private onRefreshed(token: string) {
    this.refreshSubscribers.forEach(callback => callback(token));
  }

  private onRefreshFailed() {
    // Clear auth data and redirect to login
    Keychain.resetInternetCredentials('auraconnect.api');
    storage.delete('user');
    // Navigation will be handled by AuthContext
  }

  private handleError(error: AxiosError) {
    if (!error.response) {
      if (error.message === 'No internet connection') {
        showToast('error', 'Offline', 'No internet connection');
      } else {
        showToast('error', 'Network Error', 'Please check your connection');
      }
      return;
    }

    const { status, data } = error.response;

    switch (status) {
      case 400:
        showToast('error', 'Bad Request', data.detail || 'Invalid request');
        break;
      case 403:
        showToast('error', 'Forbidden', 'You do not have permission');
        break;
      case 404:
        showToast('error', 'Not Found', 'Resource not found');
        break;
      case 500:
        showToast('error', 'Server Error', 'Something went wrong');
        break;
    }
  }

  private queueOfflineRequest(config: any) {
    // Store request for later sync
    const offlineQueue = storage.getString('offlineQueue');
    const queue = offlineQueue ? JSON.parse(offlineQueue) : [];
    
    queue.push({
      id: Date.now().toString(),
      timestamp: new Date().toISOString(),
      config: {
        method: config.method,
        url: config.url,
        data: config.data,
        params: config.params,
      },
    });

    storage.set('offlineQueue', JSON.stringify(queue));
  }

  // Public methods
  get = <T = any>(url: string, config?: any) =>
    this.client.get<T>(url, config);

  post = <T = any>(url: string, data?: any, config?: any) =>
    this.client.post<T>(url, data, config);

  put = <T = any>(url: string, data?: any, config?: any) =>
    this.client.put<T>(url, data, config);

  patch = <T = any>(url: string, data?: any, config?: any) =>
    this.client.patch<T>(url, data, config);

  delete = <T = any>(url: string, config?: any) =>
    this.client.delete<T>(url, config);
}

export const apiClient = new ApiClient();