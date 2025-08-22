import { io } from 'socket.io-client';

const WS_URL = process.env.REACT_APP_WS_URL || 'ws://localhost:8000';

class WebSocketService {
  constructor() {
    this.socket = null;
    this.listeners = new Map();
    this.reconnectAttempts = 0;
    this.maxReconnectAttempts = 5;
    this.reconnectDelay = 1000;
  }

  connect(token) {
    if (this.socket?.connected) {
      return;
    }

    this.socket = io(WS_URL, {
      auth: { token },
      transports: ['websocket'],
      reconnection: true,
      reconnectionAttempts: this.maxReconnectAttempts,
      reconnectionDelay: this.reconnectDelay,
    });

    this.socket.on('connect', () => {
      console.log('WebSocket connected');
      this.reconnectAttempts = 0;
      this.emit('connection:established');
    });

    this.socket.on('disconnect', (reason) => {
      console.log('WebSocket disconnected:', reason);
      this.emit('connection:lost', reason);
    });

    this.socket.on('error', (error) => {
      console.error('WebSocket error:', error);
      this.emit('connection:error', error);
    });

    this.socket.on('order:status', (data) => {
      this.emit('order:status', data);
    });

    this.socket.on('order:update', (data) => {
      this.emit('order:update', data);
    });

    this.socket.on('order:ready', (data) => {
      this.emit('order:ready', data);
    });

    this.socket.on('kitchen:update', (data) => {
      this.emit('kitchen:update', data);
    });

    this.socket.on('notification', (data) => {
      this.emit('notification', data);
    });
  }

  disconnect() {
    if (this.socket) {
      this.socket.disconnect();
      this.socket = null;
    }
  }

  subscribeToOrder(orderId) {
    if (!this.socket?.connected) {
      console.error('WebSocket not connected');
      return;
    }
    this.socket.emit('subscribe:order', { orderId });
  }

  unsubscribeFromOrder(orderId) {
    if (!this.socket?.connected) {
      return;
    }
    this.socket.emit('unsubscribe:order', { orderId });
  }

  on(event, callback) {
    if (!this.listeners.has(event)) {
      this.listeners.set(event, new Set());
    }
    this.listeners.get(event).add(callback);

    return () => {
      const callbacks = this.listeners.get(event);
      if (callbacks) {
        callbacks.delete(callback);
        if (callbacks.size === 0) {
          this.listeners.delete(event);
        }
      }
    };
  }

  off(event, callback) {
    const callbacks = this.listeners.get(event);
    if (callbacks) {
      callbacks.delete(callback);
      if (callbacks.size === 0) {
        this.listeners.delete(event);
      }
    }
  }

  emit(event, data) {
    const callbacks = this.listeners.get(event);
    if (callbacks) {
      callbacks.forEach((callback) => {
        try {
          callback(data);
        } catch (error) {
          console.error(`Error in WebSocket listener for ${event}:`, error);
        }
      });
    }
  }

  sendMessage(event, data) {
    if (!this.socket?.connected) {
      console.error('WebSocket not connected');
      return false;
    }
    this.socket.emit(event, data);
    return true;
  }

  isConnected() {
    return this.socket?.connected || false;
  }
}

const wsService = new WebSocketService();
export default wsService;