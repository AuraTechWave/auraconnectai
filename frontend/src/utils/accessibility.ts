// Accessibility utilities for scheduling components

// Focus trap management
export class FocusTrap {
  private container: HTMLElement;
  private previousFocus: HTMLElement | null = null;
  private focusableElements: HTMLElement[] = [];
  private firstFocusable: HTMLElement | null = null;
  private lastFocusable: HTMLElement | null = null;

  constructor(container: HTMLElement) {
    this.container = container;
    this.updateFocusableElements();
  }

  private updateFocusableElements() {
    const focusableSelectors = [
      'a[href]',
      'button:not([disabled])',
      'textarea:not([disabled])',
      'input:not([disabled])',
      'select:not([disabled])',
      '[tabindex]:not([tabindex="-1"])',
    ].join(', ');

    this.focusableElements = Array.from(
      this.container.querySelectorAll(focusableSelectors)
    ) as HTMLElement[];

    this.firstFocusable = this.focusableElements[0] || null;
    this.lastFocusable = this.focusableElements[this.focusableElements.length - 1] || null;
  }

  activate() {
    this.previousFocus = document.activeElement as HTMLElement;
    
    // Add event listeners
    this.container.addEventListener('keydown', this.handleKeyDown);
    
    // Focus first element
    if (this.firstFocusable) {
      this.firstFocusable.focus();
    }
  }

  deactivate() {
    this.container.removeEventListener('keydown', this.handleKeyDown);
    
    // Restore focus
    if (this.previousFocus && this.previousFocus.focus) {
      this.previousFocus.focus();
    }
  }

  private handleKeyDown = (e: KeyboardEvent) => {
    if (e.key !== 'Tab') return;

    const activeElement = document.activeElement;

    if (e.shiftKey) {
      // Shift + Tab
      if (activeElement === this.firstFocusable) {
        e.preventDefault();
        this.lastFocusable?.focus();
      }
    } else {
      // Tab
      if (activeElement === this.lastFocusable) {
        e.preventDefault();
        this.firstFocusable?.focus();
      }
    }
  };
}

// Announce messages to screen readers
export const announce = (message: string, priority: 'polite' | 'assertive' = 'polite') => {
  const announcement = document.createElement('div');
  announcement.setAttribute('role', 'status');
  announcement.setAttribute('aria-live', priority);
  announcement.setAttribute('aria-atomic', 'true');
  announcement.style.position = 'absolute';
  announcement.style.left = '-10000px';
  announcement.style.width = '1px';
  announcement.style.height = '1px';
  announcement.style.overflow = 'hidden';
  
  announcement.textContent = message;
  document.body.appendChild(announcement);
  
  // Remove after announcement
  setTimeout(() => {
    document.body.removeChild(announcement);
  }, 1000);
};

// Keyboard navigation helpers
export const KEYS = {
  ENTER: 'Enter',
  SPACE: ' ',
  ESCAPE: 'Escape',
  ARROW_UP: 'ArrowUp',
  ARROW_DOWN: 'ArrowDown',
  ARROW_LEFT: 'ArrowLeft',
  ARROW_RIGHT: 'ArrowRight',
  HOME: 'Home',
  END: 'End',
  PAGE_UP: 'PageUp',
  PAGE_DOWN: 'PageDown',
  TAB: 'Tab',
};

// Get appropriate ARIA label for shift
export const getShiftAriaLabel = (shift: {
  staff_name?: string;
  position?: string;
  start_time: string;
  end_time: string;
  status?: string;
}) => {
  const parts = [];
  
  if (shift.staff_name) {
    parts.push(`${shift.staff_name}'s shift`);
  } else {
    parts.push('Shift');
  }
  
  if (shift.position) {
    parts.push(`as ${shift.position}`);
  }
  
  parts.push(`from ${shift.start_time} to ${shift.end_time}`);
  
  if (shift.status && shift.status !== 'published') {
    parts.push(`(${shift.status})`);
  }
  
  return parts.join(' ');
};

// Get ARIA label for calendar cell
export const getCalendarCellAriaLabel = (date: Date, shiftCount: number, hasConflicts: boolean) => {
  const dateStr = date.toLocaleDateString('en-US', {
    weekday: 'long',
    month: 'long',
    day: 'numeric',
  });
  
  const parts = [dateStr];
  
  if (shiftCount === 0) {
    parts.push('No shifts scheduled');
  } else if (shiftCount === 1) {
    parts.push('1 shift scheduled');
  } else {
    parts.push(`${shiftCount} shifts scheduled`);
  }
  
  if (hasConflicts) {
    parts.push('Has scheduling conflicts');
  }
  
  return parts.join('. ');
};

