import React, { useState, useEffect, useCallback } from 'react';
import apiClient from '../../utils/authInterceptor';
import './InventoryDashboard.css';

interface InventoryItem {
  id: number;
  item_name: string;
  sku: string;
  quantity: number;
  threshold: number;
  unit: string;
  category?: string;
  cost_per_unit?: number;
  vendor_id?: number;
  is_low_stock: boolean;
  last_updated: string;
}

interface InventoryAlert {
  id: number;
  inventory_id: number;
  alert_type: string;
  priority: 'low' | 'medium' | 'high' | 'critical';
  status: 'pending' | 'acknowledged' | 'resolved' | 'dismissed';
  title: string;
  message: string;
  threshold_value?: number;
  current_value?: number;
  created_at: string;
  inventory_item?: InventoryItem;
}

interface DashboardStats {
  total_items: number;
  low_stock_items: number;
  pending_alerts: number;
  categories: number;
  total_value: number;
  monthly_usage: number;
}

const InventoryDashboard: React.FC = () => {
  const [stats, setStats] = useState<DashboardStats | null>(null);
  const [alerts, setAlerts] = useState<InventoryAlert[]>([]);
  const [lowStockItems, setLowStockItems] = useState<InventoryItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selectedAlert, setSelectedAlert] = useState<InventoryAlert | null>(null);
  const [refreshInterval, setRefreshInterval] = useState<number | null>(null);

  const fetchDashboardData = useCallback(async () => {
    try {
      const [statsResponse, alertsResponse, lowStockResponse] = await Promise.all([
        apiClient.get('/inventory/dashboard'),
        apiClient.get('/inventory/alerts/active'),
        apiClient.get('/inventory/low-stock')
      ]);

      setStats(statsResponse.data);
      setAlerts(alertsResponse.data);
      setLowStockItems(lowStockResponse.data);
      setError(null);
    } catch (err: any) {
      console.error('Failed to fetch dashboard data:', err);
      setError(err.response?.data?.detail || 'Failed to load dashboard data');
    }
  }, []);

  const fetchAlerts = useCallback(async () => {
    try {
      const response = await apiClient.get('/inventory/alerts/active');
      setAlerts(response.data);
    } catch (err) {
      console.error('Failed to fetch alerts:', err);
    }
  }, []);

  useEffect(() => {
    const loadData = async () => {
      setLoading(true);
      await fetchDashboardData();
      setLoading(false);
    };

    loadData();

    // Set up auto-refresh for alerts every 30 seconds
    const interval = setInterval(fetchAlerts, 30000);
    setRefreshInterval(interval);

    return () => {
      if (interval) clearInterval(interval);
    };
  }, [fetchDashboardData, fetchAlerts]);

  const acknowledgeAlert = async (alertId: number, notes?: string) => {
    try {
      await apiClient.post(`/inventory/alerts/${alertId}/acknowledge`, null, {
        params: { notes }
      });
      await fetchAlerts();
    } catch (err: any) {
      console.error('Failed to acknowledge alert:', err);
      setError(err.response?.data?.detail || 'Failed to acknowledge alert');
    }
  };

  const resolveAlert = async (alertId: number, notes?: string) => {
    try {
      await apiClient.post(`/inventory/alerts/${alertId}/resolve`, null, {
        params: { notes }
      });
      await fetchAlerts();
    } catch (err: any) {
      console.error('Failed to resolve alert:', err);
      setError(err.response?.data?.detail || 'Failed to resolve alert');
    }
  };

  const getPriorityBadgeClass = (priority: string) => {
    switch (priority) {
      case 'critical': return 'priority-critical';
      case 'high': return 'priority-high';
      case 'medium': return 'priority-medium';
      case 'low': return 'priority-low';
      default: return 'priority-medium';
    }
  };

  const formatCurrency = (amount: number) => {
    return new Intl.NumberFormat('en-US', {
      style: 'currency',
      currency: 'USD'
    }).format(amount);
  };

  const formatDateTime = (dateString: string) => {
    return new Date(dateString).toLocaleString();
  };

  if (loading) {
    return (
      <div className="inventory-dashboard">
        <div className="loading-spinner">
          <div className="spinner"></div>
          <p>Loading inventory dashboard...</p>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="inventory-dashboard">
        <div className="error-message">
          <h3>Error Loading Dashboard</h3>
          <p>{error}</p>
          <button onClick={() => window.location.reload()} className="btn btn-primary">
            Retry
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="inventory-dashboard">
      <div className="dashboard-header">
        <h2>Inventory Management Dashboard</h2>
        <div className="refresh-controls">
          <span className="last-updated">
            Last updated: {new Date().toLocaleTimeString()}
          </span>
          <button 
            onClick={fetchDashboardData} 
            className="btn btn-sm btn-outline"
            title="Refresh data"
          >
            🔄 Refresh
          </button>
        </div>
      </div>

      {/* Dashboard Stats */}
      {stats && (
        <div className="stats-grid">
          <div className="stat-card">
            <div className="stat-icon">📦</div>
            <div className="stat-content">
              <h3>{stats.total_items}</h3>
              <p>Total Items</p>
            </div>
          </div>
          
          <div className="stat-card warning">
            <div className="stat-icon">⚠️</div>
            <div className="stat-content">
              <h3>{stats.low_stock_items}</h3>
              <p>Low Stock Items</p>
            </div>
          </div>
          
          <div className="stat-card danger">
            <div className="stat-icon">🚨</div>
            <div className="stat-content">
              <h3>{stats.pending_alerts}</h3>
              <p>Pending Alerts</p>
            </div>
          </div>
          
          <div className="stat-card">
            <div className="stat-icon">📊</div>
            <div className="stat-content">
              <h3>{stats.categories}</h3>
              <p>Categories</p>
            </div>
          </div>
          
          <div className="stat-card">
            <div className="stat-icon">💰</div>
            <div className="stat-content">
              <h3>{formatCurrency(stats.total_value)}</h3>
              <p>Total Value</p>
            </div>
          </div>
          
          <div className="stat-card">
            <div className="stat-icon">📈</div>
            <div className="stat-content">
              <h3>{formatCurrency(stats.monthly_usage)}</h3>
              <p>Monthly Usage</p>
            </div>
          </div>
        </div>
      )}

      <div className="dashboard-content">
        {/* Active Alerts */}
        <div className="dashboard-section">
          <div className="section-header">
            <h3>🚨 Active Alerts ({alerts.length})</h3>
            <span className="auto-refresh-indicator">
              Auto-refresh: 30s
            </span>
          </div>
          
          {alerts.length === 0 ? (
            <div className="empty-state">
              <p>✅ No active alerts</p>
            </div>
          ) : (
            <div className="alerts-list">
              {alerts.map(alert => (
                <div key={alert.id} className={`alert-card ${getPriorityBadgeClass(alert.priority)}`}>
                  <div className="alert-header">
                    <div className="alert-info">
                      <span className={`priority-badge ${getPriorityBadgeClass(alert.priority)}`}>
                        {alert.priority.toUpperCase()}
                      </span>
                      <h4>{alert.title}</h4>
                      <span className="alert-time">{formatDateTime(alert.created_at)}</span>
                    </div>
                    <div className="alert-actions">
                      {alert.status === 'pending' && (
                        <>
                          <button
                            onClick={() => acknowledgeAlert(alert.id)}
                            className="btn btn-sm btn-outline"
                            title="Acknowledge alert"
                          >
                            👍 Acknowledge
                          </button>
                          <button
                            onClick={() => resolveAlert(alert.id)}
                            className="btn btn-sm btn-success"
                            title="Resolve alert"
                          >
                            ✅ Resolve
                          </button>
                        </>
                      )}
                      {alert.status === 'acknowledged' && (
                        <button
                          onClick={() => resolveAlert(alert.id)}
                          className="btn btn-sm btn-success"
                          title="Resolve alert"
                        >
                          ✅ Resolve
                        </button>
                      )}
                    </div>
                  </div>
                  
                  <div className="alert-content">
                    <p>{alert.message}</p>
                    {alert.threshold_value && alert.current_value && (
                      <div className="alert-metrics">
                        <span>Current: {alert.current_value}</span>
                        <span>Threshold: {alert.threshold_value}</span>
                      </div>
                    )}
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Low Stock Items */}
        <div className="dashboard-section">
          <div className="section-header">
            <h3>📉 Low Stock Items ({lowStockItems.length})</h3>
          </div>
          
          {lowStockItems.length === 0 ? (
            <div className="empty-state">
              <p>✅ All items are adequately stocked</p>
            </div>
          ) : (
            <div className="low-stock-table">
              <table>
                <thead>
                  <tr>
                    <th>Item</th>
                    <th>SKU</th>
                    <th>Current Stock</th>
                    <th>Threshold</th>
                    <th>Category</th>
                    <th>Unit Cost</th>
                    <th>Status</th>
                  </tr>
                </thead>
                <tbody>
                  {lowStockItems.map(item => (
                    <tr key={item.id} className="low-stock-row">
                      <td>
                        <div className="item-info">
                          <strong>{item.item_name}</strong>
                        </div>
                      </td>
                      <td>{item.sku}</td>
                      <td>
                        <span className="quantity-display">
                          {item.quantity} {item.unit}
                        </span>
                      </td>
                      <td>
                        <span className="threshold-display">
                          {item.threshold} {item.unit}
                        </span>
                      </td>
                      <td>{item.category || 'Uncategorized'}</td>
                      <td>
                        {item.cost_per_unit ? formatCurrency(item.cost_per_unit) : 'N/A'}
                      </td>
                      <td>
                        <span className="status-badge critical">
                          Low Stock
                        </span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

export default InventoryDashboard;