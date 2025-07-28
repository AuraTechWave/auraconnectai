import React, { useState, useEffect } from 'react';
import apiClient from '../../utils/authInterceptor';
import './VendorManagement.css';

interface Vendor {
  id: number;
  name: string;
  description?: string;
  contact_person?: string;
  email?: string;
  phone?: string;
  address_line1?: string;
  address_line2?: string;
  city?: string;
  state?: string;
  postal_code?: string;
  country?: string;
  tax_id?: string;
  payment_terms?: string;
  delivery_lead_time?: number;
  minimum_order_amount?: number;
  status: 'active' | 'inactive' | 'suspended' | 'pending_approval';
  rating?: number;
  notes?: string;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

interface VendorFormData {
  name: string;
  description: string;
  contact_person: string;
  email: string;
  phone: string;
  address_line1: string;
  address_line2: string;
  city: string;
  state: string;
  postal_code: string;
  country: string;
  tax_id: string;
  payment_terms: string;
  delivery_lead_time: number | null;
  minimum_order_amount: number | null;
  status: 'active' | 'inactive' | 'suspended' | 'pending_approval';
  notes: string;
}

interface PurchaseOrder {
  id: number;
  po_number: string;
  vendor_id: number;
  status: string;
  order_date: string;
  expected_delivery_date?: string;
  actual_delivery_date?: string;
  total_amount: number;
  notes?: string;
}

const VendorManagement: React.FC = () => {
  const [vendors, setVendors] = useState<Vendor[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [showForm, setShowForm] = useState(false);
  const [editingVendor, setEditingVendor] = useState<Vendor | null>(null);
  const [selectedVendor, setSelectedVendor] = useState<Vendor | null>(null);
  const [vendorPOs, setVendorPOs] = useState<PurchaseOrder[]>([]);
  const [searchTerm, setSearchTerm] = useState('');
  const [statusFilter, setStatusFilter] = useState<string>('');
  
  const [formData, setFormData] = useState<VendorFormData>({
    name: '',
    description: '',
    contact_person: '',
    email: '',
    phone: '',
    address_line1: '',
    address_line2: '',
    city: '',
    state: '',
    postal_code: '',
    country: '',
    tax_id: '',
    payment_terms: '',
    delivery_lead_time: null,
    minimum_order_amount: null,
    status: 'active',
    notes: ''
  });

  useEffect(() => {
    fetchVendors();
  }, []);

  const fetchVendors = async () => {
    setLoading(true);
    setError(null);
    try {
      const response = await apiClient.get('/vendors/', {
        params: {
          active_only: false,
          search: searchTerm || undefined,
          status_filter: statusFilter || undefined
        }
      });
      setVendors(response.data);
    } catch (err: any) {
      console.error('Failed to fetch vendors:', err);
      setError(err.response?.data?.detail || 'Failed to load vendors');
    } finally {
      setLoading(false);
    }
  };

  const fetchVendorPOs = async (vendorId: number) => {
    try {
      const response = await apiClient.get(`/vendors/${vendorId}/purchase-orders`);
      setVendorPOs(response.data);
    } catch (err) {
      console.error('Failed to fetch vendor purchase orders:', err);
    }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError(null);

    try {
      if (editingVendor) {
        await apiClient.put(`/vendors/${editingVendor.id}`, formData);
      } else {
        await apiClient.post('/vendors/', formData);
      }
      
      resetForm();
      await fetchVendors();
    } catch (err: any) {
      console.error('Failed to save vendor:', err);
      setError(err.response?.data?.detail || 'Failed to save vendor');
    } finally {
      setLoading(false);
    }
  };

  const handleEdit = (vendor: Vendor) => {
    setEditingVendor(vendor);
    setFormData({
      name: vendor.name,
      description: vendor.description || '',
      contact_person: vendor.contact_person || '',
      email: vendor.email || '',
      phone: vendor.phone || '',
      address_line1: vendor.address_line1 || '',
      address_line2: vendor.address_line2 || '',
      city: vendor.city || '',
      state: vendor.state || '',
      postal_code: vendor.postal_code || '',
      country: vendor.country || '',
      tax_id: vendor.tax_id || '',
      payment_terms: vendor.payment_terms || '',
      delivery_lead_time: vendor.delivery_lead_time,
      minimum_order_amount: vendor.minimum_order_amount,
      status: vendor.status,
      notes: vendor.notes || ''
    });
    setShowForm(true);
  };

  const handleDelete = async (vendorId: number) => {
    if (!window.confirm('Are you sure you want to delete this vendor?')) {
      return;
    }

    try {
      await apiClient.delete(`/vendors/${vendorId}`);
      await fetchVendors();
    } catch (err: any) {
      console.error('Failed to delete vendor:', err);
      setError(err.response?.data?.detail || 'Failed to delete vendor');
    }
  };

  const handleViewVendor = async (vendor: Vendor) => {
    setSelectedVendor(vendor);
    await fetchVendorPOs(vendor.id);
  };

  const resetForm = () => {
    setFormData({
      name: '',
      description: '',
      contact_person: '',
      email: '',
      phone: '',
      address_line1: '',
      address_line2: '',
      city: '',
      state: '',
      postal_code: '',
      country: '',
      tax_id: '',
      payment_terms: '',
      delivery_lead_time: null,
      minimum_order_amount: null,
      status: 'active',
      notes: ''
    });
    setEditingVendor(null);
    setShowForm(false);
  };

  const getStatusBadgeClass = (status: string) => {
    switch (status) {
      case 'active': return 'status-active';
      case 'inactive': return 'status-inactive';
      case 'suspended': return 'status-suspended';
      case 'pending_approval': return 'status-pending';
      default: return 'status-inactive';
    }
  };

  const formatCurrency = (amount: number) => {
    return new Intl.NumberFormat('en-US', {
      style: 'currency',
      currency: 'USD'
    }).format(amount);
  };

  const formatDate = (dateString: string) => {
    return new Date(dateString).toLocaleDateString();
  };

  const renderStars = (rating?: number) => {
    if (!rating) return <span className="no-rating">No rating</span>;
    
    const stars = [];
    for (let i = 1; i <= 5; i++) {
      stars.push(
        <span key={i} className={i <= rating ? 'star filled' : 'star'}>
          ★
        </span>
      );
    }
    return <div className="rating">{stars}</div>;
  };

  if (selectedVendor) {
    return (
      <div className="vendor-management">
        <div className="vendor-detail">
          <div className="detail-header">
            <button 
              onClick={() => setSelectedVendor(null)}
              className="btn btn-outline back-btn"
            >
              ← Back to Vendors
            </button>
            <h2>{selectedVendor.name}</h2>
            <button 
              onClick={() => handleEdit(selectedVendor)}
              className="btn btn-primary"
            >
              Edit Vendor
            </button>
          </div>

          <div className="vendor-info-grid">
            <div className="info-section">
              <h3>Contact Information</h3>
              <div className="info-item">
                <strong>Contact Person:</strong> {selectedVendor.contact_person || 'N/A'}
              </div>
              <div className="info-item">
                <strong>Email:</strong> {selectedVendor.email || 'N/A'}
              </div>
              <div className="info-item">
                <strong>Phone:</strong> {selectedVendor.phone || 'N/A'}
              </div>
            </div>

            <div className="info-section">
              <h3>Address</h3>
              <div className="address-block">
                {selectedVendor.address_line1 && <div>{selectedVendor.address_line1}</div>}
                {selectedVendor.address_line2 && <div>{selectedVendor.address_line2}</div>}
                {selectedVendor.city && (
                  <div>
                    {selectedVendor.city}, {selectedVendor.state} {selectedVendor.postal_code}
                  </div>
                )}
                {selectedVendor.country && <div>{selectedVendor.country}</div>}
              </div>
            </div>

            <div className="info-section">
              <h3>Business Details</h3>
              <div className="info-item">
                <strong>Status:</strong>
                <span className={`status-badge ${getStatusBadgeClass(selectedVendor.status)}`}>
                  {selectedVendor.status.replace('_', ' ').toUpperCase()}
                </span>
              </div>
              <div className="info-item">
                <strong>Rating:</strong> {renderStars(selectedVendor.rating)}
              </div>
              <div className="info-item">
                <strong>Lead Time:</strong> {selectedVendor.delivery_lead_time || 'N/A'} days
              </div>
              <div className="info-item">
                <strong>Min Order:</strong> 
                {selectedVendor.minimum_order_amount 
                  ? formatCurrency(selectedVendor.minimum_order_amount) 
                  : 'N/A'
                }
              </div>
            </div>
          </div>

          {selectedVendor.notes && (
            <div className="info-section">
              <h3>Notes</h3>
              <p className="notes">{selectedVendor.notes}</p>
            </div>
          )}

          <div className="purchase-orders-section">
            <h3>Recent Purchase Orders ({vendorPOs.length})</h3>
            {vendorPOs.length === 0 ? (
              <p className="empty-state">No purchase orders found</p>
            ) : (
              <div className="po-table">
                <table>
                  <thead>
                    <tr>
                      <th>PO Number</th>
                      <th>Order Date</th>
                      <th>Status</th>
                      <th>Expected Delivery</th>
                      <th>Total Amount</th>
                    </tr>
                  </thead>
                  <tbody>
                    {vendorPOs.map(po => (
                      <tr key={po.id}>
                        <td>{po.po_number}</td>
                        <td>{formatDate(po.order_date)}</td>
                        <td>
                          <span className={`status-badge status-${po.status}`}>
                            {po.status.toUpperCase()}
                          </span>
                        </td>
                        <td>
                          {po.expected_delivery_date 
                            ? formatDate(po.expected_delivery_date) 
                            : 'N/A'
                          }
                        </td>
                        <td>{formatCurrency(po.total_amount)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="vendor-management">
      <div className="page-header">
        <h2>Vendor Management</h2>
        <button 
          onClick={() => setShowForm(true)}
          className="btn btn-primary"
        >
          + Add Vendor
        </button>
      </div>

      {error && (
        <div className="error-message">
          <p>{error}</p>
          <button onClick={() => setError(null)} className="close-btn">×</button>
        </div>
      )}

      {/* Search and Filters */}
      <div className="filters-section">
        <div className="search-bar">
          <input
            type="text"
            placeholder="Search vendors..."
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            className="search-input"
          />
        </div>
        <div className="filter-group">
          <select
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value)}
            className="filter-select"
          >
            <option value="">All Statuses</option>
            <option value="active">Active</option>
            <option value="inactive">Inactive</option>
            <option value="suspended">Suspended</option>
            <option value="pending_approval">Pending Approval</option>
          </select>
          <button onClick={fetchVendors} className="btn btn-outline">
            🔍 Search
          </button>
        </div>
      </div>

      {/* Vendor Form Modal */}
      {showForm && (
        <div className="modal-overlay">
          <div className="modal-content">
            <div className="modal-header">
              <h3>{editingVendor ? 'Edit Vendor' : 'Add New Vendor'}</h3>
              <button onClick={resetForm} className="close-btn">×</button>
            </div>
            
            <form onSubmit={handleSubmit} className="vendor-form">
              <div className="form-grid">
                <div className="form-group">
                  <label>Vendor Name *</label>
                  <input
                    type="text"
                    value={formData.name}
                    onChange={(e) => setFormData({...formData, name: e.target.value})}
                    required
                    className="form-input"
                  />
                </div>

                <div className="form-group">
                  <label>Status</label>
                  <select
                    value={formData.status}
                    onChange={(e) => setFormData({...formData, status: e.target.value as any})}
                    className="form-input"
                  >
                    <option value="active">Active</option>
                    <option value="inactive">Inactive</option>
                    <option value="suspended">Suspended</option>
                    <option value="pending_approval">Pending Approval</option>
                  </select>
                </div>

                <div className="form-group">
                  <label>Contact Person</label>
                  <input
                    type="text"
                    value={formData.contact_person}
                    onChange={(e) => setFormData({...formData, contact_person: e.target.value})}
                    className="form-input"
                  />
                </div>

                <div className="form-group">
                  <label>Email</label>
                  <input
                    type="email"
                    value={formData.email}
                    onChange={(e) => setFormData({...formData, email: e.target.value})}
                    className="form-input"
                  />
                </div>

                <div className="form-group">
                  <label>Phone</label>
                  <input
                    type="tel"
                    value={formData.phone}
                    onChange={(e) => setFormData({...formData, phone: e.target.value})}
                    className="form-input"
                  />
                </div>

                <div className="form-group">
                  <label>Lead Time (days)</label>
                  <input
                    type="number"
                    value={formData.delivery_lead_time || ''}
                    onChange={(e) => setFormData({...formData, delivery_lead_time: e.target.value ? parseInt(e.target.value) : null})}
                    className="form-input"
                  />
                </div>

                <div className="form-group full-width">
                  <label>Address Line 1</label>
                  <input
                    type="text"
                    value={formData.address_line1}
                    onChange={(e) => setFormData({...formData, address_line1: e.target.value})}
                    className="form-input"
                  />
                </div>

                <div className="form-group full-width">
                  <label>Address Line 2</label>
                  <input
                    type="text"
                    value={formData.address_line2}
                    onChange={(e) => setFormData({...formData, address_line2: e.target.value})}
                    className="form-input"
                  />
                </div>

                <div className="form-group">
                  <label>City</label>
                  <input
                    type="text"
                    value={formData.city}
                    onChange={(e) => setFormData({...formData, city: e.target.value})}
                    className="form-input"
                  />
                </div>

                <div className="form-group">
                  <label>State</label>
                  <input
                    type="text"
                    value={formData.state}
                    onChange={(e) => setFormData({...formData, state: e.target.value})}
                    className="form-input"
                  />
                </div>

                <div className="form-group">
                  <label>Postal Code</label>
                  <input
                    type="text"
                    value={formData.postal_code}
                    onChange={(e) => setFormData({...formData, postal_code: e.target.value})}
                    className="form-input"
                  />
                </div>

                <div className="form-group">
                  <label>Country</label>
                  <input
                    type="text"
                    value={formData.country}
                    onChange={(e) => setFormData({...formData, country: e.target.value})}
                    className="form-input"
                  />
                </div>

                <div className="form-group full-width">
                  <label>Description</label>
                  <textarea
                    value={formData.description}
                    onChange={(e) => setFormData({...formData, description: e.target.value})}
                    className="form-textarea"
                    rows={3}
                  />
                </div>

                <div className="form-group full-width">
                  <label>Notes</label>
                  <textarea
                    value={formData.notes}
                    onChange={(e) => setFormData({...formData, notes: e.target.value})}
                    className="form-textarea"
                    rows={3}
                  />
                </div>
              </div>

              <div className="form-actions">
                <button type="button" onClick={resetForm} className="btn btn-outline">
                  Cancel
                </button>
                <button type="submit" disabled={loading} className="btn btn-primary">
                  {loading ? 'Saving...' : (editingVendor ? 'Update Vendor' : 'Create Vendor')}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Vendors List */}
      <div className="vendors-list">
        {loading ? (
          <div className="loading-spinner">
            <div className="spinner"></div>
            <p>Loading vendors...</p>
          </div>
        ) : vendors.length === 0 ? (
          <div className="empty-state">
            <p>No vendors found</p>
          </div>
        ) : (
          <div className="vendors-grid">
            {vendors.map(vendor => (
              <div key={vendor.id} className="vendor-card">
                <div className="vendor-header">
                  <h3>{vendor.name}</h3>
                  <span className={`status-badge ${getStatusBadgeClass(vendor.status)}`}>
                    {vendor.status.replace('_', ' ').toUpperCase()}
                  </span>
                </div>
                
                <div className="vendor-details">
                  <div className="detail-item">
                    <strong>Contact:</strong> {vendor.contact_person || 'N/A'}
                  </div>
                  <div className="detail-item">
                    <strong>Email:</strong> {vendor.email || 'N/A'}
                  </div>
                  <div className="detail-item">
                    <strong>Phone:</strong> {vendor.phone || 'N/A'}
                  </div>
                  <div className="detail-item">
                    <strong>Rating:</strong> {renderStars(vendor.rating)}
                  </div>
                </div>

                <div className="vendor-actions">
                  <button 
                    onClick={() => handleViewVendor(vendor)}
                    className="btn btn-sm btn-outline"
                  >
                    View Details
                  </button>
                  <button 
                    onClick={() => handleEdit(vendor)}
                    className="btn btn-sm btn-primary"
                  >
                    Edit
                  </button>
                  <button 
                    onClick={() => handleDelete(vendor.id)}
                    className="btn btn-sm btn-danger"
                  >
                    Delete
                  </button>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
};

export default VendorManagement;