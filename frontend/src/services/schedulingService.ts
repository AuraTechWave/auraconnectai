import api, { handleApiError, buildQueryString } from './api';

// Types for scheduling
export interface Shift {
  id?: string;
  staff_id: number;
  start_time: string; // ISO 8601 with timezone
  end_time: string; // ISO 8601 with timezone
  position: string;
  department?: string;
  break_duration?: number;
  notes?: string;
  status: 'draft' | 'published' | 'cancelled';
  created_at?: string;
  updated_at?: string;
}

export interface StaffAvailability {
  id?: string;
  staff_id: number;
  day_of_week: number; // 0-6
  start_time: string; // HH:MM:SS
  end_time: string; // HH:MM:SS
  is_available: boolean;
  notes?: string;
}

export interface ScheduleTemplate {
  id?: string;
  name: string;
  description?: string;
  shifts: Shift[];
  is_active: boolean;
}

export interface ScheduleConflict {
  id: string;
  type: 'double_booking' | 'overtime' | 'availability' | 'break_violation' | 'rest_period' | 'skill_mismatch';
  severity: 'high' | 'medium' | 'low';
  description: string;
  affected_shifts: string[];
  resolution_suggestions?: string[];
}

export interface PayrollSummary {
  staff_id: number;
  period_start: string;
  period_end: string;
  total_hours: number;
  regular_hours: number;
  overtime_hours: number;
  gross_pay: number;
  deductions: number;
  net_pay: number;
  details?: any;
}

// Scheduling API service
class SchedulingService {
  // Shifts CRUD
  async getShifts(params?: {
    start_date?: string;
    end_date?: string;
    staff_id?: number;
    department?: string;
    status?: string;
  }) {
    try {
      const queryString = params ? buildQueryString(params) : '';
      const response = await api.get(`/api/v1/staff/shifts${queryString ? `?${queryString}` : ''}`);
      return response.data;
    } catch (error) {
      throw new Error(handleApiError(error));
    }
  }

  async createShift(shift: Shift) {
    try {
      const response = await api.post('/api/v1/staff/shifts', shift);
      return response.data;
    } catch (error) {
      throw new Error(handleApiError(error));
    }
  }

  async updateShift(id: string, shift: Partial<Shift>) {
    try {
      const response = await api.put(`/api/v1/staff/shifts/${id}`, shift);
      return response.data;
    } catch (error) {
      throw new Error(handleApiError(error));
    }
  }

  async deleteShift(id: string) {
    try {
      await api.delete(`/api/v1/staff/shifts/${id}`);
    } catch (error) {
      throw new Error(handleApiError(error));
    }
  }

  // Bulk operations
  async bulkCreateShifts(shifts: Shift[]) {
    try {
      const response = await api.post('/api/v1/staff/shifts/bulk', { shifts });
      return response.data;
    } catch (error) {
      throw new Error(handleApiError(error));
    }
  }

  async bulkUpdateShifts(updates: Array<{ id: string; changes: Partial<Shift> }>) {
    try {
      const response = await api.put('/api/v1/staff/shifts/bulk', { updates });
      return response.data;
    } catch (error) {
      throw new Error(handleApiError(error));
    }
  }

  // Availability
  async getAvailability(staffId?: number) {
    try {
      const url = staffId 
        ? `/api/v1/staff/availability?staff_id=${staffId}`
        : '/api/v1/staff/availability';
      const response = await api.get(url);
      return response.data;
    } catch (error) {
      throw new Error(handleApiError(error));
    }
  }

  async updateAvailability(staffId: number, availability: StaffAvailability[]) {
    try {
      const response = await api.put(`/api/v1/staff/${staffId}/availability`, { availability });
      return response.data;
    } catch (error) {
      throw new Error(handleApiError(error));
    }
  }

  // Templates
  async getTemplates() {
    try {
      const response = await api.get('/api/v1/staff/schedule-templates');
      return response.data;
    } catch (error) {
      throw new Error(handleApiError(error));
    }
  }

  async createTemplate(template: ScheduleTemplate) {
    try {
      const response = await api.post('/api/v1/staff/schedule-templates', template);
      return response.data;
    } catch (error) {
      throw new Error(handleApiError(error));
    }
  }

