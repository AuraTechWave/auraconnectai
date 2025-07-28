import React, { useState, useEffect } from 'react';
import { apiClient } from '../../utils/apiClient';
import './ModifierManagement.css';

interface ModifierGroup {
  id: number;
  name: string;
  description?: string;
  selection_type: 'single' | 'multiple';
  min_selections: number;
  max_selections?: number;
  is_required: boolean;
  display_order: number;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

interface Modifier {
  id: number;
  modifier_group_id: number;
  name: string;
  description?: string;
  price_adjustment: number;
  price_type: 'fixed' | 'percentage';
  is_active: boolean;
  is_available: boolean;
  display_order: number;
  created_at: string;
  updated_at: string;
}

interface ModifierGroupFormData {
  name: string;
  description: string;
  selection_type: 'single' | 'multiple';
  min_selections: number;
  max_selections: number | '';
  is_required: boolean;
  display_order: number;
  is_active: boolean;
}

interface ModifierFormData {
  modifier_group_id: number;
  name: string;
  description: string;
  price_adjustment: number;
  price_type: 'fixed' | 'percentage';
  is_active: boolean;
  is_available: boolean;
  display_order: number;
}

const ModifierManagement: React.FC = () => {
  const [modifierGroups, setModifierGroups] = useState<ModifierGroup[]>([]);
  const [modifiers, setModifiers] = useState<Modifier[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<'groups' | 'modifiers'>('groups');
  const [showGroupForm, setShowGroupForm] = useState(false);
  const [showModifierForm, setShowModifierForm] = useState(false);
  const [editingGroup, setEditingGroup] = useState<ModifierGroup | null>(null);
  const [editingModifier, setEditingModifier] = useState<Modifier | null>(null);
  const [selectedGroup, setSelectedGroup] = useState<number | null>(null);

  const [groupFormData, setGroupFormData] = useState<ModifierGroupFormData>({
    name: '',
    description: '',
    selection_type: 'single',
    min_selections: 0,
    max_selections: '',
    is_required: false,
    display_order: 0,
    is_active: true
  });

  const [modifierFormData, setModifierFormData] = useState<ModifierFormData>({
    modifier_group_id: 0,
    name: '',
    description: '',
    price_adjustment: 0,
    price_type: 'fixed',
    is_active: true,
    is_available: true,
    display_order: 0
  });

  useEffect(() => {
    fetchModifierGroups();
  }, []);

  useEffect(() => {
    if (selectedGroup) {
      fetchModifiers(selectedGroup);
    }
  }, [selectedGroup]);

  const fetchModifierGroups = async () => {
    setLoading(true);
    setError(null);
    try {
      const response = await apiClient.get('/menu/modifier-groups?active_only=false');
      setModifierGroups(response.data);
      if (response.data.length > 0 && !selectedGroup) {
        setSelectedGroup(response.data[0].id);
      }
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to fetch modifier groups');
    } finally {
      setLoading(false);
    }
  };

  const fetchModifiers = async (groupId: number) => {
    try {
      const response = await apiClient.get(`/menu/modifier-groups/${groupId}/modifiers?active_only=false`);
      setModifiers(response.data);
    } catch (err: any) {
      console.error('Failed to fetch modifiers:', err);
    }
  };

  const handleGroupSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError(null);

    try {
      const submitData = {
        ...groupFormData,
        max_selections: groupFormData.max_selections === '' ? null : groupFormData.max_selections
      };

      if (editingGroup) {
        const response = await apiClient.put(`/menu/modifier-groups/${editingGroup.id}`, submitData);
        setModifierGroups(groups => 
          groups.map(group => group.id === editingGroup.id ? response.data : group)
        );
      } else {
        const response = await apiClient.post('/menu/modifier-groups', submitData);
        setModifierGroups(groups => [...groups, response.data]);
        setSelectedGroup(response.data.id);
      }
      
      resetGroupForm();
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to save modifier group');
    } finally {
      setLoading(false);
    }
  };

  const handleModifierSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError(null);

    try {
      if (editingModifier) {
        const response = await apiClient.put(`/menu/modifiers/${editingModifier.id}`, modifierFormData);
        setModifiers(modifiers => 
          modifiers.map(modifier => modifier.id === editingModifier.id ? response.data : modifier)
        );
      } else {
        const response = await apiClient.post('/menu/modifiers', modifierFormData);
        setModifiers(modifiers => [...modifiers, response.data]);
      }
      
      resetModifierForm();
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to save modifier');
    } finally {
      setLoading(false);
    }
  };

