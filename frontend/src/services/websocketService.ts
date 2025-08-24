// WebSocket service for real-time order updates
// Supports both native WebSocket and Socket.io

import { io, Socket } from 'socket.io-client';
import { authManager } from '../utils/auth';
import { OrderEvent, Order } from '../types/order.types';

class WebSocketService {
  // Socket.io implementation
  private socket: Socket | null = null;
  
  // Native WebSocket implementation (fallback)
  private ws: WebSocket | null = null;
  private reconnectAttempts = 0;
  private maxReconnectAttempts = 5;
  private reconnectDelay = 1000;
  private heartbeatInterval: NodeJS.Timeout | null = null;
  private reconnectTimeout: NodeJS.Timeout | null = null;
  private isIntentionallyClosed = false;
  
  // Shared event listeners
  private listeners: Map<string, Set<Function>> = new Map();
  private useSocketIO = true; // Default to Socket.io
  
  // Get WebSocket URL based on environment
  private getWebSocketUrl(): string {
    const wsUrl = process.env.REACT_APP_WEBSOCKET_URL;
    if (wsUrl) return wsUrl;
    
    // Derive from API URL
    const apiUrl = process.env.REACT_APP_API_URL || 'http://localhost:8000';
    return apiUrl
      .replace('http://', 'ws://')
      .replace('https://', 'wss://');
  }
  
  // Main connect method - tries Socket.io first, falls back to native WebSocket
  connect(restaurantId?: string | number, orderId?: number): void {
    if (this.useSocketIO) {
      this.connectSocketIO(restaurantId?.toString());
    } else {
      this.connectNativeWebSocket(orderId);
    }
  }
  
  // Socket.io connection
  private connectSocketIO(restaurantId?: string): void {
    if (this.socket?.connected) {
      console.log('Socket.io already connected');
      return;
    }
    
    const wsUrl = this.getWebSocketUrl();
    const token = authManager.getAccessToken();
    
    if (!token) {
      console.error('No auth token available for WebSocket connection');
      return;
    }
    
    this.socket = io(wsUrl, {
      auth: {
        token,
        restaurant_id: restaurantId
      },
      transports: ['websocket'],
      reconnection: true,
      reconnectionAttempts: this.maxReconnectAttempts,
      reconnectionDelay: this.reconnectDelay,
    });
    
    this.setupSocketIOHandlers();
  }
  
  // Native WebSocket connection (fallback)
  private connectNativeWebSocket(orderId?: number): void {
    if (this.ws?.readyState === WebSocket.OPEN) {
      console.log('Native WebSocket already connected');
      return;
    }
    
    this.isIntentionallyClosed = false;
    const token = authManager.getAccessToken();
    
    if (!token) {
      console.error('No auth token available for WebSocket connection');
      return;
    }
    
    const baseUrl = this.getWebSocketUrl();
    const params = new URLSearchParams({ token });
    if (orderId) params.append('order_id', orderId.toString());
    
    const wsUrl = `${baseUrl}/ws/orders?${params.toString()}`;
    
    try {
      this.ws = new WebSocket(wsUrl);
      this.setupNativeWebSocketHandlers();
    } catch (error) {
      console.error('Failed to create WebSocket connection:', error);
      // Try Socket.io as fallback
      this.useSocketIO = true;
      this.connect();
    }
  }
  
  // Socket.io event handlers
  private setupSocketIOHandlers(): void {
    if (!this.socket) return;
    
    this.socket.on('connect', () => {
      console.log('Socket.io connected');
      this.emit('connected', true);
    });
    
    this.socket.on('disconnect', () => {
      console.log('Socket.io disconnected');
      this.emit('connected', false);
    });
    
    this.socket.on('order:new', (order: Order) => {
      this.emit('order:new', order);
      this.emit('order:event', { type: 'created', order_id: order.id, order });
    });
    
    this.socket.on('order:updated', (order: Order) => {
      this.emit('order:updated', order);
      this.emit('order:event', { type: 'updated', order_id: order.id, order });
    });
    
    this.socket.on('order:status_changed', (data: { orderId: string; status: string; order: Order }) => {
      this.emit('order:status_changed', data);
      this.emit('order:event', { 
        type: 'status_changed', 
        order_id: parseInt(data.orderId), 
        status: data.status,
        order: data.order 
      });
    });
    
    this.socket.on('order:cancelled', (order: Order) => {
      this.emit('order:cancelled', order);
      this.emit('order:event', { type: 'cancelled', order_id: order.id, order });
    });
    
    this.socket.on('error', (error: any) => {
      console.error('Socket.io error:', error);
      this.emit('error', error);
    });
  }
  
