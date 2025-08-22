import React, { useState } from 'react';
import { format, parseISO } from 'date-fns';
import './ConflictResolver.css';

const API_BASE_URL = process.env.REACT_APP_API_URL || 'http://localhost:8000';

const ConflictResolver = ({ conflicts, shifts, staff, onResolve, onClose }) => {
  const [selectedConflict, setSelectedConflict] = useState(null);
  const [resolutionType, setResolutionType] = useState('');
  const [isResolving, setIsResolving] = useState(false);

  const conflictTypes = {
    DOUBLE_BOOKING: 'Double Booking',
    OVERTIME_VIOLATION: 'Overtime Violation',
    UNAVAILABLE_STAFF: 'Staff Unavailable',
    MISSING_BREAK: 'Missing Required Break',
    INSUFFICIENT_REST: 'Insufficient Rest Period',
    SKILL_MISMATCH: 'Skill/Role Mismatch'
  };

  const resolutionOptions = {
    DOUBLE_BOOKING: [
      { value: 'CANCEL_FIRST', label: 'Cancel first shift' },
      { value: 'CANCEL_SECOND', label: 'Cancel second shift' },
      { value: 'REASSIGN_FIRST', label: 'Reassign first shift to another staff' },
      { value: 'REASSIGN_SECOND', label: 'Reassign second shift to another staff' },
      { value: 'ADJUST_TIMES', label: 'Adjust shift times to avoid overlap' }
    ],
    OVERTIME_VIOLATION: [
      { value: 'REDUCE_HOURS', label: 'Reduce shift hours' },
      { value: 'REASSIGN', label: 'Reassign to another staff member' },
      { value: 'APPROVE_OVERTIME', label: 'Approve overtime (requires authorization)' },
      { value: 'SPLIT_SHIFT', label: 'Split shift between multiple staff' }
    ],
    UNAVAILABLE_STAFF: [
      { value: 'REASSIGN', label: 'Reassign to available staff' },
      { value: 'CANCEL', label: 'Cancel the shift' },
      { value: 'REQUEST_AVAILABILITY', label: 'Request staff to work (send notification)' }
    ],
    MISSING_BREAK: [
      { value: 'ADD_BREAK', label: 'Add required break to shift' },
      { value: 'SHORTEN_SHIFT', label: 'Shorten shift to comply' },
      { value: 'SPLIT_SHIFT', label: 'Split into two shifts with break' }
    ],
    INSUFFICIENT_REST: [
      { value: 'ADJUST_START', label: 'Adjust shift start time' },
      { value: 'ADJUST_END', label: 'Adjust previous shift end time' },
      { value: 'REASSIGN', label: 'Reassign to another staff member' }
    ],
    SKILL_MISMATCH: [
      { value: 'REASSIGN', label: 'Reassign to qualified staff' },
      { value: 'ADD_TRAINING', label: 'Schedule training before shift' },
      { value: 'PAIR_WITH_SENIOR', label: 'Pair with senior staff member' }
    ]
  };

  const getStaffName = (staffId) => {
    const member = staff.find(s => s.id === staffId);
    return member ? member.name : 'Unknown Staff';
  };

  const getShiftDetails = (shiftId) => {
    const shift = shifts.find(s => s.id === shiftId);
    if (!shift) return 'Unknown Shift';
    
    return `${format(parseISO(shift.start_time), 'MMM d, HH:mm')} - ${format(parseISO(shift.end_time), 'HH:mm')}`;
  };

  const handleSelectConflict = (conflict) => {
    setSelectedConflict(conflict);
    setResolutionType('');
  };

  const handleResolve = async () => {
    if (!selectedConflict || !resolutionType) return;
    
    setIsResolving(true);
    
    try {
      // Simulate resolution API call
      // In real implementation, this would call the appropriate endpoint
      const response = await fetch(
        `${API_BASE_URL}/api/v1/staff/scheduling/conflicts/resolve`,
        {
          method: 'POST',
          headers: {
            'Authorization': `Bearer ${localStorage.getItem('token')}`,
            'Content-Type': 'application/json'
          },
          body: JSON.stringify({
            conflict_id: selectedConflict.id,
            resolution_type: resolutionType,
            conflict_type: selectedConflict.type
          })
        }
      );
      
      if (!response.ok) throw new Error('Failed to resolve conflict');
      
      // Remove resolved conflict from list
      const remainingConflicts = conflicts.filter(c => c.id !== selectedConflict.id);
      
      // Reset selection
      setSelectedConflict(null);
      setResolutionType('');
      
      // Notify parent to refresh
      onResolve();
      
      // Close if no more conflicts
      if (remainingConflicts.length === 0) {
        onClose();
      }
    } catch (err) {
      console.error('Failed to resolve conflict:', err);
      alert('Failed to resolve conflict. Please try again.');
    } finally {
      setIsResolving(false);
    }
  };

  const getSeverityClass = (severity) => {
    switch (severity) {
      case 'HIGH':
        return 'severity-high';
      case 'MEDIUM':
        return 'severity-medium';
      case 'LOW':
        return 'severity-low';
      default:
        return '';
    }
  };

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="conflict-resolver" onClick={e => e.stopPropagation()}>
        <div className="resolver-header">
          <h2>Schedule Conflicts ({conflicts.length})</h2>
          <button className="close-button" onClick={onClose}>×</button>
        </div>

        <div className="resolver-content">
          <div className="conflicts-list">
            <h3>Detected Conflicts</h3>
            {conflicts.map(conflict => (
              <div 
                key={conflict.id}
                className={`conflict-item ${selectedConflict?.id === conflict.id ? 'selected' : ''}`}
                onClick={() => handleSelectConflict(conflict)}
              >
                <div className={`conflict-severity ${getSeverityClass(conflict.severity)}`}>
                  {conflict.severity}
                </div>
                <div className="conflict-info">
                  <div className="conflict-type">
                    {conflictTypes[conflict.type] || conflict.type}
                  </div>
                  <div className="conflict-details">
                    <strong>{getStaffName(conflict.staff_id)}</strong>
                    {conflict.shift_ids && conflict.shift_ids.map(shiftId => (
                      <div key={shiftId} className="shift-detail">
                        {getShiftDetails(shiftId)}
                      </div>
                    ))}
                  </div>
                  <div className="conflict-message">
                    {conflict.message}
                  </div>
                </div>
              </div>
            ))}
          </div>

          <div className="resolution-panel">
            {selectedConflict ? (
              <>
                <h3>Resolution Options</h3>
                <div className="selected-conflict-summary">
                  <p><strong>Conflict:</strong> {conflictTypes[selectedConflict.type]}</p>
                  <p><strong>Staff:</strong> {getStaffName(selectedConflict.staff_id)}</p>
                  <p><strong>Description:</strong> {selectedConflict.message}</p>
                </div>

                <div className="resolution-options">
                  {resolutionOptions[selectedConflict.type]?.map(option => (
                    <label key={option.value} className="resolution-option">
                      <input
                        type="radio"
                        name="resolution"
                        value={option.value}
                        checked={resolutionType === option.value}
                        onChange={(e) => setResolutionType(e.target.value)}
                      />
                      <span>{option.label}</span>
                    </label>
                  ))}
                </div>

                <div className="resolution-actions">
                  <button 
                    className="resolve-button"
                    onClick={handleResolve}
                    disabled={!resolutionType || isResolving}
                  >
                    {isResolving ? 'Resolving...' : 'Apply Resolution'}
                  </button>
                  <button 
                    className="skip-button"
                    onClick={() => {
                      setSelectedConflict(null);
                      setResolutionType('');
                    }}
                  >
                    Skip This Conflict
                  </button>
                </div>
              </>
            ) : (
              <div className="no-selection">
                <p>Select a conflict from the list to see resolution options</p>
              </div>
            )}
          </div>
        </div>

        <div className="resolver-footer">
          <button 
            className="ignore-all-button"
            onClick={onClose}
          >
            Ignore All Conflicts
          </button>
          <button 
            className="auto-resolve-button"
            onClick={() => alert('Auto-resolve feature coming soon!')}
          >
            Auto-Resolve All
          </button>
        </div>
      </div>
    </div>
  );
};

export default ConflictResolver;