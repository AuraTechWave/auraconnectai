const fs = require('fs');
const path = require('path');
const Ajv = require('ajv');

const ajv = new Ajv({ allErrors: true });

// Token schema
const tokenSchema = {
  type: 'object',
  additionalProperties: {
    oneOf: [
      { type: 'string' },
      { type: 'number' },
      { type: 'object' }
    ]
  }
};

// Component schema
const componentSchema = {
  type: 'object',
  required: ['name', 'description'],
  properties: {
    name: { type: 'string' },
    description: { type: 'string' },
    variants: { type: 'object' },
    anatomy: { type: 'object' },
    sizes: { type: 'object' },
    states: { type: 'object' },
    accessibility: { type: 'object' }
  }
};

// Theme schema
const themeSchema = {
  type: 'object',
  required: ['name'],
  properties: {
    name: { type: 'string' },
    description: { type: 'string' },
    extends: { type: 'string' },
    overrides: { type: 'object' }
  }
};

// Color contrast validation
function validateColorContrast(color1, color2, minRatio = 4.5) {
  // Simple hex to RGB conversion
  function hexToRgb(hex) {
    const result = /^#?([a-f\d]{2})([a-f\d]{2})([a-f\d]{2})$/i.exec(hex);
    return result ? {
      r: parseInt(result[1], 16),
      g: parseInt(result[2], 16),
      b: parseInt(result[3], 16)
    } : null;
  }
  
  // Calculate relative luminance
  function getLuminance(rgb) {
    const [r, g, b] = [rgb.r, rgb.g, rgb.b].map(val => {
      val = val / 255;
      return val <= 0.03928 ? val / 12.92 : Math.pow((val + 0.055) / 1.055, 2.4);
    });
    return 0.2126 * r + 0.7152 * g + 0.0722 * b;
  }
  
  // Calculate contrast ratio
  function getContrastRatio(rgb1, rgb2) {
    const lum1 = getLuminance(rgb1);
    const lum2 = getLuminance(rgb2);
    const brightest = Math.max(lum1, lum2);
    const darkest = Math.min(lum1, lum2);
    return (brightest + 0.05) / (darkest + 0.05);
  }
  
  const rgb1 = hexToRgb(color1);
  const rgb2 = hexToRgb(color2);
  
  if (!rgb1 || !rgb2) return true; // Skip if not valid hex
  
  const ratio = getContrastRatio(rgb1, rgb2);
  return ratio >= minRatio;
}

// Validate all files
function validateFiles() {
  const errors = [];
  
  // Validate tokens
  const tokenDir = path.join(__dirname, '../tokens');
  fs.readdirSync(tokenDir).forEach(file => {
    if (file.endsWith('.json') && file !== 'index.json') {
      const content = JSON.parse(fs.readFileSync(path.join(tokenDir, file), 'utf8'));
      const validate = ajv.compile(tokenSchema);
      if (!validate(content)) {
        errors.push({ file: `tokens/${file}`, errors: validate.errors });
      }
    }
  });
  
  // Validate components
  const componentDir = path.join(__dirname, '../components');
  fs.readdirSync(componentDir).forEach(file => {
    if (file.endsWith('.json')) {
      const content = JSON.parse(fs.readFileSync(path.join(componentDir, file), 'utf8'));
      const firstKey = Object.keys(content)[0];
      const validate = ajv.compile(componentSchema);
      if (!validate(content[firstKey])) {
        errors.push({ file: `components/${file}`, errors: validate.errors });
      }
    }
  });
  
  // Validate themes
  const themeDir = path.join(__dirname, '../themes');
  fs.readdirSync(themeDir).forEach(file => {
    if (file.endsWith('.json') && file !== 'index.json') {
      const content = JSON.parse(fs.readFileSync(path.join(themeDir, file), 'utf8'));
      const validate = ajv.compile(themeSchema);
      if (!validate(content)) {
        errors.push({ file: `themes/${file}`, errors: validate.errors });
      }
    }
  });
  
  // Validate color contrast
  const colors = JSON.parse(fs.readFileSync(path.join(tokenDir, 'colors.json'), 'utf8')).colors;
  const contrastErrors = [];
  
  // Check primary colors
  Object.entries(colors.semantic).forEach(([key, value]) => {
    if (value.base && value.contrast) {
      if (!validateColorContrast(value.base, value.contrast)) {
        contrastErrors.push(`${key}: ${value.base} on ${value.contrast}`);
      }
    }
  });
  
  if (contrastErrors.length > 0) {
    errors.push({ file: 'colors', type: 'contrast', errors: contrastErrors });
  }
  
  // Report results
  if (errors.length > 0) {
    console.error('❌ Validation failed:');
    errors.forEach(({ file, errors }) => {
      console.error(`\n${file}:`);
      console.error(JSON.stringify(errors, null, 2));
    });
    process.exit(1);
  } else {
    console.log('✅ All files validated successfully');
  }
}

validateFiles();