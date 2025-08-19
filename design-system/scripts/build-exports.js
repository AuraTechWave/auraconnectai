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

// Create token resolver for runtime use
const resolverContent = `
// Token resolver for runtime theme application
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

export function validateTheme(theme) {
  const ThemeValidator = require('../scripts/theme-validator');
  const validator = new ThemeValidator();
  return validator.validate(theme).valid;
}

export function applyTheme(theme, target = document.documentElement) {
  // Validate theme first
  const ThemeValidator = require('../scripts/theme-validator');
  const validator = new ThemeValidator();
  const validation = validator.validate(theme);
  
  if (!validation.valid) {
    console.error('Theme validation failed:', validation.errors);
    return false;
  }
  
  // Sanitize theme
  const sanitizedTheme = validator.sanitize(theme);
  const resolved = resolveTokens(sanitizedTheme.tokens || sanitizedTheme);
  
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