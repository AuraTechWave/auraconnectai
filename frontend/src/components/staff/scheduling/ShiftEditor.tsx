import React, { useState, useEffect, useRef } from 'react';
import { format, parseISO } from 'date-fns';
import { FocusTrap, announce, KEYS } from '../../../utils/accessibility';
import { formatInRestaurantTz, createShiftWithTz, getRestaurantTimezone } from '../../../utils/timezone';
import './ShiftEditor.css';

interface Shift {
  id?: number;
  staff_id: number;
  role_id?: number;
  date: string;
  start_time: string;
  end_time: string;
  shift_type: 'REGULAR' | 'OVERTIME' | 'HOLIDAY' | 'TRAINING';
  hourly_rate?: number;
  notes?: string;
  template_id?: number;
}

interface Staff {
  id: number;
  name: string;
  role: string;
  hourly_rate?: number;
}

interface ShiftTemplate {
  id: number;
  name: string;
  start_time: string;
  end_time: string;
  role_id?: number;
}

interface ShiftEditorProps {
  shift?: Shift;
  staff: Staff[];
  templates: ShiftTemplate[];
  onSave: (shiftData: any) => Promise<void>;
  onDelete?: () => Promise<void>;
  onClose: () => void;
}

interface FormData {
  staff_id: string;
  role_id: string;
  date: string;
  start_time: string;
  end_time: string;
  shift_type: 'REGULAR' | 'OVERTIME' | 'HOLIDAY' | 'TRAINING';
  hourly_rate: string;
  notes: string;
  template_id: string;
}

interface FormErrors {
  staff_id?: string;
  date?: string;
  start_time?: string;
  end_time?: string;
}

