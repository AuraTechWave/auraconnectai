import React, { useState, useEffect } from 'react';
import { format, startOfWeek, endOfWeek, addDays, parseISO } from 'date-fns';
import './StaffAvailability.css';

const API_BASE_URL = process.env.REACT_APP_API_URL || 'http://localhost:8000';

const StaffAvailability = ({ staff, selectedDate, onClose }) => {
  const [availabilities, setAvailabilities] = useState([]);
  const [selectedStaff, setSelectedStaff] = useState(staff[0]?.id || '');
  const [isLoading, setIsLoading] = useState(false);
  const [editMode, setEditMode] = useState(false);
  const [formData, setFormData] = useState({});

  const weekStart = startOfWeek(selectedDate, { weekStartsOn: 1 });
  const weekDays = Array.from({ length: 7 }, (_, i) => addDays(weekStart, i));

  const timeSlots = [
    { label: 'Morning', value: 'MORNING', start: '06:00', end: '12:00' },
    { label: 'Afternoon', value: 'AFTERNOON', start: '12:00', end: '18:00' },
    { label: 'Evening', value: 'EVENING', start: '18:00', end: '23:00' },
    { label: 'All Day', value: 'ALL_DAY', start: '06:00', end: '23:00' }
  ];

  useEffect(() => {
    if (selectedStaff) {
      fetchAvailability();
    }
  }, [selectedStaff, selectedDate]);

  const fetchAvailability = async () => {
    setIsLoading(true);
    try {
      const response = await fetch(
        `${API_BASE_URL}/api/v1/staff/scheduling/availability?staff_id=${selectedStaff}&start_date=${format(weekStart, 'yyyy-MM-dd')}&end_date=${format(endOfWeek(selectedDate, { weekStartsOn: 1 }), 'yyyy-MM-dd')}`,
        {
          headers: {
            'Authorization': `Bearer ${localStorage.getItem('token')}`
          }
        }
      );
      
      if (!response.ok) throw new Error('Failed to fetch availability');
      const data = await response.json();
      setAvailabilities(data);
      
      // Initialize form data
      const newFormData = {};
      weekDays.forEach(day => {
        const dayStr = format(day, 'yyyy-MM-dd');
        newFormData[dayStr] = {
          available: false,
          slots: []
        };
      });
      
      data.forEach(avail => {
        const date = format(parseISO(avail.date), 'yyyy-MM-dd');
        if (newFormData[date]) {
          newFormData[date].available = avail.is_available;
          if (avail.is_available) {
            newFormData[date].slots = avail.time_slots || ['ALL_DAY'];
          }
        }
      });
      
      setFormData(newFormData);
    } catch (err) {
      console.error('Failed to load availability:', err);
    } finally {
      setIsLoading(false);
    }
  };

  const handleStaffChange = (staffId) => {
    setSelectedStaff(staffId);
    setEditMode(false);
  };

  const handleToggleDay = (date) => {
    if (!editMode) return;
    
    setFormData({
      ...formData,
      [date]: {
        ...formData[date],
        available: !formData[date].available,
        slots: !formData[date].available ? ['ALL_DAY'] : []
      }
    });
  };

  const handleSlotToggle = (date, slot) => {
    if (!editMode || !formData[date].available) return;
    
    const currentSlots = formData[date].slots;
    const newSlots = currentSlots.includes(slot)
      ? currentSlots.filter(s => s !== slot)
      : [...currentSlots, slot];
    
    setFormData({
      ...formData,
      [date]: {
        ...formData[date],
        slots: newSlots
      }
    });
  };

  const handleSave = async () => {
    try {
      const updates = [];
      
      Object.entries(formData).forEach(([date, data]) => {
        if (data.available && data.slots.length > 0) {
          updates.push({
            staff_id: parseInt(selectedStaff),
            date: date,
            is_available: true,
            time_slots: data.slots,
            start_time: `${date}T${getEarliestTime(data.slots)}:00`,
            end_time: `${date}T${getLatestTime(data.slots)}:00`
          });
        } else {
          updates.push({
            staff_id: parseInt(selectedStaff),
            date: date,
            is_available: false
          });
        }
      });

      // Save each availability update
      for (const update of updates) {
        const response = await fetch(
          `${API_BASE_URL}/api/v1/staff/scheduling/availability`,
          {
            method: 'POST',
            headers: {
              'Authorization': `Bearer ${localStorage.getItem('token')}`,
              'Content-Type': 'application/json'
            },
            body: JSON.stringify(update)
          }
        );
        
        if (!response.ok) throw new Error('Failed to save availability');
      }
      
      setEditMode(false);
      await fetchAvailability();
    } catch (err) {
      console.error('Failed to save availability:', err);
      alert('Failed to save availability. Please try again.');
    }
  };

  const getEarliestTime = (slots) => {
    if (slots.includes('ALL_DAY')) return '06:00';
    const times = slots.map(s => timeSlots.find(ts => ts.value === s)?.start || '06:00');
    return times.sort()[0];
  };

  const getLatestTime = (slots) => {
    if (slots.includes('ALL_DAY')) return '23:00';
    const times = slots.map(s => timeSlots.find(ts => ts.value === s)?.end || '23:00');
    return times.sort().reverse()[0];
  };

  const getAvailabilityStatus = (date) => {
    const dateStr = format(date, 'yyyy-MM-dd');
    const data = formData[dateStr];
    
    if (!data || !data.available) return 'unavailable';
    if (data.slots.includes('ALL_DAY')) return 'all-day';
    if (data.slots.length > 0) return 'partial';
    return 'unavailable';
  };

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="staff-availability" onClick={e => e.stopPropagation()}>
        <div className="availability-header">
          <h2>Staff Availability</h2>
          <button className="close-button" onClick={onClose}>×</button>
        </div>

        <div className="availability-controls">
          <select 
            value={selectedStaff} 
            onChange={(e) => handleStaffChange(e.target.value)}
            className="staff-selector"
          >
            {staff.map(member => (
              <option key={member.id} value={member.id}>
                {member.name} - {member.role}
              </option>
            ))}
          </select>

          {!editMode ? (
            <button 
              className="edit-button"
              onClick={() => setEditMode(true)}
            >
              Edit Availability
            </button>
          ) : (
            <div className="edit-actions">
              <button 
                className="save-button"
                onClick={handleSave}
              >
                Save Changes
              </button>
              <button 
                className="cancel-button"
                onClick={() => {
                  setEditMode(false);
                  fetchAvailability();
                }}
              >
                Cancel
              </button>
            </div>
          )}
        </div>

        {isLoading ? (
          <div className="loading">Loading availability...</div>
        ) : (
          <div className="availability-grid">
            {weekDays.map(day => {
              const dateStr = format(day, 'yyyy-MM-dd');
              const dayData = formData[dateStr] || { available: false, slots: [] };
              const status = getAvailabilityStatus(day);
              
              return (
                <div key={dateStr} className="day-column">
                  <div className="day-header">
                    <div className="day-name">{format(day, 'EEE')}</div>
                    <div className="day-date">{format(day, 'MMM d')}</div>
                  </div>
                  
                  <div 
                    className={`day-status ${status} ${editMode ? 'editable' : ''}`}
                    onClick={() => handleToggleDay(dateStr)}
                  >
                    {dayData.available ? (
                      <span className="available">✓ Available</span>
                    ) : (
                      <span className="unavailable">✗ Unavailable</span>
                    )}
                  </div>
                  
                  {editMode && dayData.available && (
                    <div className="time-slots">
                      {timeSlots.map(slot => (
                        <label 
                          key={slot.value} 
                          className="slot-option"
                        >
                          <input
                            type="checkbox"
                            checked={dayData.slots.includes(slot.value)}
                            onChange={() => handleSlotToggle(dateStr, slot.value)}
                          />
                          <span>{slot.label}</span>
                          <small>{slot.start} - {slot.end}</small>
                        </label>
                      ))}
                    </div>
                  )}
                  
                  {!editMode && dayData.available && dayData.slots.length > 0 && (
                    <div className="selected-slots">
                      {dayData.slots.map(slotValue => {
                        const slot = timeSlots.find(s => s.value === slotValue);
                        return slot ? (
                          <div key={slotValue} className="slot-tag">
                            {slot.label}
                          </div>
                        ) : null;
                      })}
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        )}

        <div className="availability-legend">
          <div className="legend-item">
            <span className="legend-color available"></span>
            Available
          </div>
          <div className="legend-item">
            <span className="legend-color partial"></span>
            Partial Availability
          </div>
          <div className="legend-item">
            <span className="legend-color unavailable"></span>
            Unavailable
          </div>
        </div>
      </div>
    </div>
  );
};

export default StaffAvailability;