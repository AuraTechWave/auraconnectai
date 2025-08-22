import React from 'react';
import CustomerApp from './CustomerApp';
import AdminSettings from './components/AdminSettings';
import './App.css';

function App() {
  const isAdminPath = window.location.pathname.startsWith('/admin');
  
  if (isAdminPath) {
    return (
      <div className="App">
        <header className="App-header" style={{ backgroundColor: '#282c34', padding: '20px', color: 'white' }}>
          <h1>AuraConnect Admin Panel</h1>
        </header>
        <main>
          <AdminSettings />
        </main>
      </div>
    );
  }
  
  return <CustomerApp />;
}

export default App;
