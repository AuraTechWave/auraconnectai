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

// Generate theme-specific CSS with error handling
const generateThemeCSS = (theme, tokens) => {
  try {
    const themePath = path.join(__dirname, `../themes/${theme}.json`);
    
    if (!fs.existsSync(themePath)) {
      console.error(`❌ Theme file not found: ${theme}.json`);
      return generateCSSVariables(tokens); // Return base tokens as fallback
    }
    
    const themeData = JSON.parse(fs.readFileSync(themePath, 'utf8'));
    let css = '';
    
    // Apply overrides to tokens
    const mergedTokens = JSON.parse(JSON.stringify(tokens));
    if (themeData.overrides) {
      Object.keys(themeData.overrides).forEach(category => {
        if (mergedTokens[category]) {
          // Deep merge to preserve token structure
          mergeDeep(mergedTokens[category], themeData.overrides[category]);
        } else {
          console.warn(`⚠️  Unknown token category in theme overrides: ${category}`);
        }
      });
    }
    
    css += generateCSSVariables(mergedTokens);
    
    return css;
  } catch (error) {
    console.error(`❌ Error generating theme CSS for ${theme}:`, error.message);
    return generateCSSVariables(tokens); // Return base tokens as fallback
  }
};

// Helper function for deep merging
const mergeDeep = (target, source) => {
  for (const key in source) {
    if (source[key] && typeof source[key] === 'object' && !Array.isArray(source[key])) {
      if (!target[key]) target[key] = {};
      mergeDeep(target[key], source[key]);
    } else {
      target[key] = source[key];
    }
  }
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
  
  // Generate component CSS with error handling
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

/* Component styles */
`;

  // Extract component styles with error handling
  const componentFiles = [
    { file: 'Button.tsx', varName: 'buttonStyles' },
    { file: 'Modal.tsx', varName: 'modalStyles' },
    { file: 'Tabs.tsx', varName: 'tabsStyles' }
  ];

  for (const { file, varName } of componentFiles) {
    try {
      const filePath = path.join(__dirname, '../examples/react', file);
      
      if (!fs.existsSync(filePath)) {
        console.warn(`⚠️  Component file not found: ${file}`);
        componentCSS += `\n/* ${file} styles not found */\n`;
        continue;
      }
      
      const content = fs.readFileSync(filePath, 'utf8');
      const regex = new RegExp(`export const ${varName} = \\\`([^\\\`]+)\\\``, 's');
      const match = content.match(regex);
      
      if (match && match[1]) {
        componentCSS += `\n/* ${file} styles */\n${match[1]}\n`;
      } else {
        console.warn(`⚠️  Could not extract ${varName} from ${file}`);
        componentCSS += `\n/* Could not extract ${varName} from ${file} */\n`;
      }
    } catch (error) {
      console.error(`❌ Error processing ${file}:`, error.message);
      componentCSS += `\n/* Error processing ${file}: ${error.message} */\n`;
    }
  }

  // Write component CSS
  fs.writeFileSync(path.join(distDir, 'components.css'), componentCSS);
  
  // Generate minified version with error handling
  try {
    const minifiedCSS = mainCSS.replace(/\/\*[\s\S]*?\*\//g, '')
      .replace(/\s+/g, ' ')
      .replace(/\s*{\s*/g, '{')
      .replace(/\s*}\s*/g, '}')
      .replace(/\s*:\s*/g, ':')
      .replace(/\s*;\s*/g, ';')
      .trim();
    
    fs.writeFileSync(path.join(distDir, 'tokens.min.css'), minifiedCSS);
  } catch (error) {
    console.error('❌ Error minifying CSS:', error.message);
  }
  
  // Generate theme files with error handling
  const themes = ['light', 'dark', 'blue-brand'];
  for (const theme of themes) {
    try {
      const themePath = path.join(__dirname, `../themes/${theme}.json`);
      if (fs.existsSync(themePath)) {
        const themeCSS = `:root {\n${generateThemeCSS(theme, tokens)}\n}`;
        fs.writeFileSync(path.join(distDir, `theme-${theme}.css`), themeCSS);
        console.log(`✅ Generated theme-${theme}.css`);
      } else {
        console.warn(`⚠️  Theme file not found: ${theme}.json`);
      }
    } catch (error) {
      console.error(`❌ Error generating theme ${theme}:`, error.message);
    }
  }
  
  console.log('✅ CSS files generated successfully');
};

// Run if called directly
if (require.main === module) {
  generateCSS();
}

module.exports = { generateCSS };