  const handleEditGroup = (group: ModifierGroup) => {
    setEditingGroup(group);
    setGroupFormData({
      name: group.name,
      description: group.description || '',
      selection_type: group.selection_type,
      min_selections: group.min_selections,
      max_selections: group.max_selections || '',
      is_required: group.is_required,
      display_order: group.display_order,
      is_active: group.is_active
    });
    setShowGroupForm(true);
  };

  const handleEditModifier = (modifier: Modifier) => {
    setEditingModifier(modifier);
    setModifierFormData({
      modifier_group_id: modifier.modifier_group_id,
      name: modifier.name,
      description: modifier.description || '',
      price_adjustment: modifier.price_adjustment,
      price_type: modifier.price_type,
      is_active: modifier.is_active,
      is_available: modifier.is_available,
      display_order: modifier.display_order
    });
    setShowModifierForm(true);
  };

  const handleDeleteGroup = async (groupId: number) => {
    if (!window.confirm('Are you sure you want to delete this modifier group? This will also delete all associated modifiers.')) {
      return;
    }

    setLoading(true);
    try {
      await apiClient.delete(`/menu/modifier-groups/${groupId}`);
      setModifierGroups(groups => groups.filter(group => group.id !== groupId));
      if (selectedGroup === groupId) {
        const remainingGroups = modifierGroups.filter(group => group.id !== groupId);
        setSelectedGroup(remainingGroups.length > 0 ? remainingGroups[0].id : null);
      }
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to delete modifier group');
    } finally {
      setLoading(false);
    }
  };

  const handleDeleteModifier = async (modifierId: number) => {
    if (!window.confirm('Are you sure you want to delete this modifier?')) {
      return;
    }

    setLoading(true);
    try {
      await apiClient.delete(`/menu/modifiers/${modifierId}`);
      setModifiers(modifiers => modifiers.filter(modifier => modifier.id !== modifierId));
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to delete modifier');
    } finally {
      setLoading(false);
    }
  };

  const resetGroupForm = () => {
    setGroupFormData({
      name: '',
      description: '',
      selection_type: 'single',
      min_selections: 0,
      max_selections: '',
      is_required: false,
      display_order: 0,
      is_active: true
    });
    setEditingGroup(null);
    setShowGroupForm(false);
  };

  const resetModifierForm = () => {
    setModifierFormData({
      modifier_group_id: selectedGroup || 0,
      name: '',
      description: '',
      price_adjustment: 0,
      price_type: 'fixed',
      is_active: true,
      is_available: true,
      display_order: 0
    });
    setEditingModifier(null);
    setShowModifierForm(false);
  };

  const getGroupName = (groupId: number) => {
    const group = modifierGroups.find(g => g.id === groupId);
    return group ? group.name : 'Unknown';
  };