  // Native WebSocket event handlers
  private setupNativeWebSocketHandlers(): void {
    if (!this.ws) return;
    
    this.ws.onopen = () => {
      console.log('Native WebSocket connected');
      this.reconnectAttempts = 0;
      this.reconnectDelay = 1000;
      this.startHeartbeat();
      this.emit('connected', true);
    };
    
    this.ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data) as OrderEvent;
        this.handleNativeWebSocketMessage(data);
      } catch (error) {
        console.error('Failed to parse WebSocket message:', error);
      }
    };
    
    this.ws.onerror = (error) => {
      console.error('Native WebSocket error:', error);
      this.emit('error', error);
    };
    
    this.ws.onclose = (event) => {
      console.log('Native WebSocket closed:', event.code, event.reason);
      this.stopHeartbeat();
      this.emit('connected', false);
      
      if (!this.isIntentionallyClosed && this.reconnectAttempts < this.maxReconnectAttempts) {
        this.scheduleReconnect();
      }
    };
  }
  
  // Handle native WebSocket messages
  private handleNativeWebSocketMessage(event: OrderEvent): void {
    this.emit('order:event', event);
    
    // Map to Socket.io-style events for compatibility
    switch (event.type) {
      case 'created':
        this.emit('order:new', event.order);
        break;
      case 'updated':
        this.emit('order:updated', event.order);
        break;
      case 'status_changed':
        this.emit('order:status_changed', {
          orderId: event.order_id.toString(),
          status: event.status || '',
          order: event.order
        });
        break;
      case 'cancelled':
        this.emit('order:cancelled', event.order);
        break;
    }
  }
  
  // Heartbeat for native WebSocket
  private startHeartbeat(): void {
    this.heartbeatInterval = setInterval(() => {
      if (this.ws?.readyState === WebSocket.OPEN) {
        this.ws.send(JSON.stringify({ type: 'ping' }));
      }
    }, 30000);
  }
  
  private stopHeartbeat(): void {
    if (this.heartbeatInterval) {
      clearInterval(this.heartbeatInterval);
      this.heartbeatInterval = null;
    }
  }
  
  private scheduleReconnect(): void {
    this.reconnectAttempts++;
    console.log(`Scheduling reconnect attempt ${this.reconnectAttempts}/${this.maxReconnectAttempts}`);
    
    this.reconnectTimeout = setTimeout(() => {
      this.connectNativeWebSocket();
    }, this.reconnectDelay);
    
    // Exponential backoff
    this.reconnectDelay = Math.min(this.reconnectDelay * 2, 30000);
  }
  
  // Disconnect both implementations
  disconnect(): void {
    this.isIntentionallyClosed = true;
    
    // Disconnect Socket.io
    if (this.socket) {
      this.socket.disconnect();
      this.socket = null;
    }
    
    // Disconnect native WebSocket
    if (this.reconnectTimeout) {
      clearTimeout(this.reconnectTimeout);
      this.reconnectTimeout = null;
    }
    
    this.stopHeartbeat();
    
    if (this.ws) {
      this.ws.close(1000, 'Client disconnect');
      this.ws = null;
    }
    
    this.listeners.clear();
  }
  
  // Event listener management
  on(event: string, callback: Function): void {
    if (!this.listeners.has(event)) {
      this.listeners.set(event, new Set());
    }
    this.listeners.get(event)?.add(callback);
  }
  
  off(event: string, callback: Function): void {
    this.listeners.get(event)?.delete(callback);
  }
  
  // Subscribe with unsubscribe function (alternative API)
  subscribe(event: string, callback: Function): () => void {
    this.on(event, callback);
    return () => this.off(event, callback);
  }
  
  private emit(event: string, data: any): void {
    this.listeners.get(event)?.forEach(callback => {
      try {
        callback(data);
      } catch (error) {
        console.error(`Error in WebSocket listener for event ${event}:`, error);
      }
    });
  }
  
  // Socket.io room management
  joinRoom(room: string): void {
    if (this.socket) {
      this.socket.emit('join_room', room);
    } else if (this.ws?.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify({ type: 'join_room', room }));
    }
  }
  
  leaveRoom(room: string): void {
    if (this.socket) {
      this.socket.emit('leave_room', room);
    } else if (this.ws?.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify({ type: 'leave_room', room }));
    }
  }
  
  // Order subscriptions
  subscribeToOrders(restaurantId: string): void {
    if (this.socket) {
      this.socket.emit('subscribe:orders', { restaurant_id: restaurantId });
    } else if (this.ws?.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify({ 
        type: 'subscribe:orders', 
        restaurant_id: restaurantId 
      }));
    }
  }
  
  unsubscribeFromOrders(restaurantId: string): void {
    if (this.socket) {
      this.socket.emit('unsubscribe:orders', { restaurant_id: restaurantId });
    } else if (this.ws?.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify({ 
        type: 'unsubscribe:orders', 
        restaurant_id: restaurantId 
      }));
    }
  }
  
  // Send generic message
  send(message: any): void {
    if (this.socket?.connected) {
      this.socket.emit('message', message);
    } else if (this.ws?.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify(message));
    } else {
      console.error('WebSocket is not connected');
    }
  }
  
  // Connection state getters
  get isConnected(): boolean {
    return this.socket?.connected || this.ws?.readyState === WebSocket.OPEN || false;
  }
  
  get connectionType(): 'socket.io' | 'native' | 'disconnected' {
    if (this.socket?.connected) return 'socket.io';
    if (this.ws?.readyState === WebSocket.OPEN) return 'native';
    return 'disconnected';
  }
}

export default new WebSocketService();