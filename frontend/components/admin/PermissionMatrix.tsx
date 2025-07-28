import React, { useState, useEffect, useMemo } from 'react';
import apiClient from '../../utils/authInterceptor';
import { useRBAC } from '../../hooks/useRBAC';
import { useNotifications, NotificationContainer } from '../ui/Notification';
import { useApiQuery, invalidateQueries } from '../../hooks/useApiQuery';
import VirtualizedTable from '../ui/VirtualizedTable';
import '../ui/SharedStyles.css';
import './PermissionMatrix.css';

interface Role {
  id: number;
  name: string;
  display_name: string;
  is_active: boolean;
  permissions: Permission[];
}

interface Permission {
  id: number;
  key: string;
  name: string;
  resource: string;
  action: string;
}

interface MatrixData {
  roles: Role[];
  permissions: Permission[];
  matrix: Record<string, Record<string, boolean>>; // roleId -> permissionId -> hasPermission
}

const PermissionMatrix: React.FC = () => {
  const { hasPermission } = useRBAC();
  const [matrixData, setMatrixData] = useState<MatrixData>({
    roles: [],
    permissions: [],
    matrix: {}
  });
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const [selectedResource, setSelectedResource] = useState<string>('all');
  const [searchTerm, setSearchTerm] = useState('');
  const [showInactiveRoles, setShowInactiveRoles] = useState(false);

  const canManagePermissions = hasPermission('role:manage_permissions');

  useEffect(() => {
    fetchMatrixData();
  }, []);

  const fetchMatrixData = async () => {
    try {
      setLoading(true);
      const [rolesResponse, permissionsResponse] = await Promise.all([
        apiClient.get('/rbac/roles'),
        apiClient.get('/rbac/permissions')
      ]);

      const roles = rolesResponse.data;
      const permissions = permissionsResponse.data;

      // Build the matrix
      const matrix: Record<string, Record<string, boolean>> = {};
      
      roles.forEach((role: Role) => {
        matrix[role.id] = {};
        permissions.forEach((permission: Permission) => {
          matrix[role.id][permission.id] = role.permissions.some(p => p.id === permission.id);
        });
      });

      setMatrixData({ roles, permissions, matrix });
      setError(null);
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to fetch permission matrix');
    } finally {
      setLoading(false);
    }
  };

  const handlePermissionToggle = async (roleId: number, permissionId: number, hasPermission: boolean) => {
    if (!canManagePermissions) {
      setError('You do not have permission to manage role permissions');
      return;
    }

    try {
      if (hasPermission) {
        await apiClient.post('/rbac/remove-permission', {
          role_id: roleId,
          permission_id: permissionId
        });
      } else {
        await apiClient.post('/rbac/assign-permission', {
          role_id: roleId,
          permission_id: permissionId
        });
      }

      // Update local state
      setMatrixData(prev => ({
        ...prev,
        matrix: {
          ...prev.matrix,
          [roleId]: {
            ...prev.matrix[roleId],
            [permissionId]: !hasPermission
          }
        }
      }));

      setSuccess(`Permission ${hasPermission ? 'removed from' : 'assigned to'} role`);
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to update permission');
    }
  };

  const getUniqueResources = () => {
    const resources = matrixData.permissions.map(p => p.resource);
    return ['all', ...Array.from(new Set(resources))];
  };

  const getFilteredPermissions = () => {
    let filtered = matrixData.permissions;

    if (searchTerm) {
      filtered = filtered.filter(p => 
        p.name.toLowerCase().includes(searchTerm.toLowerCase()) ||
        p.key.toLowerCase().includes(searchTerm.toLowerCase()) ||
        p.resource.toLowerCase().includes(searchTerm.toLowerCase())
      );
    }

    if (selectedResource !== 'all') {
      filtered = filtered.filter(p => p.resource === selectedResource);
    }

    return filtered;
  };

  const getFilteredRoles = () => {
    return matrixData.roles.filter(role => 
      showInactiveRoles || role.is_active
    );
  };

  const groupPermissionsByResource = (permissions: Permission[]) => {
    return permissions.reduce((acc, perm) => {
      if (!acc[perm.resource]) {
        acc[perm.resource] = [];
      }
      acc[perm.resource].push(perm);
      return acc;
    }, {} as Record<string, Permission[]>);
  };

  const calculateStats = () => {
    const roles = getFilteredRoles();
    const permissions = getFilteredPermissions();
    
    let totalAssignments = 0;
    let possibleAssignments = roles.length * permissions.length;

    roles.forEach(role => {
      permissions.forEach(permission => {
        if (matrixData.matrix[role.id]?.[permission.id]) {
          totalAssignments++;
        }
      });
    });

    return {
      totalAssignments,
      possibleAssignments,
      percentage: possibleAssignments > 0 ? (totalAssignments / possibleAssignments * 100).toFixed(1) : '0'
    };
  };

  if (loading) {
    return <div className="loading">Loading permission matrix...</div>;
  }

  if (error) {
    return <div className="error-message">{error}</div>;
  }

  const filteredRoles = getFilteredRoles();
  const filteredPermissions = getFilteredPermissions();
  const groupedPermissions = groupPermissionsByResource(filteredPermissions);
  const stats = calculateStats();

  return (
    <div className="permission-matrix">
      <div className="matrix-header">
        <h2>Permission Matrix</h2>
        <div className="matrix-stats">
          <span className="stat-item">
            <strong>{stats.totalAssignments}</strong> / {stats.possibleAssignments} assignments
          </span>
          <span className="stat-item">
            <strong>{stats.percentage}%</strong> coverage
          </span>
        </div>
      </div>

      <div className="matrix-controls">
        <div className="search-input-wrapper">
          <input
            type="text"
            placeholder="Search permissions..."
            value={searchTerm}
            onChange={e => setSearchTerm(e.target.value)}
            className="search-input"
          />
        </div>
        
        <select
          value={selectedResource}
          onChange={e => setSelectedResource(e.target.value)}
          className="resource-filter"
        >
          {getUniqueResources().map(resource => (
            <option key={resource} value={resource}>
              {resource === 'all' ? 'All Resources' : resource}
            </option>
          ))}
        </select>

        <label className="checkbox-label">
          <input
            type="checkbox"
            checked={showInactiveRoles}
            onChange={e => setShowInactiveRoles(e.target.checked)}
          />
          Show inactive roles
        </label>
      </div>

      {!canManagePermissions && (
        <div className="readonly-notice">
          <i className="icon-info"></i>
          You have read-only access to the permission matrix
        </div>
      )}

      <div className="matrix-container">
        <table className="matrix-table">
          <thead>
            <tr>
              <th className="permission-header">Permissions</th>
              {filteredRoles.map(role => (
                <th key={role.id} className="role-header">
                  <div className="role-header-content">
                    <span className="role-name">{role.display_name}</span>
                    {!role.is_active && (
                      <span className="inactive-badge">Inactive</span>
                    )}
                  </div>
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {Object.entries(groupedPermissions).map(([resource, permissions]) => (
              <React.Fragment key={resource}>
                <tr className="resource-separator">
                  <td colSpan={filteredRoles.length + 1} className="resource-title">
                    {resource.toUpperCase()}
                  </td>
                </tr>
                {permissions.map(permission => (
                  <tr key={permission.id} className="permission-row">
                    <td className="permission-cell">
                      <div className="permission-info">
                        <span className="permission-name">{permission.name}</span>
                        <span className="permission-key">{permission.key}</span>
                      </div>
                    </td>
                    {filteredRoles.map(role => {
                      const hasPermission = matrixData.matrix[role.id]?.[permission.id] || false;
                      return (
                        <td key={role.id} className="matrix-cell">
                          <button
                            className={`permission-toggle ${hasPermission ? 'granted' : 'denied'} ${!canManagePermissions ? 'readonly' : ''}`}
                            onClick={() => canManagePermissions && handlePermissionToggle(role.id, permission.id, hasPermission)}
                            disabled={!canManagePermissions}
                            title={`${hasPermission ? 'Remove' : 'Grant'} ${permission.name} for ${role.display_name}`}
                          >
                            {hasPermission ? '✓' : '✗'}
                          </button>
                        </td>
                      );
                    })}
                  </tr>
                ))}
              </React.Fragment>
            ))}
          </tbody>
        </table>
      </div>

      {success && (
        <Toast
          message={success}
          type="success"
          onClose={() => setSuccess(null)}
        />
      )}

      {error && (
        <Toast
          message={error}
          type="error"
          onClose={() => setError(null)}
        />
      )}
    </div>
  );
};

export default PermissionMatrix;