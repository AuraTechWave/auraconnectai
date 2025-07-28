import React, { useState, useEffect } from 'react';
import apiClient from '../../utils/authInterceptor';
import { useRBAC } from '../../hooks/useRBAC';
import { useNotifications, NotificationContainer } from '../ui/Notification';
import RoleForm from './RoleForm';
import RoleTable from './RoleTable';
import '../ui/SharedStyles.css';
import './RoleManagement.css';

interface Role {
  id: number;
  name: string;
  display_name: string;
  description?: string;
  is_active: boolean;
  is_system_role: boolean;
  created_at: string;
  permissions: Permission[];
  user_count?: number;
}

interface Permission {
  id: number;
  key: string;
  name: string;
  resource: string;
  action: string;
}

interface RoleFormData {
  name: string;
  display_name: string;
  description?: string;
  is_active: boolean;
  permission_ids: number[];
}

const RoleManagement: React.FC = () => {
  const { hasPermission } = useRBAC();
  const { notifications, removeNotification, success, error } = useNotifications();
  const [roles, setRoles] = useState<Role[]>([]);
  const [permissions, setPermissions] = useState<Permission[]>([]);
  const [loading, setLoading] = useState(true);
  const [showForm, setShowForm] = useState(false);
  const [editingRole, setEditingRole] = useState<Role | null>(null);
  const [expandedRoles, setExpandedRoles] = useState<Set<number>>(new Set());

  const canWrite = hasPermission('role:write');
  const canDelete = hasPermission('role:delete');
  const canManagePermissions = hasPermission('role:manage_permissions');

  useEffect(() => {
    fetchRoles();
    fetchPermissions();
  }, []);

  const fetchRoles = async () => {
    try {
      setLoading(true);
      const response = await apiClient.get('/rbac/roles');
      
      // Fetch user count for each role
      const rolesWithCounts = await Promise.all(
        response.data.map(async (role: Role) => {
          try {
            const countResponse = await apiClient.get(`/rbac/roles/${role.id}/users/count`);
            return { ...role, user_count: countResponse.data.count };
          } catch {
            return { ...role, user_count: 0 };
          }
        })
      );
      
      setRoles(rolesWithCounts);
      setError(null);
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to fetch roles');
    } finally {
      setLoading(false);
    }
  };

  const fetchPermissions = async () => {
    try {
      const response = await apiClient.get('/rbac/permissions');
      setPermissions(response.data);
    } catch (err: any) {
      console.error('Failed to fetch permissions:', err);
    }
  };

  const handleCreateRole = async (data: RoleFormData) => {
    try {
      await apiClient.post('/rbac/roles', data);
      setSuccess('Role created successfully');
      setShowForm(false);
      fetchRoles();
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to create role');
    }
  };

  const handleUpdateRole = async (roleId: number, data: RoleFormData) => {
    try {
      await apiClient.put(`/rbac/roles/${roleId}`, data);
      setSuccess('Role updated successfully');
      setEditingRole(null);
      setShowForm(false);
      fetchRoles();
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to update role');
    }
  };

  const handleDeleteRole = async (roleId: number) => {
    const role = roles.find(r => r.id === roleId);
    if (role?.is_system_role) {
      setError('System roles cannot be deleted');
      return;
    }

    if (!window.confirm('Are you sure you want to delete this role? All users with this role will lose it.')) {
      return;
    }

    try {
      await apiClient.delete(`/rbac/roles/${roleId}`);
      setSuccess('Role deleted successfully');
      fetchRoles();
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to delete role');
    }
  };

  const handleToggleRoleStatus = async (roleId: number, isActive: boolean) => {
    try {
      await apiClient.patch(`/rbac/roles/${roleId}/status`, { is_active: isActive });
      setSuccess(`Role ${isActive ? 'activated' : 'deactivated'} successfully`);
      fetchRoles();
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to update role status');
    }
  };

  const handleAssignPermission = async (roleId: number, permissionId: number) => {
    try {
      await apiClient.post('/rbac/assign-permission', {
        role_id: roleId,
        permission_id: permissionId
      });
      setSuccess('Permission assigned successfully');
      fetchRoles();
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to assign permission');
    }
  };

  const handleRemovePermission = async (roleId: number, permissionId: number) => {
    try {
      await apiClient.post('/rbac/remove-permission', {
        role_id: roleId,
        permission_id: permissionId
      });
      setSuccess('Permission removed successfully');
      fetchRoles();
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to remove permission');
    }
  };

  const handleEdit = (role: Role) => {
    setEditingRole(role);
    setShowForm(true);
  };

  const handleCloseForm = () => {
    setShowForm(false);
    setEditingRole(null);
  };

  const toggleRoleExpanded = (roleId: number) => {
    setExpandedRoles(prev => {
      const newSet = new Set(prev);
      if (newSet.has(roleId)) {
        newSet.delete(roleId);
      } else {
        newSet.add(roleId);
      }
      return newSet;
    });
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

  return (
    <div className="role-management">
      <div className="management-header">
        <h2>Role Management</h2>
        {canWrite && (
          <button 
            className="btn btn-primary"
            onClick={() => setShowForm(true)}
          >
            <i className="icon-plus"></i>
            Add Role
          </button>
        )}
      </div>

      {loading ? (
        <div className="loading">Loading roles...</div>
      ) : error ? (
        <div className="error-message">{error}</div>
      ) : (
        <RoleTable
          roles={roles}
          permissions={permissions}
          expandedRoles={expandedRoles}
          onToggleExpanded={toggleRoleExpanded}
          onEdit={canWrite ? handleEdit : undefined}
          onDelete={canDelete ? handleDeleteRole : undefined}
          onToggleStatus={canWrite ? handleToggleRoleStatus : undefined}
          onAssignPermission={canManagePermissions ? handleAssignPermission : undefined}
          onRemovePermission={canManagePermissions ? handleRemovePermission : undefined}
          groupPermissionsByResource={groupPermissionsByResource}
        />
      )}

      {showForm && (
        <RoleForm
          role={editingRole}
          permissions={permissions}
          onSubmit={editingRole ? 
            (data) => handleUpdateRole(editingRole.id, data) : 
            handleCreateRole
          }
          onClose={handleCloseForm}
          canManagePermissions={canManagePermissions}
        />
      )}

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

export default RoleManagement;