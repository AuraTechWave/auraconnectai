// frontend/components/menu/RecipeHistory.tsx

import React, { useState, useEffect } from 'react';
import { useAuth } from '../../hooks/useAuth';
import SkeletonLoader from '../ui/SkeletonLoader';
import './RecipeHistory.css';

interface RecipeHistoryEntry {
  id: number;
  recipe_id: number;
  version: number;
  change_type: string;
  changes: any;
  changed_by: number;
  changed_at: string;
  notes: string | null;
  user_name?: string;
}

interface RecipeHistoryProps {
  recipeId: number;
  recipeName: string;
  onClose: () => void;
}

const RecipeHistory: React.FC<RecipeHistoryProps> = ({
  recipeId,
  recipeName,
  onClose
}) => {
  const { token } = useAuth();
  const [history, setHistory] = useState<RecipeHistoryEntry[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [expandedEntries, setExpandedEntries] = useState<Set<number>>(new Set());
  const [selectedVersions, setSelectedVersions] = useState<[number, number] | null>(null);
  const [showComparison, setShowComparison] = useState(false);

  useEffect(() => {
    fetchHistory();
  }, [recipeId]);

  const fetchHistory = async () => {
    try {
      const response = await fetch(`/api/v1/menu/recipes/${recipeId}/history`, {
        headers: {
          'Authorization': `Bearer ${token}`
        }
      });

      if (!response.ok) throw new Error('Failed to fetch history');
      
      const data = await response.json();
      setHistory(data);
    } catch (err) {
      setError('Failed to load recipe history');
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  const toggleExpanded = (entryId: number) => {
    const newExpanded = new Set(expandedEntries);
    if (newExpanded.has(entryId)) {
      newExpanded.delete(entryId);
    } else {
      newExpanded.add(entryId);
    }
    setExpandedEntries(newExpanded);
  };

  const selectForComparison = (version: number) => {
    if (!selectedVersions) {
      setSelectedVersions([version, version]);
    } else if (selectedVersions[0] === version && selectedVersions[1] === version) {
      setSelectedVersions(null);
    } else if (selectedVersions[0] === version) {
      setSelectedVersions([selectedVersions[1], selectedVersions[1]]);
    } else if (selectedVersions[1] === version) {
      setSelectedVersions([selectedVersions[0], selectedVersions[0]]);
    } else {
      setSelectedVersions([selectedVersions[0], version].sort((a, b) => a - b) as [number, number]);
    }
  };

  const formatDate = (dateString: string) => {
    return new Date(dateString).toLocaleString('en-US', {
      year: 'numeric',
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit'
    });
  };

  const getChangeTypeIcon = (changeType: string) => {
    switch (changeType) {
      case 'created': return '🆕';
      case 'ingredients_updated': return '🥘';
      case 'instructions_updated': return '📝';
      case 'cost_updated': return '💰';
      case 'approved': return '✅';
      case 'status_changed': return '🔄';
      default: return '📋';
    }
  };

  const getChangeTypeLabel = (changeType: string) => {
    switch (changeType) {
      case 'created': return 'Recipe Created';
      case 'ingredients_updated': return 'Ingredients Updated';
      case 'instructions_updated': return 'Instructions Updated';
      case 'cost_updated': return 'Cost Updated';
      case 'approved': return 'Recipe Approved';
      case 'status_changed': return 'Status Changed';
      default: return 'Recipe Updated';
    }
  };

  const renderChangeDetails = (changes: any) => {
    if (!changes || typeof changes !== 'object') {
      return <p className="no-changes">No detailed changes recorded</p>;
    }

    const changedFields = Object.keys(changes);
    
    return (
      <div className="change-details">
        {changedFields.map(field => {
          const change = changes[field];
          
          if (field === 'ingredients') {
            return (
              <div key={field} className="change-field">
                <h5>Ingredients Changes</h5>
                {change.added && change.added.length > 0 && (
                  <div className="ingredient-changes">
                    <strong>Added:</strong>
                    <ul>
                      {change.added.map((ing: any, index: number) => (
                        <li key={index}>
                          {ing.name} - {ing.quantity} {ing.unit}
                        </li>
                      ))}
                    </ul>
                  </div>
                )}
                {change.removed && change.removed.length > 0 && (
                  <div className="ingredient-changes">
                    <strong>Removed:</strong>
                    <ul>
                      {change.removed.map((ing: any, index: number) => (
                        <li key={index}>
                          {ing.name} - {ing.quantity} {ing.unit}
                        </li>
                      ))}
                    </ul>
                  </div>
                )}
                {change.modified && change.modified.length > 0 && (
                  <div className="ingredient-changes">
                    <strong>Modified:</strong>
                    <ul>
                      {change.modified.map((ing: any, index: number) => (
                        <li key={index}>
                          {ing.name}: {ing.old_quantity} {ing.old_unit} → {ing.new_quantity} {ing.new_unit}
                        </li>
                      ))}
                    </ul>
                  </div>
                )}
              </div>
            );
          }

          if (field === 'instructions') {
            return (
              <div key={field} className="change-field">
                <h5>Instructions Changes</h5>
                <p className="change-summary">
                  {change.added} added, {change.removed} removed, {change.modified} modified
                </p>
              </div>
            );
          }

          // For other fields, show before and after
          return (
            <div key={field} className="change-field">
              <h5>{field.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase())}</h5>
              <div className="change-comparison">
                {change.old !== undefined && (
                  <div className="old-value">
                    <span className="label">Before:</span>
                    <span className="value">{JSON.stringify(change.old)}</span>
                  </div>
                )}
                {change.new !== undefined && (
                  <div className="new-value">
                    <span className="label">After:</span>
                    <span className="value">{JSON.stringify(change.new)}</span>
                  </div>
                )}
              </div>
            </div>
          );
        })}
      </div>
    );
  };

  if (loading) return <SkeletonLoader />;
  if (error) return <div className="error-message">{error}</div>;

  return (
    <div className="recipe-history">
      <div className="history-header">
        <div className="header-content">
          <h3>Version History</h3>
          <p className="recipe-name">{recipeName}</p>
        </div>
        <button className="btn-close" onClick={onClose}>✕</button>
      </div>

      {selectedVersions && (
        <div className="comparison-bar">
          <p>
            Comparing version {selectedVersions[0]} and version {selectedVersions[1]}
          </p>
          <div className="comparison-actions">
            <button 
              className="btn btn-primary btn-sm"
              onClick={() => setShowComparison(true)}
              disabled={selectedVersions[0] === selectedVersions[1]}
            >
              Show Comparison
            </button>
            <button 
              className="btn btn-secondary btn-sm"
              onClick={() => setSelectedVersions(null)}
            >
              Clear Selection
            </button>
          </div>
        </div>
      )}

      <div className="history-timeline">
        {history.length === 0 ? (
          <div className="empty-state">
            <p>No version history available for this recipe</p>
          </div>
        ) : (
          history.map((entry, index) => {
            const isExpanded = expandedEntries.has(entry.id);
            const isSelected = selectedVersions && 
              (selectedVersions[0] === entry.version || selectedVersions[1] === entry.version);
            
            return (
              <div 
                key={entry.id} 
                className={`history-entry ${isSelected ? 'selected' : ''}`}
              >
                <div className="entry-marker">
                  <div className="timeline-dot"></div>
                  {index < history.length - 1 && <div className="timeline-line"></div>}
                </div>

                <div className="entry-content">
                  <div className="entry-header" onClick={() => toggleExpanded(entry.id)}>
                    <div className="entry-info">
                      <span className="change-icon">{getChangeTypeIcon(entry.change_type)}</span>
                      <div>
                        <h4>{getChangeTypeLabel(entry.change_type)}</h4>
                        <div className="entry-meta">
                          <span className="version-badge">v{entry.version}</span>
                          <span className="date">{formatDate(entry.changed_at)}</span>
                          <span className="user">by {entry.user_name || `User ${entry.changed_by}`}</span>
                        </div>
                      </div>
                    </div>
                    <div className="entry-actions">
                      <button
                        className="btn-icon"
                        onClick={(e) => {
                          e.stopPropagation();
                          selectForComparison(entry.version);
                        }}
                        title="Select for comparison"
                      >
                        {isSelected ? '☑️' : '⬜'}
                      </button>
                      <button className="btn-icon expand-btn">
                        {isExpanded ? '▼' : '▶'}
                      </button>
                    </div>
                  </div>

                  {isExpanded && (
                    <div className="entry-details">
                      {entry.notes && (
                        <div className="entry-notes">
                          <strong>Notes:</strong> {entry.notes}
                        </div>
                      )}
                      {renderChangeDetails(entry.changes)}
                    </div>
                  )}
                </div>
              </div>
            );
          })
        )}
      </div>

      {/* Version Comparison Modal */}
      {showComparison && selectedVersions && (
        <div className="modal-overlay" onClick={() => setShowComparison(false)}>
          <div className="modal-content large" onClick={(e) => e.stopPropagation()}>
            <div className="modal-header">
              <h3>Version Comparison</h3>
              <button className="btn-close" onClick={() => setShowComparison(false)}>✕</button>
            </div>
            <div className="comparison-content">
              <div className="version-column">
                <h4>Version {selectedVersions[0]}</h4>
                {/* Version details would be loaded here */}
                <p className="placeholder">Version comparison details would be displayed here</p>
              </div>
              <div className="version-column">
                <h4>Version {selectedVersions[1]}</h4>
                {/* Version details would be loaded here */}
                <p className="placeholder">Version comparison details would be displayed here</p>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default RecipeHistory;