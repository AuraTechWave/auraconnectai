/**
 * Custom hook for interacting with the Payroll API
 * Provides methods for payroll operations with proper error handling and loading states
 */

import { useState, useCallback } from 'react';
import { apiClient } from '../utils/apiClient';
import { 
  PayrollHistory, 
  PayrollRunRequest, 
  PayrollRunResponse,
  PayrollDetail,
  PayrollRules 
} from '../types/payroll';

interface UsePayrollAPIReturn {
  loading: boolean;
  error: Error | null;
  getPayrollHistory: (staffId: number, tenantId?: number) => Promise<PayrollHistory[]>;
  runPayroll: (request: PayrollRunRequest) => Promise<PayrollRunResponse>;
  getPayrollDetail: (payrollId: number) => Promise<PayrollDetail>;
  getPayrollRules: () => Promise<PayrollRules>;
  checkJobStatus: (jobId: string) => Promise<any>;
  exportPayroll: (request: any) => Promise<any>;
}

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
    async (staffId: number, tenantId?: number): Promise<PayrollHistory[]> => {
      return handleRequest(async () => {
        const params = new URLSearchParams();
        if (tenantId) params.append('tenant_id', tenantId.toString());
        
        const response = await apiClient.get(
          `/api/v1/payrolls/${staffId}?${params.toString()}`
        );
        return response.data.payroll_history;
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
      return handleRequest(async () => {
        const response = await apiClient.get(`/api/v1/payrolls/${payrollId}/detail`);
        return response.data;
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

// WebSocket integration for real-time payroll updates
export const usePayrollWebSocket = (onUpdate: (event: any) => void) => {
  const [connected, setConnected] = useState(false);
  
  useEffect(() => {
    const ws = new WebSocket(process.env.REACT_APP_WS_URL || 'ws://localhost:8000/ws');
    
    ws.onopen = () => {
      setConnected(true);
      ws.send(JSON.stringify({ type: 'subscribe', channel: 'payroll' }));
    };
    
    ws.onmessage = (event) => {
      const data = JSON.parse(event.data);
      if (data.channel === 'payroll') {
        onUpdate(data);
      }
    };
    
    ws.onclose = () => {
      setConnected(false);
    };
    
    return () => {
      ws.close();
    };
  }, [onUpdate]);
  
  return { connected };
};