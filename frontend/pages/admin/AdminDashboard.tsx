import React, { useState } from 'react';
import { AdminGuard } from '../../components/rbac/RBACGuard';
import UserManagement from '../../components/admin/UserManagement';
import RoleManagement from '../../components/admin/RoleManagement';
import PermissionMatrix from '../../components/admin/PermissionMatrix';
import AuditLog from '../../components/admin/AuditLog';
import './AdminDashboard.css';

type TabType = 'users' | 'roles' | 'permissions' | 'audit';

const AdminDashboard: React.FC = () => {
  const [activeTab, setActiveTab] = useState<TabType>('users');

  const renderTabContent = () => {
    switch (activeTab) {
      case 'users':
        return <UserManagement />;
      case 'roles':
        return <RoleManagement />;
      case 'permissions':
        return <PermissionMatrix />;
      case 'audit':
        return <AuditLog />;
      default:
        return null;
    }
  };

  return (
    <AdminGuard fallback={<div className="unauthorized">Access Denied: Admin privileges required</div>}>
      <div className="admin-dashboard">
        <header className="admin-header">
          <h1>Admin Dashboard</h1>
          <p>Manage users, roles, and permissions</p>
        </header>

        <nav className="admin-tabs">
          <button
            className={`tab-button ${activeTab === 'users' ? 'active' : ''}`}
            onClick={() => setActiveTab('users')}
          >
            <i className="icon-users"></i>
            Users
          </button>
          <button
            className={`tab-button ${activeTab === 'roles' ? 'active' : ''}`}
            onClick={() => setActiveTab('roles')}
          >
            <i className="icon-shield"></i>
            Roles
          </button>
          <button
            className={`tab-button ${activeTab === 'permissions' ? 'active' : ''}`}
            onClick={() => setActiveTab('permissions')}
          >
            <i className="icon-lock"></i>
            Permissions
          </button>
          <button
            className={`tab-button ${activeTab === 'audit' ? 'active' : ''}`}
            onClick={() => setActiveTab('audit')}
          >
            <i className="icon-file-text"></i>
            Audit Log
          </button>
        </nav>

        <main className="admin-content">
          {renderTabContent()}
        </main>
      </div>
    </AdminGuard>
  );
};

export default AdminDashboard;