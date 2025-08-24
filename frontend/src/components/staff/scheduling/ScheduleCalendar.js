import React, { useState, useEffect, useCallback, useMemo } from 'react';
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
import './ScheduleCalendar.css';

const ScheduleCalendar = ({ 
  shifts = [], 
  staff = [], 
  selectedDate = new Date(),
  onDateChange,
  onShiftClick,
  onShiftDrop,
  isLoading = false,
  viewMode = 'week' // 'week' | 'month' | 'day'
}) => {
  const [draggedShift, setDraggedShift] = useState(null);
  const [hoveredCell, setHoveredCell] = useState(null);
  const [selectedStaff, setSelectedStaff] = useState('all');

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
    const grouped = {};
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
  const getShiftStyle = (shift) => {
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
  const getShiftColor = (shiftType) => {
    const colors = {
      REGULAR: '#4CAF50',
      OVERTIME: '#FF9800',
      HOLIDAY: '#9C27B0',
      TRAINING: '#2196F3',
      BREAK: '#607D8B'
    };
    return colors[shiftType] || '#757575';
  };

  // Handle drag start
  const handleDragStart = (e, shift) => {
    setDraggedShift(shift);
    e.dataTransfer.effectAllowed = 'move';
    e.dataTransfer.setData('text/html', e.target.innerHTML);
  };

  // Handle drag over
  const handleDragOver = (e, staffId, date) => {
    e.preventDefault();
    e.dataTransfer.dropEffect = 'move';
    setHoveredCell({ staffId, date });
  };

  // Handle drop
  const handleDrop = (e, staffId, date) => {
    e.preventDefault();
    setHoveredCell(null);
    
    if (draggedShift && onShiftDrop) {
      onShiftDrop(draggedShift, staffId, date);
    }
    setDraggedShift(null);
  };

  // Handle drag leave
  const handleDragLeave = () => {
    setHoveredCell(null);
  };

  // Render time slots
  const renderTimeSlots = () => {
    const slots = [];
    for (let hour = 6; hour < 24; hour++) {
      slots.push(
        <div key={hour} className="time-slot">
          <span className="time-label">{format(new Date().setHours(hour, 0), 'ha')}</span>
        </div>
      );
    }
    return slots;
  };

  // Render shift card
  const renderShift = (shift) => (
    <div
      key={shift.id}
      className={`shift-card ${shift.status}`}
      style={getShiftStyle(shift)}
      draggable
      onDragStart={(e) => handleDragStart(e, shift)}
      onClick={() => onShiftClick && onShiftClick(shift)}
    >
      <div className="shift-time">
        {format(parseISO(shift.start_time), 'HH:mm')} - 
        {format(parseISO(shift.end_time), 'HH:mm')}
      </div>
      <div className="shift-role">{shift.role?.name || 'No Role'}</div>
      {shift.notes && <div className="shift-notes">{shift.notes}</div>}
    </div>
  );

  // Render day column
  const renderDayColumn = (day, staffMember) => {
    const dateStr = format(day, 'yyyy-MM-dd');
    const key = `${staffMember.id}-${dateStr}`;
    const dayShifts = shiftsByStaffAndDate[key] || [];
    const isHovered = hoveredCell?.staffId === staffMember.id && 
                     hoveredCell?.date === dateStr;

    return (
      <div
        key={key}
        className={`day-column ${isHovered ? 'hover' : ''}`}
        onDragOver={(e) => handleDragOver(e, staffMember.id, dateStr)}
        onDrop={(e) => handleDrop(e, staffMember.id, dateStr)}
        onDragLeave={handleDragLeave}
      >
        <div className="shifts-container">
          {dayShifts.map(renderShift)}
        </div>
      </div>
    );
  };

  // Render staff row
  const renderStaffRow = (staffMember) => (
    <div key={staffMember.id} className="staff-row">
      <div className="staff-header">
        <div className="staff-name">{staffMember.name}</div>
        <div className="staff-role">{staffMember.role}</div>
      </div>
      <div className="staff-schedule">
        {daysInView.map(day => renderDayColumn(day, staffMember))}
      </div>
    </div>
  );

  // Render loading state
  if (isLoading) {
    return (
      <div className="schedule-calendar loading">
        <div className="loading-spinner">Loading schedule...</div>
      </div>
    );
  }

  return (
    <div className="schedule-calendar">
      {/* Calendar Header */}
      <div className="calendar-header">
        <div className="calendar-controls">
          <select 
            value={selectedStaff} 
            onChange={(e) => setSelectedStaff(e.target.value)}
            className="staff-filter"
          >
            <option value="all">All Staff</option>
            {staff.map(s => (
              <option key={s.id} value={s.id}>{s.name}</option>
            ))}
          </select>
        </div>
        
        <div className="calendar-days-header">
          <div className="time-column-header">Time</div>
          {daysInView.map(day => (
            <div key={day.toISOString()} className="day-header">
              <div className="day-name">{format(day, 'EEE')}</div>
              <div className="day-date">{format(day, 'MMM d')}</div>
            </div>
          ))}
        </div>
      </div>

      {/* Calendar Body */}
      <div className="calendar-body">
        <div className="time-column">
          {renderTimeSlots()}
        </div>
        
        <div className="calendar-grid">
          {selectedStaff === 'all' 
            ? staff.map(renderStaffRow)
            : staff.filter(s => s.id === parseInt(selectedStaff)).map(renderStaffRow)
          }
        </div>
      </div>

      {/* Legend */}
      <div className="calendar-legend">
        <div className="legend-item">
          <span className="legend-color" style={{ backgroundColor: getShiftColor('REGULAR') }}></span>
          Regular Shift
        </div>
        <div className="legend-item">
          <span className="legend-color" style={{ backgroundColor: getShiftColor('OVERTIME') }}></span>
          Overtime
        </div>
        <div className="legend-item">
          <span className="legend-color" style={{ backgroundColor: getShiftColor('HOLIDAY') }}></span>
          Holiday
        </div>
        <div className="legend-item">
          <span className="legend-color" style={{ backgroundColor: getShiftColor('TRAINING') }}></span>
          Training
        </div>
      </div>
    </div>
  );
};

export default ScheduleCalendar;