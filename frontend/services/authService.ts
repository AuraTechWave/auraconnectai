/**
 * Authentication Service
 * 
 * Handles all authentication-related API calls
 */

import axios, { AxiosInstance } from 'axios';

const API_BASE_URL = process.env.REACT_APP_API_URL || 'http://localhost:8000';

class AuthService {
  private api: AxiosInstance;

  constructor() {
    this.api = axios.create({
      baseURL: `${API_BASE_URL}/api/v1`,
      headers: {
        'Content-Type': 'application/json',
      },
      withCredentials: true, // Important for httpOnly cookies
    });
  }

  /**
   * Login with email and password
   */
  async login(email: string, password: string) {
    const response = await this.api.post('/auth/login', {
      username: email, // Backend expects 'username' field
      password,
    });
    return response.data;
  }

  /**
   * Register a new user
   */
  async register(email: string, password: string, name: string) {
    const response = await this.api.post('/auth/register', {
      email,
      password,
      name,
    });
    return response.data;
  }

  /**
   * Logout the current user
   */
  async logout() {
    try {
      await this.api.post('/auth/logout');
    } catch (error) {
      // Logout should succeed even if backend call fails
      console.error('Logout API call failed:', error);
    }
  }

  /**
   * Get current user information
   */
  async getCurrentUser() {
    const response = await this.api.get('/auth/me');
    return response.data;
  }

  /**
   * Request password reset email
   */
  async requestPasswordReset(email: string) {
    const response = await this.api.post('/auth/password/reset-request', {
      email,
    });
    return response.data;
  }

  /**
   * Reset password with token
   */
  async resetPassword(token: string, newPassword: string) {
    const response = await this.api.post('/auth/password/reset', {
      token,
      new_password: newPassword,
    });
    return response.data;
  }

  /**
   * Refresh access token
   */
  async refreshToken(refreshToken: string) {
    const response = await this.api.post('/auth/refresh', {
      refresh_token: refreshToken,
    });
    return response.data;
  }

  /**
   * Change password for authenticated user
   */
  async changePassword(currentPassword: string, newPassword: string) {
    const response = await this.api.post('/auth/password/change', {
      current_password: currentPassword,
      new_password: newPassword,
    });
    return response.data;
  }

  /**
   * Verify email with token
   */
  async verifyEmail(token: string) {
    const response = await this.api.post('/auth/verify-email', {
      token,
    });
    return response.data;
  }
}

export const authService = new AuthService();