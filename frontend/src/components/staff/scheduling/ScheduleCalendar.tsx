import React, { useState, useEffect, useCallback, useMemo, useRef } from 'react';
import { 
  format, 
  startOfWeek, 
  endOfWeek, 
  addDays, 
  isSameDay,
  differenceInMinutes,
  startOfMonth,
  endOfMonth,
  isWithinInterval,
  parseISO
} from 'date-fns';
import { 
  FocusTrap, 
  announce, 
  KEYS, 
  getShiftAriaLabel, 
  getCalendarCellAriaLabel,
  handleCalendarKeyboardNav,
  getShiftStatusIcon,
  createLiveRegion
} from '../../../utils/accessibility';
import './ScheduleCalendar.css';

interface Shift {
  id: number;
  staff_id: number;
  date: string;
  start_time: string;
  end_time: string;
  shift_type: 'REGULAR' | 'OVERTIME' | 'HOLIDAY' | 'TRAINING' | 'BREAK';
  status: 'draft' | 'published' | 'cancelled';
  role?: {
    id: number;
    name: string;
  };
  notes?: string;
  hourly_rate?: number;
  conflicts?: any[];
}

interface Staff {
  id: number;
  name: string;
  role: string;
  hourly_rate?: number;
}

interface ScheduleCalendarProps {
  shifts?: Shift[];
  staff?: Staff[];
  selectedDate?: Date;
  onDateChange?: (date: Date) => void;
  onShiftClick?: (shift: Shift) => void;
  onShiftDrop?: (shift: Shift, staffId: number, date: string) => void;
  isLoading?: boolean;
  viewMode?: 'week' | 'month' | 'day';
}

