import React, { useState } from 'react';
import './BulkOperations.css';

interface BulkOperationsProps {
  selectedItems: number[];
  onSelectAll: () => void;
  onDeselectAll: () => void;
  onBulkDelete?: () => void;
  onBulkActivate?: () => void;
  onBulkDeactivate?: () => void;
  onBulkAssignRole?: (roleId: number) => void;
  totalItems: number;
  itemType: 'users' | 'roles';
  availableRoles?: Array<{ id: number; name: string; display_name: string }>;
}

const BulkOperations: React.FC<BulkOperationsProps> = ({
  selectedItems,
  onSelectAll,
  onDeselectAll,
  onBulkDelete,
  onBulkActivate,
  onBulkDeactivate,
  onBulkAssignRole,
  totalItems,
  itemType,
  availableRoles = []
}) => {
  const [showRoleSelector, setShowRoleSelector] = useState(false);
  const [selectedRoleId, setSelectedRoleId] = useState<number | ''>('');

  const selectedCount = selectedItems.length;

  const handleAssignRole = () => {
    if (selectedRoleId && onBulkAssignRole) {
      onBulkAssignRole(Number(selectedRoleId));
      setShowRoleSelector(false);
      setSelectedRoleId('');
    }
  };

  if (selectedCount === 0) {
    return null;
  }

  return (
    <div className="bulk-operations">
      <div className="bulk-info">
        <span className="selected-count">
          {selectedCount} of {totalItems} {itemType} selected
        </span>
        
        <div className="bulk-actions">
          <button 
            className="btn btn-sm btn-secondary"
            onClick={selectedCount === totalItems ? onDeselectAll : onSelectAll}
          >
            {selectedCount === totalItems ? 'Deselect All' : 'Select All'}
          </button>

          {onBulkActivate && (
            <button 
              className="btn btn-sm btn-success"
              onClick={onBulkActivate}
            >
              Activate Selected
            </button>
          )}

          {onBulkDeactivate && (
            <button 
              className="btn btn-sm btn-warning"
              onClick={onBulkDeactivate}
            >
              Deactivate Selected
            </button>
          )}

          {onBulkAssignRole && availableRoles.length > 0 && (
            <div className="role-assignment">
              {!showRoleSelector ? (
                <button 
                  className="btn btn-sm btn-primary"
                  onClick={() => setShowRoleSelector(true)}
                >
                  Assign Role
                </button>
              ) : (
                <div className="role-selector">
                  <select
                    value={selectedRoleId}
                    onChange={e => setSelectedRoleId(e.target.value)}
                    className="role-select"
                  >
                    <option value="">Select role...</option>
                    {availableRoles.map(role => (
                      <option key={role.id} value={role.id}>
                        {role.display_name}
                      </option>
                    ))}
                  </select>
                  <button 
                    className="btn btn-sm btn-primary"
                    onClick={handleAssignRole}
                    disabled={!selectedRoleId}
                  >
                    Assign
                  </button>
                  <button 
                    className="btn btn-sm btn-secondary"
                    onClick={() => {
                      setShowRoleSelector(false);
                      setSelectedRoleId('');
                    }}
                  >
                    Cancel
                  </button>
                </div>
              )}
            </div>
          )}

          {onBulkDelete && (
            <button 
              className="btn btn-sm btn-danger"
              onClick={onBulkDelete}
            >
              Delete Selected
            </button>
          )}
        </div>
      </div>
    </div>
  );
};

export default BulkOperations;