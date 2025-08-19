const fs = require('fs');
const path = require('path');

// Load all token files
const loadTokens = () => {
  const tokens = {};
  const tokenFiles = ['colors', 'typography', 'spacing', 'shadows', 'borders', 'animations'];
  
  tokenFiles.forEach(file => {
    const content = JSON.parse(fs.readFileSync(path.join(__dirname, `../tokens/${file}.json`), 'utf8'));
    tokens[file] = content[file];
  });
  
  return tokens;
};

// Generate CSS variables from tokens
const generateCSSVariables = (obj, prefix = '') => {
  let css = '';
  
  for (const [key, value] of Object.entries(obj)) {
    const varName = prefix ? `${prefix}-${key}` : key;
    
    if (typeof value === 'object' && value !== null) {
      css += generateCSSVariables(value, varName);
    } else {
      css += `  --${varName}: ${value};\n`;
    }
  }
  
  return css;
};

// Generate theme-specific CSS
const generateThemeCSS = (theme, tokens) => {
  const themeData = JSON.parse(fs.readFileSync(path.join(__dirname, `../themes/${theme}.json`), 'utf8'));
  let css = '';
  
  // Apply overrides to tokens
  const mergedTokens = JSON.parse(JSON.stringify(tokens));
  if (themeData.overrides) {
    Object.keys(themeData.overrides).forEach(category => {
      Object.assign(mergedTokens[category], themeData.overrides[category]);
    });
  }
  
  css += generateCSSVariables(mergedTokens);
  
  return css;
};

// Main CSS generation
const generateCSS = () => {
  const tokens = loadTokens();
  const distDir = path.join(__dirname, '../dist/css');
  
  // Ensure dist directory exists
  if (!fs.existsSync(distDir)) {
    fs.mkdirSync(distDir, { recursive: true });
  }
  
  // Base CSS file content
  let mainCSS = `/**
 * AuraConnect Design System
 * Auto-generated CSS variables from design tokens
 * DO NOT EDIT DIRECTLY
 */

/* Base tokens (light theme default) */
:root {
${generateThemeCSS('light', tokens)}
}

/* Dark theme */
[data-theme="dark"] {
${generateThemeCSS('dark', tokens)}
}

/* Utility classes */
.theme-transition {
  transition: 
    background-color var(--animations-transition-default),
    color var(--animations-transition-default),
    border-color var(--animations-transition-default),
    box-shadow var(--animations-transition-default);
}

/* Focus visible polyfill */
.js-focus-visible :focus:not(.focus-visible) {
  outline: none;
}

/* Reduced motion */
@media (prefers-reduced-motion: reduce) {
  *,
  *::before,
  *::after {
    animation-duration: 0.01ms !important;
    animation-iteration-count: 1 !important;
    transition-duration: 0.01ms !important;
  }
}

/* Print styles */
@media print {
  [data-theme="dark"] {
    --colors-semantic-background-primary: #FFFFFF;
    --colors-semantic-text-primary: #000000;
  }
}

/* High contrast mode support */
@media (prefers-contrast: high) {
  :root {
    --colors-semantic-border-default: #000000;
  }
  
  [data-theme="dark"] {
    --colors-semantic-border-default: #FFFFFF;
  }
}

/* Color scheme support */
:root {
  color-scheme: light;
}

[data-theme="dark"] {
  color-scheme: dark;
}
`;

  // Write main CSS file
  fs.writeFileSync(path.join(distDir, 'tokens.css'), mainCSS);
  
  // Generate component CSS
  let componentCSS = `/**
 * AuraConnect Design System - Component Styles
 * Uses CSS variables defined in tokens.css
 */

/* Import token variables */
@import './tokens.css';

/* Base reset */
.aura-component {
  box-sizing: border-box;
}

.aura-component *,
.aura-component *::before,
.aura-component *::after {
  box-sizing: inherit;
}

/* Typography base */
.aura-text {
  font-family: var(--typography-fontFamily-primary);
  color: var(--colors-semantic-text-primary);
  line-height: var(--typography-lineHeight-normal);
}

/* Component imports */
${fs.readFileSync(path.join(__dirname, '../examples/react/Button.tsx'), 'utf8')
  .match(/export const buttonStyles = `([^`]+)`/)?.[1] || ''}

${fs.readFileSync(path.join(__dirname, '../examples/react/Modal.tsx'), 'utf8')
  .match(/export const modalStyles = `([^`]+)`/)?.[1] || ''}

${fs.readFileSync(path.join(__dirname, '../examples/react/Tabs.tsx'), 'utf8')
  .match(/export const tabsStyles = `([^`]+)`/)?.[1] || ''}
`;

  // Write component CSS
  fs.writeFileSync(path.join(distDir, 'components.css'), componentCSS);
  
  // Generate minified version
  const minifiedCSS = mainCSS.replace(/\/\*[\s\S]*?\*\//g, '')
    .replace(/\s+/g, ' ')
    .replace(/\s*{\s*/g, '{')
    .replace(/\s*}\s*/g, '}')
    .replace(/\s*:\s*/g, ':')
    .replace(/\s*;\s*/g, ';')
    .trim();
  
  fs.writeFileSync(path.join(distDir, 'tokens.min.css'), minifiedCSS);
  
  // Generate theme files
  ['light', 'dark', 'blue-brand'].forEach(theme => {
    if (fs.existsSync(path.join(__dirname, `../themes/${theme}.json`))) {
      const themeCSS = `:root {\n${generateThemeCSS(theme, tokens)}\n}`;
      fs.writeFileSync(path.join(distDir, `theme-${theme}.css`), themeCSS);
    }
  });
  
  console.log('✅ CSS files generated successfully');
};

// Run if called directly
if (require.main === module) {
  generateCSS();
}

module.exports = { generateCSS };