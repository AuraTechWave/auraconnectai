import React, { useState, useEffect } from 'react';
import { useRBAC } from '../../hooks/useRBAC';
import MenuCategoryManagement from '../../components/menu/MenuCategoryManagement';
import MenuItemManagement from '../../components/menu/MenuItemManagement';
import ModifierManagement from '../../components/menu/ModifierManagement';
import { apiClient } from '../../utils/apiClient';
import './MenuDashboard.css';

interface MenuStats {
  total_categories: number;
  total_items: number;
  available_items: number;
  unavailable_items: number;
  total_modifiers: number;
}

const MenuDashboard: React.FC = () => {
  const { hasPermission } = useRBAC();
  const [activeTab, setActiveTab] = useState<'categories' | 'items' | 'modifiers' | 'overview'>('overview');
  const [stats, setStats] = useState<MenuStats | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (activeTab === 'overview') {
      fetchStats();
    }
  }, [activeTab]);

  const fetchStats = async () => {
    setLoading(true);
    setError(null);
    try {
      const response = await apiClient.get('/menu/stats');
      setStats(response.data);
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to fetch menu statistics');
    } finally {
      setLoading(false);
    }
  };

  // Check permissions
  const canRead = hasPermission('menu:read');
  const canCreate = hasPermission('menu:create');
  const canUpdate = hasPermission('menu:update');
  const canDelete = hasPermission('menu:delete');

  if (!canRead) {
    return (
      <div className="menu-dashboard">
        <div className="access-denied">
          <h2>Access Denied</h2>
          <p>You don't have permission to access the menu management system.</p>
        </div>
      </div>
    );
  }

  const tabs = [
    { id: 'overview', label: 'Overview', icon: '📊' },
    { id: 'categories', label: 'Categories', icon: '📂' },
    { id: 'items', label: 'Menu Items', icon: '🍽️' },
    { id: 'modifiers', label: 'Modifiers', icon: '⚙️' }
  ];

  return (
    <div className="menu-dashboard">
      <div className="dashboard-header">
        <h1>Menu Management</h1>
        <p>Manage your restaurant's menu categories, items, and modifiers</p>
      </div>

      <nav className="dashboard-nav">
        {tabs.map(tab => (
          <button
            key={tab.id}
            className={`nav-tab ${activeTab === tab.id ? 'active' : ''}`}
            onClick={() => setActiveTab(tab.id as any)}
          >
            <span className="tab-icon">{tab.icon}</span>
            <span className="tab-label">{tab.label}</span>
          </button>
        ))}
      </nav>

      <div className="dashboard-content">
        {activeTab === 'overview' && (
          <div className="overview-section">
            <h2>Menu Overview</h2>
            
            {error && (
              <div className="alert alert-error">
                {error}
              </div>
            )}

            {loading ? (
              <div className="loading">Loading statistics...</div>
            ) : stats ? (
              <div className="stats-grid">
                <div className="stat-card">
                  <div className="stat-icon">📂</div>
                  <div className="stat-content">
                    <h3>Categories</h3>
                    <div className="stat-number">{stats.total_categories}</div>
                    <div className="stat-label">Total categories</div>
                  </div>
                </div>

                <div className="stat-card">
                  <div className="stat-icon">🍽️</div>
                  <div className="stat-content">
                    <h3>Menu Items</h3>
                    <div className="stat-number">{stats.total_items}</div>
                    <div className="stat-label">Total items</div>
                  </div>
                </div>

                <div className="stat-card">
                  <div className="stat-icon">✅</div>
                  <div className="stat-content">
                    <h3>Available</h3>
                    <div className="stat-number">{stats.available_items}</div>
                    <div className="stat-label">Available items</div>
                  </div>
                </div>

                <div className="stat-card">
                  <div className="stat-icon">❌</div>
                  <div className="stat-content">
                    <h3>Unavailable</h3>
                    <div className="stat-number">{stats.unavailable_items}</div>
                    <div className="stat-label">Unavailable items</div>
                  </div>
                </div>

                <div className="stat-card">
                  <div className="stat-icon">⚙️</div>
                  <div className="stat-content">
                    <h3>Modifiers</h3>
                    <div className="stat-number">{stats.total_modifiers}</div>
                    <div className="stat-label">Total modifiers</div>
                  </div>
                </div>
              </div>
            ) : (
              <div className="empty-state">
                <p>No statistics available</p>
              </div>
            )}

            <div className="overview-actions">
              <h3>Quick Actions</h3>
              <div className="action-grid">
                {canCreate && (
                  <>
                    <button 
                      className="action-card"
                      onClick={() => setActiveTab('categories')}
                    >
                      <div className="action-icon">📂</div>
                      <div className="action-content">
                        <h4>Add Category</h4>
                        <p>Create a new menu category</p>
                      </div>
                    </button>

                    <button 
                      className="action-card"
                      onClick={() => setActiveTab('items')}
                    >
                      <div className="action-icon">🍽️</div>
                      <div className="action-content">
                        <h4>Add Menu Item</h4>
                        <p>Create a new menu item</p>
                      </div>
                    </button>

                    <button 
                      className="action-card"
                      onClick={() => setActiveTab('modifiers')}
                    >
                      <div className="action-icon">⚙️</div>
                      <div className="action-content">
                        <h4>Add Modifier</h4>
                        <p>Create new modifiers and groups</p>
                      </div>
                    </button>
                  </>
                )}

                <button 
                  className="action-card"
                  onClick={fetchStats}
                  disabled={loading}
                >
                  <div className="action-icon">🔄</div>
                  <div className="action-content">
                    <h4>Refresh Stats</h4>
                    <p>Update menu statistics</p>
                  </div>
                </button>
              </div>
            </div>

            <div className="overview-tips">
              <h3>Menu Management Tips</h3>
              <div className="tips-grid">
                <div className="tip-card">
                  <div className="tip-icon">💡</div>
                  <div className="tip-content">
                    <h4>Organization</h4>
                    <p>Use categories to organize your menu items logically. Create subcategories for better navigation.</p>
                  </div>
                </div>

                <div className="tip-card">
                  <div className="tip-icon">💰</div>
                  <div className="tip-content">
                    <h4>Pricing</h4>
                    <p>Use modifiers to offer size options, add-ons, and customizations that can increase order value.</p>
                  </div>
                </div>

                <div className="tip-card">
                  <div className="tip-icon">📱</div>
                  <div className="tip-content">
                    <h4>Availability</h4>
                    <p>Set time-based availability for items like breakfast or happy hour specials.</p>
                  </div>
                </div>

                <div className="tip-card">
                  <div className="tip-icon">🏷️</div>
                  <div className="tip-content">
                    <h4>Dietary Tags</h4>
                    <p>Use dietary tags and allergen information to help customers make informed choices.</p>
                  </div>
                </div>
              </div>
            </div>
          </div>
        )}

        {activeTab === 'categories' && <MenuCategoryManagement />}
        {activeTab === 'items' && <MenuItemManagement />}
        {activeTab === 'modifiers' && <ModifierManagement />}
      </div>

      {!canCreate && !canUpdate && !canDelete && (
        <div className="readonly-notice">
          <p>
            ℹ️ You have read-only access to the menu management system. 
            Contact your administrator for write permissions.
          </p>
        </div>
      )}
    </div>
  );
};

export default MenuDashboard;