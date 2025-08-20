import { AccessibilityRole, AccessibilityState, Platform } from 'react-native';

// Accessibility utilities for React Native

/**
 * Generate accessibility label from multiple parts
 */
export const createAccessibilityLabel = (...parts: (string | undefined)[]): string => {
  return parts.filter(Boolean).join(', ');
};

/**
 * Common accessibility roles mapping
 */
export const AccessibilityRoles = {
  BUTTON: 'button' as AccessibilityRole,
  LINK: 'link' as AccessibilityRole,
  IMAGE: 'image' as AccessibilityRole,
  TEXT: 'text' as AccessibilityRole,
  HEADER: 'header' as AccessibilityRole,
  SEARCH: 'search' as AccessibilityRole,
  TAB: 'tab' as AccessibilityRole,
  TABLIST: 'tablist' as AccessibilityRole,
  TIMER: 'timer' as AccessibilityRole,
  LIST: 'list' as AccessibilityRole,
  NONE: 'none' as AccessibilityRole,
  ALERT: 'alert' as AccessibilityRole,
  CHECKBOX: 'checkbox' as AccessibilityRole,
  RADIO: 'radio' as AccessibilityRole,
  SPINBUTTON: 'spinbutton' as AccessibilityRole,
  SWITCH: 'switch' as AccessibilityRole,
  ADJUSTABLE: 'adjustable' as AccessibilityRole,
};

/**
 * Create accessibility state object
 */
export const createAccessibilityState = (states: Partial<AccessibilityState>): AccessibilityState => {
  return {
    disabled: false,
    selected: false,
    checked: false,
    busy: false,
    expanded: false,
    ...states,
  };
};

/**
 * Generate accessibility hint based on action
 */
export const generateAccessibilityHint = (action: string, result?: string): string => {
  if (result) {
    return `${action} to ${result}`;
  }
  return action;
};

/**
 * Check if screen reader is enabled
 */
export const isScreenReaderEnabled = async (): Promise<boolean> => {
  try {
    const { AccessibilityInfo } = require('react-native');
    return await AccessibilityInfo.isScreenReaderEnabled();
  } catch {
    return false;
  }
};

/**
 * Announce message to screen reader
 */
export const announceForAccessibility = (message: string): void => {
  const { AccessibilityInfo } = require('react-native');
  AccessibilityInfo.announceForAccessibility(message);
};

/**
 * Focus accessibility on element (iOS only)
 */
export const setAccessibilityFocus = (reactTag: number): void => {
  if (Platform.OS === 'ios') {
    const { AccessibilityInfo } = require('react-native');
    AccessibilityInfo.setAccessibilityFocus(reactTag);
  }
};

/**
 * Common accessibility props for interactive elements
 */
export interface CommonAccessibilityProps {
  accessible?: boolean;
  accessibilityLabel?: string;
  accessibilityHint?: string;
  accessibilityRole?: AccessibilityRole;
  accessibilityState?: AccessibilityState;
  accessibilityValue?: {
    min?: number;
    max?: number;
    now?: number;
    text?: string;
  };
  accessibilityActions?: Array<{ name: string; label?: string }>;
  onAccessibilityAction?: (event: { actionName: string }) => void;
  importantForAccessibility?: 'auto' | 'yes' | 'no' | 'no-hide-descendants';
  accessibilityLiveRegion?: 'none' | 'polite' | 'assertive';
  accessibilityViewIsModal?: boolean;
  accessibilityElementsHidden?: boolean;
  accessibilityIgnoresInvertColors?: boolean;
}

/**
 * Get platform-specific accessibility props
 */
export const getPlatformAccessibilityProps = (
  props: CommonAccessibilityProps
): CommonAccessibilityProps => {
  if (Platform.OS === 'android') {
    // Android-specific adjustments
    return {
      ...props,
      // Android doesn't support accessibilityViewIsModal
      accessibilityViewIsModal: undefined,
    };
  }
  return props;
};

/**
 * Create accessible button props
 */
export const createAccessibleButtonProps = (
  label: string,
  hint?: string,
  state?: Partial<AccessibilityState>
): CommonAccessibilityProps => {
  return {
    accessible: true,
    accessibilityLabel: label,
    accessibilityHint: hint,
    accessibilityRole: AccessibilityRoles.BUTTON,
    accessibilityState: createAccessibilityState(state || {}),
  };
};

/**
 * Create accessible form input props
 */
export const createAccessibleInputProps = (
  label: string,
  value?: string,
  error?: string,
  required?: boolean
): CommonAccessibilityProps => {
  const accessibilityLabel = createAccessibilityLabel(
    label,
    required ? 'required' : undefined,
    error ? `Error: ${error}` : undefined,
    value ? `Current value: ${value}` : 'Empty'
  );

  return {
    accessible: true,
    accessibilityLabel,
    accessibilityValue: {
      text: value || '',
    },
    accessibilityState: createAccessibilityState({
      disabled: false,
    }),
  };
};

/**
 * WCAG color contrast ratios
 */
export const ContrastRatios = {
  NORMAL_TEXT: 4.5, // Normal text (< 18pt or < 14pt bold)
  LARGE_TEXT: 3, // Large text (>= 18pt or >= 14pt bold)
  NON_TEXT: 3, // UI components and graphical objects
  AAA_NORMAL: 7, // Enhanced contrast for normal text
  AAA_LARGE: 4.5, // Enhanced contrast for large text
};

/**
 * Check if color combination meets WCAG contrast requirements
 * Note: This is a placeholder - actual implementation would need color parsing
 */
export const meetsContrastRatio = (
  foreground: string,
  background: string,
  ratio: number = ContrastRatios.NORMAL_TEXT
): boolean => {
  // This would need actual color contrast calculation
  console.warn('Color contrast checking not implemented');
  return true;
};

/**
 * Accessibility test helpers
 */
export const a11yTestHelpers = {
  /**
   * Check if component has minimum required accessibility props
   */
  hasMinimumAccessibility: (props: any): boolean => {
    return !!(props.accessible || props.accessibilityLabel);
  },

  /**
   * Check if touchable has minimum size (44x44)
   */
  hasMinimumTouchTarget: (style: any): boolean => {
    if (!style) return false;
    const flatStyle = Array.isArray(style) ? Object.assign({}, ...style) : style;
    return (
      (flatStyle.minHeight >= 44 || flatStyle.height >= 44) &&
      (flatStyle.minWidth >= 44 || flatStyle.width >= 44)
    );
  },
};

/**
 * Common accessibility announcements
 */
export const AccessibilityAnnouncements = {
  LOADING_START: 'Loading content',
  LOADING_COMPLETE: 'Content loaded',
  ERROR: (error: string) => `Error: ${error}`,
  SUCCESS: (action: string) => `${action} successful`,
  ITEM_SELECTED: (item: string) => `${item} selected`,
  ITEM_DELETED: (item: string) => `${item} deleted`,
  PAGE_CHANGED: (page: string) => `Now on ${page}`,
  FORM_SUBMITTED: 'Form submitted successfully',
  NETWORK_OFFLINE: 'Network connection lost',
  NETWORK_ONLINE: 'Network connection restored',
};