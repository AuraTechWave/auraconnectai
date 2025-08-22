import React from 'react';
import { BrowserRouter as Router, Routes, Route, Link } from 'react-router-dom';
import AdminSettings from './components/AdminSettings';
import { StaffSchedulingInterface } from './components/staff/scheduling';
import './App.css';

function App() {
  return (
    <Router>
      <div className="App">
        <header className="App-header" style={{ backgroundColor: '#282c34', padding: '20px', color: 'white' }}>
          <h1>AuraConnect Admin Panel</h1>
          <nav style={{ marginTop: '20px' }}>
            <Link to="/" style={{ color: 'white', marginRight: '20px', textDecoration: 'none' }}>
              Settings
            </Link>
            <Link to="/staff/scheduling" style={{ color: 'white', textDecoration: 'none' }}>
              Staff Scheduling
            </Link>
          </nav>
        </header>
        <main>
          <Routes>
            <Route path="/" element={<AdminSettings />} />
            <Route path="/staff/scheduling" element={<StaffSchedulingInterface />} />
          </Routes>
        </main>
      </div>
    </Router>
  );
}

export default App;