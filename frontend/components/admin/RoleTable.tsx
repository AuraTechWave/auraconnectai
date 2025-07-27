import React from 'react';
import './RoleTable.css';

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

interface RoleTableProps {
  roles: Role[];
  permissions: Permission[];
  expandedRoles: Set<number>;
  onToggleExpanded: (roleId: number) => void;
  onEdit?: (role: Role) => void;
  onDelete?: (roleId: number) => void;
  onToggleStatus?: (roleId: number, isActive: boolean) => void;
  onAssignPermission?: (roleId: number, permissionId: number) => void;
  onRemovePermission?: (roleId: number, permissionId: number) => void;
  groupPermissionsByResource: (permissions: Permission[]) => Record<string, Permission[]>;
}

const RoleTable: React.FC<RoleTableProps> = ({
  roles,
  permissions,
  expandedRoles,
  onToggleExpanded,
  onEdit,
  onDelete,
  onToggleStatus,
  onAssignPermission,
  onRemovePermission,
  groupPermissionsByResource
}) => {
  const formatDate = (dateString: string) => {
    return new Date(dateString).toLocaleDateString();
  };

  const getAvailablePermissions = (role: Role) => {
    const rolePermissionIds = role.permissions.map(p => p.id);
    return permissions.filter(p => !rolePermissionIds.includes(p.id));
  };

  return (
    <div className="role-table">
      {roles.length === 0 ? (
        <div className="empty-state">No roles found</div>
      ) : (
        roles.map(role => (
          <div key={role.id} className="role-card">
            <div 
              className="role-header"
              onClick={() => onToggleExpanded(role.id)}
            >
              <div className="role-info">
                <div className="role-name">{role.display_name}</div>
                {role.description && (
                  <div className="role-description">{role.description}</div>
                )}
                <div className="role-meta">
                  <span className="user-count">
                    {role.user_count || 0} users
                  </span>
                  {role.is_system_role && (
                    <span className="system-role-badge">System Role</span>
                  )}
                  <span className={`status-badge ${role.is_active ? 'active' : 'inactive'}`}>
                    {role.is_active ? 'Active' : 'Inactive'}
                  </span>
                  <span className="created-date">
                    Created: {formatDate(role.created_at)}
                  </span>
                </div>
              </div>
              
              <div className="role-actions" onClick={e => e.stopPropagation()}>
                {onEdit && (
                  <button
                    className="btn-icon"
                    onClick={() => onEdit(role)}
                    title="Edit role"
                  >
                    <i className="icon-edit"></i>
                  </button>
                )}
                {onToggleStatus && (
                  <button
                    className="btn-icon"
                    onClick={() => onToggleStatus(role.id, !role.is_active)}
                    title={role.is_active ? 'Deactivate role' : 'Activate role'}
                  >
                    <i className={role.is_active ? 'icon-x' : 'icon-check'}></i>
                  </button>
                )}
                {onDelete && !role.is_system_role && (
                  <button
                    className="btn-icon btn-danger"
                    onClick={() => onDelete(role.id)}
                    title="Delete role"
                  >
                    <i className="icon-trash"></i>
                  </button>
                )}
                <div className={`expand-icon ${expandedRoles.has(role.id) ? 'expanded' : ''}`}>
                  ▼
                </div>
              </div>
            </div>

            {expandedRoles.has(role.id) && (
              <div className="role-details">
                <div className="permissions-section">
                  <h4>Current Permissions ({role.permissions.length})</h4>
                  {role.permissions.length === 0 ? (
                    <p className="no-permissions">No permissions assigned</p>
                  ) : (
                    <div className="permission-groups">
                      {Object.entries(groupPermissionsByResource(role.permissions)).map(([resource, perms]) => (
                        <div key={resource} className="permission-group">
                          <div className="permission-group-title">{resource}</div>
                          <div className="permission-list">
                            {perms.map(permission => (
                              <div key={permission.id} className="permission-item">
                                <span className="permission-name">
                                  {permission.name} ({permission.action})
                                </span>
                                {onRemovePermission && (
                                  <div className="permission-actions">
                                    <button
                                      className="btn btn-danger btn-xs"
                                      onClick={() => onRemovePermission(role.id, permission.id)}
                                      title="Remove permission"
                                    >
                                      Remove
                                    </button>
                                  </div>
                                )}
                              </div>
                            ))}
                          </div>
                        </div>
                      ))}
                    </div>
                  )}
                </div>

                {onAssignPermission && (
                  <div className="assign-permissions-section">
                    <h4>Available Permissions</h4>
                    <div className="available-permissions">
                      {getAvailablePermissions(role).length === 0 ? (
                        <p>All permissions are already assigned to this role</p>
                      ) : (
                        getAvailablePermissions(role).map(permission => (
                          <div key={permission.id} className="available-permission-item">
                            <span>
                              <strong>{permission.name}</strong> ({permission.resource}:{permission.action})
                            </span>
                            <button
                              className="btn btn-primary btn-xs"
                              onClick={() => onAssignPermission(role.id, permission.id)}
                            >
                              Assign
                            </button>
                          </div>
                        ))
                      )}
                    </div>
                  </div>
                )}
              </div>
            )}
          </div>
        ))
      )}
    </div>
  );
};

export default RoleTable;