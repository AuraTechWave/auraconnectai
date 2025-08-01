/**
 * Secure storage service for handling sensitive data like tokens
 * Uses sessionStorage by default for better security
 * Falls back to memory storage if sessionStorage is not available
 */

class SecureStorageService {
  private memoryStorage: Map<string, string> = new Map();
  private readonly TOKEN_KEY = 'customerToken';
  private readonly REFRESH_TOKEN_KEY = 'customerRefreshToken';

  /**
   * Check if sessionStorage is available
   */
  private isSessionStorageAvailable(): boolean {
    try {
      const test = '__storage_test__';
      sessionStorage.setItem(test, test);
      sessionStorage.removeItem(test);
      return true;
    } catch {
      return false;
    }
  }

  /**
   * Get storage method based on availability
   */
  private getStorage() {
    if (this.isSessionStorageAvailable()) {
      return sessionStorage;
    }
    // Fallback to memory storage
    return {
      getItem: (key: string) => this.memoryStorage.get(key) || null,
      setItem: (key: string, value: string) => this.memoryStorage.set(key, value),
      removeItem: (key: string) => this.memoryStorage.delete(key),
      clear: () => this.memoryStorage.clear(),
    };
  }

  /**
   * Set authentication token
   */
  setToken(token: string): void {
    const storage = this.getStorage();
    storage.setItem(this.TOKEN_KEY, token);
  }

  /**
   * Get authentication token
   */
  getToken(): string | null {
    const storage = this.getStorage();
    return storage.getItem(this.TOKEN_KEY);
  }

  /**
   * Remove authentication token
   */
  removeToken(): void {
    const storage = this.getStorage();
    storage.removeItem(this.TOKEN_KEY);
  }

  /**
   * Set refresh token
   */
  setRefreshToken(token: string): void {
    const storage = this.getStorage();
    storage.setItem(this.REFRESH_TOKEN_KEY, token);
  }

  /**
   * Get refresh token
   */
  getRefreshToken(): string | null {
    const storage = this.getStorage();
    return storage.getItem(this.REFRESH_TOKEN_KEY);
  }

  /**
   * Remove refresh token
   */
  removeRefreshToken(): void {
    const storage = this.getStorage();
    storage.removeItem(this.REFRESH_TOKEN_KEY);
  }

  /**
   * Clear all stored tokens
   */
  clearAll(): void {
    const storage = this.getStorage();
    storage.removeItem(this.TOKEN_KEY);
    storage.removeItem(this.REFRESH_TOKEN_KEY);
  }

  /**
   * Check if user is authenticated (has valid token)
   */
  isAuthenticated(): boolean {
    return !!this.getToken();
  }

  /**
   * Decode JWT token to get expiration time
   */
  private decodeToken(token: string): any {
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
    } catch {
      return null;
    }
  }

  /**
   * Check if token is expired
   */
  isTokenExpired(token?: string): boolean {
    const tokenToCheck = token || this.getToken();
    if (!tokenToCheck) return true;

    const decoded = this.decodeToken(tokenToCheck);
    if (!decoded || !decoded.exp) return true;

    // Check if token is expired (with 5 minute buffer)
    const expirationTime = decoded.exp * 1000;
    const currentTime = Date.now();
    const bufferTime = 5 * 60 * 1000; // 5 minutes

    return currentTime >= expirationTime - bufferTime;
  }
}

export default new SecureStorageService();