const ScheduleCalendar: React.FC<ScheduleCalendarProps> = ({ 
  shifts = [], 
  staff = [], 
  selectedDate = new Date(),
  onDateChange,
  onShiftClick,
  onShiftDrop,
  isLoading = false,
  viewMode = 'week'
}) => {
  const [draggedShift, setDraggedShift] = useState<Shift | null>(null);
  const [hoveredCell, setHoveredCell] = useState<{ staffId: number; date: string } | null>(null);
  const [selectedStaff, setSelectedStaff] = useState('all');
  const [focusedCell, setFocusedCell] = useState<{ staffId: number; date: string } | null>(null);
  const [selectedShiftId, setSelectedShiftId] = useState<number | null>(null);
  
  const gridRef = useRef<HTMLDivElement>(null);
  const liveRegionRef = useRef<ReturnType<typeof createLiveRegion> | null>(null);

  // Initialize live region for announcements
  useEffect(() => {
    liveRegionRef.current = createLiveRegion('schedule-calendar-live');
    return () => {
      liveRegionRef.current?.destroy();
    };
  }, []);

  // Calculate date range based on view mode
  const dateRange = useMemo(() => {
    if (viewMode === 'week') {
      return {
        start: startOfWeek(selectedDate, { weekStartsOn: 1 }),
        end: endOfWeek(selectedDate, { weekStartsOn: 1 })
      };
    } else if (viewMode === 'month') {
      return {
        start: startOfMonth(selectedDate),
        end: endOfMonth(selectedDate)
      };
    }
    return {
      start: selectedDate,
      end: selectedDate
    };
  }, [selectedDate, viewMode]);

  // Get days in current view
  const daysInView = useMemo(() => {
    const days = [];
    let currentDay = dateRange.start;
    while (currentDay <= dateRange.end) {
      days.push(currentDay);
      currentDay = addDays(currentDay, 1);
    }
    return days;
  }, [dateRange]);

  // Filter shifts by selected staff and date range
  const filteredShifts = useMemo(() => {
    return shifts.filter(shift => {
      const shiftDate = parseISO(shift.date);
      const inDateRange = isWithinInterval(shiftDate, dateRange);
      const matchesStaff = selectedStaff === 'all' || shift.staff_id === parseInt(selectedStaff);
      return inDateRange && matchesStaff;
    });
  }, [shifts, dateRange, selectedStaff]);

  // Group shifts by staff and date
  const shiftsByStaffAndDate = useMemo(() => {
    const grouped: Record<string, Shift[]> = {};
    filteredShifts.forEach(shift => {
      const key = `${shift.staff_id}-${shift.date}`;
      if (!grouped[key]) {
        grouped[key] = [];
      }
      grouped[key].push(shift);
    });
    return grouped;
  }, [filteredShifts]);

  // Calculate shift position and height
  const getShiftStyle = (shift: Shift): React.CSSProperties => {
    const startTime = parseISO(shift.start_time);
    const endTime = parseISO(shift.end_time);
    const startHour = startTime.getHours() + startTime.getMinutes() / 60;
    const duration = differenceInMinutes(endTime, startTime) / 60;
    
    const top = (startHour - 6) * 60; // Assuming day starts at 6 AM
    const height = duration * 60;
    
    return {
      top: `${top}px`,
      height: `${height}px`,
      backgroundColor: getShiftColor(shift.shift_type),
    };
  };

  // Get color based on shift type
  const getShiftColor = (shiftType: string): string => {
    const colors: Record<string, string> = {
      REGULAR: '#4CAF50',
      OVERTIME: '#FF9800',
      HOLIDAY: '#9C27B0',
      TRAINING: '#2196F3',
      BREAK: '#607D8B'
    };
    return colors[shiftType] || '#757575';
  };

  // Handle keyboard navigation for calendar grid
  const handleGridKeyDown = useCallback((e: React.KeyboardEvent) => {
    if (!focusedCell) return;

    const currentStaffIndex = staff.findIndex(s => s.id === focusedCell.staffId);
    const currentDateIndex = daysInView.findIndex(d => format(d, 'yyyy-MM-dd') === focusedCell.date);
    
    let newStaffIndex = currentStaffIndex;
    let newDateIndex = currentDateIndex;
    let handled = false;

    switch (e.key) {
      case KEYS.ARROW_LEFT:
        if (currentDateIndex > 0) {
          newDateIndex = currentDateIndex - 1;
          handled = true;
        }
        break;
      case KEYS.ARROW_RIGHT:
        if (currentDateIndex < daysInView.length - 1) {
          newDateIndex = currentDateIndex + 1;
          handled = true;
        }
        break;
      case KEYS.ARROW_UP:
        if (currentStaffIndex > 0) {
          newStaffIndex = currentStaffIndex - 1;
          handled = true;
        }
        break;
      case KEYS.ARROW_DOWN:
        if (currentStaffIndex < staff.length - 1) {
          newStaffIndex = currentStaffIndex + 1;
          handled = true;
        }
        break;
      case KEYS.HOME:
        newDateIndex = 0;
        handled = true;
        break;
      case KEYS.END:
        newDateIndex = daysInView.length - 1;
        handled = true;
        break;
      case KEYS.ENTER:
      case KEYS.SPACE:
        e.preventDefault();
        const cellShifts = shiftsByStaffAndDate[`${focusedCell.staffId}-${focusedCell.date}`] || [];
        if (cellShifts.length > 0) {
          // If there are shifts, focus the first one
          setSelectedShiftId(cellShifts[0].id);
          announce(`Selected ${getShiftAriaLabel(cellShifts[0])}`);
        } else {
          announce('No shifts in this cell. Press N to create a new shift.');
        }
        handled = true;
        break;
      case 'n':
      case 'N':
        // Create new shift shortcut
        e.preventDefault();
        announce('Creating new shift. Opening shift editor.');
        // Trigger new shift creation
        handled = true;
        break;
    }

    if (handled) {
      e.preventDefault();
      const newStaff = staff[newStaffIndex];
      const newDate = format(daysInView[newDateIndex], 'yyyy-MM-dd');
      setFocusedCell({ staffId: newStaff.id, date: newDate });
      
      // Announce new position
      const shiftCount = shiftsByStaffAndDate[`${newStaff.id}-${newDate}`]?.length || 0;
      announce(`${newStaff.name}, ${format(daysInView[newDateIndex], 'EEEE, MMMM d')}, ${shiftCount} shifts`);
    }
  }, [focusedCell, staff, daysInView, shiftsByStaffAndDate]);

  // Handle keyboard navigation for individual shifts
  const handleShiftKeyDown = useCallback((e: React.KeyboardEvent, shift: Shift) => {
    switch (e.key) {
      case KEYS.ENTER:
      case KEYS.SPACE:
        e.preventDefault();
        onShiftClick?.(shift);
        announce(`Editing ${getShiftAriaLabel(shift)}`);
        break;
      case KEYS.DELETE:
        e.preventDefault();
        announce(`Delete ${getShiftAriaLabel(shift)}? Press Y to confirm, N to cancel.`);
        break;
    }
  }, [onShiftClick]);

  // Handle drag start
  const handleDragStart = (e: React.DragEvent, shift: Shift) => {
    setDraggedShift(shift);
    e.dataTransfer.effectAllowed = 'move';
    e.dataTransfer.setData('text/html', e.currentTarget.innerHTML);
    announce(`Picked up ${getShiftAriaLabel(shift)}. Drag to new time slot or press Escape to cancel.`);
  };

  // Handle drag over
  const handleDragOver = (e: React.DragEvent, staffId: number, date: string) => {
    e.preventDefault();
    e.dataTransfer.dropEffect = 'move';
    setHoveredCell({ staffId, date });
  };

  // Handle drop
  const handleDrop = (e: React.DragEvent, staffId: number, date: string) => {
    e.preventDefault();
    setHoveredCell(null);
    
    if (draggedShift && onShiftDrop) {
      const targetStaff = staff.find(s => s.id === staffId);
      announce(`Moved shift to ${targetStaff?.name}, ${format(parseISO(date), 'EEEE, MMMM d')}`);
      onShiftDrop(draggedShift, staffId, date);
    }
    setDraggedShift(null);
  };

  // Handle drag leave
  const handleDragLeave = () => {
    setHoveredCell(null);
  };

  // Handle escape key to cancel drag
  useEffect(() => {
    const handleEscape = (e: KeyboardEvent) => {
      if (e.key === KEYS.ESCAPE && draggedShift) {
        setDraggedShift(null);
        setHoveredCell(null);
        announce('Drag cancelled');
      }
    };
    
    document.addEventListener('keydown', handleEscape);
    return () => document.removeEventListener('keydown', handleEscape);
  }, [draggedShift]);

  // Render time slots
  const renderTimeSlots = () => {
    const slots = [];
    for (let hour = 6; hour < 24; hour++) {
      const time = new Date();
      time.setHours(hour, 0, 0, 0);
      slots.push(
        <div key={hour} className="time-slot">
          <span className="time-label" role="presentation">
            {format(time, 'ha')}
          </span>
        </div>
      );
    }
    return slots;
  };

  // Render shift card
  const renderShift = (shift: Shift, index: number, totalShifts: number) => {
    const isSelected = selectedShiftId === shift.id;
    const ariaLabel = getShiftAriaLabel({
      staff_name: staff.find(s => s.id === shift.staff_id)?.name,
      position: shift.role?.name,
      start_time: format(parseISO(shift.start_time), 'h:mm a'),
      end_time: format(parseISO(shift.end_time), 'h:mm a'),
      status: shift.status
    });
    
    return (
      <div
        key={shift.id}
        className={`shift-card ${shift.status} ${isSelected ? 'selected' : ''} ${shift.conflicts?.length ? 'has-conflicts' : ''}`}
        style={getShiftStyle(shift)}
        draggable
        onDragStart={(e) => handleDragStart(e, shift)}
        onClick={() => onShiftClick?.(shift)}
        onKeyDown={(e) => handleShiftKeyDown(e, shift)}
        tabIndex={isSelected ? 0 : -1}
        role="button"
        aria-label={ariaLabel}
        aria-describedby={shift.conflicts?.length ? `conflicts-${shift.id}` : undefined}
        data-shift-index={index}
        data-total-shifts={totalShifts}
      >
        <div className="shift-time" aria-hidden="true">
          {format(parseISO(shift.start_time), 'HH:mm')} - 
          {format(parseISO(shift.end_time), 'HH:mm')}
          <span className="shift-status-icon" role="img" aria-label={shift.status}>
            {getShiftStatusIcon(shift.status)}
          </span>
        </div>
        <div className="shift-role" aria-hidden="true">{shift.role?.name || 'No Role'}</div>
        {shift.notes && <div className="shift-notes" aria-hidden="true">{shift.notes}</div>}
        {shift.conflicts?.length ? (
          <div id={`conflicts-${shift.id}`} className="sr-only">
            Has {shift.conflicts.length} scheduling conflicts
          </div>
        ) : null}
      </div>
    );
  };

  // Render day column
  const renderDayColumn = (day: Date, staffMember: Staff) => {
    const dateStr = format(day, 'yyyy-MM-dd');
    const key = `${staffMember.id}-${dateStr}`;
    const dayShifts = shiftsByStaffAndDate[key] || [];
    const isHovered = hoveredCell?.staffId === staffMember.id && 
                     hoveredCell?.date === dateStr;
    const isFocused = focusedCell?.staffId === staffMember.id && 
                     focusedCell?.date === dateStr;
    const hasConflicts = dayShifts.some(s => s.conflicts?.length);
    
    const cellAriaLabel = getCalendarCellAriaLabel(day, dayShifts.length, hasConflicts);

    return (
      <div
        key={key}
        className={`day-column ${isHovered ? 'hover' : ''} ${isFocused ? 'focused' : ''} ${hasConflicts ? 'has-conflicts' : ''}`}
        onDragOver={(e) => handleDragOver(e, staffMember.id, dateStr)}
        onDrop={(e) => handleDrop(e, staffMember.id, dateStr)}
        onDragLeave={handleDragLeave}
        onClick={() => setFocusedCell({ staffId: staffMember.id, date: dateStr })}
        role="gridcell"
        aria-label={cellAriaLabel}
        tabIndex={isFocused ? 0 : -1}
        data-staff-id={staffMember.id}
        data-date={dateStr}
      >
        <div className="shifts-container" role="group" aria-label={`Shifts for ${staffMember.name}`}>
          {dayShifts.map((shift, index) => renderShift(shift, index, dayShifts.length))}
        </div>
      </div>
    );
  };

  // Render staff row
  const renderStaffRow = (staffMember: Staff, staffIndex: number) => (
    <div key={staffMember.id} className="staff-row" role="row">
      <div className="staff-header" role="rowheader">
        <div className="staff-name">{staffMember.name}</div>
        <div className="staff-role">{staffMember.role}</div>
      </div>
      <div className="staff-schedule" role="group" aria-label={`Schedule for ${staffMember.name}`}>
        {daysInView.map(day => renderDayColumn(day, staffMember))}
      </div>
    </div>
  );

  // Render loading state
  if (isLoading) {
    return (
      <div className="schedule-calendar loading" role="status" aria-busy="true">
        <div className="loading-spinner">Loading schedule...</div>
      </div>
    );
  }

  const displayedStaff = selectedStaff === 'all' 
    ? staff 
    : staff.filter(s => s.id === parseInt(selectedStaff));

  return (
    <div className="schedule-calendar" role="application" aria-label="Staff schedule calendar">
      {/* Keyboard instructions (screen reader only) */}
      <div className="sr-only" role="region" aria-label="Keyboard instructions">
        <h3>Keyboard Navigation Instructions</h3>
        <ul>
          <li>Arrow keys: Navigate between cells</li>
          <li>Enter or Space: Select a shift or create new shift in empty cell</li>
          <li>Tab: Navigate to next shift within a cell</li>
          <li>N: Create new shift in focused cell</li>
          <li>Delete: Delete selected shift</li>
          <li>Escape: Cancel current operation</li>
        </ul>
      </div>

      {/* Calendar Header */}
      <div className="calendar-header">
        <div className="calendar-controls">
          <label htmlFor="staff-filter" className="sr-only">Filter by staff member</label>
          <select 
            id="staff-filter"
            value={selectedStaff} 
            onChange={(e) => {
              setSelectedStaff(e.target.value);
              const staffName = e.target.value === 'all' 
                ? 'all staff' 
                : staff.find(s => s.id === parseInt(e.target.value))?.name;
              announce(`Filtering schedule for ${staffName}`);
            }}
            className="staff-filter"
            aria-label="Filter schedule by staff member"
          >
            <option value="all">All Staff</option>
            {staff.map(s => (
              <option key={s.id} value={s.id}>{s.name}</option>
            ))}
          </select>
        </div>
        
        <div className="calendar-days-header" role="row">
          <div className="time-column-header" role="columnheader">Time</div>
          {daysInView.map(day => (
            <div key={day.toISOString()} className="day-header" role="columnheader">
              <div className="day-name">{format(day, 'EEE')}</div>
              <div className="day-date">{format(day, 'MMM d')}</div>
            </div>
          ))}
        </div>
      </div>

      {/* Calendar Body */}
      <div 
        className="calendar-body" 
        ref={gridRef}
        role="grid"
        aria-label="Schedule grid"
        onKeyDown={handleGridKeyDown}
      >
        <div className="time-column" role="presentation">
          {renderTimeSlots()}
        </div>
        
        <div className="calendar-grid">
          {displayedStaff.map((staffMember, index) => renderStaffRow(staffMember, index))}
        </div>
      </div>

      {/* Legend */}
      <div className="calendar-legend" role="region" aria-label="Shift type legend">
        <h3 className="sr-only">Shift Type Legend</h3>
        <div className="legend-item">
          <span 
            className="legend-color" 
            style={{ backgroundColor: getShiftColor('REGULAR') }}
            role="img"
            aria-label="Regular shift color"
          ></span>
          <span>{getShiftStatusIcon('published')} Regular Shift</span>
        </div>
        <div className="legend-item">
          <span 
            className="legend-color" 
            style={{ backgroundColor: getShiftColor('OVERTIME') }}
            role="img"
            aria-label="Overtime shift color"
          ></span>
          <span>Overtime</span>
        </div>
        <div className="legend-item">
          <span 
            className="legend-color" 
            style={{ backgroundColor: getShiftColor('HOLIDAY') }}
            role="img"
            aria-label="Holiday shift color"
          ></span>
          <span>Holiday</span>
        </div>
        <div className="legend-item">
          <span 
            className="legend-color" 
            style={{ backgroundColor: getShiftColor('TRAINING') }}
            role="img"
            aria-label="Training shift color"
          ></span>
          <span>Training</span>
        </div>
        <div className="legend-item">
          <span 
            className="legend-color" 
            style={{ backgroundColor: '#FF5252' }}
            role="img"
            aria-label="Conflict indicator color"
          ></span>
          <span>{getShiftStatusIcon('conflict')} Has Conflicts</span>
        </div>
      </div>
    </div>
  );
};

export default ScheduleCalendar;