const ShiftEditor: React.FC<ShiftEditorProps> = ({ 
  shift, 
  staff, 
  templates, 
  onSave, 
  onDelete, 
  onClose 
}) => {
  const [formData, setFormData] = useState<FormData>({
    staff_id: shift?.staff_id?.toString() || '',
    role_id: shift?.role_id?.toString() || '',
    date: shift?.date ? format(parseISO(shift.date), 'yyyy-MM-dd') : format(new Date(), 'yyyy-MM-dd'),
    start_time: shift?.start_time ? format(parseISO(shift.start_time), 'HH:mm') : '09:00',
    end_time: shift?.end_time ? format(parseISO(shift.end_time), 'HH:mm') : '17:00',
    shift_type: shift?.shift_type || 'REGULAR',
    hourly_rate: shift?.hourly_rate?.toString() || '',
    notes: shift?.notes || '',
    template_id: shift?.template_id?.toString() || ''
  });

  const [errors, setErrors] = useState<FormErrors>({});
  const [isSubmitting, setIsSubmitting] = useState(false);
  
  const modalRef = useRef<HTMLDivElement>(null);
  const focusTrapRef = useRef<FocusTrap | null>(null);
  const firstFieldRef = useRef<HTMLSelectElement>(null);

  // Initialize focus trap
  useEffect(() => {
    if (modalRef.current) {
      focusTrapRef.current = new FocusTrap(modalRef.current);
      focusTrapRef.current.activate();
      
      // Focus first field
      setTimeout(() => {
        firstFieldRef.current?.focus();
      }, 100);
      
      // Announce modal opened
      const action = shift ? 'Edit' : 'Create';
      announce(`${action} shift dialog opened`, 'polite');
    }

    return () => {
      focusTrapRef.current?.deactivate();
    };
  }, [shift]);

  // Handle keyboard shortcuts
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === KEYS.ESCAPE && !isSubmitting) {
        e.preventDefault();
        onClose();
      }
    };

    document.addEventListener('keydown', handleKeyDown);
    return () => document.removeEventListener('keydown', handleKeyDown);
  }, [onClose, isSubmitting]);

  // Calculate estimated cost
  const calculateEstimatedCost = (): string => {
    if (!formData.hourly_rate || !formData.start_time || !formData.end_time) return '0.00';
    
    try {
      const start = parseISO(`${formData.date}T${formData.start_time}`);
      const end = parseISO(`${formData.date}T${formData.end_time}`);
      const hours = (end.getTime() - start.getTime()) / (1000 * 60 * 60);
      
      return (hours * parseFloat(formData.hourly_rate)).toFixed(2);
    } catch {
      return '0.00';
    }
  };

  // Apply template
  const handleTemplateSelect = (templateId: string) => {
    const template = templates.find(t => t.id === parseInt(templateId));
    if (template) {
      setFormData({
        ...formData,
        template_id: templateId,
        start_time: format(parseISO(template.start_time), 'HH:mm'),
        end_time: format(parseISO(template.end_time), 'HH:mm'),
        role_id: template.role_id?.toString() || formData.role_id
      });
      announce(`Applied template: ${template.name}`);
    }
  };

  // Validate form
  const validateForm = (): boolean => {
    const newErrors: FormErrors = {};
    
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
    try {
      const start = parseISO(`${formData.date}T${formData.start_time}`);
      const end = parseISO(`${formData.date}T${formData.end_time}`);
      if (end <= start) {
        newErrors.end_time = 'End time must be after start time';
      }
    } catch {
      newErrors.end_time = 'Invalid time format';
    }
    
    setErrors(newErrors);
    
    // Announce first error if any
    if (Object.keys(newErrors).length > 0) {
      const firstError = Object.values(newErrors)[0];
      announce(`Validation error: ${firstError}`, 'assertive');
    }
    
    return Object.keys(newErrors).length === 0;
  };

  // Handle form submission
  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    
    if (!validateForm()) return;
    
    setIsSubmitting(true);
    announce('Saving shift...', 'polite');
    
    try {
      const selectedStaff = staff.find(s => s.id === parseInt(formData.staff_id));
      
      // Create timezone-aware shift times
      const shiftDate = parseISO(formData.date);
      const { start, end } = createShiftWithTz(shiftDate, formData.start_time, formData.end_time);
      
      const submitData = {
        ...formData,
        start_time: start.toISOString(),
        end_time: end.toISOString(),
        staff_id: parseInt(formData.staff_id),
        role_id: formData.role_id ? parseInt(formData.role_id) : null,
        template_id: formData.template_id ? parseInt(formData.template_id) : null,
        hourly_rate: formData.hourly_rate ? parseFloat(formData.hourly_rate) : 
                     selectedStaff?.hourly_rate || null,
        estimated_cost: parseFloat(calculateEstimatedCost())
      };
      
      await onSave(submitData);
      announce('Shift saved successfully', 'assertive');
    } catch (error) {
      console.error('Failed to save shift:', error);
      announce('Failed to save shift. Please try again.', 'assertive');
    } finally {
      setIsSubmitting(false);
    }
  };

  // Handle input changes
  const handleChange = (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement | HTMLTextAreaElement>) => {
    const { name, value } = e.target;
    setFormData({ ...formData, [name]: value });
    
    // Clear error for this field
    if (errors[name as keyof FormErrors]) {
      setErrors({ ...errors, [name]: undefined });
    }
  };

  // Handle delete with confirmation
  const handleDelete = async () => {
    const confirmed = window.confirm('Are you sure you want to delete this shift? This action cannot be undone.');
    if (confirmed && onDelete) {
      announce('Deleting shift...', 'polite');
      try {
        await onDelete();
        announce('Shift deleted successfully', 'assertive');
      } catch (error) {
        announce('Failed to delete shift', 'assertive');
      }
    }
  };

  const timezoneAbbr = formatInRestaurantTz(new Date(), 'zzz');

  return (
    <div 
      className="modal-overlay" 
      onClick={onClose}
      role="presentation"
    >
      <div 
        ref={modalRef}
        className="shift-editor" 
        onClick={e => e.stopPropagation()}
        role="dialog"
        aria-modal="true"
        aria-labelledby="shift-editor-title"
      >
        <div className="editor-header">
          <h2 id="shift-editor-title">
            {shift ? 'Edit Shift' : 'Create New Shift'}
          </h2>
          <button 
            className="close-button" 
            onClick={onClose}
            aria-label="Close shift editor"
          >
            ×
          </button>
        </div>

        <form onSubmit={handleSubmit} noValidate>
          <div className="form-row">
            <div className="form-group">
              <label htmlFor="staff_id">
                Staff Member <abbr title="required" aria-label="required">*</abbr>
              </label>
              <select
                ref={firstFieldRef}
                id="staff_id"
                name="staff_id"
                value={formData.staff_id}
                onChange={handleChange}
                className={errors.staff_id ? 'error' : ''}
                required
                aria-invalid={!!errors.staff_id}
                aria-describedby={errors.staff_id ? 'staff_id-error' : undefined}
              >
                <option value="">Select staff member</option>
                {staff.map(member => (
                  <option key={member.id} value={member.id}>
                    {member.name} - {member.role}
                  </option>
                ))}
              </select>
              {errors.staff_id && (
                <span id="staff_id-error" className="error-message" role="alert">
                  {errors.staff_id}
                </span>
              )}
            </div>

            <div className="form-group">
              <label htmlFor="template_id">Use Template</label>
              <select
                id="template_id"
                name="template_id"
                value={formData.template_id}
                onChange={(e) => handleTemplateSelect(e.target.value)}
                aria-describedby="template-help"
              >
                <option value="">No template</option>
                {templates.map(template => (
                  <option key={template.id} value={template.id}>
                    {template.name}
                  </option>
                ))}
              </select>
              <span id="template-help" className="form-help">
                Templates pre-fill shift times
              </span>
            </div>
          </div>

          <div className="form-row">
            <div className="form-group">
              <label htmlFor="date">
                Date <abbr title="required" aria-label="required">*</abbr>
              </label>
              <input
                type="date"
                id="date"
                name="date"
                value={formData.date}
                onChange={handleChange}
                className={errors.date ? 'error' : ''}
                required
                aria-invalid={!!errors.date}
                aria-describedby={errors.date ? 'date-error' : 'date-help'}
              />
              <span id="date-help" className="form-help">
                Schedule date (timezone: {timezoneAbbr})
              </span>
              {errors.date && (
                <span id="date-error" className="error-message" role="alert">
                  {errors.date}
                </span>
              )}
            </div>

            <div className="form-group">
              <label htmlFor="shift_type">Shift Type</label>
              <select
                id="shift_type"
                name="shift_type"
                value={formData.shift_type}
                onChange={handleChange}
                aria-describedby="shift-type-help"
              >
                <option value="REGULAR">Regular</option>
                <option value="OVERTIME">Overtime</option>
                <option value="HOLIDAY">Holiday</option>
                <option value="TRAINING">Training</option>
              </select>
              <span id="shift-type-help" className="form-help">
                Affects pay calculations
              </span>
            </div>
          </div>

          <div className="form-row">
            <div className="form-group">
              <label htmlFor="start_time">
                Start Time <abbr title="required" aria-label="required">*</abbr>
              </label>
              <input
                type="time"
                id="start_time"
                name="start_time"
                value={formData.start_time}
                onChange={handleChange}
                className={errors.start_time ? 'error' : ''}
                required
                aria-invalid={!!errors.start_time}
                aria-describedby={errors.start_time ? 'start_time-error' : 'time-help'}
              />
              {errors.start_time && (
                <span id="start_time-error" className="error-message" role="alert">
                  {errors.start_time}
                </span>
              )}
            </div>

            <div className="form-group">
              <label htmlFor="end_time">
                End Time <abbr title="required" aria-label="required">*</abbr>
              </label>
              <input
                type="time"
                id="end_time"
                name="end_time"
                value={formData.end_time}
                onChange={handleChange}
                className={errors.end_time ? 'error' : ''}
                required
                aria-invalid={!!errors.end_time}
                aria-describedby={errors.end_time ? 'end_time-error' : 'time-help'}
              />
              <span id="time-help" className="form-help">
                Times in {timezoneAbbr} timezone
              </span>
              {errors.end_time && (
                <span id="end_time-error" className="error-message" role="alert">
                  {errors.end_time}
                </span>
              )}
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
                aria-describedby="rate-help"
              />
              <span id="rate-help" className="form-help">
                Leave blank to use staff default
              </span>
            </div>

            <div className="form-group">
              <label id="cost-label">Estimated Cost</label>
              <div 
                className="calculated-value"
                role="status"
                aria-live="polite"
                aria-labelledby="cost-label"
              >
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
              rows={3}
              placeholder="Add any special instructions or notes..."
              aria-describedby="notes-help"
            />
            <span id="notes-help" className="form-help">
              Optional notes visible to staff
            </span>
          </div>

          <div className="editor-actions">
            <button 
              type="button" 
              className="button secondary"
              onClick={onClose}
              disabled={isSubmitting}
            >
              Cancel
            </button>
            
            {shift && onDelete && (
              <button 
                type="button" 
                className="button danger"
                onClick={handleDelete}
                disabled={isSubmitting}
                aria-describedby="delete-warning"
              >
                Delete
              </button>
            )}
            <span id="delete-warning" className="sr-only">
              This will permanently delete the shift
            </span>
            
            <button 
              type="submit" 
              className="button primary"
              disabled={isSubmitting}
              aria-busy={isSubmitting}
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