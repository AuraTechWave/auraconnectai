import { io, Socket } from 'socket.io-client';
import { Order } from '@/types/order.types';

class WebSocketService {
  private socket: Socket | null = null;
  private listeners: Map<string, Set<Function>> = new Map();
  
  connect(restaurantId: string): void {
    if (this.socket?.connected) {
      return;
    }
    
    const wsUrl = process.env.REACT_APP_WEBSOCKET_URL || 'ws://localhost:8000';
    const token = localStorage.getItem('authToken');
    
    this.socket = io(wsUrl, {
      auth: {
        token,
        restaurant_id: restaurantId
      },
      transports: ['websocket'],
      reconnection: true,
      reconnectionAttempts: 5,
      reconnectionDelay: 1000,
    });
    
    this.setupEventHandlers();
  }
  
  private setupEventHandlers(): void {
    if (!this.socket) return;
    
    this.socket.on('connect', () => {
      console.log('WebSocket connected');
      this.emit('connected', true);
    });
    
    this.socket.on('disconnect', () => {
      console.log('WebSocket disconnected');
      this.emit('connected', false);
    });
    
    this.socket.on('order:new', (order: Order) => {
      this.emit('order:new', order);
    });
    
    this.socket.on('order:updated', (order: Order) => {
      this.emit('order:updated', order);
    });
    
    this.socket.on('order:status_changed', (data: { orderId: string; status: string; order: Order }) => {
      this.emit('order:status_changed', data);
    });
    
    this.socket.on('order:cancelled', (order: Order) => {
      this.emit('order:cancelled', order);
    });
    
    this.socket.on('error', (error: any) => {
      console.error('WebSocket error:', error);
      this.emit('error', error);
    });
  }
  
  disconnect(): void {
    if (this.socket) {
      this.socket.disconnect();
      this.socket = null;
      this.listeners.clear();
    }
  }
  
  on(event: string, callback: Function): void {
    if (!this.listeners.has(event)) {
      this.listeners.set(event, new Set());
    }
    this.listeners.get(event)?.add(callback);
  }
  
  off(event: string, callback: Function): void {
    this.listeners.get(event)?.delete(callback);
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
  
  // Send events to server
  joinRoom(room: string): void {
    this.socket?.emit('join_room', room);
  }
  
  leaveRoom(room: string): void {
    this.socket?.emit('leave_room', room);
  }
  
  subscribeToOrders(restaurantId: string): void {
    this.socket?.emit('subscribe:orders', { restaurant_id: restaurantId });
  }
  
  unsubscribeFromOrders(restaurantId: string): void {
    this.socket?.emit('unsubscribe:orders', { restaurant_id: restaurantId });
  }
}

export default new WebSocketService();