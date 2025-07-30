// frontend/components/webhooks/ExternalPOSWebhookDashboard.tsx

import React, { useState, useEffect } from 'react';
import {
  Webhook, Activity, AlertCircle, CheckCircle, Clock,
  RefreshCw, Settings, TrendingUp, AlertTriangle,
  CreditCard, DollarSign, Hash, Calendar
} from 'lucide-react';

interface WebhookProvider {
  provider_code: string;
  provider_name: string;
  webhook_url: string;
  is_active: boolean;
  recent_events: number;
  success_rate: number;
  status: 'healthy' | 'degraded' | 'unhealthy';
}

interface WebhookStatistics {
  provider_code: string;
  total_events: number;
  processed_events: number;
  failed_events: number;
  pending_events: number;
  duplicate_events: number;
  success_rate: number;
  average_processing_time_ms: number | null;
  last_event_at: string | null;
}

interface WebhookEvent {
  event_id: string;
  provider_code: string;
  event_type: string;
  processing_status: string;
  is_verified: boolean;
  created_at: string;
  processed_at: string | null;
}

interface WebhookHealth {
  status: 'healthy' | 'degraded' | 'unhealthy';
  providers: WebhookProvider[];
  retry_scheduler_status: {
    scheduler_running: boolean;
    jobs: Array<{ name: string; next_run_time: string | null }>;
  };
  recent_errors: Array<{
    message: string;
    occurred_at: string;
  }>;
  recommendations: string[];
}

