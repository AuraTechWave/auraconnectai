const fs = require('fs');
const path = require('path');

// Ensure dist directory exists
const distDir = path.join(__dirname, '../dist');
if (!fs.existsSync(distDir)) {
  fs.mkdirSync(distDir, { recursive: true });
}

// Load all tokens
const tokens = {};
const tokenFiles = ['colors', 'typography', 'spacing', 'shadows', 'borders', 'animations'];

tokenFiles.forEach(file => {
  const content = JSON.parse(fs.readFileSync(path.join(__dirname, `../tokens/${file}.json`), 'utf8'));
  Object.assign(tokens, content);
});

// Create main index export
const indexContent = `
// Auto-generated file - do not edit directly
export * from './tokens.js';
export * as themes from './themes/index.js';

// Re-export for convenience
export { default as lightTheme } from './themes/light.js';
export { default as darkTheme } from './themes/dark.js';
`;

fs.writeFileSync(path.join(distDir, 'index.js'), indexContent);
fs.writeFileSync(path.join(distDir, 'index.mjs'), indexContent);

// Create TypeScript definitions
const typeDefinitions = `
// Auto-generated file - do not edit directly
export interface DesignTokens {
  colors: {
    primitive: Record<string, Record<string, string>>;
    semantic: Record<string, Record<string, string>>;
  };
  typography: {
    fontFamily: Record<string, string>;
    fontSize: Record<string, string>;
    fontWeight: Record<string, number>;
    lineHeight: Record<string, number>;
    letterSpacing: Record<string, string>;
    variants: Record<string, any>;
  };
  spacing: {
    base: number;
    scale: Record<string, string>;
    component: Record<string, Record<string, string>>;
    layout: Record<string, Record<string, string>>;
  };
  shadows: {
    elevation: Record<string, string>;
    focus: Record<string, string>;
    inset: Record<string, string>;
  };
  borders: {
    radius: Record<string, string>;
    width: Record<string, string>;
    style: Record<string, string>;
    color: Record<string, string>;
  };
  animations: {
    duration: Record<string, string>;
    easing: Record<string, string>;
    transition: Record<string, string>;
  };
}

export interface Theme {
  name: string;
  description: string;
  tokens: DesignTokens;
}

export declare const tokens: DesignTokens;
export declare const lightTheme: Theme;
export declare const darkTheme: Theme;
`;

fs.writeFileSync(path.join(distDir, 'index.d.ts'), typeDefinitions);

