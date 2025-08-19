/**
 * Client-side theme validator
 * Browser-compatible validation without Node.js dependencies
 */

// Whitelist of overridable properties for white-labeling
export const WHITELISTED_OVERRIDES = [
  'colors.semantic.primary',
  'colors.semantic.secondary', 
  'typography.fontFamily.primary',
  'borders.radius'
];

// Regex patterns for validation
const COLOR_REGEX = /^#([A-Fa-f0-9]{6}|[A-Fa-f0-9]{3})$/;
const RGB_REGEX = /^rgb\(\s*\d{1,3}\s*,\s*\d{1,3}\s*,\s*\d{1,3}\s*\)$/;
const RGBA_REGEX = /^rgba\(\s*\d{1,3}\s*,\s*\d{1,3}\s*,\s*\d{1,3}\s*,\s*(0|1|0?\.\d+)\s*\)$/;
const HSL_REGEX = /^hsl\(\s*\d{1,3}\s*,\s*\d{1,3}%\s*,\s*\d{1,3}%\s*\)$/;
const SAFE_FONT_REGEX = /^[a-zA-Z0-9\s,'".-]+$/;

/**
 * Validate a theme configuration
 * @param {Object} theme - Theme object to validate
 * @returns {Object} { valid: boolean, errors: Array }
 */
export function validateTheme(theme) {
  const errors = [];
  
  // Basic structure validation
  if (!theme || typeof theme !== 'object') {
    errors.push({ type: 'structure', message: 'Theme must be an object' });
    return { valid: false, errors };
  }
  
  if (!theme.name || typeof theme.name !== 'string') {
    errors.push({ type: 'structure', message: 'Theme must have a name property' });
  }
  
  // Validate overrides if present
  if (theme.overrides) {
    const overrideErrors = validateOverrides(theme.overrides);
    errors.push(...overrideErrors);
    
    // Validate colors
    if (theme.overrides.colors) {
      const colorErrors = validateColors(theme.overrides.colors);
      errors.push(...colorErrors);
    }
    
    // Validate fonts
    if (theme.overrides.typography?.fontFamily) {
      const fontErrors = validateFonts(theme.overrides.typography.fontFamily);
      errors.push(...fontErrors);
    }
  }
  
  return { valid: errors.length === 0, errors };
}

/**
 * Validate override paths against whitelist
 */
function validateOverrides(overrides, path = '') {
  const errors = [];
  
  for (const [key, value] of Object.entries(overrides)) {
    const currentPath = path ? `${path}.${key}` : key;
    
    if (typeof value === 'object' && value !== null && !Array.isArray(value)) {
      errors.push(...validateOverrides(value, currentPath));
    } else {
      const isWhitelisted = WHITELISTED_OVERRIDES.some(allowed => 
        currentPath.startsWith(allowed)
      );
      
      if (!isWhitelisted) {
        errors.push({
          type: 'override',
          path: currentPath,
          message: `Property "${currentPath}" is not allowed for override`
        });
      }
    }
  }
  
  return errors;
}

/**
 * Validate color values
 */
function validateColors(colors, path = 'colors') {
  const errors = [];
  
  const validateColorValue = (value, colorPath) => {
    if (typeof value === 'string') {
      const isValid = COLOR_REGEX.test(value) ||
                     RGB_REGEX.test(value) ||
                     RGBA_REGEX.test(value) ||
                     HSL_REGEX.test(value);
      
      if (!isValid) {
        errors.push({
          type: 'color',
          path: colorPath,
          value,
          message: `Invalid color format: "${value}"`
        });
      }
    }
  };
  
  const traverse = (obj, currentPath) => {
    for (const [key, value] of Object.entries(obj)) {
      const newPath = `${currentPath}.${key}`;
      if (typeof value === 'object' && value !== null && !Array.isArray(value)) {
        traverse(value, newPath);
      } else {
        validateColorValue(value, newPath);
      }
    }
  };
  
  traverse(colors, path);
  return errors;
}

/**
 * Validate font family values
 */
function validateFonts(fonts) {
  const errors = [];
  
  for (const [key, value] of Object.entries(fonts)) {
    if (typeof value === 'string') {
      const cleanedValue = value.replace(/['"]/g, '');
      
      if (!SAFE_FONT_REGEX.test(cleanedValue)) {
        errors.push({
          type: 'font',
          path: `typography.fontFamily.${key}`,
          value,
          message: `Font family contains unsafe characters: "${value}"`
        });
      }
      
      // Check for potential script injection
      if (value.toLowerCase().includes('javascript:') || 
          value.toLowerCase().includes('<script') ||
          value.includes('eval(') ||
          value.includes('expression(')) {
        errors.push({
          type: 'security',
          path: `typography.fontFamily.${key}`,
          value,
          message: `Font family contains potential security risk: "${value}"`
        });
      }
    }
  }
  
  return errors;
}

/**
 * Sanitize a theme object
 * @param {Object} theme - Theme to sanitize
 * @returns {Object} Sanitized theme
 */
export function sanitizeTheme(theme) {
  const sanitized = JSON.parse(JSON.stringify(theme));
  
  // Sanitize font families
  if (sanitized.overrides?.typography?.fontFamily) {
    for (const [key, value] of Object.entries(sanitized.overrides.typography.fontFamily)) {
      if (typeof value === 'string') {
        // Remove any potentially dangerous characters
        sanitized.overrides.typography.fontFamily[key] = value
          .replace(/[<>]/g, '')
          .replace(/javascript:/gi, '')
          .replace(/eval\(/g, '')
          .replace(/expression\(/g, '');
      }
    }
  }
  
  return sanitized;
}