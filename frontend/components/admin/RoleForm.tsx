import React, { useState, useEffect } from 'react';
import './RoleForm.css';

interface Role {
  id: number;
  name: string;
  display_name: string;
  description?: string;
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

interface RoleFormData {
  name: string;
  display_name: string;
  description?: string;
  is_active: boolean;
  permission_ids: number[];
}

interface RoleFormProps {
  role?: Role | null;
  permissions: Permission[];
  onSubmit: (data: RoleFormData) => void;
  onClose: () => void;
  canManagePermissions?: boolean;
}

const RoleForm: React.FC<RoleFormProps> = ({
  role,
  permissions,
  onSubmit,
  onClose,
  canManagePermissions = false
}) => {
  const [formData, setFormData] = useState<RoleFormData>({
    name: '',
    display_name: '',
    description: '',
    is_active: true,
    permission_ids: []
  });

  const [errors, setErrors] = useState<Record<string, string>>({});
  const [loading, setLoading] = useState(false);
  const [searchTerm, setSearchTerm] = useState('');
  const [selectedResource, setSelectedResource] = useState<string>('all');

  useEffect(() => {
    if (role) {
      setFormData({
        name: role.name,
        display_name: role.display_name,
        description: role.description || '',
        is_active: role.is_active,
        permission_ids: role.permissions.map(p => p.id)
      });
    }
  }, [role]);

  const validateForm = (): boolean => {
    const newErrors: Record<string, string> = {};

    if (!formData.name.trim()) {
      newErrors.name = 'Role name is required';
    } else if (!/^[a-z_]+$/.test(formData.name)) {
      newErrors.name = 'Role name must contain only lowercase letters and underscores';
    }

    if (!formData.display_name.trim()) {
      newErrors.display_name = 'Display name is required';
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
      await onSubmit(formData);
    } finally {
      setLoading(false);
    }
  };

  const handleInputChange = (field: keyof RoleFormData, value: any) => {
    setFormData(prev => ({ ...prev, [field]: value }));
    // Clear error for this field
    setErrors(prev => ({ ...prev, [field]: '' }));
  };

  const handlePermissionToggle = (permissionId: number) => {
    setFormData(prev => ({
      ...prev,
      permission_ids: prev.permission_ids.includes(permissionId)
        ? prev.permission_ids.filter(id => id !== permissionId)
        : [...prev.permission_ids, permissionId]
    }));
  };

  const getUniqueResources = () => {
    const resources = permissions.map(p => p.resource);
    return ['all', ...Array.from(new Set(resources))];
  };

  const getFilteredPermissions = () => {
    let filtered = permissions;

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

  const groupPermissionsByResource = (permissions: Permission[]) => {
    return permissions.reduce((acc, perm) => {
      if (!acc[perm.resource]) {
        acc[perm.resource] = [];
      }
      acc[perm.resource].push(perm);
      return acc;
    }, {} as Record<string, Permission[]>);
  };

  const selectedCount = formData.permission_ids.length;
  const totalCount = permissions.length;

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal-content large" onClick={e => e.stopPropagation()}>
        <div className="modal-header">
          <h3>{role ? 'Edit Role' : 'Create New Role'}</h3>
          <button className="close-btn" onClick={onClose}>×</button>
        </div>

        <form onSubmit={handleSubmit} className="role-form">
          <div className="form-section">
            <h4>Role Information</h4>
            
            <div className="form-row">
              <div className="form-group">
                <label htmlFor="name">Role Name *</label>
                <input
                  id="name"
                  type="text"
                  value={formData.name}
                  onChange={e => handleInputChange('name', e.target.value)}
                  className={errors.name ? 'error' : ''}
                  placeholder="e.g., staff_manager"
                  disabled={!!role} // Role name cannot be changed
                />
                {errors.name && <span className="error-text">{errors.name}</span>}
                <small>Only lowercase letters and underscores allowed</small>
              </div>

              <div className="form-group">
                <label htmlFor="display_name">Display Name *</label>
                <input
                  id="display_name"
                  type="text"
                  value={formData.display_name}
                  onChange={e => handleInputChange('display_name', e.target.value)}
                  className={errors.display_name ? 'error' : ''}
                  placeholder="e.g., Staff Manager"
                />
                {errors.display_name && <span className="error-text">{errors.display_name}</span>}
              </div>
            </div>

            <div className="form-group">
              <label htmlFor="description">Description</label>
              <textarea
                id="description"
                value={formData.description}
                onChange={e => handleInputChange('description', e.target.value)}
                placeholder="Describe the role's purpose and responsibilities..."
                rows={3}
              />
            </div>

            <div className="form-group">
              <label>
                <input
                  type="checkbox"
                  checked={formData.is_active}
                  onChange={e => handleInputChange('is_active', e.target.checked)}
                />
                Active Role
              </label>
            </div>
          </div>

          {canManagePermissions && (
            <div className="form-section">
              <h4>
                Permissions ({selectedCount}/{totalCount} selected)
              </h4>
              
              <div className="permission-filters">
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
                
                <div className="bulk-actions">
                  <button
                    type="button"
                    className="btn btn-sm btn-secondary"
                    onClick={() => {
                      const filteredIds = getFilteredPermissions().map(p => p.id);
                      setFormData(prev => ({
                        ...prev,
                        permission_ids: [...new Set([...prev.permission_ids, ...filteredIds])]
                      }));
                    }}
                  >
                    Select All Filtered
                  </button>
                  <button
                    type="button"
                    className="btn btn-sm btn-secondary"
                    onClick={() => {
                      const filteredIds = getFilteredPermissions().map(p => p.id);
                      setFormData(prev => ({
                        ...prev,
                        permission_ids: prev.permission_ids.filter(id => !filteredIds.includes(id))
                      }));
                    }}
                  >
                    Deselect All Filtered
                  </button>
                </div>
              </div>

              <div className="permissions-grid">
                {Object.entries(groupPermissionsByResource(getFilteredPermissions())).map(([resource, perms]) => (
                  <div key={resource} className="permission-group">
                    <div className="permission-group-header">
                      <h5>{resource}</h5>
                      <div className="group-actions">
                        <button
                          type="button"
                          className="btn-link"
                          onClick={() => {
                            perms.forEach(p => {
                              if (!formData.permission_ids.includes(p.id)) {
                                handlePermissionToggle(p.id);
                              }
                            });
                          }}
                        >
                          Select All
                        </button>
                        <button
                          type="button"
                          className="btn-link"
                          onClick={() => {
                            perms.forEach(p => {
                              if (formData.permission_ids.includes(p.id)) {
                                handlePermissionToggle(p.id);
                              }
                            });
                          }}
                        >
                          Deselect All
                        </button>
                      </div>
                    </div>
                    
                    <div className="permission-list">
                      {perms.map(permission => (
                        <label key={permission.id} className="permission-checkbox">
                          <input
                            type="checkbox"
                            checked={formData.permission_ids.includes(permission.id)}
                            onChange={() => handlePermissionToggle(permission.id)}
                          />
                          <div className="permission-info">
                            <span className="permission-name">{permission.name}</span>
                            <span className="permission-key">{permission.key}</span>
                          </div>
                        </label>
                      ))}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

          <div className="form-actions">
            <button type="button" className="btn btn-secondary" onClick={onClose}>
              Cancel
            </button>
            <button type="submit" className="btn btn-primary" disabled={loading}>
              {loading ? 'Saving...' : (role ? 'Update Role' : 'Create Role')}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
};

export default RoleForm;