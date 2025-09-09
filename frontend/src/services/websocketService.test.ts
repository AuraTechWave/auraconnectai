import { WebSocketService } from './websocketService';
import { io } from 'socket.io-client';

// Mock socket.io-client
jest.mock('socket.io-client');
const mockIo = io as jest.MockedFunction<typeof io>;

// Mock WebSocket
const mockWebSocket = jest.fn();
Object.defineProperty(global, 'WebSocket', {
  value: mockWebSocket,
  writable: true
});

// Mock localStorage
const mockLocalStorage = {
  getItem: jest.fn(),
  setItem: jest.fn(),
  removeItem: jest.fn()
};
Object.defineProperty(window, 'localStorage', {
  value: mockLocalStorage
});

// Mock console methods
const consoleSpy = {
  log: jest.spyOn(console, 'log').mockImplementation(),
  error: jest.spyOn(console, 'error').mockImplementation(),
  warn: jest.spyOn(console, 'warn').mockImplementation()
};

describe('WebSocketService', () => {
  let wsService: WebSocketService;
  let mockSocket: any;
  let mockWS: any;

  beforeEach(() => {
    wsService = new WebSocketService();
    
    // Mock Socket.io socket
    mockSocket = {
      connected: false,
      connect: jest.fn(),
      disconnect: jest.fn(),
      on: jest.fn(),
      off: jest.fn(),
      emit: jest.fn(),
      join: jest.fn(),
      leave: jest.fn()
    };
    
    // Mock native WebSocket
    mockWS = {
      readyState: WebSocket.CONNECTING,
      send: jest.fn(),
      close: jest.fn(),
      addEventListener: jest.fn(),
      removeEventListener: jest.fn()
    };
    
    mockIo.mockReturnValue(mockSocket);
    mockWebSocket.mockReturnValue(mockWS);
    
    // Clear all mocks
    jest.clearAllMocks();
    mockLocalStorage.getItem.mockClear();
    consoleSpy.log.mockClear();
    consoleSpy.error.mockClear();
  });

  afterEach(() => {
    wsService.disconnect();
  });

  describe('WebSocket URL Generation', () => {
    test('uses REACT_APP_WEBSOCKET_URL when available', () => {
      const originalEnv = process.env.REACT_APP_WEBSOCKET_URL;
      process.env.REACT_APP_WEBSOCKET_URL = 'wss://ws.example.com';
      
      mockLocalStorage.getItem.mockReturnValue('test-token');
      wsService.connect('restaurant-1');
      
      expect(mockIo).toHaveBeenCalledWith('wss://ws.example.com', expect.any(Object));
      
      process.env.REACT_APP_WEBSOCKET_URL = originalEnv;
    });

    test('derives WebSocket URL from API URL', () => {
      const originalWsUrl = process.env.REACT_APP_WEBSOCKET_URL;
      const originalApiUrl = process.env.REACT_APP_API_URL;
      
      delete process.env.REACT_APP_WEBSOCKET_URL;
      process.env.REACT_APP_API_URL = 'https://api.example.com';
      
      mockLocalStorage.getItem.mockReturnValue('test-token');
      wsService.connect('restaurant-1');
      
      expect(mockIo).toHaveBeenCalledWith('wss://api.example.com', expect.any(Object));
      
      process.env.REACT_APP_WEBSOCKET_URL = originalWsUrl;
      process.env.REACT_APP_API_URL = originalApiUrl;
    });

    test('converts http to ws and https to wss', () => {
      const originalWsUrl = process.env.REACT_APP_WEBSOCKET_URL;
      const originalApiUrl = process.env.REACT_APP_API_URL;
      
      delete process.env.REACT_APP_WEBSOCKET_URL;
      process.env.REACT_APP_API_URL = 'http://localhost:8000';
      
      mockLocalStorage.getItem.mockReturnValue('test-token');
      wsService.connect('restaurant-1');
      
      expect(mockIo).toHaveBeenCalledWith('ws://localhost:8000', expect.any(Object));
      
      process.env.REACT_APP_WEBSOCKET_URL = originalWsUrl;
      process.env.REACT_APP_API_URL = originalApiUrl;
    });
  });

  describe('Socket.io Connection', () => {
    test('establishes Socket.io connection with auth token', () => {
      mockLocalStorage.getItem.mockReturnValue('auth-token-123');
      
      wsService.connect('restaurant-1');
      
      expect(mockIo).toHaveBeenCalledWith(expect.any(String), {
        auth: {
          token: 'auth-token-123',
          restaurant_id: 'restaurant-1'
        },
        transports: ['websocket'],
        reconnection: true,
        reconnectionAttempts: 5,
        reconnectionDelay: 1000
      });
    });

    test('does not connect without auth token', () => {
      mockLocalStorage.getItem.mockReturnValue(null);
      
      wsService.connect('restaurant-1');
      
      expect(mockIo).not.toHaveBeenCalled();
      expect(consoleSpy.error).toHaveBeenCalledWith(
        'No auth token available for WebSocket connection'
      );
    });

    test('does not connect if already connected', () => {
      mockSocket.connected = true;
      mockLocalStorage.getItem.mockReturnValue('test-token');
      
      wsService.connect('restaurant-1');
      
      expect(mockIo).not.toHaveBeenCalled();
      expect(consoleSpy.log).toHaveBeenCalledWith('Socket.io already connected');
    });

    test('sets up Socket.io event handlers', () => {
      mockLocalStorage.getItem.mockReturnValue('test-token');
      
      wsService.connect('restaurant-1');
      
      expect(mockSocket.on).toHaveBeenCalledWith('connect', expect.any(Function));
      expect(mockSocket.on).toHaveBeenCalledWith('disconnect', expect.any(Function));
      expect(mockSocket.on).toHaveBeenCalledWith('connect_error', expect.any(Function));
      expect(mockSocket.on).toHaveBeenCalledWith('order_updated', expect.any(Function));
      expect(mockSocket.on).toHaveBeenCalledWith('order_created', expect.any(Function));
    });
  });

  describe('Native WebSocket Fallback', () => {
    beforeEach(() => {
      // Force native WebSocket usage
      wsService['useSocketIO'] = false;
    });

    test('creates native WebSocket connection with proper URL and token', () => {
      mockLocalStorage.getItem.mockReturnValue('ws-token-456');
      
      wsService.connect(undefined, 123);
      
      expect(mockWebSocket).toHaveBeenCalledWith(
        expect.stringContaining('token=ws-token-456')
      );
      expect(mockWebSocket).toHaveBeenCalledWith(
        expect.stringContaining('order_id=123')
      );
    });

    test('does not connect native WebSocket without token', () => {
      mockLocalStorage.getItem.mockReturnValue(null);
      
      wsService.connect();
      
      expect(mockWebSocket).not.toHaveBeenCalled();
      expect(consoleSpy.error).toHaveBeenCalledWith(
        'No auth token available for WebSocket connection'
      );
    });

    test('does not connect if WebSocket already open', () => {
      mockWS.readyState = WebSocket.OPEN;
      wsService['ws'] = mockWS;
      mockLocalStorage.getItem.mockReturnValue('test-token');
      
      wsService.connect();
      
      expect(mockWebSocket).not.toHaveBeenCalled();
      expect(consoleSpy.log).toHaveBeenCalledWith('Native WebSocket already connected');
    });

    test('sets up native WebSocket event handlers', () => {
      mockLocalStorage.getItem.mockReturnValue('test-token');
      
      wsService.connect();
      
      expect(mockWS.addEventListener).toHaveBeenCalledWith('open', expect.any(Function));
      expect(mockWS.addEventListener).toHaveBeenCalledWith('message', expect.any(Function));
      expect(mockWS.addEventListener).toHaveBeenCalledWith('error', expect.any(Function));
      expect(mockWS.addEventListener).toHaveBeenCalledWith('close', expect.any(Function));
    });
  });

  describe('Event Subscription', () => {
    test('subscribes to order updates', () => {
      const callback = jest.fn();
      wsService.subscribeToOrderUpdates(callback);
      
      // Verify callback is stored
      expect(wsService['listeners'].get('order_updated')?.has(callback)).toBe(true);
    });

    test('unsubscribes from order updates', () => {
      const callback = jest.fn();
      wsService.subscribeToOrderUpdates(callback);
      wsService.unsubscribeFromOrderUpdates(callback);
      
      // Verify callback is removed
      expect(wsService['listeners'].get('order_updated')?.has(callback)).toBe(false);
    });

    test('subscribes to order creation', () => {
      const callback = jest.fn();
      wsService.subscribeToOrderCreation(callback);
      
      expect(wsService['listeners'].get('order_created')?.has(callback)).toBe(true);
    });

    test('subscribes to connection status', () => {
      const callback = jest.fn();
      wsService.subscribeToConnectionStatus(callback);
      
      expect(wsService['listeners'].get('connection_status')?.has(callback)).toBe(true);
    });

    test('handles multiple subscribers for same event', () => {
      const callback1 = jest.fn();
      const callback2 = jest.fn();
      
      wsService.subscribeToOrderUpdates(callback1);
      wsService.subscribeToOrderUpdates(callback2);
      
      const listeners = wsService['listeners'].get('order_updated');
      expect(listeners?.size).toBe(2);
      expect(listeners?.has(callback1)).toBe(true);
      expect(listeners?.has(callback2)).toBe(true);
    });
  });

  describe('Message Handling', () => {
    test('emits order update events to subscribers', () => {
      const callback1 = jest.fn();
      const callback2 = jest.fn();
      
      wsService.subscribeToOrderUpdates(callback1);
      wsService.subscribeToOrderUpdates(callback2);
      
      const orderEvent = {
        type: 'updated',
        order_id: 123,
        data: { status: 'confirmed' },
        timestamp: new Date().toISOString()
      };
      
      // Simulate receiving message
      wsService['emit']('order_updated', orderEvent);
      
      expect(callback1).toHaveBeenCalledWith(orderEvent);
      expect(callback2).toHaveBeenCalledWith(orderEvent);
    });

    test('handles order creation events', () => {
      const callback = jest.fn();
      wsService.subscribeToOrderCreation(callback);
      
      const newOrderEvent = {
        type: 'created',
        order_id: 456,
        order: {
          id: 456,
          status: 'pending',
          total: 25.99
        },
        timestamp: new Date().toISOString()
      };
      
      wsService['emit']('order_created', newOrderEvent);
      
      expect(callback).toHaveBeenCalledWith(newOrderEvent);
    });

    test('handles connection status changes', () => {
      const callback = jest.fn();
      wsService.subscribeToConnectionStatus(callback);
      
      wsService['emit']('connection_status', { connected: true });
      
      expect(callback).toHaveBeenCalledWith({ connected: true });
    });
  });

  describe('Room Management', () => {
    beforeEach(() => {
      mockLocalStorage.getItem.mockReturnValue('test-token');
      wsService.connect();
    });

    test('joins restaurant room', () => {
      wsService.joinRestaurantRoom('restaurant-123');
      
      expect(mockSocket.emit).toHaveBeenCalledWith('join_room', {
        room: 'restaurant-123',
        type: 'restaurant'
      });
    });

    test('leaves restaurant room', () => {
      wsService.leaveRestaurantRoom('restaurant-123');
      
      expect(mockSocket.emit).toHaveBeenCalledWith('leave_room', {
        room: 'restaurant-123',
        type: 'restaurant'
      });
    });

    test('joins order room', () => {
      wsService.joinOrderRoom(456);
      
      expect(mockSocket.emit).toHaveBeenCalledWith('join_room', {
        room: 'order-456',
        type: 'order'
      });
    });

    test('leaves order room', () => {
      wsService.leaveOrderRoom(456);
      
      expect(mockSocket.emit).toHaveBeenCalledWith('leave_room', {
        room: 'order-456',
        type: 'order'
      });
    });
  });

  describe('Connection Management', () => {
    test('disconnects Socket.io connection', () => {
      mockLocalStorage.getItem.mockReturnValue('test-token');
      wsService.connect();
      
      wsService.disconnect();
      
      expect(mockSocket.disconnect).toHaveBeenCalled();
    });

    test('disconnects native WebSocket', () => {
      wsService['useSocketIO'] = false;
      mockLocalStorage.getItem.mockReturnValue('test-token');
      wsService.connect();
      
      wsService.disconnect();
      
      expect(mockWS.close).toHaveBeenCalled();
    });

    test('checks Socket.io connection status', () => {
      mockSocket.connected = true;
      wsService['socket'] = mockSocket;
      
      expect(wsService.isConnected()).toBe(true);
    });

    test('checks native WebSocket connection status', () => {
      wsService['useSocketIO'] = false;
      mockWS.readyState = WebSocket.OPEN;
      wsService['ws'] = mockWS;
      
      expect(wsService.isConnected()).toBe(true);
    });

    test('returns false when not connected', () => {
      expect(wsService.isConnected()).toBe(false);
    });
  });

  describe('Reconnection Logic', () => {
    beforeEach(() => {
      wsService['useSocketIO'] = false; // Use native WebSocket for reconnection testing
    });

    test('attempts reconnection on connection loss', (done) => {
      mockLocalStorage.getItem.mockReturnValue('test-token');
      wsService.connect();
      
      // Mock connection loss
      const closeHandler = mockWS.addEventListener.mock.calls.find(
        call => call[0] === 'close'
      )?.[1];
      
      if (closeHandler) {
        closeHandler({ code: 1000, wasClean: false });
        
        // Check that reconnection is attempted
        setTimeout(() => {
          expect(wsService['reconnectAttempts']).toBeGreaterThan(0);
          done();
        }, 100);
      }
    });

    test('stops reconnecting after max attempts', () => {
      wsService['reconnectAttempts'] = 5;
      wsService['maxReconnectAttempts'] = 5;
      
      const shouldReconnect = wsService['shouldReconnect'](1000, false);
      
      expect(shouldReconnect).toBe(false);
    });

    test('does not reconnect on intentional close', () => {
      wsService['isIntentionallyClosed'] = true;
      
      const shouldReconnect = wsService['shouldReconnect'](1000, true);
      
      expect(shouldReconnect).toBe(false);
    });
  });

  describe('Error Handling', () => {
    test('handles Socket.io connection errors', () => {
      mockLocalStorage.getItem.mockReturnValue('test-token');
      wsService.connect();
      
      const errorHandler = mockSocket.on.mock.calls.find(
        call => call[0] === 'connect_error'
      )?.[1];
      
      if (errorHandler) {
        const error = new Error('Connection failed');
        errorHandler(error);
        
        expect(consoleSpy.error).toHaveBeenCalledWith('Socket.io connection error:', error);
      }
    });

    test('handles native WebSocket errors', () => {
      wsService['useSocketIO'] = false;
      mockLocalStorage.getItem.mockReturnValue('test-token');
      wsService.connect();
      
      const errorHandler = mockWS.addEventListener.mock.calls.find(
        call => call[0] === 'error'
      )?.[1];
      
      if (errorHandler) {
        const error = new Error('WebSocket error');
        errorHandler(error);
        
        expect(consoleSpy.error).toHaveBeenCalledWith('WebSocket error:', error);
      }
    });

    test('handles WebSocket creation failure', () => {
      wsService['useSocketIO'] = false;
      mockWebSocket.mockImplementation(() => {
        throw new Error('WebSocket creation failed');
      });
      mockLocalStorage.getItem.mockReturnValue('test-token');
      
      wsService.connect();
      
      expect(consoleSpy.error).toHaveBeenCalledWith(
        'Failed to create WebSocket connection:',
        expect.any(Error)
      );
    });
  });

  describe('Cleanup', () => {
    test('clears all listeners on disconnect', () => {
      const callback1 = jest.fn();
      const callback2 = jest.fn();
      
      wsService.subscribeToOrderUpdates(callback1);
      wsService.subscribeToOrderCreation(callback2);
      
      wsService.disconnect();
      
      expect(wsService['listeners'].size).toBe(0);
    });

    test('clears reconnection timeout on disconnect', () => {
      wsService['reconnectTimeout'] = setTimeout(() => {}, 1000);
      const timeoutId = wsService['reconnectTimeout'];
      
      wsService.disconnect();
      
      expect(wsService['reconnectTimeout']).toBe(null);
    });

    test('clears heartbeat interval on disconnect', () => {
      wsService['heartbeatInterval'] = setInterval(() => {}, 1000);
      
      wsService.disconnect();
      
      expect(wsService['heartbeatInterval']).toBe(null);
    });
  });
});