import React, { useState, useEffect } from 'react';
import { format, parseISO, setHours, setMinutes } from 'date-fns';
import './ShiftEditor.css';

const ShiftEditor = ({ shift, staff, templates, onSave, onDelete, onClose }) => {
  const [formData, setFormData] = useState({
    staff_id: shift?.staff_id || '',
    role_id: shift?.role_id || '',
    date: shift?.date ? format(parseISO(shift.date), 'yyyy-MM-dd') : format(new Date(), 'yyyy-MM-dd'),
    start_time: shift?.start_time ? format(parseISO(shift.start_time), 'HH:mm') : '09:00',
    end_time: shift?.end_time ? format(parseISO(shift.end_time), 'HH:mm') : '17:00',
    shift_type: shift?.shift_type || 'REGULAR',
    hourly_rate: shift?.hourly_rate || '',
    notes: shift?.notes || '',
    template_id: shift?.template_id || ''
  });

  const [errors, setErrors] = useState({});
  const [isSubmitting, setIsSubmitting] = useState(false);

  // Calculate estimated cost
  const calculateEstimatedCost = () => {
    if (!formData.hourly_rate || !formData.start_time || !formData.end_time) return 0;
    
    const start = parseISO(`${formData.date}T${formData.start_time}`);
    const end = parseISO(`${formData.date}T${formData.end_time}`);
    const hours = (end - start) / (1000 * 60 * 60);
    
    return (hours * parseFloat(formData.hourly_rate)).toFixed(2);
  };

  // Apply template
  const handleTemplateSelect = (templateId) => {
    const template = templates.find(t => t.id === parseInt(templateId));
    if (template) {
      setFormData({
        ...formData,
        template_id: templateId,
        start_time: format(parseISO(template.start_time), 'HH:mm'),
        end_time: format(parseISO(template.end_time), 'HH:mm'),
        role_id: template.role_id || formData.role_id
      });
    }
  };

  // Validate form
  const validateForm = () => {
    const newErrors = {};
    
    if (!formData.staff_id) {
      newErrors.staff_id = 'Please select a staff member';
    }
    
    if (!formData.date) {
      newErrors.date = 'Please select a date';
    }
    
    if (!formData.start_time) {
      newErrors.start_time = 'Please enter start time';
    }
    
    if (!formData.end_time) {
      newErrors.end_time = 'Please enter end time';
    }
    
    // Check if end time is after start time
    const start = parseISO(`${formData.date}T${formData.start_time}`);
    const end = parseISO(`${formData.date}T${formData.end_time}`);
    if (end <= start) {
      newErrors.end_time = 'End time must be after start time';
    }
    
    setErrors(newErrors);
    return Object.keys(newErrors).length === 0;
  };

  // Handle form submission
  const handleSubmit = async (e) => {
    e.preventDefault();
    
    if (!validateForm()) return;
    
    setIsSubmitting(true);
    
    try {
      const submitData = {
        ...formData,
        start_time: `${formData.date}T${formData.start_time}:00`,
        end_time: `${formData.date}T${formData.end_time}:00`,
        staff_id: parseInt(formData.staff_id),
        role_id: formData.role_id ? parseInt(formData.role_id) : null,
        template_id: formData.template_id ? parseInt(formData.template_id) : null,
        hourly_rate: formData.hourly_rate ? parseFloat(formData.hourly_rate) : null,
        estimated_cost: calculateEstimatedCost()
      };
      
      await onSave(submitData);
    } catch (error) {
      console.error('Failed to save shift:', error);
    } finally {
      setIsSubmitting(false);
    }
  };

  // Handle input changes
  const handleChange = (e) => {
    const { name, value } = e.target;
    setFormData({ ...formData, [name]: value });
    
    // Clear error for this field
    if (errors[name]) {
      setErrors({ ...errors, [name]: '' });
    }
  };

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="shift-editor" onClick={e => e.stopPropagation()}>
        <div className="editor-header">
          <h2>{shift ? 'Edit Shift' : 'Create New Shift'}</h2>
          <button className="close-button" onClick={onClose}>×</button>
        </div>

        <form onSubmit={handleSubmit}>
          <div className="form-row">
            <div className="form-group">
              <label htmlFor="staff_id">Staff Member *</label>
              <select
                id="staff_id"
                name="staff_id"
                value={formData.staff_id}
                onChange={handleChange}
                className={errors.staff_id ? 'error' : ''}
              >
                <option value="">Select staff member</option>
                {staff.map(member => (
                  <option key={member.id} value={member.id}>
                    {member.name} - {member.role}
                  </option>
                ))}
              </select>
              {errors.staff_id && <span className="error-message">{errors.staff_id}</span>}
            </div>

            <div className="form-group">
              <label htmlFor="template_id">Use Template</label>
              <select
                id="template_id"
                name="template_id"
                value={formData.template_id}
                onChange={(e) => handleTemplateSelect(e.target.value)}
              >
                <option value="">No template</option>
                {templates.map(template => (
                  <option key={template.id} value={template.id}>
                    {template.name}
                  </option>
                ))}
              </select>
            </div>
          </div>

          <div className="form-row">
            <div className="form-group">
              <label htmlFor="date">Date *</label>
              <input
                type="date"
                id="date"
                name="date"
                value={formData.date}
                onChange={handleChange}
                className={errors.date ? 'error' : ''}
              />
              {errors.date && <span className="error-message">{errors.date}</span>}
            </div>

            <div className="form-group">
              <label htmlFor="shift_type">Shift Type</label>
              <select
                id="shift_type"
                name="shift_type"
                value={formData.shift_type}
                onChange={handleChange}
              >
                <option value="REGULAR">Regular</option>
                <option value="OVERTIME">Overtime</option>
                <option value="HOLIDAY">Holiday</option>
                <option value="TRAINING">Training</option>
              </select>
            </div>
          </div>

          <div className="form-row">
            <div className="form-group">
              <label htmlFor="start_time">Start Time *</label>
              <input
                type="time"
                id="start_time"
                name="start_time"
                value={formData.start_time}
                onChange={handleChange}
                className={errors.start_time ? 'error' : ''}
              />
              {errors.start_time && <span className="error-message">{errors.start_time}</span>}
            </div>

            <div className="form-group">
              <label htmlFor="end_time">End Time *</label>
              <input
                type="time"
                id="end_time"
                name="end_time"
                value={formData.end_time}
                onChange={handleChange}
                className={errors.end_time ? 'error' : ''}
              />
              {errors.end_time && <span className="error-message">{errors.end_time}</span>}
            </div>
          </div>

          <div className="form-row">
            <div className="form-group">
              <label htmlFor="hourly_rate">Hourly Rate ($)</label>
              <input
                type="number"
                id="hourly_rate"
                name="hourly_rate"
                value={formData.hourly_rate}
                onChange={handleChange}
                step="0.01"
                min="0"
                placeholder="0.00"
              />
            </div>

            <div className="form-group">
              <label>Estimated Cost</label>
              <div className="calculated-value">
                ${calculateEstimatedCost()}
              </div>
            </div>
          </div>

          <div className="form-group">
            <label htmlFor="notes">Notes</label>
            <textarea
              id="notes"
              name="notes"
              value={formData.notes}
              onChange={handleChange}
              rows="3"
              placeholder="Add any special instructions or notes..."
            />
          </div>

          <div className="editor-actions">
            <button 
              type="button" 
              className="button secondary"
              onClick={onClose}
            >
              Cancel
            </button>
            
            {shift && onDelete && (
              <button 
                type="button" 
                className="button danger"
                onClick={() => {
                  if (window.confirm('Are you sure you want to delete this shift?')) {
                    onDelete();
                  }
                }}
              >
                Delete
              </button>
            )}
            
            <button 
              type="submit" 
              className="button primary"
              disabled={isSubmitting}
            >
              {isSubmitting ? 'Saving...' : (shift ? 'Update Shift' : 'Create Shift')}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
};

export default ShiftEditor;