/**
 * Token Manager Service
 * 
 * Manages JWT tokens with secure storage and automatic refresh
 */

interface TokenData {
  access_token: string;
  refresh_token: string;
  expires_in?: number;
  token_type?: string;
}

class TokenManager {
  private readonly ACCESS_TOKEN_KEY = 'aura_access_token';
  private readonly REFRESH_TOKEN_KEY = 'aura_refresh_token';
  private readonly TOKEN_EXPIRY_KEY = 'aura_token_expiry';

  /**
   * Store tokens securely
   * Note: In production, consider using httpOnly cookies for better security
   */
  setTokens(accessToken: string, refreshToken?: string, expiresIn?: number) {
    // Store access token
    localStorage.setItem(this.ACCESS_TOKEN_KEY, accessToken);
    
    // Store refresh token if provided
    if (refreshToken) {
      localStorage.setItem(this.REFRESH_TOKEN_KEY, refreshToken);
    }
    
    // Calculate and store expiry time
    if (expiresIn) {
      const expiryTime = Date.now() + (expiresIn * 1000);
      localStorage.setItem(this.TOKEN_EXPIRY_KEY, expiryTime.toString());
    } else {
      // Default to 30 minutes if not specified
      const expiryTime = Date.now() + (30 * 60 * 1000);
      localStorage.setItem(this.TOKEN_EXPIRY_KEY, expiryTime.toString());
    }
  }

  /**
   * Get access token
   */
  getAccessToken(): string | null {
    const token = localStorage.getItem(this.ACCESS_TOKEN_KEY);
    
    // Check if token is expired
    if (token && this.isTokenExpired()) {
      return null;
    }
    
    return token;
  }

  /**
   * Get refresh token
   */
  getRefreshToken(): string | null {
    return localStorage.getItem(this.REFRESH_TOKEN_KEY);
  }

  /**
   * Get token expiry time in milliseconds
   */
  getTokenExpiry(): number {
    const expiry = localStorage.getItem(this.TOKEN_EXPIRY_KEY);
    if (!expiry) return 0;
    
    const expiryTime = parseInt(expiry, 10);
    const now = Date.now();
    
    return Math.max(0, expiryTime - now);
  }

  /**
   * Check if access token is expired
   */
  isTokenExpired(): boolean {
    const expiry = localStorage.getItem(this.TOKEN_EXPIRY_KEY);
    if (!expiry) return true;
    
    const expiryTime = parseInt(expiry, 10);
    return Date.now() >= expiryTime;
  }

  /**
   * Clear all tokens
   */
  clearTokens() {
    localStorage.removeItem(this.ACCESS_TOKEN_KEY);
    localStorage.removeItem(this.REFRESH_TOKEN_KEY);
    localStorage.removeItem(this.TOKEN_EXPIRY_KEY);
    
    // Also clear session storage if used
    sessionStorage.removeItem(this.ACCESS_TOKEN_KEY);
    sessionStorage.removeItem(this.REFRESH_TOKEN_KEY);
    sessionStorage.removeItem(this.TOKEN_EXPIRY_KEY);
  }

  /**
   * Parse JWT token to get payload
   */
  parseToken(token: string): any {
    try {
      const base64Url = token.split('.')[1];
      const base64 = base64Url.replace(/-/g, '+').replace(/_/g, '/');
      const jsonPayload = decodeURIComponent(
        atob(base64)
          .split('')
          .map((c) => '%' + ('00' + c.charCodeAt(0).toString(16)).slice(-2))
          .join('')
      );
      return JSON.parse(jsonPayload);
    } catch (error) {
      console.error('Failed to parse token:', error);
      return null;
    }
  }

  /**
   * Get user info from token
   */
  getUserFromToken(): any {
    const token = this.getAccessToken();
    if (!token) return null;
    
    const payload = this.parseToken(token);
    if (!payload) return null;
    
    return {
      id: payload.sub,
      email: payload.email,
      role: payload.role,
      restaurant_id: payload.restaurant_id,
      location_id: payload.location_id,
      permissions: payload.permissions,
    };
  }

  /**
   * Check if user has a specific permission
   */
  hasPermission(permission: string): boolean {
    const user = this.getUserFromToken();
    if (!user) return false;
    
    // Admin has all permissions
    if (user.role === 'admin') return true;
    
    // Check specific permissions
    return user.permissions?.includes(permission) || false;
  }

  /**
   * Check if user has any of the specified roles
   */
  hasRole(roles: string | string[]): boolean {
    const user = this.getUserFromToken();
    if (!user) return false;
    
    const roleArray = Array.isArray(roles) ? roles : [roles];
    return roleArray.includes(user.role);
  }
}

export const tokenManager = new TokenManager();