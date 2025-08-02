// frontend/components/sync/SyncStatusDashboard.tsx

import React, { useState, useEffect } from 'react';
import apiClient from '../../utils/authInterceptor';
import {
  RefreshCw, AlertCircle, CheckCircle, Clock,
  Wifi, WifiOff, AlertTriangle, Activity
} from 'lucide-react';

interface SyncStatus {
  sync_status_counts: Record<string, number>;
  unsynced_orders: number;
  pending_conflicts: number;
  last_batch?: {
    batch_id: string;
    started_at: string;
    completed_at?: string;
    successful_syncs: number;
    failed_syncs: number;
  };
  scheduler: {
    scheduler_running: boolean;
    jobs: Array<{
      id: string;
      name: string;
      next_run_time?: string;
    }>;
  };
  configuration: {
    sync_enabled: boolean;
    sync_interval_minutes: number;
    conflict_resolution_mode: string;
  };
}

interface SyncMetrics {
  total_synced_today: number;
  total_failed_today: number;
  average_sync_time_ms: number;
  sync_success_rate: number;
  pending_orders: number;
  retry_queue_size: number;
  conflict_rate: number;
  last_successful_batch?: string;
  next_scheduled_sync?: string;
}

export const SyncStatusDashboard: React.FC = () => {
  const [status, setStatus] = useState<SyncStatus | null>(null);
  const [metrics, setMetrics] = useState<SyncMetrics | null>(null);
  const [loading, setLoading] = useState(true);
  const [syncing, setSyncing] = useState(false);

  useEffect(() => {
    fetchSyncStatus();
    fetchSyncMetrics();
    
    // Poll for updates periodically
    const pollInterval = parseInt(process.env.REACT_APP_SYNC_DASHBOARD_POLL_SECONDS || '30') * 1000;
    const interval = setInterval(() => {
      fetchSyncStatus();
      fetchSyncMetrics();
    }, pollInterval);
    
    return () => clearInterval(interval);
  }, []);

  const fetchSyncStatus = async () => {
    try {
      const response = await apiClient.get('/api/orders/sync/status');
      setStatus(response.data);
    } catch (error) {
      console.error('Failed to fetch sync status:', error);
    } finally {
      setLoading(false);
    }
  };

  const fetchSyncMetrics = async () => {
    try {
      const response = await apiClient.get('/api/orders/sync/metrics');
      setMetrics(response.data);
    } catch (error) {
      console.error('Failed to fetch sync metrics:', error);
    }
  };

  const triggerManualSync = async () => {
    setSyncing(true);
    try {
      const response = await apiClient.post('/api/orders/sync/manual', {});
      
      if (response.status === 200) {
        // Refresh status after sync
        setTimeout(() => {
          fetchSyncStatus();
          fetchSyncMetrics();
        }, 2000);
      }
    } catch (error) {
      console.error('Failed to trigger sync:', error);
    } finally {
      setSyncing(false);
    }
  };

  const getSyncStatusIcon = (statusCounts: Record<string, number>) => {
    if (statusCounts.failed > 0) return <AlertCircle className="text-red-500" />;
    if (statusCounts.conflict > 0) return <AlertTriangle className="text-yellow-500" />;
    if (statusCounts.pending > 0) return <Clock className="text-blue-500" />;
    return <CheckCircle className="text-green-500" />;
  };

  const formatTime = (ms: number) => {
    if (ms < 1000) return `${ms.toFixed(0)}ms`;
    return `${(ms / 1000).toFixed(1)}s`;
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <RefreshCw className="animate-spin h-8 w-8 text-blue-500" />
      </div>
    );
  }

  return (
    <div className="p-6 space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center space-x-3">
          <Activity className="h-8 w-8 text-blue-600" />
          <h1 className="text-2xl font-bold">Order Sync Status</h1>
        </div>
        
        <button
          onClick={triggerManualSync}
          disabled={syncing}
          className="flex items-center space-x-2 px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50"
        >
          <RefreshCw className={`h-4 w-4 ${syncing ? 'animate-spin' : ''}`} />
          <span>{syncing ? 'Syncing...' : 'Sync Now'}</span>
        </button>
      </div>

      {/* Connection Status */}
      <div className="bg-white rounded-lg shadow p-6">
        <div className="flex items-center justify-between">
          <div className="flex items-center space-x-3">
            {status?.configuration.sync_enabled ? (
              <Wifi className="h-6 w-6 text-green-500" />
            ) : (
              <WifiOff className="h-6 w-6 text-red-500" />
            )}
            <div>
              <h3 className="font-semibold">Sync Status</h3>
              <p className="text-sm text-gray-600">
                {status?.configuration.sync_enabled ? 'Enabled' : 'Disabled'} •
                Every {status?.configuration.sync_interval_minutes} minutes
              </p>
            </div>
          </div>
          
          {status?.scheduler.scheduler_running && (
            <div className="text-sm text-gray-600">
              Next sync: {new Date(status.scheduler.jobs[0]?.next_run_time || '').toLocaleTimeString()}
            </div>
          )}
        </div>
      </div>

      {/* Metrics Overview */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <div className="bg-white rounded-lg shadow p-4">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm text-gray-600">Unsynced Orders</p>
              <p className="text-2xl font-bold">{status?.unsynced_orders || 0}</p>
            </div>
            <RefreshCw className="h-8 w-8 text-gray-400" />
          </div>
        </div>

        <div className="bg-white rounded-lg shadow p-4">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm text-gray-600">Success Rate</p>
              <p className="text-2xl font-bold">
                {metrics?.sync_success_rate.toFixed(1)}%
              </p>
            </div>
            <CheckCircle className="h-8 w-8 text-green-500" />
          </div>
        </div>

        <div className="bg-white rounded-lg shadow p-4">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm text-gray-600">Conflicts</p>
              <p className="text-2xl font-bold">{status?.pending_conflicts || 0}</p>
            </div>
            <AlertTriangle className="h-8 w-8 text-yellow-500" />
          </div>
        </div>

        <div className="bg-white rounded-lg shadow p-4">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm text-gray-600">Avg Sync Time</p>
              <p className="text-2xl font-bold">
                {formatTime(metrics?.average_sync_time_ms || 0)}
              </p>
            </div>
            <Clock className="h-8 w-8 text-blue-500" />
          </div>
        </div>
      </div>

      {/* Sync Details */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Today's Activity */}
        <div className="bg-white rounded-lg shadow p-6">
          <h3 className="font-semibold mb-4">Today's Activity</h3>
          <div className="space-y-3">
            <div className="flex justify-between">
              <span className="text-gray-600">Synced Successfully</span>
              <span className="font-medium text-green-600">
                {metrics?.total_synced_today || 0}
              </span>
            </div>
            <div className="flex justify-between">
              <span className="text-gray-600">Failed Syncs</span>
              <span className="font-medium text-red-600">
                {metrics?.total_failed_today || 0}
              </span>
            </div>
            <div className="flex justify-between">
              <span className="text-gray-600">Retry Queue</span>
              <span className="font-medium text-yellow-600">
                {metrics?.retry_queue_size || 0}
              </span>
            </div>
            <div className="flex justify-between">
              <span className="text-gray-600">Conflict Rate</span>
              <span className="font-medium">
                {metrics?.conflict_rate.toFixed(1)}%
              </span>
            </div>
          </div>
        </div>

        {/* Last Batch Info */}
        <div className="bg-white rounded-lg shadow p-6">
          <h3 className="font-semibold mb-4">Last Sync Batch</h3>
          {status?.last_batch ? (
            <div className="space-y-3">
              <div className="flex justify-between">
                <span className="text-gray-600">Batch ID</span>
                <span className="font-mono text-sm">
                  {status.last_batch.batch_id.slice(0, 8)}...
                </span>
              </div>
              <div className="flex justify-between">
                <span className="text-gray-600">Started</span>
                <span className="text-sm">
                  {new Date(status.last_batch.started_at).toLocaleTimeString()}
                </span>
              </div>
              <div className="flex justify-between">
                <span className="text-gray-600">Successful</span>
                <span className="font-medium text-green-600">
                  {status.last_batch.successful_syncs}
                </span>
              </div>
              <div className="flex justify-between">
                <span className="text-gray-600">Failed</span>
                <span className="font-medium text-red-600">
                  {status.last_batch.failed_syncs}
                </span>
              </div>
            </div>
          ) : (
            <p className="text-gray-500">No sync batches yet</p>
          )}
        </div>
      </div>

      {/* Sync Status by Type */}
      <div className="bg-white rounded-lg shadow p-6">
        <h3 className="font-semibold mb-4">Sync Queue Status</h3>
        <div className="grid grid-cols-2 md:grid-cols-6 gap-4">
          {Object.entries(status?.sync_status_counts || {}).map(([status, count]) => (
            <div key={status} className="text-center">
              <p className="text-sm text-gray-600 capitalize">{status}</p>
              <p className="text-xl font-bold">{count}</p>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
};