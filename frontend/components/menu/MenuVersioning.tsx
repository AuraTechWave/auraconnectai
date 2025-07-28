import React, { useState, useEffect } from 'react';
import apiClient from '../../utils/authInterceptor';
import { useRBAC } from '../../hooks/useRBAC';
import { useNotifications } from '../ui/Notification';
import { useApiQuery, invalidateQueries } from '../../hooks/useApiQuery';
import VirtualizedTable from '../ui/VirtualizedTable';
import '../ui/SharedStyles.css';
import './MenuVersioning.css';

interface MenuVersion {
  id: number;
  version_number: string;
  version_name?: string;
  description?: string;
  version_type: 'manual' | 'scheduled' | 'rollback' | 'migration' | 'auto_save';
  is_active: boolean;
  is_published: boolean;
  published_at?: string;
  scheduled_publish_at?: string;
  created_by: number;
  total_items: number;
  total_categories: number;
  total_modifiers: number;
  changes_summary?: Record<string, any>;
  parent_version_id?: number;
  created_at: string;
  updated_at: string;
}

interface VersionComparison {
  from_version_id: number;
  to_version_id: number;
  from_version_number: string;
  to_version_number: string;
  summary: Record<string, number>;
  categories: any[];
  items: any[];
  modifiers: any[];
  generated_at: string;
}

interface AuditLog {
  id: number;
  action: string;
  entity_type: string;
  entity_name?: string;
  change_type: string;
  change_summary?: string;
  user_id: number;
  created_at: string;
}

