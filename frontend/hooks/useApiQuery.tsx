import { useState, useEffect, useCallback, useRef } from 'react';
import apiClient from '../utils/authInterceptor';

interface QueryOptions {
  enabled?: boolean;
  refetchInterval?: number;
  staleTime?: number;
  cacheTime?: number;
  retry?: number;
  retryDelay?: number;
}

interface QueryResult<T> {
  data: T | null;
  loading: boolean;
  error: string | null;
  refetch: () => Promise<void>;
  isStale: boolean;
}

interface CacheEntry<T> {
  data: T;
  timestamp: number;
  isStale: boolean;
}

// Simple in-memory cache
const queryCache = new Map<string, CacheEntry<any>>();

// Default options
const defaultOptions: QueryOptions = {
  enabled: true,
  staleTime: 5 * 60 * 1000, // 5 minutes
  cacheTime: 10 * 60 * 1000, // 10 minutes
  retry: 3,
  retryDelay: 1000,
};

export function useApiQuery<T = any>(
  queryKey: string | string[],
  queryFn: () => Promise<T>,
  options: QueryOptions = {}
): QueryResult<T> {
  const opts = { ...defaultOptions, ...options };
  const cacheKey = Array.isArray(queryKey) ? queryKey.join(':') : queryKey;
  
  const [data, setData] = useState<T | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [isStale, setIsStale] = useState(false);
  
  const retryCountRef = useRef(0);
  const intervalRef = useRef<NodeJS.Timeout | null>(null);
  const mountedRef = useRef(true);

  useEffect(() => {
    mountedRef.current = true;
    return () => {
      mountedRef.current = false;
      if (intervalRef.current) {
        clearInterval(intervalRef.current);
      }
    };
  }, []);

  const executeQuery = useCallback(async (isRetry = false) => {
    if (!opts.enabled) return;

    // Check cache first
    const cached = queryCache.get(cacheKey);
    if (cached && !isRetry) {
      const age = Date.now() - cached.timestamp;
      if (age < opts.staleTime!) {
        setData(cached.data);
        setIsStale(false);
        setError(null);
        return;
      } else if (age < opts.cacheTime!) {
        // Use stale data while fetching fresh data
        setData(cached.data);
        setIsStale(true);
        setError(null);
      }
    }

    try {
      if (!cached || isRetry) {
        setLoading(true);
      }
      
      const result = await queryFn();
      
      if (!mountedRef.current) return;

      // Update cache
      queryCache.set(cacheKey, {
        data: result,
        timestamp: Date.now(),
        isStale: false,
      });

      setData(result);
      setIsStale(false);
      setError(null);
      retryCountRef.current = 0;
    } catch (err: any) {
      if (!mountedRef.current) return;

      const errorMessage = err.response?.data?.detail || err.message || 'An error occurred';
      
      // Only set error if we don't have cached data
      if (!cached) {
        setError(errorMessage);
      }

      // Retry logic
      if (retryCountRef.current < opts.retry!) {
        retryCountRef.current++;
        setTimeout(() => {
          if (mountedRef.current) {
            executeQuery(true);
          }
        }, opts.retryDelay! * retryCountRef.current);
      }
    } finally {
      if (mountedRef.current) {
        setLoading(false);
      }
    }
  }, [cacheKey, queryFn, opts.enabled, opts.staleTime, opts.cacheTime, opts.retry, opts.retryDelay]);

  const refetch = useCallback(async () => {
    await executeQuery(true);
  }, [executeQuery]);

  useEffect(() => {
    executeQuery();
  }, [executeQuery]);

  // Set up auto-refetch interval
  useEffect(() => {
    if (opts.refetchInterval && opts.refetchInterval > 0) {
      intervalRef.current = setInterval(() => {
        executeQuery(true);
      }, opts.refetchInterval);

      return () => {
        if (intervalRef.current) {
          clearInterval(intervalRef.current);
        }
      };
    }
  }, [opts.refetchInterval, executeQuery]);

  return {
    data,
    loading,
    error,
    refetch,
    isStale,
  };
}

// Mutation hook for POST/PUT/DELETE operations
interface MutationOptions<TData, TVariables> {
  onSuccess?: (data: TData, variables: TVariables) => void;
  onError?: (error: any, variables: TVariables) => void;
  onSettled?: (data: TData | undefined, error: any, variables: TVariables) => void;
}

interface MutationResult<TData, TVariables> {
  mutate: (variables: TVariables) => Promise<TData>;
  loading: boolean;
  error: string | null;
  data: TData | null;
  reset: () => void;
}

export function useApiMutation<TData = any, TVariables = any>(
  mutationFn: (variables: TVariables) => Promise<TData>,
  options: MutationOptions<TData, TVariables> = {}
): MutationResult<TData, TVariables> {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [data, setData] = useState<TData | null>(null);

  const mutate = useCallback(async (variables: TVariables): Promise<TData> => {
    try {
      setLoading(true);
      setError(null);
      
      const result = await mutationFn(variables);
      setData(result);
      
      options.onSuccess?.(result, variables);
      options.onSettled?.(result, null, variables);
      
      return result;
    } catch (err: any) {
      const errorMessage = err.response?.data?.detail || err.message || 'An error occurred';
      setError(errorMessage);
      
      options.onError?.(err, variables);
      options.onSettled?.(undefined, err, variables);
      
      throw err;
    } finally {
      setLoading(false);
    }
  }, [mutationFn, options]);

  const reset = useCallback(() => {
    setLoading(false);
    setError(null);
    setData(null);
  }, []);

  return {
    mutate,
    loading,
    error,
    data,
    reset,
  };
}

// Utility function to invalidate cache entries
export function invalidateQuery(queryKey: string | string[]) {
  const cacheKey = Array.isArray(queryKey) ? queryKey.join(':') : queryKey;
  queryCache.delete(cacheKey);
}

// Utility function to invalidate all cache entries matching a pattern
export function invalidateQueries(pattern: string) {
  for (const key of queryCache.keys()) {
    if (key.includes(pattern)) {
      queryCache.delete(key);
    }
  }
}

// Utility function to get cached data
export function getQueryData<T>(queryKey: string | string[]): T | null {
  const cacheKey = Array.isArray(queryKey) ? queryKey.join(':') : queryKey;
  const cached = queryCache.get(cacheKey);
  return cached ? cached.data : null;
}

// Utility function to set cached data
export function setQueryData<T>(queryKey: string | string[], data: T) {
  const cacheKey = Array.isArray(queryKey) ? queryKey.join(':') : queryKey;
  queryCache.set(cacheKey, {
    data,
    timestamp: Date.now(),
    isStale: false,
  });
}