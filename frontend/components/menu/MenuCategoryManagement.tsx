import React, { useState, useEffect } from 'react';
import { apiClient } from '../../utils/apiClient';
import './MenuCategoryManagement.css';

interface MenuCategory {
  id: number;
  name: string;
  description?: string;
  display_order: number;
  is_active: boolean;
  parent_category_id?: number;
  image_url?: string;
  created_at: string;
  updated_at: string;
}

interface CategoryFormData {
  name: string;
  description: string;
  display_order: number;
  is_active: boolean;
  parent_category_id?: number;
  image_url: string;
}

const MenuCategoryManagement: React.FC = () => {
  const [categories, setCategories] = useState<MenuCategory[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [showForm, setShowForm] = useState(false);
  const [editingCategory, setEditingCategory] = useState<MenuCategory | null>(null);
  const [formData, setFormData] = useState<CategoryFormData>({
    name: '',
    description: '',
    display_order: 0,
    is_active: true,
    parent_category_id: undefined,
    image_url: ''
  });

  useEffect(() => {
    fetchCategories();
  }, []);

  const fetchCategories = async () => {
    setLoading(true);
    setError(null);
    try {
      const response = await apiClient.get('/menu/categories?active_only=false');
      setCategories(response.data);
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to fetch categories');
    } finally {
      setLoading(false);
    }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError(null);

    try {
      if (editingCategory) {
        const response = await apiClient.put(
          `/menu/categories/${editingCategory.id}`,
          formData
        );
        setCategories(categories.map(cat => 
          cat.id === editingCategory.id ? response.data : cat
        ));
      } else {
        const response = await apiClient.post('/menu/categories', formData);
        setCategories([...categories, response.data]);
      }
      
      resetForm();
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to save category');
    } finally {
      setLoading(false);
    }
  };

  const handleEdit = (category: MenuCategory) => {
    setEditingCategory(category);
    setFormData({
      name: category.name,
      description: category.description || '',
      display_order: category.display_order,
      is_active: category.is_active,
      parent_category_id: category.parent_category_id,
      image_url: category.image_url || ''
    });
    setShowForm(true);
  };

  const handleDelete = async (categoryId: number) => {
    if (!window.confirm('Are you sure you want to delete this category?')) {
      return;
    }

    setLoading(true);
    try {
      await apiClient.delete(`/menu/categories/${categoryId}`);
      setCategories(categories.filter(cat => cat.id !== categoryId));
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to delete category');
    } finally {
      setLoading(false);
    }
  };

  const resetForm = () => {
    setFormData({
      name: '',
      description: '',
      display_order: 0,
      is_active: true,
      parent_category_id: undefined,
      image_url: ''
    });
    setEditingCategory(null);
    setShowForm(false);
  };

  const getParentCategoryName = (parentId?: number) => {
    if (!parentId) return 'None';
    const parent = categories.find(cat => cat.id === parentId);
    return parent ? parent.name : 'Unknown';
  };

  return (
    <div className="menu-category-management">
      <div className="category-header">
        <h2>Menu Categories</h2>
        <button 
          className="btn btn-primary"
          onClick={() => setShowForm(true)}
          disabled={loading}
        >
          Add Category
        </button>
      </div>

      {error && (
        <div className="alert alert-error">
          {error}
        </div>
      )}

      {showForm && (
        <div className="category-form-modal">
          <div className="category-form-content">
            <h3>{editingCategory ? 'Edit Category' : 'Add New Category'}</h3>
            
            <form onSubmit={handleSubmit}>
              <div className="form-group">
                <label htmlFor="name">Name *</label>
                <input
                  type="text"
                  id="name"
                  value={formData.name}
                  onChange={(e) => setFormData({...formData, name: e.target.value})}
                  required
                  disabled={loading}
                  placeholder="Category name"
                />
              </div>

              <div className="form-group">
                <label htmlFor="description">Description</label>
                <textarea
                  id="description"
                  value={formData.description}
                  onChange={(e) => setFormData({...formData, description: e.target.value})}
                  disabled={loading}
                  placeholder="Category description"
                  rows={3}
                />
              </div>

              <div className="form-row">
                <div className="form-group">
                  <label htmlFor="display_order">Display Order</label>
                  <input
                    type="number"
                    id="display_order"
                    value={formData.display_order}
                    onChange={(e) => setFormData({...formData, display_order: parseInt(e.target.value) || 0})}
                    disabled={loading}
                    min="0"
                  />
                </div>

                <div className="form-group">
                  <label htmlFor="parent_category">Parent Category</label>
                  <select
                    id="parent_category"
                    value={formData.parent_category_id || ''}
                    onChange={(e) => setFormData({
                      ...formData, 
                      parent_category_id: e.target.value ? parseInt(e.target.value) : undefined
                    })}
                    disabled={loading}
                  >
                    <option value="">None (Top Level)</option>
                    {categories
                      .filter(cat => editingCategory ? cat.id !== editingCategory.id : true)
                      .map(cat => (
                        <option key={cat.id} value={cat.id}>
                          {cat.name}
                        </option>
                      ))
                    }
                  </select>
                </div>
              </div>

              <div className="form-group">
                <label htmlFor="image_url">Image URL</label>
                <input
                  type="url"
                  id="image_url"
                  value={formData.image_url}
                  onChange={(e) => setFormData({...formData, image_url: e.target.value})}
                  disabled={loading}
                  placeholder="https://example.com/image.jpg"
                />
              </div>

              <div className="form-group">
                <label className="checkbox-label">
                  <input
                    type="checkbox"
                    checked={formData.is_active}
                    onChange={(e) => setFormData({...formData, is_active: e.target.checked})}
                    disabled={loading}
                  />
                  Active
                </label>
              </div>

              <div className="form-actions">
                <button 
                  type="submit" 
                  className="btn btn-primary" 
                  disabled={loading}
                >
                  {loading ? 'Saving...' : (editingCategory ? 'Update' : 'Create')}
                </button>
                <button 
                  type="button" 
                  className="btn btn-secondary" 
                  onClick={resetForm}
                  disabled={loading}
                >
                  Cancel
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      <div className="categories-list">
        {loading && categories.length === 0 ? (
          <div className="loading">Loading categories...</div>
        ) : (
          <div className="categories-table">
            <table>
              <thead>
                <tr>
                  <th>Name</th>
                  <th>Description</th>
                  <th>Parent Category</th>
                  <th>Order</th>
                  <th>Status</th>
                  <th>Created</th>
                  <th>Actions</th>
                </tr>
              </thead>
              <tbody>
                {categories.map(category => (
                  <tr key={category.id} className={!category.is_active ? 'inactive' : ''}>
                    <td>
                      <div className="category-name">
                        {category.image_url && (
                          <img 
                            src={category.image_url} 
                            alt={category.name}
                            className="category-thumbnail"
                          />
                        )}
                        {category.name}
                      </div>
                    </td>
                    <td>{category.description || '-'}</td>
                    <td>{getParentCategoryName(category.parent_category_id)}</td>
                    <td>{category.display_order}</td>
                    <td>
                      <span className={`status ${category.is_active ? 'active' : 'inactive'}`}>
                        {category.is_active ? 'Active' : 'Inactive'}
                      </span>
                    </td>
                    <td>{new Date(category.created_at).toLocaleDateString()}</td>
                    <td>
                      <div className="action-buttons">
                        <button 
                          className="btn btn-sm btn-primary"
                          onClick={() => handleEdit(category)}
                          disabled={loading}
                        >
                          Edit
                        </button>
                        <button 
                          className="btn btn-sm btn-danger"
                          onClick={() => handleDelete(category.id)}
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

            {categories.length === 0 && !loading && (
              <div className="empty-state">
                <p>No categories found. Create your first category to get started.</p>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
};

export default MenuCategoryManagement;