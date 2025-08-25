import React, { useState, useEffect, useRef } from 'react';
import { format, parseISO } from 'date-fns';
import { FocusTrap, announce, KEYS } from '../../../utils/accessibility';
import { schedulingService } from '../../../services/schedulingService';
import { formatInRestaurantTz } from '../../../utils/timezone';
import './ConflictResolver.css';

interface Conflict {
  id: string;
  type: 'DOUBLE_BOOKING' | 'OVERTIME_VIOLATION' | 'UNAVAILABLE_STAFF' | 
        'MISSING_BREAK' | 'INSUFFICIENT_REST' | 'SKILL_MISMATCH';
  severity: 'HIGH' | 'MEDIUM' | 'LOW';
  staff_id: number;
  shift_ids?: number[];
  message: string;
}

interface Shift {
  id: number;
  staff_id: number;
  start_time: string;
  end_time: string;
  status: string;
}

interface Staff {
  id: number;
  name: string;
  role: string;
}

interface ConflictResolverProps {
  conflicts: Conflict[];
  shifts: Shift[];
  staff: Staff[];
  onResolve: () => void;
  onClose: () => void;
}

const ConflictResolver: React.FC<ConflictResolverProps> = ({ 
  conflicts, 
  shifts, 
  staff, 
  onResolve, 
  onClose 
}) => {
  const [selectedConflict, setSelectedConflict] = useState<Conflict | null>(null);
  const [resolutionType, setResolutionType] = useState('');
  const [isResolving, setIsResolving] = useState(false);
  
  const modalRef = useRef<HTMLDivElement>(null);
  const focusTrapRef = useRef<FocusTrap | null>(null);

  const conflictTypes: Record<string, string> = {
    DOUBLE_BOOKING: 'Double Booking',
    OVERTIME_VIOLATION: 'Overtime Violation',
    UNAVAILABLE_STAFF: 'Staff Unavailable',
    MISSING_BREAK: 'Missing Required Break',
    INSUFFICIENT_REST: 'Insufficient Rest Period',
    SKILL_MISMATCH: 'Skill/Role Mismatch'
  };

  const resolutionOptions: Record<string, Array<{ value: string; label: string }>> = {
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

  // Initialize focus trap
  useEffect(() => {
    if (modalRef.current) {
      focusTrapRef.current = new FocusTrap(modalRef.current);
      focusTrapRef.current.activate();
      
      // Announce modal opened
      announce(`Conflict resolver opened. ${conflicts.length} conflicts to resolve.`, 'assertive');
    }

    return () => {
      focusTrapRef.current?.deactivate();
    };
  }, [conflicts.length]);

  // Handle keyboard shortcuts
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === KEYS.ESCAPE) {
        e.preventDefault();
        onClose();
      }
    };

    document.addEventListener('keydown', handleKeyDown);
    return () => document.removeEventListener('keydown', handleKeyDown);
  }, [onClose]);

  const getStaffName = (staffId: number): string => {
    const member = staff.find(s => s.id === staffId);
    return member ? member.name : 'Unknown Staff';
  };

  const getShiftDetails = (shiftId: number): string => {
    const shift = shifts.find(s => s.id === shiftId);
    if (!shift) return 'Unknown Shift';
    
    return `${formatInRestaurantTz(shift.start_time, 'MMM d, h:mm a')} - ${formatInRestaurantTz(shift.end_time, 'h:mm a')}`;
  };

  const handleSelectConflict = (conflict: Conflict) => {
    setSelectedConflict(conflict);
    setResolutionType('');
    announce(`Selected ${conflictTypes[conflict.type]} conflict for ${getStaffName(conflict.staff_id)}`);
  };

  const handleResolve = async () => {
    if (!selectedConflict || !resolutionType) return;
    
    setIsResolving(true);
    announce('Resolving conflict...', 'polite');
    
    try {
      await schedulingService.resolveConflict({
        conflict_id: selectedConflict.id,
        resolution_type: resolutionType,
        conflict_type: selectedConflict.type
      });
      
      // Remove resolved conflict from list
      const remainingConflicts = conflicts.filter(c => c.id !== selectedConflict.id);
      
      // Reset selection
      setSelectedConflict(null);
      setResolutionType('');
      
      announce('Conflict resolved successfully', 'assertive');
      
      // Notify parent to refresh
      onResolve();
      
      // Close if no more conflicts
      if (remainingConflicts.length === 0) {
        announce('All conflicts resolved. Closing resolver.', 'assertive');
        setTimeout(onClose, 1500);
      }
    } catch (err) {
      console.error('Failed to resolve conflict:', err);
      announce('Failed to resolve conflict. Please try again.', 'assertive');
    } finally {
      setIsResolving(false);
    }
  };

  const getSeverityClass = (severity: string): string => {
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

  const getSeverityIcon = (severity: string): string => {
    switch (severity) {
      case 'HIGH':
        return '🔴';
      case 'MEDIUM':
        return '🟡';
      case 'LOW':
        return '🟢';
      default:
        return '';
    }
  };

  return (
    <div 
      className="modal-overlay" 
      onClick={onClose}
      role="presentation"
    >
      <div 
        ref={modalRef}
        className="conflict-resolver" 
        onClick={e => e.stopPropagation()}
        role="dialog"
        aria-modal="true"
        aria-labelledby="conflict-resolver-title"
        aria-describedby="conflict-resolver-desc"
      >
        <div className="resolver-header">
          <h2 id="conflict-resolver-title">
            Schedule Conflicts ({conflicts.length})
          </h2>
          <button 
            className="close-button" 
            onClick={onClose}
            aria-label="Close conflict resolver"
          >
            ×
          </button>
        </div>

        <p id="conflict-resolver-desc" className="sr-only">
          Review and resolve scheduling conflicts. Use arrow keys to navigate conflicts, 
          Enter to select, and Tab to move between options.
        </p>

        <div className="resolver-content">
          <div className="conflicts-list" role="region" aria-label="Conflicts list">
            <h3>Detected Conflicts</h3>
            <div role="list">
              {conflicts.map((conflict, index) => (
                <div 
                  key={conflict.id}
                  className={`conflict-item ${selectedConflict?.id === conflict.id ? 'selected' : ''}`}
                  onClick={() => handleSelectConflict(conflict)}
                  onKeyDown={(e) => {
                    if (e.key === KEYS.ENTER || e.key === KEYS.SPACE) {
                      e.preventDefault();
                      handleSelectConflict(conflict);
                    }
                  }}
                  role="listitem"
                  tabIndex={0}
                  aria-current={selectedConflict?.id === conflict.id ? 'true' : undefined}
                  aria-label={`${conflictTypes[conflict.type]} for ${getStaffName(conflict.staff_id)}, severity: ${conflict.severity}`}
                >
                  <div 
                    className={`conflict-severity ${getSeverityClass(conflict.severity)}`}
                    aria-hidden="true"
                  >
                    <span role="img" aria-label={`${conflict.severity} severity`}>
                      {getSeverityIcon(conflict.severity)}
                    </span>
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
          </div>

          <div className="resolution-panel" role="region" aria-label="Resolution options">
            {selectedConflict ? (
              <>
                <h3>Resolution Options</h3>
                <div className="selected-conflict-summary" aria-live="polite">
                  <p><strong>Conflict:</strong> {conflictTypes[selectedConflict.type]}</p>
                  <p><strong>Staff:</strong> {getStaffName(selectedConflict.staff_id)}</p>
                  <p><strong>Description:</strong> {selectedConflict.message}</p>
                </div>

                <fieldset className="resolution-options">
                  <legend className="sr-only">Choose a resolution option</legend>
                  {resolutionOptions[selectedConflict.type]?.map(option => (
                    <label key={option.value} className="resolution-option">
                      <input
                        type="radio"
                        name="resolution"
                        value={option.value}
                        checked={resolutionType === option.value}
                        onChange={(e) => {
                          setResolutionType(e.target.value);
                          announce(`Selected: ${option.label}`);
                        }}
                        aria-describedby={`${option.value}-desc`}
                      />
                      <span>{option.label}</span>
                    </label>
                  ))}
                </fieldset>

                <div className="resolution-actions">
                  <button 
                    className="resolve-button"
                    onClick={handleResolve}
                    disabled={!resolutionType || isResolving}
                    aria-busy={isResolving}
                  >
                    {isResolving ? 'Resolving...' : 'Apply Resolution'}
                  </button>
                  <button 
                    className="skip-button"
                    onClick={() => {
                      setSelectedConflict(null);
                      setResolutionType('');
                      announce('Skipped conflict');
                    }}
                  >
                    Skip This Conflict
                  </button>
                </div>
              </>
            ) : (
              <div className="no-selection" role="status" aria-live="polite">
                <p>Select a conflict from the list to see resolution options</p>
              </div>
            )}
          </div>
        </div>

        <div className="resolver-footer">
          <button 
            className="ignore-all-button"
            onClick={() => {
              announce('Ignoring all conflicts');
              onClose();
            }}
          >
            Ignore All Conflicts
          </button>
          <button 
            className="auto-resolve-button"
            onClick={() => announce('Auto-resolve feature coming soon!', 'polite')}
            aria-describedby="auto-resolve-desc"
          >
            Auto-Resolve All
          </button>
          <span id="auto-resolve-desc" className="sr-only">
            Automatically resolve all conflicts using recommended solutions
          </span>
        </div>
      </div>
    </div>
  );
};

export default ConflictResolver;