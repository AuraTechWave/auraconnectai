import { Platform, Dimensions } from 'react-native';

const { width: screenWidth, height: screenHeight } = Dimensions.get('window');

// ============================================
// SPACING SYSTEM - 8px base unit
// ============================================
export const spacing = {
  xxs: 4,
  xs: 8,
  sm: 12,
  md: 16,
  lg: 24,
  xl: 32,
  xxl: 48,
  xxxl: 64,
} as const;

// ============================================
// TYPOGRAPHY SYSTEM
// ============================================
export const typography = {
  fontFamily: {
    regular: Platform.select({
      ios: 'System',
      android: 'Roboto',
      default: 'System',
    }),
    medium: Platform.select({
      ios: 'System',
      android: 'Roboto-Medium',
      default: 'System',
    }),
    bold: Platform.select({
      ios: 'System',
      android: 'Roboto-Bold',
      default: 'System',
    }),
    light: Platform.select({
      ios: 'System',
      android: 'Roboto-Light',
      default: 'System',
    }),
  },
  fontSize: {
    tiny: 10,
    caption: 12,
    body: 14,
    bodyLarge: 16,
    subtitle: 18,
    title: 20,
    h3: 24,
    h2: 28,
    h1: 32,
    display: 40,
  },
  lineHeight: {
    tiny: 14,
    caption: 16,
    body: 20,
    bodyLarge: 24,
    subtitle: 26,
    title: 28,
    h3: 32,
    h2: 36,
    h1: 40,
    display: 48,
  },
  fontWeight: {
    light: '300' as const,
    regular: '400' as const,
    medium: '500' as const,
    semiBold: '600' as const,
    bold: '700' as const,
  },
} as const;

// ============================================
// COLOR SYSTEM - Modern palette inspired by AdminMart
// ============================================
export const colors = {
  // Primary Colors - Blue theme
  primary: {
    50: '#eff6ff',
    100: '#dbeafe',
    200: '#bfdbfe',
    300: '#93c5fd',
    400: '#60a5fa',
    500: '#3b82f6', // Main primary
    600: '#2563eb',
    700: '#1d4ed8',
    800: '#1e40af',
    900: '#1e3a8a',
  },
  // Secondary Colors - Purple/Indigo
  secondary: {
    50: '#f5f3ff',
    100: '#ede9fe',
    200: '#ddd6fe',
    300: '#c4b5fd',
    400: '#a78bfa',
    500: '#8b5cf6', // Main secondary
    600: '#7c3aed',
    700: '#6d28d9',
    800: '#5b21b6',
    900: '#4c1d95',
  },
  // Accent Colors - Amber/Orange
  accent: {
    50: '#fffbeb',
    100: '#fef3c7',
    200: '#fde68a',
    300: '#fcd34d',
    400: '#fbbf24',
    500: '#f59e0b', // Main accent
    600: '#d97706',
    700: '#b45309',
    800: '#92400e',
    900: '#78350f',
  },
  // Success - Green
  success: {
    50: '#f0fdf4',
    100: '#dcfce7',
    200: '#bbf7d0',
    300: '#86efac',
    400: '#4ade80',
    500: '#22c55e', // Main success
    600: '#16a34a',
    700: '#15803d',
    800: '#166534',
    900: '#14532d',
  },
  // Warning - Yellow
  warning: {
    50: '#fefce8',
    100: '#fef9c3',
    200: '#fef08a',
    300: '#fde047',
    400: '#facc15',
    500: '#eab308', // Main warning
    600: '#ca8a04',
    700: '#a16207',
    800: '#854d0e',
    900: '#713f12',
  },
  // Error - Red (adjusted for WCAG AA compliance)
  error: {
    50: '#fef2f2',
    100: '#fee2e2',
    200: '#fecaca',
    300: '#fca5a5',
    400: '#f87171',
    500: '#ef4444', // Main error for backgrounds
    600: '#dc2626', // Main error for text on light backgrounds (AA compliant)
    700: '#b91c1c',
    800: '#991b1b',
    900: '#7f1d1d',
  },
  // Neutral - Gray
  neutral: {
    50: '#fafafa',
    100: '#f4f4f5',
    200: '#e4e4e7',
    300: '#d4d4d8',
    400: '#a1a1aa',
    500: '#71717a',
    600: '#52525b',
    700: '#3f3f46',
    800: '#27272a',
    900: '#18181b',
  },
  // Background colors
  background: {
    primary: '#ffffff',
    secondary: '#f8fafc',
    tertiary: '#f1f5f9',
    elevated: '#ffffff',
    modal: 'rgba(0, 0, 0, 0.5)',
  },
  // Text colors
  text: {
    primary: '#1e293b',
    secondary: '#64748b',
    tertiary: '#94a3b8',
    disabled: '#cbd5e1',
    inverse: '#ffffff',
    link: '#3b82f6',
    error: '#dc2626', // AA compliant error text on white
    success: '#16a34a', // AA compliant success text on white
    warning: '#ca8a04', // AA compliant warning text on white
  },
  // Border colors
  border: {
    default: '#e2e8f0',
    light: '#f1f5f9',
    dark: '#cbd5e1',
    focus: '#3b82f6',
    error: '#ef4444',
  },
  // Special UI colors
  ui: {
    overlay: 'rgba(0, 0, 0, 0.4)',
    divider: '#e2e8f0',
    skeleton: '#f1f5f9',
    shimmer: '#f8fafc',
  },
} as const;