  return (
    <div className="modifier-management">
      <div className="modifier-header">
        <h2>Modifier Management</h2>
        <div className="tab-buttons">
          <button 
            className={`tab-btn ${activeTab === 'groups' ? 'active' : ''}`}
            onClick={() => setActiveTab('groups')}
          >
            Modifier Groups
          </button>
          <button 
            className={`tab-btn ${activeTab === 'modifiers' ? 'active' : ''}`}
            onClick={() => setActiveTab('modifiers')}
          >
            Modifiers
          </button>
        </div>
      </div>

      {error && (
        <div className="alert alert-error">
          {error}
        </div>
      )}

      {/* Modifier Groups Tab */}
      {activeTab === 'groups' && (
        <div className="groups-section">
          <div className="section-header">
            <h3>Modifier Groups</h3>
            <button 
              className="btn btn-primary"
              onClick={() => setShowGroupForm(true)}
              disabled={loading}
            >
              Add Group
            </button>
          </div>

          {showGroupForm && (
            <div className="form-modal">
              <div className="form-content">
                <h4>{editingGroup ? 'Edit Modifier Group' : 'Add New Modifier Group'}</h4>
                
                <form onSubmit={handleGroupSubmit}>
                  <div className="form-group">
                    <label htmlFor="group-name">Name *</label>
                    <input
                      type="text"
                      id="group-name"
                      value={groupFormData.name}
                      onChange={(e) => setGroupFormData({...groupFormData, name: e.target.value})}
                      required
                      disabled={loading}
                    />
                  </div>

                  <div className="form-group">
                    <label htmlFor="group-description">Description</label>
                    <textarea
                      id="group-description"
                      value={groupFormData.description}
                      onChange={(e) => setGroupFormData({...groupFormData, description: e.target.value})}
                      disabled={loading}
                      rows={3}
                    />
                  </div>

                  <div className="form-row">
                    <div className="form-group">
                      <label htmlFor="selection-type">Selection Type</label>
                      <select
                        id="selection-type"
                        value={groupFormData.selection_type}
                        onChange={(e) => setGroupFormData({...groupFormData, selection_type: e.target.value as 'single' | 'multiple'})}
                        disabled={loading}
                      >
                        <option value="single">Single Selection</option>
                        <option value="multiple">Multiple Selection</option>
                      </select>
                    </div>

                    <div className="form-group">
                      <label htmlFor="display-order">Display Order</label>
                      <input
                        type="number"
                        id="display-order"
                        value={groupFormData.display_order}
                        onChange={(e) => setGroupFormData({...groupFormData, display_order: parseInt(e.target.value) || 0})}
                        disabled={loading}
                        min="0"
                      />
                    </div>
                  </div>

                  <div className="form-row">
                    <div className="form-group">
                      <label htmlFor="min-selections">Minimum Selections</label>
                      <input
                        type="number"
                        id="min-selections"
                        value={groupFormData.min_selections}
                        onChange={(e) => setGroupFormData({...groupFormData, min_selections: parseInt(e.target.value) || 0})}
                        disabled={loading}
                        min="0"
                      />
                    </div>

                    <div className="form-group">
                      <label htmlFor="max-selections">Maximum Selections</label>
                      <input
                        type="number"
                        id="max-selections"
                        value={groupFormData.max_selections}
                        onChange={(e) => setGroupFormData({...groupFormData, max_selections: e.target.value ? parseInt(e.target.value) : ''})}
                        disabled={loading}
                        min="0"
                        placeholder="Unlimited"
                      />
                    </div>
                  </div>

                  <div className="form-row">
                    <div className="form-group">
                      <label className="checkbox-label">
                        <input
                          type="checkbox"
                          checked={groupFormData.is_required}
                          onChange={(e) => setGroupFormData({...groupFormData, is_required: e.target.checked})}
                          disabled={loading}
                        />
                        Required
                      </label>
                    </div>

                    <div className="form-group">
                      <label className="checkbox-label">
                        <input
                          type="checkbox"
                          checked={groupFormData.is_active}
                          onChange={(e) => setGroupFormData({...groupFormData, is_active: e.target.checked})}
                          disabled={loading}
                        />
                        Active
                      </label>
                    </div>
                  </div>

                  <div className="form-actions">
                    <button 
                      type="submit" 
                      className="btn btn-primary" 
                      disabled={loading}
                    >
                      {loading ? 'Saving...' : (editingGroup ? 'Update' : 'Create')}
                    </button>
                    <button 
                      type="button" 
                      className="btn btn-secondary" 
                      onClick={resetGroupForm}
                      disabled={loading}
                    >
                      Cancel
                    </button>
                  </div>
                </form>
              </div>
            </div>
          )}

          <div className="groups-list">
            {loading && modifierGroups.length === 0 ? (
              <div className="loading">Loading modifier groups...</div>
            ) : (
              <div className="groups-table">
                <table>
                  <thead>
                    <tr>
                      <th>Name</th>
                      <th>Description</th>
                      <th>Type</th>
                      <th>Selections</th>
                      <th>Required</th>
                      <th>Status</th>
                      <th>Actions</th>
                    </tr>
                  </thead>
                  <tbody>
                    {modifierGroups.map(group => (
                      <tr key={group.id} className={!group.is_active ? 'inactive' : ''}>
                        <td>{group.name}</td>
                        <td>{group.description || '-'}</td>
                        <td>
                          <span className={`selection-type ${group.selection_type}`}>
                            {group.selection_type === 'single' ? 'Single' : 'Multiple'}
                          </span>
                        </td>
                        <td>
                          {group.min_selections} - {group.max_selections || '∞'}
                        </td>
                        <td>
                          <span className={`required ${group.is_required ? 'yes' : 'no'}`}>
                            {group.is_required ? 'Yes' : 'No'}
                          </span>
                        </td>
                        <td>
                          <span className={`status ${group.is_active ? 'active' : 'inactive'}`}>
                            {group.is_active ? 'Active' : 'Inactive'}
                          </span>
                        </td>
                        <td>
                          <div className="action-buttons">
                            <button 
                              className="btn btn-sm btn-primary"
                              onClick={() => handleEditGroup(group)}
                              disabled={loading}
                            >
                              Edit
                            </button>
                            <button 
                              className="btn btn-sm btn-secondary"
                              onClick={() => {
                                setSelectedGroup(group.id);
                                setActiveTab('modifiers');
                              }}
                              disabled={loading}
                            >
                              View Modifiers
                            </button>
                            <button 
                              className="btn btn-sm btn-danger"
                              onClick={() => handleDeleteGroup(group.id)}
                              disabled={loading}
                            >
                              Delete
                            </button>
                          </div>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>

                {modifierGroups.length === 0 && !loading && (
                  <div className="empty-state">
                    <p>No modifier groups found. Create your first group to get started.</p>
                  </div>
                )}
              </div>
            )}
          </div>
        </div>
      )}

      {/* Modifiers Tab */}
      {activeTab === 'modifiers' && (
        <div className="modifiers-section">
          <div className="section-header">
            <div>
              <h3>Modifiers</h3>
              {selectedGroup && (
                <div className="group-selector">
                  <label htmlFor="group-select">Modifier Group:</label>
                  <select
                    id="group-select"
                    value={selectedGroup}
                    onChange={(e) => setSelectedGroup(parseInt(e.target.value))}
                  >
                    {modifierGroups.map(group => (
                      <option key={group.id} value={group.id}>{group.name}</option>
                    ))}
                  </select>
                </div>
              )}
            </div>
            <button 
              className="btn btn-primary"
              onClick={() => {
                setModifierFormData({...modifierFormData, modifier_group_id: selectedGroup || 0});
                setShowModifierForm(true);
              }}
              disabled={loading || !selectedGroup}
            >
              Add Modifier
            </button>
          </div>

          {showModifierForm && (
            <div className="form-modal">
              <div className="form-content">
                <h4>{editingModifier ? 'Edit Modifier' : 'Add New Modifier'}</h4>
                
                <form onSubmit={handleModifierSubmit}>
                  <div className="form-group">
                    <label htmlFor="modifier-name">Name *</label>
                    <input
                      type="text"
                      id="modifier-name"
                      value={modifierFormData.name}
                      onChange={(e) => setModifierFormData({...modifierFormData, name: e.target.value})}
                      required
                      disabled={loading}
                    />
                  </div>

                  <div className="form-group">
                    <label htmlFor="modifier-description">Description</label>
                    <textarea
                      id="modifier-description"
                      value={modifierFormData.description}
                      onChange={(e) => setModifierFormData({...modifierFormData, description: e.target.value})}
                      disabled={loading}
                      rows={3}
                    />
                  </div>

                  <div className="form-row">
                    <div className="form-group">
                      <label htmlFor="price-adjustment">Price Adjustment</label>
                      <input
                        type="number"
                        id="price-adjustment"
                        value={modifierFormData.price_adjustment}
                        onChange={(e) => setModifierFormData({...modifierFormData, price_adjustment: parseFloat(e.target.value) || 0})}
                        disabled={loading}
                        step="0.01"
                      />
                    </div>

                    <div className="form-group">
                      <label htmlFor="price-type">Price Type</label>
                      <select
                        id="price-type"
                        value={modifierFormData.price_type}
                        onChange={(e) => setModifierFormData({...modifierFormData, price_type: e.target.value as 'fixed' | 'percentage'})}
                        disabled={loading}
                      >
                        <option value="fixed">Fixed Amount</option>
                        <option value="percentage">Percentage</option>
                      </select>
                    </div>
                  </div>

                  <div className="form-row">
                    <div className="form-group">
                      <label htmlFor="modifier-display-order">Display Order</label>
                      <input
                        type="number"
                        id="modifier-display-order"
                        value={modifierFormData.display_order}
                        onChange={(e) => setModifierFormData({...modifierFormData, display_order: parseInt(e.target.value) || 0})}
                        disabled={loading}
                        min="0"
                      />
                    </div>
                  </div>

                  <div className="form-row">
                    <div className="form-group">
                      <label className="checkbox-label">
                        <input
                          type="checkbox"
                          checked={modifierFormData.is_active}
                          onChange={(e) => setModifierFormData({...modifierFormData, is_active: e.target.checked})}
                          disabled={loading}
                        />
                        Active
                      </label>
                    </div>

                    <div className="form-group">
                      <label className="checkbox-label">
                        <input
                          type="checkbox"
                          checked={modifierFormData.is_available}
                          onChange={(e) => setModifierFormData({...modifierFormData, is_available: e.target.checked})}
                          disabled={loading}
                        />
                        Available
                      </label>
                    </div>
                  </div>

                  <div className="form-actions">
                    <button 
                      type="submit" 
                      className="btn btn-primary" 
                      disabled={loading}
                    >
                      {loading ? 'Saving...' : (editingModifier ? 'Update' : 'Create')}
                    </button>
                    <button 
                      type="button" 
                      className="btn btn-secondary" 
                      onClick={resetModifierForm}
                      disabled={loading}
                    >
                      Cancel
                    </button>
                  </div>
                </form>
              </div>
            </div>
          )}

          {selectedGroup ? (
            <div className="modifiers-list">
              <div className="modifiers-table">
                <table>
                  <thead>
                    <tr>
                      <th>Name</th>
                      <th>Description</th>
                      <th>Price Adjustment</th>
                      <th>Status</th>
                      <th>Availability</th>
                      <th>Actions</th>
                    </tr>
                  </thead>
                  <tbody>
                    {modifiers.map(modifier => (
                      <tr key={modifier.id} className={!modifier.is_active ? 'inactive' : ''}>
                        <td>{modifier.name}</td>
                        <td>{modifier.description || '-'}</td>
                        <td>
                          <span className={`price-adjustment ${modifier.price_adjustment >= 0 ? 'positive' : 'negative'}`}>
                            {modifier.price_adjustment >= 0 ? '+' : ''}
                            {modifier.price_type === 'percentage' 
                              ? `${modifier.price_adjustment}%` 
                              : `$${modifier.price_adjustment.toFixed(2)}`
                            }
                          </span>
                        </td>
                        <td>
                          <span className={`status ${modifier.is_active ? 'active' : 'inactive'}`}>
                            {modifier.is_active ? 'Active' : 'Inactive'}
                          </span>
                        </td>
                        <td>
                          <span className={`availability ${modifier.is_available ? 'available' : 'unavailable'}`}>
                            {modifier.is_available ? 'Available' : 'Unavailable'}
                          </span>
                        </td>
                        <td>
                          <div className="action-buttons">
                            <button 
                              className="btn btn-sm btn-primary"
                              onClick={() => handleEditModifier(modifier)}
                              disabled={loading}
                            >
                              Edit
                            </button>
                            <button 
                              className="btn btn-sm btn-danger"
                              onClick={() => handleDeleteModifier(modifier.id)}
                              disabled={loading}
                            >
                              Delete
                            </button>
                          </div>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>

                {modifiers.length === 0 && (
                  <div className="empty-state">
                    <p>No modifiers found for this group. Add modifiers to get started.</p>
                  </div>
                )}
              </div>
            </div>
          ) : (
            <div className="empty-state">
              <p>Please select a modifier group to view modifiers.</p>
            </div>
          )}
        </div>
      )}
    </div>
  );
};

export default ModifierManagement;