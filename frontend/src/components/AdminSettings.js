import React, { useState, useEffect } from 'react';
import apiClient from '../utils/authInterceptor';

const AdminSettings = () => {
  const [globalSyncEnabled, setGlobalSyncEnabled] = useState(true);
  const [teamSettings, setTeamSettings] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  useEffect(() => {
    fetchSettings();
  }, []);

  const fetchSettings = async () => {
    try {
      const response = await apiClient.get('/settings/pos-sync');
      const settings = response.data;
      
      const global = settings.find(s => s.team_id === null);
      const teams = settings.filter(s => s.team_id !== null);
      
      setGlobalSyncEnabled(global?.enabled ?? true);
      setTeamSettings(teams);
      setError(null);
    } catch (error) {
      console.error('Failed to fetch settings:', error);
      setError('Failed to load settings');
    }
  };

  const updateGlobalSetting = async (enabled) => {
    setLoading(true);
    setError(null);
    try {
      await apiClient.post('/settings/pos-sync', {
        tenant_id: 1,
        team_id: null,
        enabled,
        updated_by: 1
      });
      
      setGlobalSyncEnabled(enabled);
    } catch (error) {
      console.error('Failed to update global setting:', error);
      setError('Failed to update global setting');
    }
    setLoading(false);
  };

  const updateTeamSetting = async (teamId, enabled) => {
    setLoading(true);
    setError(null);
    try {
      await apiClient.post('/settings/pos-sync', {
        tenant_id: 1,
        team_id: teamId,
        enabled,
        updated_by: 1
      });
      
      setTeamSettings(prev => 
        prev.map(team => 
          team.team_id === teamId ? { ...team, enabled } : team
        )
      );
    } catch (error) {
      console.error('Failed to update team setting:', error);
      setError('Failed to update team setting');
    }
    setLoading(false);
  };

  const addTeamSetting = async () => {
    const teamId = prompt('Enter team ID:');
    if (teamId && !isNaN(teamId)) {
      await updateTeamSetting(parseInt(teamId), true);
      await fetchSettings();
    }
  };

  return (
    <div className="admin-settings" style={{ padding: '20px', maxWidth: '600px' }}>
      <h2>POS Sync Settings</h2>
      
      {error && (
        <div style={{ color: 'red', marginBottom: '20px', padding: '10px', border: '1px solid red', borderRadius: '4px' }}>
          {error}
        </div>
      )}
      
      <div className="setting-group" style={{ marginBottom: '30px', padding: '15px', border: '1px solid #ddd', borderRadius: '8px' }}>
        <h3>Global POS Sync</h3>
        <label style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
          <input
            type="checkbox"
            checked={globalSyncEnabled}
            onChange={(e) => updateGlobalSetting(e.target.checked)}
            disabled={loading}
          />
          Enable POS synchronization globally
        </label>
        <p style={{ fontSize: '14px', color: '#666', marginTop: '10px' }}>
          This setting controls POS sync for all teams unless overridden by team-specific settings.
        </p>
      </div>

      <div className="setting-group" style={{ padding: '15px', border: '1px solid #ddd', borderRadius: '8px' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '15px' }}>
          <h3>Team-Level Settings</h3>
          <button 
            onClick={addTeamSetting}
            disabled={loading}
            style={{ padding: '5px 10px', backgroundColor: '#007bff', color: 'white', border: 'none', borderRadius: '4px', cursor: 'pointer' }}
          >
            Add Team Setting
          </button>
        </div>
        
        {teamSettings.length === 0 ? (
          <p style={{ color: '#666', fontStyle: 'italic' }}>No team-specific settings configured.</p>
        ) : (
          teamSettings.map(team => (
            <div key={team.team_id} style={{ marginBottom: '10px', padding: '10px', backgroundColor: '#f8f9fa', borderRadius: '4px' }}>
              <label style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                <input
                  type="checkbox"
                  checked={team.enabled}
                  onChange={(e) => updateTeamSetting(team.team_id, e.target.checked)}
                  disabled={loading}
                />
                Team {team.team_id} POS Sync
              </label>
              <p style={{ fontSize: '12px', color: '#666', marginTop: '5px', marginLeft: '25px' }}>
                Overrides global setting for this team
              </p>
            </div>
          ))
        )}
      </div>
      
      {loading && (
        <div style={{ marginTop: '20px', padding: '10px', backgroundColor: '#e3f2fd', borderRadius: '4px' }}>
          Updating settings...
        </div>
      )}
    </div>
  );
};

export default AdminSettings;