export const ExternalPOSWebhookDashboard: React.FC = () => {
  const [health, setHealth] = useState<WebhookHealth | null>(null);
  const [statistics, setStatistics] = useState<WebhookStatistics[]>([]);
  const [recentEvents, setRecentEvents] = useState<WebhookEvent[]>([]);
  const [loading, setLoading] = useState(true);
  const [selectedProvider, setSelectedProvider] = useState<string | null>(null);
  const [refreshing, setRefreshing] = useState(false);

  useEffect(() => {
    fetchDashboardData();
    
    // Refresh every 30 seconds
    const interval = setInterval(fetchDashboardData, 30000);
    return () => clearInterval(interval);
  }, []);

  const fetchDashboardData = async () => {
    try {
      const headers = {
        'Authorization': `Bearer ${localStorage.getItem('token')}`
      };

      // Fetch health status
      const healthRes = await fetch('/api/webhooks/external-pos/monitoring/health', { headers });
      const healthData = await healthRes.json();
      setHealth(healthData);

      // Fetch statistics
      const statsRes = await fetch('/api/webhooks/external-pos/monitoring/statistics', { headers });
      const statsData = await statsRes.json();
      setStatistics(statsData);

      // Fetch recent events
      const eventsRes = await fetch('/api/webhooks/external-pos/monitoring/events?limit=10', { headers });
      const eventsData = await eventsRes.json();
      setRecentEvents(eventsData);

      setLoading(false);
    } catch (error) {
      console.error('Failed to fetch webhook dashboard data:', error);
      setLoading(false);
    }
  };

  const triggerRetry = async () => {
    setRefreshing(true);
    try {
      const response = await fetch('/api/webhooks/external-pos/monitoring/retry-failed', {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${localStorage.getItem('token')}`,
          'Content-Type': 'application/json'
        }
      });

      if (response.ok) {
        // Refresh data after retry
        setTimeout(fetchDashboardData, 2000);
      }
    } catch (error) {
      console.error('Failed to trigger retry:', error);
    } finally {
      setRefreshing(false);
    }
  };

  const getStatusIcon = (status: string) => {
    switch (status) {
      case 'healthy':
        return <CheckCircle className="text-green-500" />;
      case 'degraded':
        return <AlertTriangle className="text-yellow-500" />;
      case 'unhealthy':
        return <AlertCircle className="text-red-500" />;
      default:
        return <Clock className="text-gray-500" />;
    }
  };

  const getProcessingStatusBadge = (status: string) => {
    const statusStyles = {
      processed: 'bg-green-100 text-green-800',
      failed: 'bg-red-100 text-red-800',
      pending: 'bg-yellow-100 text-yellow-800',
      retry: 'bg-orange-100 text-orange-800',
      duplicate: 'bg-gray-100 text-gray-800'
    };

    return (
      <span className={`px-2 py-1 text-xs rounded-full ${statusStyles[status] || 'bg-gray-100 text-gray-800'}`}>
        {status}
      </span>
    );
  };

  const formatDuration = (ms: number | null) => {
    if (!ms) return '-';
    if (ms < 1000) return `${Math.round(ms)}ms`;
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
          <Webhook className="h-8 w-8 text-blue-600" />
          <h1 className="text-2xl font-bold">External POS Webhooks</h1>
        </div>
        
        <div className="flex space-x-3">
          <button
            onClick={triggerRetry}
            disabled={refreshing}
            className="flex items-center space-x-2 px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50"
          >
            <RefreshCw className={`h-4 w-4 ${refreshing ? 'animate-spin' : ''}`} />
            <span>Retry Failed</span>
          </button>
          
          <button className="flex items-center space-x-2 px-4 py-2 border border-gray-300 rounded-lg hover:bg-gray-50">
            <Settings className="h-4 w-4" />
            <span>Configure</span>
          </button>
        </div>
      </div>

      {/* Health Status */}
      {health && (
        <div className="bg-white rounded-lg shadow p-6">
          <div className="flex items-center justify-between mb-4">
            <div className="flex items-center space-x-3">
              {getStatusIcon(health.status)}
              <div>
                <h3 className="font-semibold">System Health</h3>
                <p className="text-sm text-gray-600 capitalize">{health.status}</p>
              </div>
            </div>
            
            <div className="text-sm text-gray-600">
              Scheduler: {health.retry_scheduler_status.scheduler_running ? (
                <span className="text-green-600">Running</span>
              ) : (
                <span className="text-red-600">Stopped</span>
              )}
            </div>
          </div>

          {/* Recommendations */}
          {health.recommendations.length > 0 && (
            <div className="mt-4 p-3 bg-yellow-50 rounded-lg">
              <p className="text-sm font-medium text-yellow-800 mb-1">Recommendations:</p>
              <ul className="text-sm text-yellow-700 space-y-1">
                {health.recommendations.map((rec, idx) => (
                  <li key={idx}>• {rec}</li>
                ))}
              </ul>
            </div>
          )}
        </div>
      )}

      {/* Provider Statistics */}
      <div className="grid grid-cols-1 lg:grid-cols-2 xl:grid-cols-4 gap-4">
        {statistics.map((stat) => {
          const provider = health?.providers.find(p => p.provider_code === stat.provider_code);
          
          return (
            <div 
              key={stat.provider_code}
              className="bg-white rounded-lg shadow p-4 cursor-pointer hover:shadow-lg transition-shadow"
              onClick={() => setSelectedProvider(stat.provider_code)}
            >
              <div className="flex items-center justify-between mb-3">
                <h4 className="font-semibold capitalize">{stat.provider_code}</h4>
                {provider && getStatusIcon(provider.status)}
              </div>
              
              <div className="space-y-2">
                <div className="flex justify-between text-sm">
                  <span className="text-gray-600">Total Events</span>
                  <span className="font-medium">{stat.total_events}</span>
                </div>
                
                <div className="flex justify-between text-sm">
                  <span className="text-gray-600">Success Rate</span>
                  <span className={`font-medium ${stat.success_rate >= 95 ? 'text-green-600' : stat.success_rate >= 80 ? 'text-yellow-600' : 'text-red-600'}`}>
                    {stat.success_rate.toFixed(1)}%
                  </span>
                </div>
                
                <div className="flex justify-between text-sm">
                  <span className="text-gray-600">Avg Time</span>
                  <span className="font-medium">{formatDuration(stat.average_processing_time_ms)}</span>
                </div>
                
                {stat.failed_events > 0 && (
                  <div className="flex justify-between text-sm">
                    <span className="text-gray-600">Failed</span>
                    <span className="font-medium text-red-600">{stat.failed_events}</span>
                  </div>
                )}
              </div>
              
              {stat.last_event_at && (
                <div className="mt-3 pt-3 border-t text-xs text-gray-500">
                  Last event: {new Date(stat.last_event_at).toLocaleTimeString()}
                </div>
              )}
            </div>
          );
        })}
      </div>

      {/* Recent Events */}
      <div className="bg-white rounded-lg shadow">
        <div className="p-6 border-b">
          <h3 className="font-semibold">Recent Webhook Events</h3>
        </div>
        
        <div className="overflow-x-auto">
          <table className="w-full">
            <thead className="bg-gray-50">
              <tr>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Provider</th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Event Type</th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Status</th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Verified</th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Created</th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Processed</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-200">
              {recentEvents.map((event) => (
                <tr key={event.event_id} className="hover:bg-gray-50">
                  <td className="px-6 py-4 whitespace-nowrap text-sm capitalize">
                    {event.provider_code}
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap text-sm">
                    {event.event_type}
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap">
                    {getProcessingStatusBadge(event.processing_status)}
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap">
                    {event.is_verified ? (
                      <CheckCircle className="h-4 w-4 text-green-500" />
                    ) : (
                      <AlertCircle className="h-4 w-4 text-red-500" />
                    )}
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-600">
                    {new Date(event.created_at).toLocaleTimeString()}
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-600">
                    {event.processed_at ? new Date(event.processed_at).toLocaleTimeString() : '-'}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          
          {recentEvents.length === 0 && (
            <div className="text-center py-8 text-gray-500">
              No webhook events found
            </div>
          )}
        </div>
      </div>

      {/* Recent Errors */}
      {health && health.recent_errors.length > 0 && (
        <div className="bg-white rounded-lg shadow p-6">
          <h3 className="font-semibold mb-4 text-red-600">Recent Errors</h3>
          <div className="space-y-2">
            {health.recent_errors.map((error, idx) => (
              <div key={idx} className="p-3 bg-red-50 rounded text-sm">
                <p className="text-red-800">{error.message}</p>
                <p className="text-red-600 text-xs mt-1">
                  {new Date(error.occurred_at).toLocaleString()}
                </p>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
};