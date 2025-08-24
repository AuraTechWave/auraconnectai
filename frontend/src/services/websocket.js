import { io } from 'socket.io-client';

// Secure WebSocket URL configuration
const getWebSocketUrl = () => {
  const wsUrl = process.env.REACT_APP_WS_URL;
  
  // In production, require explicit WS URL configuration
  if (process.env.NODE_ENV === 'production' && !wsUrl) {
    throw new Error('REACT_APP_WS_URL is required in production');
  }
  
  // Development fallback
  if (process.env.NODE_ENV === 'development' && !wsUrl) {
    console.warn('REACT_APP_WS_URL not set, using development default');
    return 'ws://localhost:8000';
  }
  
  // Enforce WSS in production or when page is HTTPS
  if (window.location.protocol === 'https:' || process.env.NODE_ENV === 'production') {
    if (wsUrl && !wsUrl.startsWith('wss://')) {
      console.error('WebSocket URL must use WSS when page is HTTPS');
      // Convert ws:// to wss:// if needed
      return wsUrl.replace(/^ws:/, 'wss:');
    }
  }
  
  return wsUrl;
};

const WS_URL = getWebSocketUrl();

class WebSocketService {
  constructor() {
    this.socket = null;
    this.listeners = new Map();
    this.reconnectAttempts = 0;
    this.maxReconnectAttempts = 10;
    this.baseDelay = 1000;
    this.maxDelay = 30000;
    this.connectionState = 'disconnected';
    this.authToken = null;
  }

  connect(token) {
    if (this.socket?.connected) {
      return;
    }

    this.authToken = token;

    this.socket = io(WS_URL, {
      auth: { token },
      transports: ['websocket'],
      reconnection: true,
      reconnectionAttempts: this.maxReconnectAttempts,
      reconnectionDelay: this.baseDelay,
      reconnectionDelayMax: this.maxDelay,
    });

    this.socket.on('connect', () => {
      console.log('WebSocket connected');
      this.reconnectAttempts = 0;
      this.connectionState = 'connected';
      this.emit('connection:established');
    });

    this.socket.on('disconnect', (reason) => {
      console.log('WebSocket disconnected:', reason);
      this.connectionState = 'disconnected';
      this.emit('connection:lost', reason);
      
      // Handle auth-related disconnections
      if (reason === 'io server disconnect') {
        // Server forced disconnect, might be auth issue
        this.handleAuthDisconnect();
      }
    });

    this.socket.on('error', (error) => {
      console.error('WebSocket error:', error);
      this.emit('connection:error', error);
    });

    this.socket.on('reconnect_attempt', (attemptNumber) => {
      this.reconnectAttempts = attemptNumber;
      this.connectionState = 'reconnecting';
      this.emit('connection:reconnecting', attemptNumber);
    });

    this.socket.on('reconnect_failed', () => {
      this.connectionState = 'failed';
      this.emit('connection:failed');
      console.error('WebSocket reconnection failed after', this.maxReconnectAttempts, 'attempts');
    });

    // Handle token refresh
    this.socket.on('token_expired', () => {
      this.handleTokenRefresh();
    });

    // Set up exponential backoff for reconnection
    this.socket.io.on('reconnect_attempt', () => {
      const delay = this.calculateBackoffDelay();
      this.socket.io._reconnectionDelay = delay;
      this.socket.io._reconnectionDelayMax = delay;
    });
  }

  calculateBackoffDelay() {
    // Exponential backoff with jitter
    const exponentialDelay = Math.min(
      this.baseDelay * Math.pow(2, this.reconnectAttempts),
      this.maxDelay
    );
    const jitter = Math.random() * 0.3 * exponentialDelay; // 30% jitter
    return Math.round(exponentialDelay + jitter);
  }

  async handleTokenRefresh() {
    try {
      // Get fresh token from auth system
      const newToken = await this.refreshAuthToken();
      if (newToken) {
        this.authToken = newToken;
        // Reconnect with new token
        this.disconnect();
        this.connect(newToken);
      } else {
        this.handleAuthDisconnect();
      }
    } catch (error) {
      console.error('Token refresh failed:', error);
      this.handleAuthDisconnect();
    }
  }

  async refreshAuthToken() {
    // This should call your auth refresh endpoint
    const event = new CustomEvent('auth:refresh-needed');
    window.dispatchEvent(event);
    
    // Wait for token refresh to complete
    return new Promise((resolve) => {
      const handleRefresh = (e) => {
        window.removeEventListener('auth:token-refreshed', handleRefresh);
        resolve(e.detail?.token);
      };
      window.addEventListener('auth:token-refreshed', handleRefresh);
      
      // Timeout after 5 seconds
      setTimeout(() => {
        window.removeEventListener('auth:token-refreshed', handleRefresh);
        resolve(null);
      }, 5000);
    });
  }

  handleAuthDisconnect() {
    this.disconnect();
    window.dispatchEvent(new CustomEvent('auth:logout'));
  }

  disconnect() {
    if (this.socket) {
      // Remove all listeners before disconnecting
      this.socket.removeAllListeners();
      this.socket.disconnect();
      this.socket = null;
      this.connectionState = 'disconnected';
    }
  }

  on(event, callback) {
    if (!this.socket) {
      console.warn('WebSocket not connected. Event listener queued:', event);
    }

    // Store listener reference
    if (!this.listeners.has(event)) {
      this.listeners.set(event, new Set());
    }
    this.listeners.get(event).add(callback);

    // Attach to socket if connected
    if (this.socket) {
      this.socket.on(event, callback);
    }

    // Return unsubscribe function
    return () => this.off(event, callback);
  }

  off(event, callback) {
    // Remove from internal registry
    if (this.listeners.has(event)) {
      this.listeners.get(event).delete(callback);
      if (this.listeners.get(event).size === 0) {
        this.listeners.delete(event);
      }
    }

    // Remove from socket if connected
    if (this.socket) {
      this.socket.off(event, callback);
    }
  }

  emit(event, data) {
    if (!this.socket?.connected) {
      console.warn('WebSocket not connected. Cannot emit:', event);
      return false;
    }

    this.socket.emit(event, data);
    return true;
  }

  // Re-attach listeners after reconnection
  reattachListeners() {
    if (!this.socket) return;

    this.listeners.forEach((callbacks, event) => {
      callbacks.forEach(callback => {
        this.socket.on(event, callback);
      });
    });
  }

  getConnectionState() {
    return this.connectionState;
  }

  isConnected() {
    return this.socket?.connected || false;
  }

  // Order tracking specific methods
  subscribeToOrder(orderId) {
    return this.emit('order:subscribe', { order_id: orderId });
  }

  unsubscribeFromOrder(orderId) {
    return this.emit('order:unsubscribe', { order_id: orderId });
  }

  subscribeToOrders(customerId) {
    return this.emit('orders:subscribe', { customer_id: customerId });
  }

  unsubscribeFromOrders(customerId) {
    return this.emit('orders:unsubscribe', { customer_id: customerId });
  }
}

// Export singleton instance
const websocketService = new WebSocketService();

// Auto-reconnect on token refresh
window.addEventListener('auth:token-refreshed', (event) => {
  if (event.detail?.token && websocketService.authToken !== event.detail.token) {
    websocketService.disconnect();
    websocketService.connect(event.detail.token);
  }
});

export default websocketService;