// Dark theme colors
export const darkColors = {
  ...colors,
  background: {
    primary: '#0f172a',
    secondary: '#1e293b',
    tertiary: '#334155',
    elevated: '#1e293b',
    modal: 'rgba(0, 0, 0, 0.8)',
  },
  text: {
    primary: '#f8fafc',
    secondary: '#cbd5e1',
    tertiary: '#94a3b8',
    disabled: '#64748b',
    inverse: '#1e293b',
    link: '#60a5fa',
  },
  border: {
    default: '#334155',
    light: '#1e293b',
    dark: '#475569',
    focus: '#60a5fa',
    error: '#f87171',
  },
  ui: {
    overlay: 'rgba(0, 0, 0, 0.7)',
    divider: '#334155',
    skeleton: '#334155',
    shimmer: '#475569',
  },
} as const;

// ============================================
// BORDER RADIUS
// ============================================
export const borderRadius = {
  none: 0,
  xs: 4,
  sm: 6,
  md: 8,
  lg: 12,
  xl: 16,
  xxl: 24,
  full: 9999,
} as const;

// ============================================
// SHADOWS - iOS and Android specific
// ============================================
export const shadows = {
  none: {
    shadowColor: 'transparent',
    shadowOffset: { width: 0, height: 0 },
    shadowOpacity: 0,
    shadowRadius: 0,
    elevation: 0,
  },
  xs: {
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 1 },
    shadowOpacity: 0.05,
    shadowRadius: 2,
    elevation: 1,
  },
  sm: {
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.08,
    shadowRadius: 4,
    elevation: 2,
  },
  md: {
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 4 },
    shadowOpacity: 0.10,
    shadowRadius: 6,
    elevation: 4,
  },
  lg: {
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 8 },
    shadowOpacity: 0.12,
    shadowRadius: 10,
    elevation: 8,
  },
  xl: {
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 12 },
    shadowOpacity: 0.15,
    shadowRadius: 16,
    elevation: 12,
  },
  xxl: {
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 20 },
    shadowOpacity: 0.20, // Capped at 0.20 for better readability
    shadowRadius: 24,
    elevation: 16,
  },
} as const;

