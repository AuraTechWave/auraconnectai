import React, { useState, useEffect } from 'react';
import apiClient from '../../utils/authInterceptor';
import { useRBAC } from '../../hooks/useRBAC';
import SearchFilter from './SearchFilter';
import './AuditLog.css';

interface AuditLogEntry {
  id: number;
  action: string;
  entity_type: string;
  entity_id?: number;
  details?: string;
  performed_by_user_id: number;
  performed_by_username: string;
  tenant_id?: number;
  created_at: string;
}

type FilterType = 'all' | 'user_management' | 'role_management' | 'permission_changes';

const AuditLog: React.FC = () => {
  const { hasPermission } = useRBAC();
  const [logs, setLogs] = useState<AuditLogEntry[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [searchTerm, setSearchTerm] = useState('');
  const [filterType, setFilterType] = useState<FilterType>('all');
  const [currentPage, setCurrentPage] = useState(1);
  const [totalPages, setTotalPages] = useState(1);
  const [dateRange, setDateRange] = useState({
    start: '',
    end: ''
  });

  const canViewAudit = hasPermission('system:audit');

  useEffect(() => {
    if (canViewAudit) {
      fetchAuditLogs();
    }
  }, [currentPage, searchTerm, filterType, dateRange, canViewAudit]);

  const fetchAuditLogs = async () => {
    try {
      setLoading(true);
      const params = new URLSearchParams({
        page: currentPage.toString(),
        page_size: '50',
        ...(searchTerm && { search: searchTerm }),
        ...(filterType !== 'all' && { entity_type: filterType }),
        ...(dateRange.start && { start_date: dateRange.start }),
        ...(dateRange.end && { end_date: dateRange.end })
      });

      const response = await apiClient.get(`/rbac/audit-logs?${params}`);
      
      setLogs(response.data.entries);
      setTotalPages(Math.ceil(response.data.total_count / response.data.page_size));
      setError(null);
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to fetch audit logs');
      setLogs([]);
      setTotalPages(1);
    } finally {
      setLoading(false);
    }
  };

  const formatTimestamp = (timestamp: string) => {
    return new Date(timestamp).toLocaleString();
  };

  const getActionIcon = (action: string) => {
    switch (action) {
      case 'create_user':
      case 'create_role':
        return '➕';
      case 'update_user':
      case 'update_role':
        return '✏️';
      case 'delete_user':
      case 'delete_role':
        return '🗑️';
      case 'assign_role':
      case 'assign_permission':
        return '🔗';
      case 'remove_role':
      case 'remove_permission':
        return '❌';
      case 'login':
        return '🔓';
      case 'logout':
        return '🔒';
      default:
        return '📝';
    }
  };

  const getActionColor = (action: string) => {
    if (action.includes('create') || action.includes('assign')) return 'success';
    if (action.includes('delete') || action.includes('remove')) return 'danger';
    if (action.includes('update')) return 'warning';
    return 'info';
  };

  const formatDetails = (details?: string) => {
    if (!details) return 'No details available';
    try {
      return JSON.stringify(JSON.parse(details), null, 2);
    } catch {
      return details;
    }
  };

  if (!canViewAudit) {
    return (
      <div className="audit-log">
        <div className="unauthorized">
          <i className="icon-lock"></i>
          <p>You do not have permission to view audit logs.</p>
          <small>Required permission: system:audit</small>
        </div>
      </div>
    );
  }

  return (
    <div className="audit-log">
      <div className="audit-header">
        <h2>Audit Log</h2>
        <div className="audit-info">
          <p>Track all RBAC-related changes and user activities</p>
        </div>
      </div>

      <div className="audit-controls">
        <SearchFilter
          searchTerm={searchTerm}
          onSearchChange={setSearchTerm}
          placeholder="Search by username, action, or resource..."
        />

        <div className="filter-section">
          <select
            value={filterType}
            onChange={e => setFilterType(e.target.value as FilterType)}
            className="type-filter"
          >
            <option value="all">All Actions</option>
            <option value="user_management">User Management</option>
            <option value="role_management">Role Management</option>
            <option value="permission_changes">Permission Changes</option>
          </select>

          <div className="date-filters">
            <input
              type="date"
              value={dateRange.start}
              onChange={e => setDateRange(prev => ({ ...prev, start: e.target.value }))}
              className="date-input"
              placeholder="Start date"
            />
            <input
              type="date"
              value={dateRange.end}
              onChange={e => setDateRange(prev => ({ ...prev, end: e.target.value }))}
              className="date-input"
              placeholder="End date"
            />
          </div>
        </div>
      </div>

      {loading ? (
        <div className="loading">Loading audit logs...</div>
      ) : error ? (
        <div className="error-message">{error}</div>
      ) : (
        <>
          <div className="audit-table-wrapper">
            <table className="audit-table">
              <thead>
                <tr>
                  <th>Timestamp</th>
                  <th>User</th>
                  <th>Action</th>
                  <th>Resource</th>
                  <th>Details</th>
                  <th>Tenant</th>
                </tr>
              </thead>
              <tbody>
                {logs.length === 0 ? (
                  <tr>
                    <td colSpan={6} className="empty-state">
                      No audit logs found for the selected criteria
                    </td>
                  </tr>
                ) : (
                  logs.map(log => (
                    <tr key={log.id}>
                      <td className="timestamp-cell">
                        {formatTimestamp(log.created_at)}
                      </td>
                      <td className="user-cell">
                        <strong>{log.performed_by_username}</strong>
                        <small>ID: {log.performed_by_user_id}</small>
                      </td>
                      <td className="action-cell">
                        <span className={`action-badge ${getActionColor(log.action)}`}>
                          <span className="action-icon">{getActionIcon(log.action)}</span>
                          {log.action.replace(/_/g, ' ')}
                        </span>
                      </td>
                      <td className="resource-cell">
                        <div>
                          <strong>{log.entity_type}</strong>
                          {log.entity_id && (
                            <small>ID: {log.entity_id}</small>
                          )}
                        </div>
                      </td>
                      <td className="details-cell">
                        <details>
                          <summary>View Details</summary>
                          <pre>{formatDetails(log.details)}</pre>
                        </details>
                      </td>
                      <td className="ip-cell">
                        {log.tenant_id ? `Tenant ${log.tenant_id}` : 'Global'}
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>

          <div className="pagination">
            <button
              disabled={currentPage === 1}
              onClick={() => setCurrentPage(prev => prev - 1)}
            >
              Previous
            </button>
            <span>Page {currentPage} of {totalPages}</span>
            <button
              disabled={currentPage === totalPages}
              onClick={() => setCurrentPage(prev => prev + 1)}
            >
              Next
            </button>
          </div>
        </>
      )}
    </div>
  );
};

export default AuditLog;