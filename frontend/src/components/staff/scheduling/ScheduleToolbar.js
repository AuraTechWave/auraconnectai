import React, { useState } from 'react';
import { format, startOfWeek, endOfWeek } from 'date-fns';
import './ScheduleToolbar.css';

const ScheduleToolbar = ({
  selectedDate,
  viewMode,
  scheduleStatus,
  onPreviousWeek,
  onNextWeek,
  onToday,
  onViewModeChange,
  onCreateShift,
  onGenerateSchedule,
  onPublishSchedule,
  onExport,
  onShowAvailability,
  hasConflicts,
  onShowConflicts,
  onShowPayroll
}) => {
  const [showGenerateOptions, setShowGenerateOptions] = useState(false);
  const [showExportMenu, setShowExportMenu] = useState(false);
  const [generateOptions, setGenerateOptions] = useState({
    use_templates: true,
    respect_availability: true,
    minimize_overtime: true,
    balance_hours: true
  });

  const weekStart = startOfWeek(selectedDate, { weekStartsOn: 1 });
  const weekEnd = endOfWeek(selectedDate, { weekStartsOn: 1 });

  const handleGenerateClick = () => {
    setShowGenerateOptions(!showGenerateOptions);
  };

  const handleConfirmGenerate = () => {
    onGenerateSchedule(generateOptions);
    setShowGenerateOptions(false);
  };

  const handleExportClick = (format) => {
    onExport(format);
    setShowExportMenu(false);
  };

  return (
    <div className="schedule-toolbar">
      <div className="toolbar-section">
        {/* Navigation Controls */}
        <div className="date-navigation">
          <button 
            className="nav-button" 
            onClick={onPreviousWeek}
            title="Previous Week"
          >
            ←
          </button>
          
          <div className="date-display">
            <h2>{format(weekStart, 'MMM d')} - {format(weekEnd, 'MMM d, yyyy')}</h2>
            <div className="view-mode-selector">
              <button 
                className={`view-mode ${viewMode === 'day' ? 'active' : ''}`}
                onClick={() => onViewModeChange('day')}
              >
                Day
              </button>
              <button 
                className={`view-mode ${viewMode === 'week' ? 'active' : ''}`}
                onClick={() => onViewModeChange('week')}
              >
                Week
              </button>
              <button 
                className={`view-mode ${viewMode === 'month' ? 'active' : ''}`}
                onClick={() => onViewModeChange('month')}
              >
                Month
              </button>
            </div>
          </div>
          
          <button 
            className="nav-button" 
            onClick={onNextWeek}
            title="Next Week"
          >
            →
          </button>
          
          <button 
            className="today-button" 
            onClick={onToday}
          >
            Today
          </button>
        </div>
      </div>

      <div className="toolbar-section">
        {/* Action Buttons */}
        <div className="action-buttons">
          <button 
            className="toolbar-button primary"
            onClick={onCreateShift}
          >
            + Add Shift
          </button>
          
          <button 
            className="toolbar-button"
            onClick={onShowAvailability}
          >
            Staff Availability
          </button>

          <button 
            className="toolbar-button"
            onClick={onShowPayroll}
          >
            Payroll Integration
          </button>

          <div className="dropdown-container">
            <button 
              className="toolbar-button"
              onClick={handleGenerateClick}
            >
              Generate Schedule ▼
            </button>
            
            {showGenerateOptions && (
              <div className="dropdown-menu">
                <h3>Generation Options</h3>
                <label className="checkbox-option">
                  <input 
                    type="checkbox"
                    checked={generateOptions.use_templates}
                    onChange={(e) => setGenerateOptions({
                      ...generateOptions,
                      use_templates: e.target.checked
                    })}
                  />
                  Use shift templates
                </label>
                <label className="checkbox-option">
                  <input 
                    type="checkbox"
                    checked={generateOptions.respect_availability}
                    onChange={(e) => setGenerateOptions({
                      ...generateOptions,
                      respect_availability: e.target.checked
                    })}
                  />
                  Respect staff availability
                </label>
                <label className="checkbox-option">
                  <input 
                    type="checkbox"
                    checked={generateOptions.minimize_overtime}
                    onChange={(e) => setGenerateOptions({
                      ...generateOptions,
                      minimize_overtime: e.target.checked
                    })}
                  />
                  Minimize overtime
                </label>
                <label className="checkbox-option">
                  <input 
                    type="checkbox"
                    checked={generateOptions.balance_hours}
                    onChange={(e) => setGenerateOptions({
                      ...generateOptions,
                      balance_hours: e.target.checked
                    })}
                  />
                  Balance staff hours
                </label>
                <div className="dropdown-actions">
                  <button 
                    className="confirm-button"
                    onClick={handleConfirmGenerate}
                  >
                    Generate
                  </button>
                  <button 
                    className="cancel-button"
                    onClick={() => setShowGenerateOptions(false)}
                  >
                    Cancel
                  </button>
                </div>
              </div>
            )}
          </div>

          {scheduleStatus === 'draft' && (
            <button 
              className="toolbar-button success"
              onClick={onPublishSchedule}
            >
              Publish Schedule
            </button>
          )}

          {hasConflicts && (
            <button 
              className="toolbar-button warning"
              onClick={onShowConflicts}
            >
              ⚠ Conflicts ({hasConflicts})
            </button>
          )}

          <div className="dropdown-container">
            <button 
              className="toolbar-button"
              onClick={() => setShowExportMenu(!showExportMenu)}
            >
              Export ▼
            </button>
            
            {showExportMenu && (
              <div className="dropdown-menu compact">
                <button onClick={() => handleExportClick('pdf')}>
                  Export as PDF
                </button>
                <button onClick={() => handleExportClick('excel')}>
                  Export as Excel
                </button>
                <button onClick={() => handleExportClick('csv')}>
                  Export as CSV
                </button>
                <button onClick={() => handleExportClick('print')}>
                  Print Schedule
                </button>
              </div>
            )}
          </div>
        </div>

        {/* Status Indicator */}
        <div className={`schedule-status ${scheduleStatus}`}>
          {scheduleStatus === 'draft' ? '📝 Draft' : '✅ Published'}
        </div>
      </div>
    </div>
  );
};

export default ScheduleToolbar;