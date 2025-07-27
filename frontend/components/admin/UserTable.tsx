import React from 'react';
import './UserTable.css';

interface User {
  id: number;
  username: string;
  email: string;
  first_name?: string;
  last_name?: string;
  is_active: boolean;
  is_email_verified: boolean;
  created_at: string;
  last_login?: string;
  roles: string[];
}

interface UserTableProps {
  users: User[];
  onEdit?: (user: User) => void;
  onDelete?: (userId: number) => void;
  onToggleStatus?: (userId: number, isActive: boolean) => void;
  onResetPassword?: (userId: number) => void;
  canManageRoles?: boolean;
}

const UserTable: React.FC<UserTableProps> = ({
  users,
  onEdit,
  onDelete,
  onToggleStatus,
  onResetPassword,
  canManageRoles
}) => {
  const formatDate = (dateString: string) => {
    return new Date(dateString).toLocaleDateString();
  };

  const getFullName = (user: User) => {
    if (user.first_name || user.last_name) {
      return `${user.first_name || ''} ${user.last_name || ''}`.trim();
    }
    return '-';
  };

  return (
    <div className="user-table-wrapper">
      <table className="user-table">
        <thead>
          <tr>
            <th>Username</th>
            <th>Email</th>
            <th>Full Name</th>
            <th>Roles</th>
            <th>Status</th>
            <th>Created</th>
            <th>Last Login</th>
            <th>Actions</th>
          </tr>
        </thead>
        <tbody>
          {users.length === 0 ? (
            <tr>
              <td colSpan={8} className="empty-state">
                No users found
              </td>
            </tr>
          ) : (
            users.map(user => (
              <tr key={user.id}>
                <td>
                  <div className="username-cell">
                    {user.username}
                    {user.is_email_verified && (
                      <span className="verified-badge" title="Email verified">✓</span>
                    )}
                  </div>
                </td>
                <td>{user.email}</td>
                <td>{getFullName(user)}</td>
                <td>
                  <div className="roles-cell">
                    {user.roles.length > 0 ? (
                      user.roles.map(role => (
                        <span key={role} className="role-badge">
                          {role}
                        </span>
                      ))
                    ) : (
                      <span className="no-roles">No roles</span>
                    )}
                  </div>
                </td>
                <td>
                  <span className={`status-badge ${user.is_active ? 'active' : 'inactive'}`}>
                    {user.is_active ? 'Active' : 'Inactive'}
                  </span>
                </td>
                <td>{formatDate(user.created_at)}</td>
                <td>{user.last_login ? formatDate(user.last_login) : 'Never'}</td>
                <td>
                  <div className="action-buttons">
                    {onEdit && (
                      <button
                        className="btn-icon"
                        onClick={() => onEdit(user)}
                        title="Edit user"
                      >
                        <i className="icon-edit"></i>
                      </button>
                    )}
                    {onToggleStatus && (
                      <button
                        className="btn-icon"
                        onClick={() => onToggleStatus(user.id, !user.is_active)}
                        title={user.is_active ? 'Deactivate user' : 'Activate user'}
                      >
                        <i className={user.is_active ? 'icon-x' : 'icon-check'}></i>
                      </button>
                    )}
                    {onResetPassword && (
                      <button
                        className="btn-icon"
                        onClick={() => onResetPassword(user.id)}
                        title="Reset password"
                      >
                        <i className="icon-key"></i>
                      </button>
                    )}
                    {onDelete && (
                      <button
                        className="btn-icon btn-danger"
                        onClick={() => onDelete(user.id)}
                        title="Delete user"
                      >
                        <i className="icon-trash"></i>
                      </button>
                    )}
                  </div>
                </td>
              </tr>
            ))
          )}
        </tbody>
      </table>
    </div>
  );
};

export default UserTable;