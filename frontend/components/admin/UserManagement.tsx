import React, { useState, useEffect } from 'react';
import { apiClient } from '../../utils/apiClient';
import { useRBAC } from '../../hooks/useRBAC';
import UserForm from './UserForm';
import UserTable from './UserTable';
import SearchFilter from './SearchFilter';
import Toast from '../ui/Toast';
import './UserManagement.css';

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
  accessible_tenant_ids: number[];
  default_tenant_id?: number;
  roles: string[];
}

interface UserFormData {
  username: string;
  email: string;
  password?: string;
  first_name?: string;
  last_name?: string;
  is_active: boolean;
  accessible_tenant_ids: number[];
  default_tenant_id?: number;
  role_ids: number[];
}

const UserManagement: React.FC = () => {
  const { hasPermission } = useRBAC();
  const [users, setUsers] = useState<User[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const [showForm, setShowForm] = useState(false);
  const [editingUser, setEditingUser] = useState<User | null>(null);
  const [searchTerm, setSearchTerm] = useState('');
  const [filterStatus, setFilterStatus] = useState<'all' | 'active' | 'inactive'>('all');
  const [currentPage, setCurrentPage] = useState(1);
  const [totalPages, setTotalPages] = useState(1);

  const canWrite = hasPermission('user:write');
  const canDelete = hasPermission('user:delete');
  const canManageRoles = hasPermission('user:manage_roles');

  useEffect(() => {
    fetchUsers();
  }, [currentPage, searchTerm, filterStatus]);

  const fetchUsers = async () => {
    try {
      setLoading(true);
      const params = new URLSearchParams({
        page: currentPage.toString(),
        limit: '20',
        search: searchTerm,
        status: filterStatus
      });

      const response = await apiClient.get(`/rbac/users?${params}`);
      setUsers(response.data.items);
      setTotalPages(response.data.total_pages);
      setError(null);
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to fetch users');
    } finally {
      setLoading(false);
    }
  };

  const handleCreateUser = async (data: UserFormData) => {
    try {
      await apiClient.post('/rbac/users', data);
      setSuccess('User created successfully');
      setShowForm(false);
      fetchUsers();
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to create user');
    }
  };

  const handleUpdateUser = async (userId: number, data: UserFormData) => {
    try {
      await apiClient.put(`/rbac/users/${userId}`, data);
      setSuccess('User updated successfully');
      setEditingUser(null);
      setShowForm(false);
      fetchUsers();
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to update user');
    }
  };

  const handleDeleteUser = async (userId: number) => {
    if (!window.confirm('Are you sure you want to delete this user?')) {
      return;
    }

    try {
      await apiClient.delete(`/rbac/users/${userId}`);
      setSuccess('User deleted successfully');
      fetchUsers();
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to delete user');
    }
  };

  const handleToggleUserStatus = async (userId: number, isActive: boolean) => {
    try {
      await apiClient.patch(`/rbac/users/${userId}/status`, { is_active: isActive });
      setSuccess(`User ${isActive ? 'activated' : 'deactivated'} successfully`);
      fetchUsers();
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to update user status');
    }
  };

  const handleResetPassword = async (userId: number) => {
    if (!window.confirm('Send password reset email to this user?')) {
      return;
    }

    try {
      await apiClient.post(`/rbac/users/${userId}/reset-password`);
      setSuccess('Password reset email sent');
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to reset password');
    }
  };

  const handleEdit = (user: User) => {
    setEditingUser(user);
    setShowForm(true);
  };

  const handleCloseForm = () => {
    setShowForm(false);
    setEditingUser(null);
  };

  const filteredUsers = users.filter(user => {
    if (filterStatus === 'active' && !user.is_active) return false;
    if (filterStatus === 'inactive' && user.is_active) return false;
    return true;
  });

  return (
    <div className="user-management">
      <div className="management-header">
        <h2>User Management</h2>
        {canWrite && (
          <button 
            className="btn btn-primary"
            onClick={() => setShowForm(true)}
          >
            <i className="icon-plus"></i>
            Add User
          </button>
        )}
      </div>

      <SearchFilter
        searchTerm={searchTerm}
        onSearchChange={setSearchTerm}
        filterStatus={filterStatus}
        onFilterChange={setFilterStatus}
        placeholder="Search by username or email..."
      />

      {loading ? (
        <div className="loading">Loading users...</div>
      ) : error ? (
        <div className="error-message">{error}</div>
      ) : (
        <>
          <UserTable
            users={filteredUsers}
            onEdit={canWrite ? handleEdit : undefined}
            onDelete={canDelete ? handleDeleteUser : undefined}
            onToggleStatus={canWrite ? handleToggleUserStatus : undefined}
            onResetPassword={canWrite ? handleResetPassword : undefined}
            canManageRoles={canManageRoles}
          />

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

      {showForm && (
        <UserForm
          user={editingUser}
          onSubmit={editingUser ? 
            (data) => handleUpdateUser(editingUser.id, data) : 
            handleCreateUser
          }
          onClose={handleCloseForm}
          canManageRoles={canManageRoles}
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

export default UserManagement;