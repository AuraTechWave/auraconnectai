import {
  MD3LightTheme as DefaultTheme,
  MD3Theme,
  configureFonts,
} from 'react-native-paper';

const fontConfig = {
  web: {
    regular: {
      fontFamily: 'sans-serif',
      fontWeight: '400' as const,
    },
    medium: {
      fontFamily: 'sans-serif-medium',
      fontWeight: '500' as const,
    },
    light: {
      fontFamily: 'sans-serif-light',
      fontWeight: '300' as const,
    },
    thin: {
      fontFamily: 'sans-serif-thin',
      fontWeight: '100' as const,
    },
  },
  ios: {
    regular: {
      fontFamily: 'System',
      fontWeight: '400' as const,
    },
    medium: {
      fontFamily: 'System',
      fontWeight: '500' as const,
    },
    light: {
      fontFamily: 'System',
      fontWeight: '300' as const,
    },
    thin: {
      fontFamily: 'System',
      fontWeight: '100' as const,
    },
  },
  android: {
    regular: {
      fontFamily: 'sans-serif',
      fontWeight: '400' as const,
    },
    medium: {
      fontFamily: 'sans-serif-medium',
      fontWeight: '500' as const,
    },
    light: {
      fontFamily: 'sans-serif-light',
      fontWeight: '300' as const,
    },
    thin: {
      fontFamily: 'sans-serif-thin',
      fontWeight: '100' as const,
    },
  },
};

export const theme: MD3Theme = {
  ...DefaultTheme,
  colors: {
    ...DefaultTheme.colors,
    primary: '#2563eb',
    primaryContainer: '#dbeafe',
    secondary: '#7c3aed',
    secondaryContainer: '#ede9fe',
    tertiary: '#f59e0b',
    tertiaryContainer: '#fef3c7',
    error: '#dc2626',
    errorContainer: '#fee2e2',
    background: '#f8fafc',
    surface: '#ffffff',
    surfaceVariant: '#f1f5f9',
    onPrimary: '#ffffff',
    onPrimaryContainer: '#1e40af',
    onSecondary: '#ffffff',
    onSecondaryContainer: '#5b21b6',
    onTertiary: '#ffffff',
    onTertiaryContainer: '#d97706',
    onError: '#ffffff',
    onErrorContainer: '#991b1b',
    onBackground: '#0f172a',
    onSurface: '#0f172a',
    onSurfaceVariant: '#475569',
    outline: '#cbd5e1',
    outlineVariant: '#e2e8f0',
    inverseSurface: '#1e293b',
    inverseOnSurface: '#f8fafc',
    inversePrimary: '#60a5fa',
    shadow: '#000000',
    scrim: '#000000',
    elevation: {
      ...DefaultTheme.colors.elevation,
      level0: 'transparent',
      level1: '#f8fafc',
      level2: '#f1f5f9',
      level3: '#e2e8f0',
      level4: '#cbd5e1',
      level5: '#94a3b8',
    },
  },
  fonts: configureFonts({ config: fontConfig }),
  roundness: 8,
};

// Dark theme
export const darkTheme: MD3Theme = {
  ...theme,
  dark: true,
  colors: {
    ...theme.colors,
    primary: '#60a5fa',
    primaryContainer: '#1e40af',
    secondary: '#a78bfa',
    secondaryContainer: '#5b21b6',
    tertiary: '#fbbf24',
    tertiaryContainer: '#d97706',
    error: '#f87171',
    errorContainer: '#991b1b',
    background: '#0f172a',
    surface: '#1e293b',
    surfaceVariant: '#334155',
    onPrimary: '#1e293b',
    onPrimaryContainer: '#dbeafe',
    onSecondary: '#1e293b',
    onSecondaryContainer: '#ede9fe',
    onTertiary: '#1e293b',
    onTertiaryContainer: '#fef3c7',
    onError: '#1e293b',
    onErrorContainer: '#fee2e2',
    onBackground: '#f8fafc',
    onSurface: '#f8fafc',
    onSurfaceVariant: '#cbd5e1',
    outline: '#475569',
    outlineVariant: '#334155',
    inverseSurface: '#f8fafc',
    inverseOnSurface: '#0f172a',
    inversePrimary: '#2563eb',
    elevation: {
      ...theme.colors.elevation,
      level0: 'transparent',
      level1: '#1e293b',
      level2: '#334155',
      level3: '#475569',
      level4: '#64748b',
      level5: '#94a3b8',
    },
  },
};