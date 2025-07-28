import React, { useState, useEffect } from 'react';
import { apiClient } from '../../utils/apiClient';
import './MenuItemManagement.css';

interface MenuCategory {
  id: number;
  name: string;
  is_active: boolean;
}

interface MenuItem {
  id: number;
  name: string;
  description?: string;
  price: number;
  category_id: number;
  sku?: string;
  is_active: boolean;
  is_available: boolean;
  availability_start_time?: string;
  availability_end_time?: string;
  calories?: number;
  allergens?: string[];
  dietary_tags?: string[];
  prep_time_minutes?: number;
  serving_size?: string;
  image_url?: string;
  images?: string[];
  display_order: number;
  created_at: string;
  updated_at: string;
}

interface MenuItemFormData {
  name: string;
  description: string;
  price: number;
  category_id: number;
  sku: string;
  is_active: boolean;
  is_available: boolean;
  availability_start_time: string;
  availability_end_time: string;
  calories: number | '';
  allergens: string[];
  dietary_tags: string[];
  prep_time_minutes: number | '';
  serving_size: string;
  image_url: string;
  display_order: number;
}

interface SearchParams {
  query: string;
  category_id: number | '';
  is_active: boolean | '';
  is_available: boolean | '';
  min_price: number | '';
  max_price: number | '';
}

