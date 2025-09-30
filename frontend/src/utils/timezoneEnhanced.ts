import { 
  fromZonedTime as zonedTimeToUtc, 
  toZonedTime as utcToZonedTime, 
  formatInTimeZone,
  getTimezoneOffset 
} from 'date-fns-tz';
import { format, parseISO, isValid } from 'date-fns';
import { tenantService } from '../services/tenantService';

interface DSTTransition {
  date: Date;
  isDST: boolean;
  offset: number;
}

class TimezoneService {
  private defaultTimezone = 'America/New_York';
  private cachedTimezone: string | null = null;

  /**
   * Get the current tenant's timezone
   */
  getTimezone(): string {
    if (this.cachedTimezone) {
      return this.cachedTimezone;
    }

    const tenant = tenantService.getCurrentTenant();
    if (tenant?.timezone) {
      this.cachedTimezone = tenant.timezone;
      return tenant.timezone;
    }

    // Fallback to browser timezone
    try {
      return Intl.DateTimeFormat().resolvedOptions().timeZone || this.defaultTimezone;
    } catch {
      return this.defaultTimezone;
    }
  }

  /**
   * Convert local time to UTC
   */
  toUTC(date: Date | string, timezone?: string): Date {
    const tz = timezone || this.getTimezone();
    const dateObj = typeof date === 'string' ? parseISO(date) : date;
    
    if (!isValid(dateObj)) {
      throw new Error('Invalid date provided');
    }

    return zonedTimeToUtc(dateObj, tz);
  }

  /**
   * Convert UTC to local timezone
   */
  fromUTC(date: Date | string, timezone?: string): Date {
    const tz = timezone || this.getTimezone();
    const dateObj = typeof date === 'string' ? parseISO(date) : date;
    
    if (!isValid(dateObj)) {
      throw new Error('Invalid date provided');
    }

    return utcToZonedTime(dateObj, tz);
  }

  /**
   * Format date in specific timezone
   */
  formatInTimezone(
    date: Date | string, 
    formatStr: string, 
    timezone?: string
  ): string {
    const tz = timezone || this.getTimezone();
    const dateObj = typeof date === 'string' ? parseISO(date) : date;
    
    if (!isValid(dateObj)) {
      throw new Error('Invalid date provided');
    }

    return formatInTimeZone(dateObj, tz, formatStr);
  }

  /**
   * Check if a date falls within DST
   */
  isDST(date: Date, timezone?: string): boolean {
    const tz = timezone || this.getTimezone();
    const offset = getTimezoneOffset(tz, date);
    
    // Check offset one month before and after
    const monthBefore = new Date(date);
    monthBefore.setMonth(date.getMonth() - 1);
    const monthAfter = new Date(date);
    monthAfter.setMonth(date.getMonth() + 1);
    
    const offsetBefore = getTimezoneOffset(tz, monthBefore);
    const offsetAfter = getTimezoneOffset(tz, monthAfter);
    
    // If current offset is less than either neighboring month, we're in DST
    return offset < Math.max(offsetBefore, offsetAfter);
  }

  /**
   * Get DST transitions for a year
   */
  getDSTTransitions(year: number, timezone?: string): DSTTransition[] {
    const tz = timezone || this.getTimezone();
    const transitions: DSTTransition[] = [];
    
    // Check each day of the year for offset changes
    let previousOffset: number | null = null;
    
    for (let month = 0; month < 12; month++) {
      const daysInMonth = new Date(year, month + 1, 0).getDate();
      
      for (let day = 1; day <= daysInMonth; day++) {
        const date = new Date(year, month, day, 12, 0, 0); // Check at noon to avoid edge cases
        const offset = getTimezoneOffset(tz, date);
        
        if (previousOffset !== null && offset !== previousOffset) {
          transitions.push({
            date,
            isDST: offset < previousOffset,
            offset
          });
        }
        
        previousOffset = offset;
      }
    }
    
    return transitions;
  }

  /**
   * Validate if a shift crosses DST boundary
   */
  crossesDST(startDate: Date, endDate: Date, timezone?: string): boolean {
    const tz = timezone || this.getTimezone();
    const startOffset = getTimezoneOffset(tz, startDate);
    const endOffset = getTimezoneOffset(tz, endDate);
    
    return startOffset !== endOffset;
  }

  /**
   * Adjust for DST when calculating duration
   */
  getDurationWithDST(startDate: Date, endDate: Date, timezone?: string): number {
    const tz = timezone || this.getTimezone();
    
    // Convert both to UTC for accurate duration calculation
    const startUTC = this.toUTC(startDate, tz);
    const endUTC = this.toUTC(endDate, tz);
    
    return endUTC.getTime() - startUTC.getTime();
  }

  /**
   * Get timezone abbreviation (e.g., EST, PST)
   */
  getTimezoneAbbr(date?: Date, timezone?: string): string {
    const tz = timezone || this.getTimezone();
    const dateToUse = date || new Date();
    
    try {
      const formatted = dateToUse.toLocaleString('en-US', {
        timeZone: tz,
        timeZoneName: 'short'
      });
      
      const match = formatted.match(/[A-Z]{3,4}$/);
      return match ? match[0] : tz;
    } catch {
      return tz;
    }
  }

  /**
   * Validate timezone string
   */
  isValidTimezone(timezone: string): boolean {
    try {
      new Date().toLocaleString('en-US', { timeZone: timezone });
      return true;
    } catch {
      return false;
    }
  }

  /**
   * Get list of common timezones
   */
  getCommonTimezones(): { value: string; label: string }[] {
    return [
      { value: 'America/New_York', label: 'Eastern Time (ET)' },
      { value: 'America/Chicago', label: 'Central Time (CT)' },
      { value: 'America/Denver', label: 'Mountain Time (MT)' },
      { value: 'America/Los_Angeles', label: 'Pacific Time (PT)' },
      { value: 'America/Phoenix', label: 'Arizona Time' },
      { value: 'America/Anchorage', label: 'Alaska Time' },
      { value: 'Pacific/Honolulu', label: 'Hawaii Time' },
      { value: 'Europe/London', label: 'London' },
      { value: 'Europe/Paris', label: 'Paris' },
      { value: 'Europe/Berlin', label: 'Berlin' },
      { value: 'Asia/Tokyo', label: 'Tokyo' },
      { value: 'Asia/Shanghai', label: 'Shanghai' },
      { value: 'Australia/Sydney', label: 'Sydney' },
      { value: 'UTC', label: 'UTC' },
    ];
  }

  /**
   * Clear cached timezone (call when tenant changes)
   */
  clearCache(): void {
    this.cachedTimezone = null;
  }
}

// Export singleton instance
export const timezoneService = new TimezoneService();

// Export convenience functions
export const toUTC = (date: Date | string, timezone?: string) => 
  timezoneService.toUTC(date, timezone);

export const fromUTC = (date: Date | string, timezone?: string) => 
  timezoneService.fromUTC(date, timezone);

export const formatInTimezone = (
  date: Date | string, 
  formatStr: string, 
  timezone?: string
) => timezoneService.formatInTimezone(date, formatStr, timezone);

export const isDST = (date: Date, timezone?: string) => 
  timezoneService.isDST(date, timezone);

export const crossesDST = (startDate: Date, endDate: Date, timezone?: string) => 
  timezoneService.crossesDST(startDate, endDate, timezone);

export default timezoneService;