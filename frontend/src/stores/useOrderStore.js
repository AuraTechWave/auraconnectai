import { create } from 'zustand';
import { orderApi } from '../services/api';
import wsService from '../services/websocket';

const useOrderStore = create((set, get) => ({
  orders: [],
  currentOrder: null,
  activeOrders: [],
  orderHistory: [],
  isLoading: false,
  error: null,
  wsConnected: false,

  createOrder: async (orderData) => {
    set({ isLoading: true, error: null });
    try {
      const response = await orderApi.createOrder(orderData);
      const newOrder = response.data;
      
      set((state) => ({
        orders: [newOrder, ...state.orders],
        currentOrder: newOrder,
        activeOrders: [newOrder, ...state.activeOrders],
        isLoading: false,
      }));

      wsService.subscribeToOrder(newOrder.id);
      
      return { success: true, order: newOrder };
    } catch (error) {
      set({ 
        error: error.response?.data?.message || 'Failed to create order', 
        isLoading: false 
      });
      return { success: false, error: error.response?.data?.message };
    }
  },

  fetchOrder: async (orderId) => {
    set({ isLoading: true });
    try {
      const response = await orderApi.getOrder(orderId);
      set({ currentOrder: response.data, isLoading: false });
      return response.data;
    } catch (error) {
      set({ error: error.message, isLoading: false });
      return null;
    }
  },

  fetchMyOrders: async () => {
    set({ isLoading: true });
    try {
      const response = await orderApi.getMyOrders();
      const orders = response.data;
      
      const active = orders.filter(
        (order) => !['completed', 'cancelled'].includes(order.status)
      );
      const history = orders.filter(
        (order) => ['completed', 'cancelled'].includes(order.status)
      );

      set({ 
        orders,
        activeOrders: active,
        orderHistory: history,
        isLoading: false 
      });
    } catch (error) {
      set({ error: error.message, isLoading: false });
    }
  },

  trackOrder: async (orderId) => {
    try {
      const response = await orderApi.trackOrder(orderId);
      return response.data;
    } catch (error) {
      console.error('Failed to track order:', error);
      return null;
    }
  },

  cancelOrder: async (orderId) => {
    set({ isLoading: true });
    try {
      await orderApi.cancelOrder(orderId);
      
      set((state) => {
        const updatedOrders = state.orders.map((order) =>
          order.id === orderId ? { ...order, status: 'cancelled' } : order
        );
        
        const updatedActive = state.activeOrders.filter(
          (order) => order.id !== orderId
        );
        
        const cancelledOrder = state.orders.find((order) => order.id === orderId);
        const updatedHistory = cancelledOrder
          ? [{ ...cancelledOrder, status: 'cancelled' }, ...state.orderHistory]
          : state.orderHistory;

        return {
          orders: updatedOrders,
          activeOrders: updatedActive,
          orderHistory: updatedHistory,
          currentOrder: 
            state.currentOrder?.id === orderId
              ? { ...state.currentOrder, status: 'cancelled' }
              : state.currentOrder,
          isLoading: false,
        };
      });

      wsService.unsubscribeFromOrder(orderId);
      
      return { success: true };
    } catch (error) {
      set({ 
        error: error.response?.data?.message || 'Failed to cancel order', 
        isLoading: false 
      });
      return { success: false, error: error.response?.data?.message };
    }
  },

  updateOrderStatus: (orderId, status, data) => {
    set((state) => {
      const updatedOrders = state.orders.map((order) =>
        order.id === orderId ? { ...order, status, ...data } : order
      );

      const isCompleted = ['completed', 'cancelled'].includes(status);
      
      let updatedActive = state.activeOrders;
      let updatedHistory = state.orderHistory;

      if (isCompleted) {
        updatedActive = state.activeOrders.filter((order) => order.id !== orderId);
        const completedOrder = updatedOrders.find((order) => order.id === orderId);
        if (completedOrder && !updatedHistory.find((order) => order.id === orderId)) {
          updatedHistory = [completedOrder, ...updatedHistory];
        }
      }

      return {
        orders: updatedOrders,
        activeOrders: updatedActive,
        orderHistory: updatedHistory,
        currentOrder:
          state.currentOrder?.id === orderId
            ? { ...state.currentOrder, status, ...data }
            : state.currentOrder,
      };
    });
  },

  initWebSocket: (token) => {
    wsService.connect(token);

    wsService.on('connection:established', () => {
      set({ wsConnected: true });
      const activeOrders = get().activeOrders;
      activeOrders.forEach((order) => {
        wsService.subscribeToOrder(order.id);
      });
    });

    wsService.on('connection:lost', () => {
      set({ wsConnected: false });
    });

    wsService.on('order:status', (data) => {
      get().updateOrderStatus(data.orderId, data.status, data);
    });

    wsService.on('order:update', (data) => {
      get().updateOrderStatus(data.orderId, data.status, data);
    });

    wsService.on('order:ready', (data) => {
      get().updateOrderStatus(data.orderId, 'ready', data);
    });
  },

  disconnectWebSocket: () => {
    const activeOrders = get().activeOrders;
    activeOrders.forEach((order) => {
      wsService.unsubscribeFromOrder(order.id);
    });
    wsService.disconnect();
    set({ wsConnected: false });
  },

  clearError: () => set({ error: null }),
}));

export default useOrderStore;