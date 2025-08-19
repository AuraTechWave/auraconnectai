const Ajv = require('ajv');

// Whitelist of overridable properties for white-labeling
const WHITELISTED_OVERRIDES = [
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

// Theme schema
const themeSchema = {
  type: 'object',
  required: ['name'],
  properties: {
    name: {
      type: 'string',
      pattern: '^[a-zA-Z0-9\\s-]+$',
      maxLength: 50
    },
    description: {
      type: 'string',
      maxLength: 200
    },
    extends: {
      type: 'string',
      enum: ['base', 'light', 'dark']
    },
    overrides: {
      type: 'object'
    }
  },
  additionalProperties: false
};

class ThemeValidator {
  constructor() {
    this.ajv = new Ajv({ allErrors: true });
    this.validateSchema = this.ajv.compile(themeSchema);
  }

  /**
   * Validate a theme configuration
   * @param {Object} theme - Theme object to validate
   * @returns {Object} { valid: boolean, errors: Array }
   */
  validate(theme) {
    const errors = [];
    
    // 1. Schema validation
    if (!this.validateSchema(theme)) {
      errors.push(...this.validateSchema.errors.map(e => ({
        type: 'schema',
        message: `${e.dataPath} ${e.message}`
      })));
    }
    
    // 2. Validate overrides are whitelisted
    if (theme.overrides) {
      const overrideErrors = this.validateOverrides(theme.overrides);
      errors.push(...overrideErrors);
    }
    
    // 3. Validate color formats
    if (theme.overrides?.colors) {
      const colorErrors = this.validateColors(theme.overrides.colors);
      errors.push(...colorErrors);
    }
    
    // 4. Validate font families
    if (theme.overrides?.typography?.fontFamily) {
      const fontErrors = this.validateFonts(theme.overrides.typography.fontFamily);
      errors.push(...fontErrors);
    }
    
    return {
      valid: errors.length === 0,
      errors
    };
  }

  /**
   * Validate override paths are whitelisted
   */
  validateOverrides(overrides, path = '') {
    const errors = [];
    
    for (const [key, value] of Object.entries(overrides)) {
      const currentPath = path ? `${path}.${key}` : key;
      
      if (typeof value === 'object' && value !== null) {
        // Recurse into nested objects
        errors.push(...this.validateOverrides(value, currentPath));
      } else {
        // Check if this path is whitelisted
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
  validateColors(colors, path = 'colors') {
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
        if (typeof value === 'object' && value !== null) {
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
  validateFonts(fonts) {
    const errors = [];
    
    for (const [key, value] of Object.entries(fonts)) {
      if (typeof value === 'string') {
        // Remove quotes and check for safe characters
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
   */
  sanitize(theme) {
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
}

// Export for use in other scripts
module.exports = ThemeValidator;

// CLI usage
if (require.main === module) {
  const validator = new ThemeValidator();
  
  // Example validation
  const testTheme = {
    name: 'Test Theme',
    extends: 'light',
    overrides: {
      colors: {
        semantic: {
          primary: {
            base: '#0066CC'
          }
        }
      }
    }
  };
  
  const result = validator.validate(testTheme);
  
  if (result.valid) {
    console.log('✅ Theme is valid');
  } else {
    console.error('❌ Theme validation failed:');
    result.errors.forEach(error => {
      console.error(`  - ${error.type}: ${error.message}`);
    });
  }
}