const MenuVersioning: React.FC = () => {
  const { hasPermission } = useRBAC();
  const { addNotification, NotificationContainer } = useNotifications();
  
  // States
  const [activeTab, setActiveTab] = useState<'versions' | 'comparison' | 'audit'>('versions');
  const [selectedVersions, setSelectedVersions] = useState<number[]>([]);
  const [showCreateForm, setShowCreateForm] = useState(false);
  const [showCompareModal, setShowCompareModal] = useState(false);
  const [comparisonResult, setComparisonResult] = useState<VersionComparison | null>(null);
  
  // Form states
  const [newVersionForm, setNewVersionForm] = useState({
    version_name: '',
    description: '',
    version_type: 'manual' as const,
    include_inactive: false,
    scheduled_publish_at: ''
  });

  // Permissions
  const canCreateVersions = hasPermission('menu:create');
  const canPublishVersions = hasPermission('menu:update');
  const canDeleteVersions = hasPermission('menu:delete');

  // API queries
  const {
    data: versionsData,
    loading: versionsLoading,
    error: versionsError,
    refetch: refetchVersions
  } = useApiQuery(['menu-versions'], () => apiClient.get('/menu/versions').then(res => res.data));

  const {
    data: auditLogs,
    loading: auditLoading,
    error: auditError,
    refetch: refetchAudit
  } = useApiQuery(['menu-audit'], () => apiClient.get('/menu/versions/audit/logs').then(res => res.data));

  const {
    data: versionStats,
    loading: statsLoading
  } = useApiQuery(['version-stats'], () => apiClient.get('/menu/versions/stats').then(res => res.data));

  // Create new version
  const handleCreateVersion = async () => {
    if (!canCreateVersions) {
      addNotification({ type: 'error', message: 'You do not have permission to create versions' });
      return;
    }

    try {
      const payload = {
        ...newVersionForm,
        scheduled_publish_at: newVersionForm.scheduled_publish_at || null
      };

      await apiClient.post('/menu/versions', payload);
      
      addNotification({
        type: 'success',
        message: `Version "${newVersionForm.version_name || 'New Version'}" created successfully`
      });
      
      setShowCreateForm(false);
      setNewVersionForm({
        version_name: '',
        description: '',
        version_type: 'manual',
        include_inactive: false,
        scheduled_publish_at: ''
      });
      
      refetchVersions();
      invalidateQueries(['version-stats']);
      
    } catch (error: any) {
      addNotification({
        type: 'error',
        message: error.response?.data?.detail || 'Failed to create version'
      });
    }
  };

  // Publish version
  const handlePublishVersion = async (versionId: number, scheduled?: boolean) => {
    if (!canPublishVersions) {
      addNotification({ type: 'error', message: 'You do not have permission to publish versions' });
      return;
    }

    try {
      const payload = {
        scheduled_at: scheduled ? newVersionForm.scheduled_publish_at || null : null,
        force: false
      };

      await apiClient.post(`/menu/versions/${versionId}/publish`, payload);
      
      addNotification({
        type: 'success',
        message: scheduled ? 'Version scheduled for publication' : 'Version published successfully'
      });
      
      refetchVersions();
      invalidateQueries(['version-stats']);
      
    } catch (error: any) {
      addNotification({
        type: 'error',
        message: error.response?.data?.detail || 'Failed to publish version'
      });
    }
  };

  // Compare versions
  const handleCompareVersions = async () => {
    if (selectedVersions.length !== 2) {
      addNotification({ type: 'error', message: 'Please select exactly 2 versions to compare' });
      return;
    }

    try {
      const response = await apiClient.post('/menu/versions/compare', {
        from_version_id: selectedVersions[0],
        to_version_id: selectedVersions[1],
        include_details: true
      });
      
      setComparisonResult(response.data);
      setShowCompareModal(true);
      
    } catch (error: any) {
      addNotification({
        type: 'error',
        message: error.response?.data?.detail || 'Failed to compare versions'
      });
    }
  };

  // Rollback to version
  const handleRollback = async (versionId: number) => {
    if (!canPublishVersions) {
      addNotification({ type: 'error', message: 'You do not have permission to rollback versions' });
      return;
    }

    const reason = prompt('Please provide a reason for the rollback:');
    if (!reason) return;

    try {
      await apiClient.post('/menu/versions/rollback', {
        target_version_id: versionId,
        create_backup: true,
        rollback_reason: reason
      });
      
      addNotification({
        type: 'success',
        message: 'Successfully rolled back to selected version'
      });
      
      refetchVersions();
      invalidateQueries(['version-stats']);
      
    } catch (error: any) {
      addNotification({
        type: 'error',
        message: error.response?.data?.detail || 'Failed to rollback version'
      });
    }
  };

  // Delete version
  const handleDeleteVersion = async (versionId: number) => {
    if (!canDeleteVersions) {
      addNotification({ type: 'error', message: 'You do not have permission to delete versions' });
      return;
    }

    if (!confirm('Are you sure you want to delete this version? This action cannot be undone.')) {
      return;
    }

    try {
      await apiClient.delete(`/menu/versions/${versionId}`);
      
      addNotification({
        type: 'success',
        message: 'Version deleted successfully'
      });
      
      refetchVersions();
      invalidateQueries(['version-stats']);
      
    } catch (error: any) {
      addNotification({
        type: 'error',
        message: error.response?.data?.detail || 'Failed to delete version'
      });
    }
  };

  // Version table columns
  const versionColumns = [
    {
      key: 'version_number',
      label: 'Version',
      render: (version: MenuVersion) => (
        <div className="version-info">
          <span className="version-number">{version.version_number}</span>
          {version.version_name && (
            <span className="version-name">{version.version_name}</span>
          )}
          <div className="version-badges">
            {version.is_active && <span className="badge active">Active</span>}
            {version.is_published && <span className="badge published">Published</span>}
            <span className={`badge type-${version.version_type}`}>
              {version.version_type}
            </span>
          </div>
        </div>
      )
    },
    {
      key: 'content',
      label: 'Content',
      render: (version: MenuVersion) => (
        <div className="content-summary">
          <span>{version.total_categories} categories</span>
          <span>{version.total_items} items</span>
          <span>{version.total_modifiers} modifiers</span>
        </div>
      )
    },
    {
      key: 'dates',
      label: 'Dates',
      render: (version: MenuVersion) => (
        <div className="version-dates">
          <div>Created: {new Date(version.created_at).toLocaleDateString()}</div>
          {version.published_at && (
            <div>Published: {new Date(version.published_at).toLocaleDateString()}</div>
          )}
          {version.scheduled_publish_at && (
            <div>Scheduled: {new Date(version.scheduled_publish_at).toLocaleDateString()}</div>
          )}
        </div>
      )
    },
    {
      key: 'actions',
      label: 'Actions',
      render: (version: MenuVersion) => (
        <div className="version-actions">
          <input
            type="checkbox"
            checked={selectedVersions.includes(version.id)}
            onChange={(e) => {
              if (e.target.checked) {
                setSelectedVersions([...selectedVersions, version.id]);
              } else {
                setSelectedVersions(selectedVersions.filter(id => id !== version.id));
              }
            }}
          />
          
          {!version.is_published && canPublishVersions && (
            <button
              className="btn btn-sm btn-primary"
              onClick={() => handlePublishVersion(version.id)}
            >
              Publish
            </button>
          )}
          
          {!version.is_active && canPublishVersions && (
            <button
              className="btn btn-sm btn-secondary"
              onClick={() => handleRollback(version.id)}
            >
              Rollback
            </button>
          )}
          
          {!version.is_active && !version.is_published && canDeleteVersions && (
            <button
              className="btn btn-sm btn-danger"
              onClick={() => handleDeleteVersion(version.id)}
            >
              Delete
            </button>
          )}
        </div>
      )
    }
  ];

  // Audit log columns
  const auditColumns = [
    {
      key: 'timestamp',
      label: 'Time',
      render: (log: AuditLog) => (
        <div className="audit-timestamp">
          {new Date(log.created_at).toLocaleString()}
        </div>
      )
    },
    {
      key: 'action',
      label: 'Action',
      render: (log: AuditLog) => (
        <div className="audit-action">
          <span className={`action-badge ${log.change_type}`}>
            {log.action}
          </span>
          <span className="entity-type">{log.entity_type}</span>
        </div>
      )
    },
    {
      key: 'details',
      label: 'Details',
      render: (log: AuditLog) => (
        <div className="audit-details">
          {log.entity_name && <div className="entity-name">{log.entity_name}</div>}
          {log.change_summary && <div className="change-summary">{log.change_summary}</div>}
        </div>
      )
    },
    {
      key: 'user',
      label: 'User',
      render: (log: AuditLog) => (
        <div className="audit-user">
          User ID: {log.user_id}
        </div>
      )
    }
  ];

  if (versionsLoading) {
    return <div className="loading">Loading menu versions...</div>;
  }

  return (
    <div className="menu-versioning">
      <div className="versioning-header">
        <h2>Menu Versioning & Audit Trail</h2>
        
        {versionStats && (
          <div className="version-stats">
            <div className="stat-card">
              <h3>{versionStats.total_versions}</h3>
              <span>Total Versions</span>
            </div>
            <div className="stat-card">
              <h3>{versionStats.published_versions}</h3>
              <span>Published</span>
            </div>
            <div className="stat-card">
              <h3>{versionStats.draft_versions}</h3>
              <span>Drafts</span>
            </div>
            <div className="stat-card">
              <h3>{versionStats.total_changes_today}</h3>
              <span>Changes Today</span>
            </div>
          </div>
        )}
      </div>

      <div className="versioning-tabs">
        <button
          className={`tab ${activeTab === 'versions' ? 'active' : ''}`}
          onClick={() => setActiveTab('versions')}
        >
          Versions
        </button>
        <button
          className={`tab ${activeTab === 'comparison' ? 'active' : ''}`}
          onClick={() => setActiveTab('comparison')}
        >
          Comparison
        </button>
        <button
          className={`tab ${activeTab === 'audit' ? 'active' : ''}`}
          onClick={() => setActiveTab('audit')}
        >
          Audit Trail
        </button>
      </div>

      <div className="versioning-content">
        {activeTab === 'versions' && (
          <div className="versions-tab">
            <div className="versions-controls">
              {canCreateVersions && (
                <button
                  className="btn btn-primary"
                  onClick={() => setShowCreateForm(true)}
                >
                  Create Version
                </button>
              )}
              
              {selectedVersions.length === 2 && (
                <button
                  className="btn btn-secondary"
                  onClick={handleCompareVersions}
                >
                  Compare Selected
                </button>
              )}
              
              <div className="selection-info">
                {selectedVersions.length > 0 && (
                  <span>{selectedVersions.length} version(s) selected</span>
                )}
              </div>
            </div>

            {versionsData && (
              <VirtualizedTable
                data={versionsData.items || []}
                columns={versionColumns}
                height={600}
                itemHeight={120}
              />
            )}
          </div>
        )}

        {activeTab === 'comparison' && (
          <div className="comparison-tab">
            {comparisonResult ? (
              <div className="comparison-result">
                <h3>
                  Comparing {comparisonResult.from_version_number} → {comparisonResult.to_version_number}
                </h3>
                
                <div className="comparison-summary">
                  <div className="summary-stats">
                    {Object.entries(comparisonResult.summary).map(([type, count]) => (
                      <div key={type} className="summary-stat">
                        <span className="count">{count}</span>
                        <span className="type">{type}</span>
                      </div>
                    ))}
                  </div>
                </div>

                <div className="comparison-details">
                  {comparisonResult.categories.length > 0 && (
                    <div className="change-section">
                      <h4>Category Changes ({comparisonResult.categories.length})</h4>
                      {/* Render category changes */}
                    </div>
                  )}
                  
                  {comparisonResult.items.length > 0 && (
                    <div className="change-section">
                      <h4>Item Changes ({comparisonResult.items.length})</h4>
                      {/* Render item changes */}
                    </div>
                  )}
                  
                  {comparisonResult.modifiers.length > 0 && (
                    <div className="change-section">
                      <h4>Modifier Changes ({comparisonResult.modifiers.length})</h4>
                      {/* Render modifier changes */}
                    </div>
                  )}
                </div>
              </div>
            ) : (
              <div className="comparison-empty">
                <p>Select two versions from the Versions tab to compare them.</p>
              </div>
            )}
          </div>
        )}

        {activeTab === 'audit' && (
          <div className="audit-tab">
            {auditLogs && (
              <VirtualizedTable
                data={auditLogs.items || []}
                columns={auditColumns}
                height={600}
                itemHeight={80}
              />
            )}
          </div>
        )}
      </div>

      {/* Create Version Modal */}
      {showCreateForm && (
        <div className="modal-overlay">
          <div className="modal">
            <div className="modal-header">
              <h3>Create New Version</h3>
              <button
                className="close-btn"
                onClick={() => setShowCreateForm(false)}
              >
                ×
              </button>
            </div>
            
            <div className="modal-body">
              <div className="form-group">
                <label>Version Name</label>
                <input
                  type="text"
                  value={newVersionForm.version_name}
                  onChange={(e) => setNewVersionForm({
                    ...newVersionForm,
                    version_name: e.target.value
                  })}
                  placeholder="Optional descriptive name"
                />
              </div>
              
              <div className="form-group">
                <label>Description</label>
                <textarea
                  value={newVersionForm.description}
                  onChange={(e) => setNewVersionForm({
                    ...newVersionForm,
                    description: e.target.value
                  })}
                  placeholder="Describe the changes in this version"
                  rows={3}
                />
              </div>
              
              <div className="form-group">
                <label>Version Type</label>
                <select
                  value={newVersionForm.version_type}
                  onChange={(e) => setNewVersionForm({
                    ...newVersionForm,
                    version_type: e.target.value as any
                  })}
                >
                  <option value="manual">Manual</option>
                  <option value="scheduled">Scheduled</option>
                  <option value="auto_save">Auto Save</option>
                </select>
              </div>
              
              <div className="form-group">
                <label className="checkbox-label">
                  <input
                    type="checkbox"
                    checked={newVersionForm.include_inactive}
                    onChange={(e) => setNewVersionForm({
                      ...newVersionForm,
                      include_inactive: e.target.checked
                    })}
                  />
                  Include inactive items
                </label>
              </div>
              
              {newVersionForm.version_type === 'scheduled' && (
                <div className="form-group">
                  <label>Scheduled Publish Time</label>
                  <input
                    type="datetime-local"
                    value={newVersionForm.scheduled_publish_at}
                    onChange={(e) => setNewVersionForm({
                      ...newVersionForm,
                      scheduled_publish_at: e.target.value
                    })}
                  />
                </div>
              )}
            </div>
            
            <div className="modal-footer">
              <button
                className="btn btn-secondary"
                onClick={() => setShowCreateForm(false)}
              >
                Cancel
              </button>
              <button
                className="btn btn-primary"
                onClick={handleCreateVersion}
              >
                Create Version
              </button>
            </div>
          </div>
        </div>
      )}

      <NotificationContainer />
    </div>
  );
};

export default MenuVersioning;