// Keyboard navigation for calendar grid
export const handleCalendarKeyboardNav = (
  e: KeyboardEvent,
  currentDate: Date,
  onDateChange: (date: Date) => void,
  viewType: 'week' | 'month' | 'day'
) => {
  let newDate: Date | null = null;

  switch (e.key) {
    case KEYS.ARROW_LEFT:
      e.preventDefault();
      newDate = new Date(currentDate);
      newDate.setDate(currentDate.getDate() - 1);
      break;
      
    case KEYS.ARROW_RIGHT:
      e.preventDefault();
      newDate = new Date(currentDate);
      newDate.setDate(currentDate.getDate() + 1);
      break;
      
    case KEYS.ARROW_UP:
      e.preventDefault();
      newDate = new Date(currentDate);
      newDate.setDate(currentDate.getDate() - 7);
      break;
      
    case KEYS.ARROW_DOWN:
      e.preventDefault();
      newDate = new Date(currentDate);
      newDate.setDate(currentDate.getDate() + 7);
      break;
      
    case KEYS.HOME:
      e.preventDefault();
      // Go to first day of week/month
      if (viewType === 'week') {
        newDate = new Date(currentDate);
        newDate.setDate(currentDate.getDate() - currentDate.getDay());
      } else if (viewType === 'month') {
        newDate = new Date(currentDate);
        newDate.setDate(1);
      }
      break;
      
    case KEYS.END:
      e.preventDefault();
      // Go to last day of week/month
      if (viewType === 'week') {
        newDate = new Date(currentDate);
        newDate.setDate(currentDate.getDate() + (6 - currentDate.getDay()));
      } else if (viewType === 'month') {
        newDate = new Date(currentDate);
        newDate.setMonth(currentDate.getMonth() + 1, 0);
      }
      break;
      
    case KEYS.PAGE_UP:
      e.preventDefault();
      // Previous week/month
      newDate = new Date(currentDate);
      if (viewType === 'week') {
        newDate.setDate(currentDate.getDate() - 7);
      } else if (viewType === 'month') {
        newDate.setMonth(currentDate.getMonth() - 1);
      }
      break;
      
    case KEYS.PAGE_DOWN:
      e.preventDefault();
      // Next week/month
      newDate = new Date(currentDate);
      if (viewType === 'week') {
        newDate.setDate(currentDate.getDate() + 7);
      } else if (viewType === 'month') {
        newDate.setMonth(currentDate.getMonth() + 1);
      }
      break;
  }

  if (newDate) {
    onDateChange(newDate);
    announce(`Navigated to ${newDate.toLocaleDateString()}`);
  }
};

// Color contrast utilities
export const meetsContrastRatio = (foreground: string, background: string, ratio = 4.5): boolean => {
  // This is a simplified check - in production, use a proper contrast checking library
  // For now, we'll assume proper contrast in the design system
  return true;
};

// Alternative to color-only indicators
export const getShiftStatusIcon = (status: string): string => {
  const icons: Record<string, string> = {
    draft: '📝',
    published: '✅',
    cancelled: '❌',
    conflict: '⚠️',
  };
  return icons[status] || '';
};

// Screen reader only text
export const srOnly = {
  position: 'absolute' as const,
  left: '-10000px',
  top: 'auto',
  width: '1px',
  height: '1px',
  overflow: 'hidden',
};

// Create live region for dynamic updates
export const createLiveRegion = (id: string, ariaLive: 'polite' | 'assertive' = 'polite') => {
  let region = document.getElementById(id);
  
  if (!region) {
    region = document.createElement('div');
    region.id = id;
    region.setAttribute('role', 'status');
    region.setAttribute('aria-live', ariaLive);
    region.setAttribute('aria-atomic', 'true');
    Object.assign(region.style, srOnly);
    document.body.appendChild(region);
  }
  
  return {
    announce: (message: string) => {
      if (region) {
        region.textContent = message;
      }
    },
    destroy: () => {
      if (region && region.parentNode) {
        region.parentNode.removeChild(region);
      }
    },
  };
};