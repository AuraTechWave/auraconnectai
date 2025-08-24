// Secure authentication utilities

interface TokenPayload {
  access_token: string;
  refresh_token?: string;
  expires_in: number;
  token_type: string;
}

class AuthManager {
  private static instance: AuthManager;
  private tokenKey = 'auth_token';
  private refreshKey = 'refresh_token';
  private expiryKey = 'token_expiry';
  
  private constructor() {}
  
  static getInstance(): AuthManager {
    if (!AuthManager.instance) {
      AuthManager.instance = new AuthManager();
    }
    return AuthManager.instance;
  }
  
  // Store tokens securely (in production, consider httpOnly cookies)
  setTokens(payload: TokenPayload): void {
    const expiry = new Date();
    expiry.setSeconds(expiry.getSeconds() + payload.expires_in);
    
    // In production, these should be httpOnly cookies set by the server
    sessionStorage.setItem(this.tokenKey, payload.access_token);
    if (payload.refresh_token) {
      sessionStorage.setItem(this.refreshKey, payload.refresh_token);
    }
    sessionStorage.setItem(this.expiryKey, expiry.toISOString());
  }
  
  getAccessToken(): string | null {
    const token = sessionStorage.getItem(this.tokenKey);
    const expiry = sessionStorage.getItem(this.expiryKey);
    
    if (!token || !expiry) return null;
    
    // Check if token is expired
    if (new Date(expiry) < new Date()) {
      this.clearTokens();
      return null;
    }
    
    return token;
  }
  
  getRefreshToken(): string | null {
    return sessionStorage.getItem(this.refreshKey);
  }
  
  clearTokens(): void {
    sessionStorage.removeItem(this.tokenKey);
    sessionStorage.removeItem(this.refreshKey);
    sessionStorage.removeItem(this.expiryKey);
  }
  
  isAuthenticated(): boolean {
    return !!this.getAccessToken();
  }
  
  // Check if token will expire soon (within 5 minutes)
  shouldRefreshToken(): boolean {
    const expiry = sessionStorage.getItem(this.expiryKey);
    if (!expiry) return false;
    
    const expiryDate = new Date(expiry);
    const now = new Date();
    const fiveMinutes = 5 * 60 * 1000;
    
    return (expiryDate.getTime() - now.getTime()) < fiveMinutes;
  }
}

export const authManager = AuthManager.getInstance();

// Security utilities
export const sanitizeInput = (input: string): string => {
  // Basic XSS prevention
  return input
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#x27;')
    .replace(/\//g, '&#x2F;');
};

// CSRF token management
export const getCSRFToken = (): string | null => {
  // In production, this should come from a meta tag or cookie
  const meta = document.querySelector('meta[name="csrf-token"]');
  return meta ? meta.getAttribute('content') : null;
};