// Create client-side theme validator
const clientValidatorContent = `
// Client-side theme validation (no Node.js dependencies)

// Whitelist of overridable properties for white-labeling
const WHITELISTED_OVERRIDES = [
  'colors.semantic.primary',
  'colors.semantic.secondary',
  'typography.fontFamily.primary',
  'borders.radius'
];

// Regex patterns for validation
const COLOR_REGEX = /^#([A-Fa-f0-9]{6}|[A-Fa-f0-9]{3})$/;
const RGB_REGEX = /^rgb\\(\\s*\\d{1,3}\\s*,\\s*\\d{1,3}\\s*,\\s*\\d{1,3}\\s*\\)$/;
const RGBA_REGEX = /^rgba\\(\\s*\\d{1,3}\\s*,\\s*\\d{1,3}\\s*,\\s*\\d{1,3}\\s*,\\s*(0|1|0?\\.\\d+)\\s*\\)$/;
const HSL_REGEX = /^hsl\\(\\s*\\d{1,3}\\s*,\\s*\\d{1,3}%\\s*,\\s*\\d{1,3}%\\s*\\)$/;
const SAFE_FONT_REGEX = /^[a-zA-Z0-9\\s,'".-]+$/;

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

function validateOverrides(overrides, path = '') {
  const errors = [];
  
  for (const [key, value] of Object.entries(overrides)) {
    const currentPath = path ? \`\${path}.\${key}\` : key;
    
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
          message: \`Property "\${currentPath}" is not allowed for override\`
        });
      }
    }
  }
  
  return errors;
}

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
          message: \`Invalid color format: "\${value}"\`
        });
      }
    }
  };
  
  const traverse = (obj, currentPath) => {
    for (const [key, value] of Object.entries(obj)) {
      const newPath = \`\${currentPath}.\${key}\`;
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

function validateFonts(fonts) {
  const errors = [];
  
  for (const [key, value] of Object.entries(fonts)) {
    if (typeof value === 'string') {
      const cleanedValue = value.replace(/['"]/g, '');
      
      if (!SAFE_FONT_REGEX.test(cleanedValue)) {
        errors.push({
          type: 'font',
          path: \`typography.fontFamily.\${key}\`,
          value,
          message: \`Font family contains unsafe characters: "\${value}"\`
        });
      }
      
      if (value.toLowerCase().includes('javascript:') || 
          value.toLowerCase().includes('<script') ||
          value.includes('eval(') ||
          value.includes('expression(')) {
        errors.push({
          type: 'security',
          path: \`typography.fontFamily.\${key}\`,
          value,
          message: \`Font family contains potential security risk: "\${value}"\`
        });
      }
    }
  }
  
  return errors;
}

export function sanitizeTheme(theme) {
  const sanitized = JSON.parse(JSON.stringify(theme));
  
  if (sanitized.overrides?.typography?.fontFamily) {
    for (const [key, value] of Object.entries(sanitized.overrides.typography.fontFamily)) {
      if (typeof value === 'string') {
        sanitized.overrides.typography.fontFamily[key] = value
          .replace(/[<>]/g, '')
          .replace(/javascript:/gi, '')
          .replace(/eval\\(/g, '')
          .replace(/expression\\(/g, '');
      }
    }
  }
  
  return sanitized;
}
`;

// Create token resolver for runtime use
const resolverContent = `
// Token resolver for runtime theme application
${clientValidatorContent}

export function resolveTokens(tokens, references) {
  const resolved = JSON.parse(JSON.stringify(tokens));
  
  function resolveValue(value, root) {
    if (typeof value !== 'string' || !value.startsWith('$')) {
      return value;
    }
    
    const path = value.replace('$', '').split('.');
    let current = root;
    
    for (const segment of path) {
      current = current?.[segment];
      if (current === undefined) {
        console.warn(\`Token reference not found: \${value}\`);
        return value;
      }
    }
    
    return current;
  }
  
  function resolveObject(obj, root) {
    for (const key in obj) {
      if (typeof obj[key] === 'object' && obj[key] !== null) {
        resolveObject(obj[key], root);
      } else {
        obj[key] = resolveValue(obj[key], root);
      }
    }
  }
  
  resolveObject(resolved, tokens);
  return resolved;
}

export function applyTheme(theme, target = document.documentElement) {
  // Validate theme first
  const validation = validateTheme(theme);
  
  if (!validation.valid) {
    console.error('Theme validation failed:', validation.errors);
    return false;
  }
  
  // Sanitize theme
  const sanitizedTheme = sanitizeTheme(theme);
  const resolved = resolveTokens(sanitizedTheme.tokens || sanitizedTheme, sanitizedTheme);
  
  // Apply CSS variables
  function setCSSVariables(obj, prefix = '') {
    for (const key in obj) {
      const value = obj[key];
      const varName = prefix ? \`\${prefix}-\${key}\` : key;
      
      if (typeof value === 'object' && value !== null) {
        setCSSVariables(value, varName);
      } else {
        target.style.setProperty(\`--\${varName}\`, value);
      }
    }
  }
  
  setCSSVariables(resolved);
  
  // Set theme attribute
  if (sanitizedTheme.name) {
    target.setAttribute('data-theme', sanitizedTheme.name);
  }
  
  return true;
}
`;

fs.writeFileSync(path.join(distDir, 'resolver.js'), resolverContent);

console.log('✅ Export files created successfully');