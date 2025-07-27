import React, { useState, useEffect } from 'react';
import { apiClient } from '../../utils/apiClient';
import './UserForm.css';

interface User {
  id: number;
  username: string;
  email: string;
  first_name?: string;
  last_name?: string;
  is_active: boolean;
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

interface Role {
  id: number;
  name: string;
  display_name: string;
}

interface Tenant {
  id: number;
  name: string;
}

interface UserFormProps {
  user?: User | null;
  onSubmit: (data: UserFormData) => void;
  onClose: () => void;
  canManageRoles?: boolean;
}

const UserForm: React.FC<UserFormProps> = ({
  user,
  onSubmit,
  onClose,
  canManageRoles = false
}) => {
  const [formData, setFormData] = useState<UserFormData>({
    username: '',
    email: '',
    password: '',
    first_name: '',
    last_name: '',
    is_active: true,
    accessible_tenant_ids: [],
    default_tenant_id: undefined,
    role_ids: []
  });

  const [roles, setRoles] = useState<Role[]>([]);
  const [tenants, setTenants] = useState<Tenant[]>([]);
  const [loading, setLoading] = useState(false);
  const [errors, setErrors] = useState<Record<string, string>>({});

  useEffect(() => {
    fetchRoles();
    fetchTenants();
    
    if (user) {
      // Load user data and fetch current roles
      loadUserData();
    }
  }, [user]);

  const fetchRoles = async () => {
    try {
      const response = await apiClient.get('/rbac/roles');
      setRoles(response.data.items || response.data);
    } catch (err) {
      console.error('Failed to fetch roles:', err);
    }
  };

  const fetchTenants = async () => {
    // Mock tenants for now - replace with actual API call
    setTenants([
      { id: 1, name: 'Default Tenant' },
      { id: 2, name: 'Restaurant A' },
      { id: 3, name: 'Restaurant B' }
    ]);
  };

  const loadUserData = async () => {
    if (!user) return;

    try {
      // Fetch user's current roles
      const response = await apiClient.get(`/rbac/users/${user.id}/roles`);
      const userRoleIds = response.data.map((role: Role) => role.id);

      setFormData({
        username: user.username,
        email: user.email,
        password: '', // Don't populate password for edits
        first_name: user.first_name || '',
        last_name: user.last_name || '',
        is_active: user.is_active,
        accessible_tenant_ids: user.accessible_tenant_ids,
        default_tenant_id: user.default_tenant_id,
        role_ids: userRoleIds
      });
    } catch (err) {
      console.error('Failed to load user roles:', err);
    }
  };

  const validateForm = (): boolean => {
    const newErrors: Record<string, string> = {};

    if (!formData.username.trim()) {
      newErrors.username = 'Username is required';
    }

    if (!formData.email.trim()) {
      newErrors.email = 'Email is required';
    } else if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(formData.email)) {
      newErrors.email = 'Invalid email format';
    }

    if (!user && !formData.password) {
      newErrors.password = 'Password is required for new users';
    } else if (formData.password && formData.password.length < 8) {
      newErrors.password = 'Password must be at least 8 characters';
    }

    setErrors(newErrors);
    return Object.keys(newErrors).length === 0;
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();

    if (!validateForm()) {
      return;
    }

    setLoading(true);
    
    try {
      const submitData = { ...formData };
      
      // Remove password if empty (for updates)
      if (!submitData.password) {
        delete submitData.password;
      }

      await onSubmit(submitData);
    } finally {
      setLoading(false);
    }
  };

  const handleInputChange = (field: keyof UserFormData, value: any) => {
    setFormData(prev => ({ ...prev, [field]: value }));
    // Clear error for this field
    setErrors(prev => ({ ...prev, [field]: '' }));
  };

  const handleRoleToggle = (roleId: number) => {
    setFormData(prev => ({
      ...prev,
      role_ids: prev.role_ids.includes(roleId)
        ? prev.role_ids.filter(id => id !== roleId)
        : [...prev.role_ids, roleId]
    }));
  };

