import React from 'react';
import { BrowserRouter as Router, Routes, Route, Navigate, Link } from 'react-router-dom';
import CustomerApp from './CustomerApp';
import AdminSettings from './components/AdminSettings';
import { StaffSchedulingInterface } from './components/staff/scheduling';
import './App.css';

function AdminLayout({ children }) {
  return (
    <div className="App">
      <header className="App-header" style={{ backgroundColor: '#282c34', padding: '20px', color: 'white' }}>
        <h1>AuraConnect Admin Panel</h1>
        <nav style={{ marginTop: '10px' }}>
          <Link to="/admin/settings" style={{ color: 'white', marginRight: '20px' }}>Settings</Link>
          <Link to="/staff/scheduling" style={{ color: 'white' }}>Staff Scheduling</Link>
        </nav>
      </header>
      <main>{children}</main>
    </div>
  );
}

function App() {
  const isAdminPath = window.location.pathname.startsWith('/admin');
  const isStaffPath = window.location.pathname.startsWith('/staff');
  
  if (isAdminPath || isStaffPath) {
    return (
      <Router>
        <Routes>
          <Route path="/admin/settings" element={<AdminLayout><AdminSettings /></AdminLayout>} />
          <Route path="/staff/scheduling" element={<AdminLayout><StaffSchedulingInterface /></AdminLayout>} />
          <Route path="/admin" element={<Navigate to="/admin/settings" replace />} />
        </Routes>
      </Router>
    );
  }
  
  return <CustomerApp />;
}

export default App;
