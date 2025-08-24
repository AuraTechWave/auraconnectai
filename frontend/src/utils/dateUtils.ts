import { format, parseISO, isValid } from 'date-fns';

// Format date string to ISO format for API
export const toISOString = (date: Date | string | undefined): string | undefined => {
  if (!date) return undefined;
  
  const dateObj = typeof date === 'string' ? parseISO(date) : date;
  return isValid(dateObj) ? dateObj.toISOString() : undefined;
};

// Format date for display
export const formatDate = (date: Date | string, formatStr: string = 'yyyy-MM-dd'): string => {
  const dateObj = typeof date === 'string' ? parseISO(date) : date;
  return isValid(dateObj) ? format(dateObj, formatStr) : '';
};

// Get start and end of day for date range filters
export const getDateRange = (startDate: Date, endDate: Date) => {
  const start = new Date(startDate);
  start.setHours(0, 0, 0, 0);
  
  const end = new Date(endDate);
  end.setHours(23, 59, 59, 999);
  
  return {
    start: start.toISOString(),
    end: end.toISOString(),
  };
};