  const handleTenantToggle = (tenantId: number) => {
    setFormData(prev => ({
      ...prev,
      accessible_tenant_ids: prev.accessible_tenant_ids.includes(tenantId)
        ? prev.accessible_tenant_ids.filter(id => id !== tenantId)
        : [...prev.accessible_tenant_ids, tenantId]
    }));
  };

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal-content" onClick={e => e.stopPropagation()}>
        <div className="modal-header">
          <h3>{user ? 'Edit User' : 'Create New User'}</h3>
          <button className="close-btn" onClick={onClose}>×</button>
        </div>

        <form onSubmit={handleSubmit} className="user-form">
          <div className="form-group">
            <label htmlFor="username">Username *</label>
            <input
              id="username"
              type="text"
              value={formData.username}
              onChange={e => handleInputChange('username', e.target.value)}
              className={errors.username ? 'error' : ''}
              disabled={!!user} // Username cannot be changed
            />
            {errors.username && <span className="error-text">{errors.username}</span>}
          </div>

          <div className="form-group">
            <label htmlFor="email">Email *</label>
            <input
              id="email"
              type="email"
              value={formData.email}
              onChange={e => handleInputChange('email', e.target.value)}
              className={errors.email ? 'error' : ''}
            />
            {errors.email && <span className="error-text">{errors.email}</span>}
          </div>

          <div className="form-group">
            <label htmlFor="password">
              Password {!user && '*'}
            </label>
            <input
              id="password"
              type="password"
              value={formData.password}
              onChange={e => handleInputChange('password', e.target.value)}
              className={errors.password ? 'error' : ''}
              placeholder={user ? 'Leave blank to keep current password' : ''}
            />
            {errors.password && <span className="error-text">{errors.password}</span>}
          </div>

          <div className="form-row">
            <div className="form-group">
              <label htmlFor="first_name">First Name</label>
              <input
                id="first_name"
                type="text"
                value={formData.first_name}
                onChange={e => handleInputChange('first_name', e.target.value)}
              />
            </div>

            <div className="form-group">
              <label htmlFor="last_name">Last Name</label>
              <input
                id="last_name"
                type="text"
                value={formData.last_name}
                onChange={e => handleInputChange('last_name', e.target.value)}
              />
            </div>
          </div>

          <div className="form-group">
            <label>
              <input
                type="checkbox"
                checked={formData.is_active}
                onChange={e => handleInputChange('is_active', e.target.checked)}
              />
              Active User
            </label>
          </div>

          {canManageRoles && (
            <div className="form-group">
              <label>Roles</label>
              <div className="checkbox-grid">
                {roles.map(role => (
                  <label key={role.id} className="checkbox-label">
                    <input
                      type="checkbox"
                      checked={formData.role_ids.includes(role.id)}
                      onChange={() => handleRoleToggle(role.id)}
                    />
                    {role.display_name}
                  </label>
                ))}
              </div>
            </div>
          )}

          <div className="form-group">
            <label>Accessible Tenants</label>
            <div className="checkbox-grid">
              {tenants.map(tenant => (
                <label key={tenant.id} className="checkbox-label">
                  <input
                    type="checkbox"
                    checked={formData.accessible_tenant_ids.includes(tenant.id)}
                    onChange={() => handleTenantToggle(tenant.id)}
                  />
                  {tenant.name}
                </label>
              ))}
            </div>
          </div>

          {formData.accessible_tenant_ids.length > 0 && (
            <div className="form-group">
              <label htmlFor="default_tenant">Default Tenant</label>
              <select
                id="default_tenant"
                value={formData.default_tenant_id || ''}
                onChange={e => handleInputChange('default_tenant_id', e.target.value ? Number(e.target.value) : undefined)}
              >
                <option value="">Select default tenant...</option>
                {tenants
                  .filter(t => formData.accessible_tenant_ids.includes(t.id))
                  .map(tenant => (
                    <option key={tenant.id} value={tenant.id}>
                      {tenant.name}
                    </option>
                  ))}
              </select>
            </div>
          )}

          <div className="form-actions">
            <button type="button" className="btn btn-secondary" onClick={onClose}>
              Cancel
            </button>
            <button type="submit" className="btn btn-primary" disabled={loading}>
              {loading ? 'Saving...' : (user ? 'Update User' : 'Create User')}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
};

export default UserForm;