// ============================================
// ANIMATIONS
// ============================================
export const animations = {
  duration: {
    instant: 0,
    fast: 200,
    normal: 300,
    slow: 500,
    verySlow: 1000,
  },
  easing: {
    linear: [0, 0, 1, 1],
    easeIn: [0.42, 0, 1, 1],
    easeOut: [0, 0, 0.58, 1],
    easeInOut: [0.42, 0, 0.58, 1],
    spring: [0.25, 0.46, 0.45, 0.94],
    bounce: [0.68, -0.55, 0.265, 1.55],
  },
} as const;

// ============================================
// TOUCH TARGETS & INTERACTION
// ============================================
export const touchTargets = {
  min: 44, // iOS HIG minimum
  small: 48,
  medium: 56,
  large: 64,
} as const;

// ============================================
// Z-INDEX LAYERS
// ============================================
export const zIndex = {
  base: 0,
  dropdown: 100,
  sticky: 200,
  fixed: 300,
  modalBackdrop: 400,
  modal: 500,
  popover: 600,
  tooltip: 700,
  toast: 800,
  loadingOverlay: 900,
} as const;

// ============================================
// BREAKPOINTS
// ============================================
export const breakpoints = {
  small: 360,
  medium: 414,
  large: 768,
  xlarge: 1024,
} as const;

// ============================================
// LAYOUT
// ============================================
export const layout = {
  screenWidth,
  screenHeight,
  isSmallDevice: screenWidth < breakpoints.medium,
  isTablet: screenWidth >= breakpoints.large,
  contentMaxWidth: 1200,
  headerHeight: Platform.select({
    ios: 44,
    android: 56,
    default: 56,
  }),
  tabBarHeight: Platform.select({
    ios: 49,
    android: 56,
    default: 56,
  }),
  statusBarHeight: Platform.select({
    ios: 44,
    android: 24,
    default: 24,
  }),
} as const;

// ============================================
// ICON SIZES
// ============================================
export const iconSizes = {
  tiny: 12,
  small: 16,
  medium: 20,
  large: 24,
  xlarge: 32,
  xxlarge: 48,
} as const;

// ============================================
// COMPONENT VARIANTS
// ============================================
export const variants = {
  button: {
    primary: 'primary',
    secondary: 'secondary',
    tertiary: 'tertiary',
    danger: 'danger',
    ghost: 'ghost',
    outline: 'outline',
  },
  size: {
    tiny: 'tiny',
    small: 'small',
    medium: 'medium',
    large: 'large',
    xlarge: 'xlarge',
  },
  status: {
    info: 'info',
    success: 'success',
    warning: 'warning',
    error: 'error',
    neutral: 'neutral',
  },
} as const;

// ============================================
// ACCESSIBILITY
// ============================================
export const accessibility = {
  minTouchTarget: 44,
  focusIndicatorWidth: 2,
  focusIndicatorColor: colors.primary[500],
  highContrastBorder: 3,
  reducedMotionDuration: 0,
} as const;

// ============================================
// HELPER FUNCTIONS
// ============================================
export const getColorWithOpacity = (color: string, opacity: number): string => {
  return `${color}${Math.round(opacity * 255).toString(16).padStart(2, '0')}`;
};

export const isSmallScreen = (): boolean => {
  return screenWidth < breakpoints.medium;
};

export const isTablet = (): boolean => {
  return screenWidth >= breakpoints.large;
};

export const getScaledSize = (size: number): number => {
  const scale = screenWidth / 375; // iPhone 11 Pro as base
  const newSize = size * scale;
  return Math.round(newSize);
};

// Export theme object for compatibility
export const designTokens = {
  colors,
  darkColors,
  spacing,
  typography,
  borderRadius,
  shadows,
  animations,
  touchTargets,
  zIndex,
  breakpoints,
  layout,
  iconSizes,
  variants,
  accessibility,
} as const;

export type DesignTokens = typeof designTokens;
export type Colors = typeof colors;
export type DarkColors = typeof darkColors;
export type Spacing = typeof spacing;
export type Typography = typeof typography;