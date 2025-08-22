import React, { useState, useEffect } from 'react';
import useCustomerStore from '../../stores/useCustomerStore';
import './ProfilePage.css';

function ProfilePage() {
  const { 
    customer, 
    updateProfile, 
    addresses, 
    fetchAddresses,
    addAddress,
    deleteAddress,
    preferences,
    fetchPreferences,
    updatePreferences
  } = useCustomerStore();

  const [isEditing, setIsEditing] = useState(false);
  const [formData, setFormData] = useState({
    name: customer?.name || '',
    email: customer?.email || '',
    phone: customer?.phone || '',
  });

  useEffect(() => {
    fetchAddresses();
    fetchPreferences();
  }, []);

  const handleUpdateProfile = async () => {
    const result = await updateProfile(formData);
    if (result.success) {
      setIsEditing(false);
    }
  };

  return (
    <div className="profile-page">
      <h1>My Profile</h1>

      <section className="profile-section">
        <h2>Personal Information</h2>
        {!isEditing ? (
          <div className="profile-info">
            <p><strong>Name:</strong> {customer?.name}</p>
            <p><strong>Email:</strong> {customer?.email}</p>
            <p><strong>Phone:</strong> {customer?.phone}</p>
            <button onClick={() => setIsEditing(true)} className="edit-btn">
              Edit Profile
            </button>
          </div>
        ) : (
          <div className="profile-form">
            <input
              type="text"
              value={formData.name}
              onChange={(e) => setFormData({ ...formData, name: e.target.value })}
              placeholder="Name"
            />
            <input
              type="email"
              value={formData.email}
              onChange={(e) => setFormData({ ...formData, email: e.target.value })}
              placeholder="Email"
            />
            <input
              type="tel"
              value={formData.phone}
              onChange={(e) => setFormData({ ...formData, phone: e.target.value })}
              placeholder="Phone"
            />
            <div className="form-actions">
              <button onClick={handleUpdateProfile} className="save-btn">
                Save Changes
              </button>
              <button onClick={() => setIsEditing(false)} className="cancel-btn">
                Cancel
              </button>
            </div>
          </div>
        )}
      </section>

      <section className="addresses-section">
        <h2>Saved Addresses</h2>
        <div className="addresses-list">
          {addresses.length === 0 ? (
            <p>No saved addresses</p>
          ) : (
            addresses.map((address) => (
              <div key={address.id} className="address-card">
                <p>{address.street}</p>
                <p>{address.city}, {address.state} {address.zip}</p>
                <button 
                  onClick={() => deleteAddress(address.id)}
                  className="delete-btn"
                >
                  Delete
                </button>
              </div>
            ))
          )}
        </div>
      </section>

      <section className="preferences-section">
        <h2>Preferences</h2>
        <div className="preferences-form">
          <label>
            <input
              type="checkbox"
              checked={preferences?.emailNotifications || false}
              onChange={(e) => updatePreferences({ 
                ...preferences, 
                emailNotifications: e.target.checked 
              })}
            />
            Email Notifications
          </label>
          <label>
            <input
              type="checkbox"
              checked={preferences?.smsNotifications || false}
              onChange={(e) => updatePreferences({ 
                ...preferences, 
                smsNotifications: e.target.checked 
              })}
            />
            SMS Notifications
          </label>
        </div>
      </section>
    </div>
  );
}

export default ProfilePage;