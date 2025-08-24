import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { useState, useEffect, useCallback } from 'react';
import orderService from '../services/orderService';
import websocketService from '../services/websocketService';
import { 
  Order, 
  OrderListParams, 
  OrderCreateRequest, 
  OrderUpdateRequest,
  OrderEvent 
} from '../types/order.types';

// Query keys
const ORDERS_KEY = 'orders';
const ORDER_KEY = 'order';

// Custom hook for orders list with real-time updates
export const useOrders = (params?: OrderListParams) => {
  const queryClient = useQueryClient();
  const [newOrdersCount, setNewOrdersCount] = useState(0);
  
  // Fetch orders
  const query = useQuery({
    queryKey: [ORDERS_KEY, params],
    queryFn: () => orderService.getOrders(params),
    refetchInterval: params?.status?.includes('pending') ? 30000 : false, // Refetch pending orders every 30s
  });
  
  // Subscribe to WebSocket updates
  useEffect(() => {
    if (!process.env.REACT_APP_ENABLE_WEBSOCKET) return;
    
    const unsubscribe = websocketService.subscribe('all', (event: OrderEvent) => {
      // Handle different event types
      switch (event.type) {
        case 'order_created':
          setNewOrdersCount(prev => prev + 1);
          // Optionally refetch or update cache
          queryClient.invalidateQueries([ORDERS_KEY]);
          break;
          
        case 'order_updated':
        case 'order_status_changed':
          // Update specific order in cache
          queryClient.setQueryData(
            [ORDERS_KEY, params],
            (oldData: any) => {
              if (!oldData) return oldData;
              
              return {
                ...oldData,
                items: oldData.items.map((order: Order) =>
                  order.id === event.order_id
                    ? { ...order, ...event.data }
                    : order
                ),
              };
            }
          );
          break;
      }
    });
    
    // Connect WebSocket
    websocketService.connect();
    
    return () => {
      unsubscribe();
    };
  }, [queryClient, params]);
  
  const resetNewOrdersCount = useCallback(() => {
    setNewOrdersCount(0);
  }, []);
  
  return {
    ...query,
    newOrdersCount,
    resetNewOrdersCount,
  };
};

// Custom hook for single order
export const useOrder = (orderId: number) => {
  const queryClient = useQueryClient();
  
  const query = useQuery({
    queryKey: [ORDER_KEY, orderId],
    queryFn: () => orderService.getOrder(orderId),
    enabled: !!orderId,
  });
  
  // Subscribe to updates for this specific order
  useEffect(() => {
    if (!orderId || !process.env.REACT_APP_ENABLE_WEBSOCKET) return;
    
    const unsubscribe = websocketService.subscribe(orderId.toString(), (event: OrderEvent) => {
      // Update order in cache
      queryClient.setQueryData([ORDER_KEY, orderId], (oldData: any) => {
        if (!oldData) return oldData;
        return { ...oldData, ...event.data };
      });
    });
    
    return unsubscribe;
  }, [orderId, queryClient]);
  
  return query;
};

// Create order mutation
export const useCreateOrder = () => {
  const queryClient = useQueryClient();
  
  return useMutation({
    mutationFn: (data: OrderCreateRequest) => orderService.createOrder(data),
    onSuccess: () => {
      queryClient.invalidateQueries([ORDERS_KEY]);
    },
  });
};

// Update order mutation
export const useUpdateOrder = () => {
  const queryClient = useQueryClient();
  
  return useMutation({
    mutationFn: ({ id, data }: { id: number; data: OrderUpdateRequest }) =>
      orderService.updateOrder(id, data),
    onSuccess: (updatedOrder) => {
      // Update specific order
      queryClient.setQueryData([ORDER_KEY, updatedOrder.id], updatedOrder);
      // Invalidate list
      queryClient.invalidateQueries([ORDERS_KEY]);
    },
  });
};

// Delay order mutation
export const useDelayOrder = () => {
  const queryClient = useQueryClient();
  
  return useMutation({
    mutationFn: ({ orderId, minutes, reason }: { 
      orderId: number; 
      minutes: number; 
      reason?: string 
    }) => orderService.delayOrder(orderId, minutes, reason),
    onSuccess: (_, variables) => {
      queryClient.invalidateQueries([ORDER_KEY, variables.orderId]);
      queryClient.invalidateQueries([ORDERS_KEY]);
    },
  });
};

// Archive order mutation
export const useArchiveOrder = () => {
  const queryClient = useQueryClient();
  
  return useMutation({
    mutationFn: (orderId: number) => orderService.archiveOrder(orderId),
    onSuccess: (_, orderId) => {
      queryClient.invalidateQueries([ORDER_KEY, orderId]);
      queryClient.invalidateQueries([ORDERS_KEY]);
    },
  });
};