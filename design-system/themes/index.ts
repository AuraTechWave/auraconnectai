/**
 * Theme exports for AuraConnect Design System
 * This file provides TypeScript/JavaScript exports for the JSON theme files
 */

import baseTheme from './base.json';
import lightTheme from './light.json';
import darkTheme from './dark.json';
import blueBrandTheme from './blue-brand.json';

// Merge themes with their base configurations
function mergeTheme(theme: any): any {
  if (theme.extends === 'base') {
    return {
      ...baseTheme,
      ...theme,
      tokens: {
        ...baseTheme.tokens,
        ...theme.overrides
      }
    };
  }
  return theme;
}

// Export individual themes
export const themes = {
  base: baseTheme,
  light: mergeTheme(lightTheme),
  dark: mergeTheme(darkTheme),
  blueBrand: mergeTheme(blueBrandTheme)
};

// Export default theme
export const defaultTheme = themes.light;

// Export theme types
export interface ThemeColors {
  brand: {
    primary: Record<string, string>;
    secondary: Record<string, string>;
  };
  semantic: {
    background: Record<string, string>;
    surface: Record<string, string>;
    text: Record<string, string>;
    border: Record<string, string>;
    primary: Record<string, string>;
    secondary: Record<string, string>;
    success: Record<string, string>;
    warning: Record<string, string>;
    error: Record<string, string>;
    info: Record<string, string>;
  };
  neutral: Record<string, string>;
}

export interface Theme {
  name: string;
  description: string;
  tokens: {
    colors: ThemeColors;
    typography: Record<string, any>;
    spacing: Record<string, string>;
    borderRadius: Record<string, string>;
    boxShadow: Record<string, string>;
    animation: Record<string, any>;
  };
}

// Helper function to get theme by name
export function getTheme(themeName: 'base' | 'light' | 'dark' | 'blueBrand'): Theme {
  return themes[themeName];
}

// Helper function to get CSS variables from theme
export function getThemeCSSVariables(theme: Theme): Record<string, string> {
  const cssVars: Record<string, string> = {};
  
  // Flatten the theme object into CSS variables
  function flatten(obj: any, prefix = ''): void {
    Object.keys(obj).forEach(key => {
      const value = obj[key];
      const varName = prefix ? `${prefix}-${key}` : key;
      
      if (typeof value === 'object' && value !== null) {
        flatten(value, varName);
      } else {
        cssVars[`--${varName}`] = value;
      }
    });
  }
  
  flatten(theme.tokens);
  return cssVars;
}

export default themes;