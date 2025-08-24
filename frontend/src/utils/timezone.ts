import { format, toZonedTime, fromZonedTime } from 'date-fns-tz';
import { parseISO, isValid } from 'date-fns';

// Get restaurant timezone from config or environment
export const getRestaurantTimezone = (): string => {
  // This should come from restaurant settings API
  // For now, use environment variable or default
  return process.env.REACT_APP_RESTAURANT_TIMEZONE || 'America/New_York';
};

// Convert a date to restaurant timezone
export const toRestaurantTime = (date: Date | string): Date => {
  const dateObj = typeof date === 'string' ? parseISO(date) : date;
  if (!isValid(dateObj)) {
    throw new Error('Invalid date provided');
  }
  return toZonedTime(dateObj, getRestaurantTimezone());
};

// Convert from restaurant timezone to UTC
export const fromRestaurantTime = (date: Date | string): Date => {
  const dateObj = typeof date === 'string' ? parseISO(date) : date;
  if (!isValid(dateObj)) {
    throw new Error('Invalid date provided');
  }
  return fromZonedTime(dateObj, getRestaurantTimezone());
};

// Format date in restaurant timezone
export const formatInRestaurantTz = (
  date: Date | string,
  formatStr: string = 'yyyy-MM-dd HH:mm:ss zzz'
): string => {
  const dateObj = typeof date === 'string' ? parseISO(date) : date;
  if (!isValid(dateObj)) {
    return 'Invalid date';
  }
  return format(toZonedTime(dateObj, getRestaurantTimezone()), formatStr, {
    timeZone: getRestaurantTimezone(),
  });
};

// Create ISO string with timezone offset
export const toISOStringWithTz = (date: Date | string): string => {
  const dateObj = typeof date === 'string' ? parseISO(date) : date;
  if (!isValid(dateObj)) {
    throw new Error('Invalid date provided');
  }
  
  // Convert to restaurant timezone and format with offset
  const zonedDate = toZonedTime(dateObj, getRestaurantTimezone());
  return format(zonedDate, "yyyy-MM-dd'T'HH:mm:ssXXX", {
    timeZone: getRestaurantTimezone(),
  });
};

// Parse ISO string and convert to restaurant timezone
export const parseISOInRestaurantTz = (isoString: string): Date => {
  const date = parseISO(isoString);
  if (!isValid(date)) {
    throw new Error('Invalid ISO string provided');
  }
  return toRestaurantTime(date);
};

// Get start/end of day in restaurant timezone
export const getRestaurantDayBounds = (date: Date) => {
  const tz = getRestaurantTimezone();
  const zonedDate = toZonedTime(date, tz);
  
  // Start of day in restaurant timezone
  const startOfDay = new Date(zonedDate);
  startOfDay.setHours(0, 0, 0, 0);
  
  // End of day in restaurant timezone
  const endOfDay = new Date(zonedDate);
  endOfDay.setHours(23, 59, 59, 999);
  
  return {
    start: fromZonedTime(startOfDay, tz), // Convert back to UTC for API
    end: fromZonedTime(endOfDay, tz),     // Convert back to UTC for API
  };
};

// Handle shift times with timezone awareness
export const createShiftWithTz = (
  date: Date,
  startTime: string, // "HH:mm" format
  endTime: string    // "HH:mm" format
): { start: Date; end: Date } => {
  const tz = getRestaurantTimezone();
  
  // Parse times
  const [startHour, startMinute] = startTime.split(':').map(Number);
  const [endHour, endMinute] = endTime.split(':').map(Number);
  
  // Create dates in restaurant timezone
  const startDate = new Date(date);
  startDate.setHours(startHour, startMinute, 0, 0);
  const zonedStart = toZonedTime(startDate, tz);
  
  let endDate = new Date(date);
  endDate.setHours(endHour, endMinute, 0, 0);
  
  // Handle overnight shifts
  if (endHour < startHour || (endHour === startHour && endMinute < startMinute)) {
    endDate.setDate(endDate.getDate() + 1);
  }
  const zonedEnd = toZonedTime(endDate, tz);
  
  return {
    start: fromZonedTime(zonedStart, tz), // UTC for API
    end: fromZonedTime(zonedEnd, tz),     // UTC for API
  };
};

// Format shift times for display
export const formatShiftTime = (startDate: Date | string, endDate: Date | string): string => {
  const start = formatInRestaurantTz(startDate, 'h:mm a');
  const end = formatInRestaurantTz(endDate, 'h:mm a');
  const date = formatInRestaurantTz(startDate, 'MMM d');
  
  return `${date} ${start} - ${end}`;
};

// Check if date is in DST
export const isDST = (date: Date): boolean => {
  const tz = getRestaurantTimezone();
  const january = new Date(date.getFullYear(), 0, 1);
  const july = new Date(date.getFullYear(), 6, 1);
  
  const janOffset = format(toZonedTime(january, tz), 'XXX');
  const julyOffset = format(toZonedTime(july, tz), 'XXX');
  const currentOffset = format(toZonedTime(date, tz), 'XXX');
  
  // If current offset matches July offset and they differ, we're in DST
  return janOffset !== julyOffset && currentOffset === julyOffset;
};

// Timezone-aware date comparison
export const isInRestaurantDay = (date: Date, targetDay: Date): boolean => {
  const dateInTz = toRestaurantTime(date);
  const targetInTz = toRestaurantTime(targetDay);
  
  return (
    dateInTz.getFullYear() === targetInTz.getFullYear() &&
    dateInTz.getMonth() === targetInTz.getMonth() &&
    dateInTz.getDate() === targetInTz.getDate()
  );
};

// Get timezone abbreviation
export const getTimezoneAbbr = (): string => {
  const now = new Date();
  return format(toZonedTime(now, getRestaurantTimezone()), 'zzz');
};

// Preserve fractional hours when converting
export const preserveFractionalHours = (date: Date | string): Date => {
  const dateObj = typeof date === 'string' ? parseISO(date) : date;
  if (!isValid(dateObj)) {
    throw new Error('Invalid date provided');
  }
  
  // Keep milliseconds to preserve fractional seconds/minutes
  return new Date(dateObj.getTime());
};