const MenuItemManagement: React.FC = () => {
  const [items, setItems] = useState<MenuItem[]>([]);
  const [categories, setCategories] = useState<MenuCategory[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [showForm, setShowForm] = useState(false);
  const [editingItem, setEditingItem] = useState<MenuItem | null>(null);
  const [searchParams, setSearchParams] = useState<SearchParams>({
    query: '',
    category_id: '',
    is_active: '',
    is_available: '',
    min_price: '',
    max_price: ''
  });
  const [pagination, setPagination] = useState({
    page: 1,
    size: 20,
    total: 0,
    pages: 0
  });

  const [formData, setFormData] = useState<MenuItemFormData>({
    name: '',
    description: '',
    price: 0,
    category_id: 0,
    sku: '',
    is_active: true,
    is_available: true,
    availability_start_time: '',
    availability_end_time: '',
    calories: '',
    allergens: [],
    dietary_tags: [],
    prep_time_minutes: '',
    serving_size: '',
    image_url: '',
    display_order: 0
  });

  const commonAllergens = [
    'Gluten', 'Dairy', 'Eggs', 'Nuts', 'Peanuts', 'Shellfish', 'Fish', 'Soy', 'Sesame'
  ];

  const commonDietaryTags = [
    'Vegetarian', 'Vegan', 'Gluten-Free', 'Dairy-Free', 'Low-Carb', 'Keto', 'Halal', 'Kosher'
  ];

  useEffect(() => {
    fetchCategories();
    fetchMenuItems();
  }, [searchParams, pagination.page]);

  const fetchCategories = async () => {
    try {
      const response = await apiClient.get('/menu/categories');
      setCategories(response.data);
    } catch (err: any) {
      console.error('Failed to fetch categories:', err);
    }
  };

  const fetchMenuItems = async () => {
    setLoading(true);
    setError(null);
    
    try {
      const params = new URLSearchParams();
      if (searchParams.query) params.append('query', searchParams.query);
      if (searchParams.category_id) params.append('category_id', searchParams.category_id.toString());
      if (searchParams.is_active !== '') params.append('is_active', searchParams.is_active.toString());
      if (searchParams.is_available !== '') params.append('is_available', searchParams.is_available.toString());
      if (searchParams.min_price) params.append('min_price', searchParams.min_price.toString());
      if (searchParams.max_price) params.append('max_price', searchParams.max_price.toString());
      params.append('limit', pagination.size.toString());
      params.append('offset', ((pagination.page - 1) * pagination.size).toString());

      const response = await apiClient.get(`/menu/items?${params.toString()}`);
      setItems(response.data.items);
      setPagination(prev => ({
        ...prev,
        total: response.data.total,
        pages: response.data.pages
      }));
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to fetch menu items');
    } finally {
      setLoading(false);
    }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError(null);

    try {
      const submitData = {
        ...formData,
        calories: formData.calories === '' ? null : formData.calories,
        prep_time_minutes: formData.prep_time_minutes === '' ? null : formData.prep_time_minutes
      };

      if (editingItem) {
        const response = await apiClient.put(`/menu/items/${editingItem.id}`, submitData);
        setItems(items.map(item => item.id === editingItem.id ? response.data : item));
      } else {
        const response = await apiClient.post('/menu/items', submitData);
        fetchMenuItems(); // Refresh the list
      }
      
      resetForm();
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to save menu item');
    } finally {
      setLoading(false);
    }
  };

  const handleEdit = (item: MenuItem) => {
    setEditingItem(item);
    setFormData({
      name: item.name,
      description: item.description || '',
      price: item.price,
      category_id: item.category_id,
      sku: item.sku || '',
      is_active: item.is_active,
      is_available: item.is_available,
      availability_start_time: item.availability_start_time || '',
      availability_end_time: item.availability_end_time || '',
      calories: item.calories || '',
      allergens: item.allergens || [],
      dietary_tags: item.dietary_tags || [],
      prep_time_minutes: item.prep_time_minutes || '',
      serving_size: item.serving_size || '',
      image_url: item.image_url || '',
      display_order: item.display_order
    });
    setShowForm(true);
  };

  const handleDelete = async (itemId: number) => {
    if (!window.confirm('Are you sure you want to delete this menu item?')) {
      return;
    }

    setLoading(true);
    try {
      await apiClient.delete(`/menu/items/${itemId}`);
      setItems(items.filter(item => item.id !== itemId));
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to delete menu item');
    } finally {
      setLoading(false);
    }
  };

  const resetForm = () => {
    setFormData({
      name: '',
      description: '',
      price: 0,
      category_id: 0,
      sku: '',
      is_active: true,
      is_available: true,
      availability_start_time: '',
      availability_end_time: '',
      calories: '',
      allergens: [],
      dietary_tags: [],
      prep_time_minutes: '',
      serving_size: '',
      image_url: '',
      display_order: 0
    });
    setEditingItem(null);
    setShowForm(false);
  };

  const handleAllergenToggle = (allergen: string) => {
    const newAllergens = formData.allergens.includes(allergen)
      ? formData.allergens.filter(a => a !== allergen)
      : [...formData.allergens, allergen];
    setFormData({...formData, allergens: newAllergens});
  };

  const handleDietaryTagToggle = (tag: string) => {
    const newTags = formData.dietary_tags.includes(tag)
      ? formData.dietary_tags.filter(t => t !== tag)
      : [...formData.dietary_tags, tag];
    setFormData({...formData, dietary_tags: newTags});
  };

  const getCategoryName = (categoryId: number) => {
    const category = categories.find(cat => cat.id === categoryId);
    return category ? category.name : 'Unknown';
  };

  return (
    <div className="menu-item-management">
      <div className="item-header">
        <h2>Menu Items</h2>
        <button 
          className="btn btn-primary"
          onClick={() => setShowForm(true)}
          disabled={loading}
        >
          Add Menu Item
        </button>
      </div>

      {error && (
        <div className="alert alert-error">
          {error}
        </div>
      )}

      {/* Search and Filters */}
      <div className="search-filters">
        <div className="search-row">
          <input
            type="text"
            placeholder="Search menu items..."
            value={searchParams.query}
            onChange={(e) => setSearchParams({...searchParams, query: e.target.value})}
            className="search-input"
          />
          
          <select
            value={searchParams.category_id}
            onChange={(e) => setSearchParams({...searchParams, category_id: e.target.value ? parseInt(e.target.value) : ''})}
            className="filter-select"
          >
            <option value="">All Categories</option>
            {categories.map(cat => (
              <option key={cat.id} value={cat.id}>{cat.name}</option>
            ))}
          </select>

          <select
            value={searchParams.is_active}
            onChange={(e) => setSearchParams({...searchParams, is_active: e.target.value === '' ? '' : e.target.value === 'true'})}
            className="filter-select"
          >
            <option value="">All Status</option>
            <option value="true">Active</option>
            <option value="false">Inactive</option>
          </select>

          <select
            value={searchParams.is_available}
            onChange={(e) => setSearchParams({...searchParams, is_available: e.target.value === '' ? '' : e.target.value === 'true'})}
            className="filter-select"
          >
            <option value="">All Availability</option>
            <option value="true">Available</option>
            <option value="false">Unavailable</option>
          </select>
        </div>

        <div className="price-filters">
          <input
            type="number"
            placeholder="Min Price"
            value={searchParams.min_price}
            onChange={(e) => setSearchParams({...searchParams, min_price: e.target.value ? parseFloat(e.target.value) : ''})}
            className="price-input"
            min="0"
            step="0.01"
          />
          <input
            type="number"
            placeholder="Max Price"
            value={searchParams.max_price}
            onChange={(e) => setSearchParams({...searchParams, max_price: e.target.value ? parseFloat(e.target.value) : ''})}
            className="price-input"
            min="0"
            step="0.01"
          />
        </div>
      </div>

      {/* Form Modal */}
      {showForm && (
        <div className="item-form-modal">
          <div className="item-form-content">
            <h3>{editingItem ? 'Edit Menu Item' : 'Add New Menu Item'}</h3>
            
            <form onSubmit={handleSubmit}>
              <div className="form-section">
                <h4>Basic Information</h4>
                
                <div className="form-row">
                  <div className="form-group">
                    <label htmlFor="name">Name *</label>
                    <input
                      type="text"
                      id="name"
                      value={formData.name}
                      onChange={(e) => setFormData({...formData, name: e.target.value})}
                      required
                      disabled={loading}
                    />
                  </div>

                  <div className="form-group">
                    <label htmlFor="sku">SKU</label>
                    <input
                      type="text"
                      id="sku"
                      value={formData.sku}
                      onChange={(e) => setFormData({...formData, sku: e.target.value})}
                      disabled={loading}
                    />
                  </div>
                </div>

                <div className="form-group">
                  <label htmlFor="description">Description</label>
                  <textarea
                    id="description"
                    value={formData.description}
                    onChange={(e) => setFormData({...formData, description: e.target.value})}
                    disabled={loading}
                    rows={3}
                  />
                </div>

                <div className="form-row">
                  <div className="form-group">
                    <label htmlFor="category_id">Category *</label>
                    <select
                      id="category_id"
                      value={formData.category_id}
                      onChange={(e) => setFormData({...formData, category_id: parseInt(e.target.value)})}
                      required
                      disabled={loading}
                    >
                      <option value="">Select Category</option>
                      {categories.map(cat => (
                        <option key={cat.id} value={cat.id}>{cat.name}</option>
                      ))}
                    </select>
                  </div>

                  <div className="form-group">
                    <label htmlFor="price">Price *</label>
                    <input
                      type="number"
                      id="price"
                      value={formData.price}
                      onChange={(e) => setFormData({...formData, price: parseFloat(e.target.value) || 0})}
                      required
                      disabled={loading}
                      min="0"
                      step="0.01"
                    />
                  </div>
                </div>
              </div>

              <div className="form-section">
                <h4>Availability & Settings</h4>
                
                <div className="form-row">
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

                  <div className="form-group">
                    <label className="checkbox-label">
                      <input
                        type="checkbox"
                        checked={formData.is_available}
                        onChange={(e) => setFormData({...formData, is_available: e.target.checked})}
                        disabled={loading}
                      />
                      Available
                    </label>
                  </div>
                </div>

                <div className="form-row">
                  <div className="form-group">
                    <label htmlFor="availability_start_time">Available From</label>
                    <input
                      type="time"
                      id="availability_start_time"
                      value={formData.availability_start_time}
                      onChange={(e) => setFormData({...formData, availability_start_time: e.target.value})}
                      disabled={loading}
                    />
                  </div>

                  <div className="form-group">
                    <label htmlFor="availability_end_time">Available Until</label>
                    <input
                      type="time"
                      id="availability_end_time"
                      value={formData.availability_end_time}
                      onChange={(e) => setFormData({...formData, availability_end_time: e.target.value})}
                      disabled={loading}
                    />
                  </div>
                </div>
              </div>

              <div className="form-section">
                <h4>Nutritional Information</h4>
                
                <div className="form-row">
                  <div className="form-group">
                    <label htmlFor="calories">Calories</label>
                    <input
                      type="number"
                      id="calories"
                      value={formData.calories}
                      onChange={(e) => setFormData({...formData, calories: e.target.value ? parseInt(e.target.value) : ''})}
                      disabled={loading}
                      min="0"
                    />
                  </div>

                  <div className="form-group">
                    <label htmlFor="serving_size">Serving Size</label>
                    <input
                      type="text"
                      id="serving_size"
                      value={formData.serving_size}
                      onChange={(e) => setFormData({...formData, serving_size: e.target.value})}
                      disabled={loading}
                      placeholder="e.g., 1 cup, 250g"
                    />
                  </div>
                </div>

                <div className="form-group">
                  <label>Allergens</label>
                  <div className="checkbox-grid">
                    {commonAllergens.map(allergen => (
                      <label key={allergen} className="checkbox-label">
                        <input
                          type="checkbox"
                          checked={formData.allergens.includes(allergen)}
                          onChange={() => handleAllergenToggle(allergen)}
                          disabled={loading}
                        />
                        {allergen}
                      </label>
                    ))}
                  </div>
                </div>

                <div className="form-group">
                  <label>Dietary Tags</label>
                  <div className="checkbox-grid">
                    {commonDietaryTags.map(tag => (
                      <label key={tag} className="checkbox-label">
                        <input
                          type="checkbox"
                          checked={formData.dietary_tags.includes(tag)}
                          onChange={() => handleDietaryTagToggle(tag)}
                          disabled={loading}
                        />
                        {tag}
                      </label>
                    ))}
                  </div>
                </div>
              </div>

              <div className="form-section">
                <h4>Additional Details</h4>
                
                <div className="form-row">
                  <div className="form-group">
                    <label htmlFor="prep_time_minutes">Prep Time (minutes)</label>
                    <input
                      type="number"
                      id="prep_time_minutes"
                      value={formData.prep_time_minutes}
                      onChange={(e) => setFormData({...formData, prep_time_minutes: e.target.value ? parseInt(e.target.value) : ''})}
                      disabled={loading}
                      min="0"
                    />
                  </div>

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
                </div>

                <div className="form-group">
                  <label htmlFor="image_url">Image URL</label>
                  <input
                    type="url"
                    id="image_url"
                    value={formData.image_url}
                    onChange={(e) => setFormData({...formData, image_url: e.target.value})}
                    disabled={loading}
                  />
                </div>
              </div>

              <div className="form-actions">
                <button 
                  type="submit" 
                  className="btn btn-primary" 
                  disabled={loading}
                >
                  {loading ? 'Saving...' : (editingItem ? 'Update' : 'Create')}
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

      {/* Items List */}
      <div className="items-list">
        {loading && items.length === 0 ? (
          <div className="loading">Loading menu items...</div>
        ) : (
          <div className="items-table">
            <table>
              <thead>
                <tr>
                  <th>Item</th>
                  <th>Category</th>
                  <th>Price</th>
                  <th>Status</th>
                  <th>Availability</th>
                  <th>Created</th>
                  <th>Actions</th>
                </tr>
              </thead>
              <tbody>
                {items.map(item => (
                  <tr key={item.id} className={!item.is_active ? 'inactive' : ''}>
                    <td>
                      <div className="item-info">
                        {item.image_url && (
                          <img 
                            src={item.image_url} 
                            alt={item.name}
                            className="item-thumbnail"
                          />
                        )}
                        <div>
                          <div className="item-name">{item.name}</div>
                          {item.sku && <div className="item-sku">SKU: {item.sku}</div>}
                          {item.description && <div className="item-description">{item.description}</div>}
                        </div>
                      </div>
                    </td>
                    <td>{getCategoryName(item.category_id)}</td>
                    <td>${item.price.toFixed(2)}</td>
                    <td>
                      <span className={`status ${item.is_active ? 'active' : 'inactive'}`}>
                        {item.is_active ? 'Active' : 'Inactive'}
                      </span>
                    </td>
                    <td>
                      <span className={`availability ${item.is_available ? 'available' : 'unavailable'}`}>
                        {item.is_available ? 'Available' : 'Unavailable'}
                      </span>
                    </td>
                    <td>{new Date(item.created_at).toLocaleDateString()}</td>
                    <td>
                      <div className="action-buttons">
                        <button 
                          className="btn btn-sm btn-primary"
                          onClick={() => handleEdit(item)}
                          disabled={loading}
                        >
                          Edit
                        </button>
                        <button 
                          className="btn btn-sm btn-danger"
                          onClick={() => handleDelete(item.id)}
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

            {items.length === 0 && !loading && (
              <div className="empty-state">
                <p>No menu items found. Create your first menu item to get started.</p>
              </div>
            )}
          </div>
        )}

        {/* Pagination */}
        {pagination.pages > 1 && (
          <div className="pagination">
            <button 
              onClick={() => setPagination(prev => ({...prev, page: prev.page - 1}))}
              disabled={pagination.page === 1}
              className="btn btn-secondary btn-sm"
            >
              Previous
            </button>
            
            <span className="pagination-info">
              Page {pagination.page} of {pagination.pages} ({pagination.total} items)
            </span>
            
            <button 
              onClick={() => setPagination(prev => ({...prev, page: prev.page + 1}))}
              disabled={pagination.page === pagination.pages}
              className="btn btn-secondary btn-sm"
            >
              Next
            </button>
          </div>
        )}
      </div>
    </div>
  );
};

export default MenuItemManagement;