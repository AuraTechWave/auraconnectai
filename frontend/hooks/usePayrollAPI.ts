/**
 * Custom hook for interacting with the Payroll API
 * Provides methods for payroll operations with proper error handling and loading states
 */

import { useState, useCallback, useEffect } from 'react';
import { apiClient } from '../utils/apiClient';
import { 
  PayrollHistory, 
  PayrollHistoryResponse,
  PayrollRunRequest, 
  PayrollRunResponse,
  PayrollDetail,
  PayrollRules,
  PayrollWebSocketEvent 
} from '../types/payroll';

interface UsePayrollAPIReturn {
  loading: boolean;
  error: Error | null;
  getPayrollHistory: (staffId: number, tenantId?: number) => Promise<PayrollHistoryResponse>;
  runPayroll: (request: PayrollRunRequest) => Promise<PayrollRunResponse>;
  getPayrollDetail: (payrollId: number) => Promise<PayrollDetail>;
  getPayrollRules: () => Promise<PayrollRules>;
  checkJobStatus: (jobId: string) => Promise<any>;
  exportPayroll: (request: any) => Promise<any>;
}

// Simple in-memory cache for payroll details
const payrollDetailCache = new Map<number, { data: PayrollDetail; timestamp: number }>();
const CACHE_TTL = 5 * 60 * 1000; // 5 minutes


export const usePayrollAPI = (): UsePayrollAPIReturn => {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<Error | null>(null);

  const handleRequest = useCallback(async <T,>(
    requestFn: () => Promise<T>
  ): Promise<T> => {
    setLoading(true);
    setError(null);
    
    try {
      const result = await requestFn();
      return result;
    } catch (err) {
      const error = err instanceof Error ? err : new Error('An error occurred');
      setError(error);
      throw error;
    } finally {
      setLoading(false);
    }
  }, []);

  const getPayrollHistory = useCallback(
    async (staffId: number, tenantId?: number): Promise<PayrollHistoryResponse> => {
      return handleRequest(async () => {
        const params = new URLSearchParams();
        if (tenantId) params.append('tenant_id', tenantId.toString());
        
        const response = await apiClient.get(
          `/api/v1/payrolls/${staffId}?${params.toString()}`
        );
        return response.data;
      });
    },
    [handleRequest]
  );

  const runPayroll = useCallback(
    async (request: PayrollRunRequest): Promise<PayrollRunResponse> => {
      return handleRequest(async () => {
        const response = await apiClient.post('/api/v1/payrolls/run', request);
        return response.data;
      });
    },
    [handleRequest]
  );

  const getPayrollDetail = useCallback(
    async (payrollId: number): Promise<PayrollDetail> => {
      // Check cache first
      const cached = payrollDetailCache.get(payrollId);
      if (cached && Date.now() - cached.timestamp < CACHE_TTL) {
        console.log(`Returning cached payroll detail for ${payrollId}`);
        return cached.data;
      }
      
      return handleRequest(async () => {
        const response = await apiClient.get(`/api/v1/payrolls/${payrollId}/detail`);
        const data = response.data;
        
        // Cache the result
        payrollDetailCache.set(payrollId, {
          data,
          timestamp: Date.now()
        });
        
        // Clean up old cache entries
        if (payrollDetailCache.size > 50) {
          const entriesToDelete: number[] = [];
          const now = Date.now();
          
          payrollDetailCache.forEach((value, key) => {
            if (now - value.timestamp > CACHE_TTL) {
              entriesToDelete.push(key);
            }
          });
          
          entriesToDelete.forEach(key => payrollDetailCache.delete(key));
        }
        
        return data;
      });
    },
    [handleRequest]
  );

  const getPayrollRules = useCallback(
    async (): Promise<PayrollRules> => {
      return handleRequest(async () => {
        const response = await apiClient.get('/api/v1/payrolls/rules');
        return response.data;
      });
    },
    [handleRequest]
  );

  const checkJobStatus = useCallback(
    async (jobId: string): Promise<any> => {
      return handleRequest(async () => {
        const response = await apiClient.get(`/api/v1/payrolls/run/${jobId}/status`);
        return response.data;
      });
    },
    [handleRequest]
  );

  const exportPayroll = useCallback(
    async (request: any): Promise<any> => {
      return handleRequest(async () => {
        const response = await apiClient.post('/api/v1/payrolls/export', request);
        return response.data;
      });
    },
    [handleRequest]
  );

  return {
    loading,
    error,
    getPayrollHistory,
    runPayroll,
    getPayrollDetail,
    getPayrollRules,
    checkJobStatus,
    exportPayroll
  };
};

// Enhanced WebSocket integration for real-time payroll updates
export const usePayrollWebSocket = (
  onUpdate: (event: PayrollWebSocketEvent) => void,
  staffId?: number
) => {
  const [connected, setConnected] = useState(false);
  const [connectionStatus, setConnectionStatus] = useState<'connecting' | 'connected' | 'disconnected' | 'error'>('disconnected');
  
  useEffect(() => {
    let ws: WebSocket | null = null;
    let reconnectTimer: NodeJS.Timeout | null = null;
    let heartbeatTimer: NodeJS.Timeout | null = null;
    
    const connect = () => {
      setConnectionStatus('connecting');
      // Use secure WebSocket URL from environment or build dynamically
      const wsProtocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
      const wsHost = process.env.REACT_APP_WS_URL || 
                     process.env.REACT_APP_API_URL?.replace(/^https?:/, wsProtocol) || 
                     `${wsProtocol}//${window.location.host}`;
      const wsUrl = `${wsHost}/ws`;
      
      ws = new WebSocket(wsUrl);
      
      ws.onopen = () => {
        setConnected(true);
        setConnectionStatus('connected');
        
        // Subscribe to payroll events
        const subscribeMessage = {
          type: 'subscribe',
          channel: 'payroll',
          ...(staffId && { filters: { staff_id: staffId } })
        };
        ws?.send(JSON.stringify(subscribeMessage));
        
        // Start heartbeat
        heartbeatTimer = setInterval(() => {
          if (ws?.readyState === WebSocket.OPEN) {
            ws.send(JSON.stringify({ type: 'ping' }));
          }
        }, 30000);
      };
      
      ws.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data);
          
          // Handle different message types
          if (data.type === 'pong') {
            // Heartbeat response
            return;
          }
          
          if (data.channel === 'payroll' && data.payload) {
            onUpdate({
              type: data.payload.type,
              payload: data.payload.data,
              timestamp: data.timestamp || new Date().toISOString()
            });
          }
        } catch (error) {
          console.warn('Failed to parse WebSocket message:', error);
        }
      };
      
      ws.onclose = (event) => {
        setConnected(false);
        
        if (event.wasClean) {
          setConnectionStatus('disconnected');
        } else {
          setConnectionStatus('error');
          // Attempt to reconnect after 5 seconds
          reconnectTimer = setTimeout(connect, 5000);
        }
        
        // Clear heartbeat
        if (heartbeatTimer) {
          clearInterval(heartbeatTimer);
        }
      };
      
      ws.onerror = () => {
        setConnectionStatus('error');
      };
    };
    
    connect();
    
    return () => {
      if (reconnectTimer) {
        clearTimeout(reconnectTimer);
      }
      if (heartbeatTimer) {
        clearInterval(heartbeatTimer);
      }
      if (ws) {
        ws.close(1000, 'Component unmounting');
      }
    };
  }, [onUpdate, staffId]);
  
  return { 
    connected, 
    connectionStatus,
    isReconnecting: connectionStatus === 'error'
  };
};