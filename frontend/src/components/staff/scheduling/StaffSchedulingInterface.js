import React, { useState, useEffect, useCallback } from 'react';
import { 
  format, 
  startOfWeek, 
  endOfWeek, 
  addWeeks, 
  subWeeks,
  parseISO,
  isValid
} from 'date-fns';
import ScheduleCalendar from './ScheduleCalendar';
import ShiftEditor from './ShiftEditor';
import StaffAvailability from './StaffAvailability';
import ScheduleToolbar from './ScheduleToolbar';
import ConflictResolver from './ConflictResolver';
import ScheduleExporter from './ScheduleExporter';
import PayrollIntegration from './PayrollIntegration';
import './StaffSchedulingInterface.css';
import './SchedulePrint.css';

const API_BASE_URL = process.env.REACT_APP_API_URL || 'http://localhost:8000';

const StaffSchedulingInterface = () => {
  // State management
  const [selectedDate, setSelectedDate] = useState(new Date());
  const [viewMode, setViewMode] = useState('week');
  const [shifts, setShifts] = useState([]);
  const [staff, setStaff] = useState([]);
  const [templates, setTemplates] = useState([]);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState(null);
  const [selectedShift, setSelectedShift] = useState(null);
  const [showShiftEditor, setShowShiftEditor] = useState(false);
  const [showAvailability, setShowAvailability] = useState(false);
  const [conflicts, setConflicts] = useState([]);
  const [showConflicts, setShowConflicts] = useState(false);
  const [scheduleStatus, setScheduleStatus] = useState('draft');
  const [showPayroll, setShowPayroll] = useState(false);

  // Fetch initial data
  useEffect(() => {
    fetchStaff();
    fetchTemplates();
  }, []);

  // Fetch shifts when date changes
  useEffect(() => {
    fetchShifts();
  }, [selectedDate, viewMode]);

  // API calls
  const fetchStaff = async () => {
    try {
      const response = await fetch(`${API_BASE_URL}/api/v1/staff/members`, {
        headers: {
          'Authorization': `Bearer ${localStorage.getItem('token')}`
        }
      });
      if (!response.ok) throw new Error('Failed to fetch staff');
      const data = await response.json();
      setStaff(data);
    } catch (err) {
      setError('Failed to load staff members');
      console.error(err);
    }
  };

  const fetchShifts = async () => {
    setIsLoading(true);
    try {
      const startDate = startOfWeek(selectedDate, { weekStartsOn: 1 });
      const endDate = endOfWeek(selectedDate, { weekStartsOn: 1 });
      
      const response = await fetch(
        `${API_BASE_URL}/api/v1/staff/scheduling/shifts?start_date=${format(startDate, 'yyyy-MM-dd')}&end_date=${format(endDate, 'yyyy-MM-dd')}`,
        {
          headers: {
            'Authorization': `Bearer ${localStorage.getItem('token')}`
          }
        }
      );
      
      if (!response.ok) throw new Error('Failed to fetch shifts');
      const data = await response.json();
      setShifts(data);
      
      // Check for conflicts
      await checkConflicts(data);
    } catch (err) {
      setError('Failed to load shifts');
      console.error(err);
    } finally {
      setIsLoading(false);
    }
  };

  const fetchTemplates = async () => {
    try {
      const response = await fetch(`${API_BASE_URL}/api/v1/staff/scheduling/templates`, {
        headers: {
          'Authorization': `Bearer ${localStorage.getItem('token')}`
        }
      });
      if (!response.ok) throw new Error('Failed to fetch templates');
      const data = await response.json();
      setTemplates(data);
    } catch (err) {
      console.error('Failed to load templates:', err);
    }
  };

  const checkConflicts = async (shiftData) => {
    try {
      const startDate = startOfWeek(selectedDate, { weekStartsOn: 1 });
      const endDate = endOfWeek(selectedDate, { weekStartsOn: 1 });
      
      const response = await fetch(
        `${API_BASE_URL}/api/v1/staff/scheduling/analytics/conflicts?start_date=${format(startDate, 'yyyy-MM-dd')}&end_date=${format(endDate, 'yyyy-MM-dd')}`,
        {
          headers: {
            'Authorization': `Bearer ${localStorage.getItem('token')}`
          }
        }
      );
      
      if (!response.ok) throw new Error('Failed to check conflicts');
      const conflictData = await response.json();
      setConflicts(conflictData);
      
      if (conflictData.length > 0) {
        setShowConflicts(true);
      }
    } catch (err) {
      console.error('Failed to check conflicts:', err);
    }
  };

  // Shift management
  const handleShiftClick = (shift) => {
    setSelectedShift(shift);
    setShowShiftEditor(true);
  };

  const handleShiftDrop = async (shift, newStaffId, newDate) => {
    try {
      // Validate newDate parameter
      let parsedNewDate;
      if (typeof newDate === 'string') {
        parsedNewDate = parseISO(newDate);
        if (!isValid(parsedNewDate)) {
          throw new Error('Invalid date string provided');
        }
      } else if (newDate instanceof Date) {
        if (!isValid(newDate)) {
          throw new Error('Invalid date object provided');
        }
        parsedNewDate = newDate;
      } else {
        throw new Error('Invalid date format provided');
      }

      // Parse existing shift times
      const startTime = parseISO(shift.start_time);
      const endTime = parseISO(shift.end_time);
      
      if (!isValid(startTime) || !isValid(endTime)) {
        throw new Error('Invalid shift times');
      }
      
      // Extract time components from original shift
      const hoursDiff = startTime.getHours();
      const minutesDiff = startTime.getMinutes();
      const secondsDiff = startTime.getSeconds();
      
      // Create new start time preserving original time components
      const newStartTime = new Date(parsedNewDate);
      newStartTime.setHours(hoursDiff, minutesDiff, secondsDiff, 0);
      
      // Calculate duration in milliseconds to preserve precision
      const durationMs = endTime.getTime() - startTime.getTime();
      
      // Calculate new end time by adding duration to new start time
      const newEndTime = new Date(newStartTime.getTime() + durationMs);

      const updatedShift = {
        ...shift,
        staff_id: newStaffId,
        date: format(parsedNewDate, 'yyyy-MM-dd'),
        start_time: newStartTime.toISOString(),
        end_time: newEndTime.toISOString()
      };

      const response = await fetch(
        `${API_BASE_URL}/api/v1/staff/scheduling/shifts/${shift.id}`,
        {
          method: 'PUT',
          headers: {
            'Authorization': `Bearer ${localStorage.getItem('token')}`,
            'Content-Type': 'application/json'
          },
          body: JSON.stringify(updatedShift)
        }
      );

      if (!response.ok) throw new Error('Failed to update shift');
      
      // Refresh shifts
      await fetchShifts();
    } catch (err) {
      setError('Failed to move shift');
      console.error(err);
    }
  };

  const handleCreateShift = async (shiftData) => {
    try {
      const response = await fetch(
        `${API_BASE_URL}/api/v1/staff/scheduling/shifts`,
        {
          method: 'POST',
          headers: {
            'Authorization': `Bearer ${localStorage.getItem('token')}`,
            'Content-Type': 'application/json'
          },
          body: JSON.stringify(shiftData)
        }
      );

      if (!response.ok) throw new Error('Failed to create shift');
      
      setShowShiftEditor(false);
      await fetchShifts();
    } catch (err) {
      setError('Failed to create shift');
      console.error(err);
    }
  };

  const handleUpdateShift = async (shiftId, shiftData) => {
    try {
      const response = await fetch(
        `${API_BASE_URL}/api/v1/staff/scheduling/shifts/${shiftId}`,
        {
          method: 'PUT',
          headers: {
            'Authorization': `Bearer ${localStorage.getItem('token')}`,
            'Content-Type': 'application/json'
          },
          body: JSON.stringify(shiftData)
        }
      );

      if (!response.ok) throw new Error('Failed to update shift');
      
      setShowShiftEditor(false);
      setSelectedShift(null);
      await fetchShifts();
    } catch (err) {
      setError('Failed to update shift');
      console.error(err);
    }
  };

  const handleDeleteShift = async (shiftId) => {
    if (!window.confirm('Are you sure you want to delete this shift?')) return;
    
    try {
      const response = await fetch(
        `${API_BASE_URL}/api/v1/staff/scheduling/shifts/${shiftId}`,
        {
          method: 'DELETE',
          headers: {
            'Authorization': `Bearer ${localStorage.getItem('token')}`
          }
        }
      );

      if (!response.ok) throw new Error('Failed to delete shift');
      
      setShowShiftEditor(false);
      setSelectedShift(null);
      await fetchShifts();
    } catch (err) {
      setError('Failed to delete shift');
      console.error(err);
    }
  };

  // Schedule management
  const handleGenerateSchedule = async (options) => {
    setIsLoading(true);
    try {
      const response = await fetch(
        `${API_BASE_URL}/api/v1/staff/scheduling/generate`,
        {
          method: 'POST',
          headers: {
            'Authorization': `Bearer ${localStorage.getItem('token')}`,
            'Content-Type': 'application/json'
          },
          body: JSON.stringify({
            start_date: format(startOfWeek(selectedDate, { weekStartsOn: 1 }), 'yyyy-MM-dd'),
            end_date: format(endOfWeek(selectedDate, { weekStartsOn: 1 }), 'yyyy-MM-dd'),
            ...options
          })
        }
      );

      if (!response.ok) throw new Error('Failed to generate schedule');
      
      await fetchShifts();
    } catch (err) {
      setError('Failed to generate schedule');
      console.error(err);
    } finally {
      setIsLoading(false);
    }
  };

  const handlePublishSchedule = async () => {
    if (!window.confirm('Are you sure you want to publish this schedule? Staff will be notified.')) return;
    
    setIsLoading(true);
    try {
      const response = await fetch(
        `${API_BASE_URL}/api/v1/staff/scheduling/schedule/publish`,
        {
          method: 'POST',
          headers: {
            'Authorization': `Bearer ${localStorage.getItem('token')}`,
            'Content-Type': 'application/json'
          },
          body: JSON.stringify({
            start_date: format(startOfWeek(selectedDate, { weekStartsOn: 1 }), 'yyyy-MM-dd'),
            end_date: format(endOfWeek(selectedDate, { weekStartsOn: 1 }), 'yyyy-MM-dd'),
            notify_staff: true
          })
        }
      );

      if (!response.ok) throw new Error('Failed to publish schedule');
      
      const result = await response.json();
      setScheduleStatus('published');
      await fetchShifts();
      
      alert(`Schedule published successfully! ${result.notifications_sent} notifications sent.`);
    } catch (err) {
      setError('Failed to publish schedule');
      console.error(err);
    } finally {
      setIsLoading(false);
    }
  };

  // Navigation
  const handlePreviousWeek = () => {
    setSelectedDate(subWeeks(selectedDate, 1));
  };

  const handleNextWeek = () => {
    setSelectedDate(addWeeks(selectedDate, 1));
  };

  const handleToday = () => {
    setSelectedDate(new Date());
  };

  // Export functionality
  const handleExportSchedule = async (exportFormat) => {
    try {
      const startDate = startOfWeek(selectedDate, { weekStartsOn: 1 });
      const endDate = endOfWeek(selectedDate, { weekStartsOn: 1 });
      
      switch (exportFormat) {
        case 'pdf':
          ScheduleExporter.exportToPDF(shifts, staff, startDate, endDate);
          break;
        case 'excel':
          ScheduleExporter.exportToExcel(shifts, staff, startDate, endDate);
          break;
        case 'csv':
          ScheduleExporter.exportToCSV(shifts, staff, startDate, endDate);
          break;
        case 'print':
          ScheduleExporter.prepareForPrint(startDate, endDate);
          break;
        default:
          throw new Error('Unsupported export format');
      }
    } catch (err) {
      setError('Failed to export schedule');
      console.error(err);
    }
  };

  return (
    <div className="staff-scheduling-interface">
      {/* Toolbar */}
      <ScheduleToolbar
        selectedDate={selectedDate}
        viewMode={viewMode}
        scheduleStatus={scheduleStatus}
        onPreviousWeek={handlePreviousWeek}
        onNextWeek={handleNextWeek}
        onToday={handleToday}
        onViewModeChange={setViewMode}
        onCreateShift={() => setShowShiftEditor(true)}
        onGenerateSchedule={handleGenerateSchedule}
        onPublishSchedule={handlePublishSchedule}
        onExport={handleExportSchedule}
        onShowAvailability={() => setShowAvailability(true)}
        hasConflicts={conflicts.length > 0}
        onShowConflicts={() => setShowConflicts(true)}
        onShowPayroll={() => setShowPayroll(true)}
      />

      {/* Error Alert */}
      {error && (
        <div className="error-alert">
          <span>{error}</span>
          <button onClick={() => setError(null)}>×</button>
        </div>
      )}

      {/* Main Calendar View */}
      <div className="schedule-content">
        <ScheduleCalendar
          shifts={shifts}
          staff={staff}
          selectedDate={selectedDate}
          viewMode={viewMode}
          onDateChange={setSelectedDate}
          onShiftClick={handleShiftClick}
          onShiftDrop={handleShiftDrop}
          isLoading={isLoading}
        />
      </div>

      {/* Shift Editor Modal */}
      {showShiftEditor && (
        <ShiftEditor
          shift={selectedShift}
          staff={staff}
          templates={templates}
          onSave={selectedShift ? 
            (data) => handleUpdateShift(selectedShift.id, data) : 
            handleCreateShift
          }
          onDelete={selectedShift ? 
            () => handleDeleteShift(selectedShift.id) : 
            null
          }
          onClose={() => {
            setShowShiftEditor(false);
            setSelectedShift(null);
          }}
        />
      )}

      {/* Staff Availability Modal */}
      {showAvailability && (
        <StaffAvailability
          staff={staff}
          selectedDate={selectedDate}
          onClose={() => setShowAvailability(false)}
        />
      )}

      {/* Conflict Resolver Modal */}
      {showConflicts && (
        <ConflictResolver
          conflicts={conflicts}
          shifts={shifts}
          staff={staff}
          onResolve={fetchShifts}
          onClose={() => setShowConflicts(false)}
        />
      )}

      {/* Payroll Integration Modal */}
      {showPayroll && (
        <PayrollIntegration
          shifts={shifts}
          staff={staff}
          selectedDate={selectedDate}
          onClose={() => setShowPayroll(false)}
        />
      )}
    </div>
  );
};

export default StaffSchedulingInterface;