  async applyTemplate(templateId: string, startDate: string) {
    try {
      const response = await api.post(`/api/v1/staff/schedule-templates/${templateId}/apply`, {
        start_date: startDate
      });
      return response.data;
    } catch (error) {
      throw new Error(handleApiError(error));
    }
  }

  // Automated scheduling
  async generateSchedule(params: {
    start_date: string;
    end_date: string;
    constraints?: {
      min_staff_per_shift?: number;
      max_overtime_hours?: number;
      required_skills?: string[];
      honor_availability?: boolean;
    };
  }) {
    try {
      const response = await api.post('/api/v1/staff/schedule/generate', params);
      return response.data;
    } catch (error) {
      throw new Error(handleApiError(error));
    }
  }

  // Conflict detection
  async checkConflicts(params: {
    start_date: string;
    end_date: string;
    include_draft?: boolean;
  }) {
    try {
      const queryString = buildQueryString(params);
      const response = await api.get(`/api/v1/staff/schedule/conflicts?${queryString}`);
      return response.data;
    } catch (error) {
      throw new Error(handleApiError(error));
    }
  }

  async resolveConflict(data: {
    conflict_id: string;
    resolution_type: string;
    conflict_type: string;
  }) {
    try {
      const response = await api.post('/api/v1/staff/scheduling/conflicts/resolve', data);
      return response.data;
    } catch (error) {
      throw new Error(handleApiError(error));
    }
  }

  // Publishing
  async publishSchedule(params: {
    start_date: string;
    end_date: string;
    notify_staff?: boolean;
    message?: string;
  }) {
    try {
      const response = await api.post('/api/v1/staff/schedule/publish', params);
      return response.data;
    } catch (error) {
      throw new Error(handleApiError(error));
    }
  }

  // Payroll integration (read-only from frontend)
  async getPayrollSummary(params: {
    start_date: string;
    end_date: string;
    staff_ids?: number[];
  }) {
    try {
      const response = await api.post('/api/v1/payroll/summary', params);
      return response.data;
    } catch (error) {
      throw new Error(handleApiError(error));
    }
  }

  async exportPayrollReport(params: {
    start_date: string;
    end_date: string;
    format: 'pdf' | 'excel' | 'csv';
    staff_ids?: number[];
  }) {
    try {
      const response = await api.post('/api/v1/payroll/export', params, {
        responseType: 'blob'
      });
      return response.data;
    } catch (error) {
      throw new Error(handleApiError(error));
    }
  }

  // Time tracking
  async clockIn(staffId: number, timestamp?: string) {
    try {
      const response = await api.post(`/api/v1/staff/${staffId}/clock-in`, {
        timestamp: timestamp || new Date().toISOString()
      });
      return response.data;
    } catch (error) {
      throw new Error(handleApiError(error));
    }
  }

  async clockOut(staffId: number, timestamp?: string) {
    try {
      const response = await api.post(`/api/v1/staff/${staffId}/clock-out`, {
        timestamp: timestamp || new Date().toISOString()
      });
      return response.data;
    } catch (error) {
      throw new Error(handleApiError(error));
    }
  }

  // Swap requests
  async requestSwap(shiftId: string, requestedStaffId: number, reason?: string) {
    try {
      const response = await api.post(`/api/v1/staff/shifts/${shiftId}/swap-request`, {
        requested_staff_id: requestedStaffId,
        reason
      });
      return response.data;
    } catch (error) {
      throw new Error(handleApiError(error));
    }
  }

  async approveSwap(swapRequestId: string) {
    try {
      const response = await api.post(`/api/v1/staff/swap-requests/${swapRequestId}/approve`);
      return response.data;
    } catch (error) {
      throw new Error(handleApiError(error));
    }
  }

  async rejectSwap(swapRequestId: string, reason?: string) {
    try {
      const response = await api.post(`/api/v1/staff/swap-requests/${swapRequestId}/reject`, { reason });
      return response.data;
    } catch (error) {
      throw new Error(handleApiError(error));
    }
  }

}

export const schedulingService = new SchedulingService();