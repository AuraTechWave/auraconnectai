const wcagContrast = require('wcag-contrast');
const fs = require('fs');
const path = require('path');

// Load color tokens
const colorsPath = path.join(__dirname, '../tokens/colors.json');
const { colors } = JSON.parse(fs.readFileSync(colorsPath, 'utf8'));

// Function to resolve color references
function resolveColor(value) {
  if (typeof value === 'string' && value.startsWith('{') && value.endsWith('}')) {
    // Remove braces and split by dots
    const path = value.slice(1, -1).split('.');
    let resolved = colors;
    
    for (const segment of path) {
      resolved = resolved[segment];
      if (!resolved) return value;
    }
    
    // If we found a value property, use it
    return resolved.value || value;
  }
  return value;
}

// Test configurations
const tests = [
  // Text on backgrounds - AA (4.5:1)
  { name: 'Primary text on white', fg: colors.semantic.text.primary.value, bg: colors.semantic.background.primary.value, min: 4.5 },
  { name: 'Secondary text on white', fg: colors.semantic.text.secondary.value, bg: colors.semantic.background.primary.value, min: 4.5 },
  { name: 'Primary text on secondary bg', fg: colors.semantic.text.primary.value, bg: colors.semantic.background.secondary.value, min: 4.5 },
  
  // Button text - AA (4.5:1) - assuming white text on colored backgrounds
  { name: 'White on primary button', fg: colors.semantic.text.inverse.value, bg: colors.semantic.primary.value, min: 4.5 },
  { name: 'White on secondary button', fg: colors.semantic.text.inverse.value, bg: colors.semantic.secondary.value, min: 4.5 },
  { name: 'White on success button', fg: colors.semantic.text.inverse.value, bg: colors.semantic.success.value, min: 4.5 },
  { name: 'Dark on warning button', fg: colors.semantic.text.primary.value, bg: colors.semantic.warning.value, min: 4.5 },
  { name: 'White on error button', fg: colors.semantic.text.inverse.value, bg: colors.semantic.error.value, min: 4.5 },
  
  // UI elements - AA (3:1)
  { name: 'Default border on white', fg: colors.semantic.border.default.value, bg: colors.semantic.background.primary.value, min: 3 },
  { name: 'Focus border on white', fg: colors.semantic.border.focus.value, bg: colors.semantic.background.primary.value, min: 3 },
  
  // State colors on white background
  { name: 'Success color on white', fg: colors.semantic.success.value, bg: colors.semantic.background.primary.value, min: 3 },
  { name: 'Warning color on white', fg: colors.semantic.warning.value, bg: colors.semantic.background.primary.value, min: 3 },
  { name: 'Error color on white', fg: colors.semantic.error.value, bg: colors.semantic.background.primary.value, min: 3 },
];

// Run tests
console.log('Running WCAG contrast tests...\n');

let passed = 0;
let failed = 0;

tests.forEach(test => {
  try {
    // Resolve color references
    const fgColor = resolveColor(test.fg);
    const bgColor = resolveColor(test.bg);
    
    const contrastRatio = wcagContrast.hex(fgColor, bgColor);
    const passes = contrastRatio >= test.min;
    
    if (passes) {
      console.log(`✅ ${test.name}`);
      console.log(`   ${fgColor} on ${bgColor} = ${contrastRatio.toFixed(2)}:1 (min: ${test.min}:1)`);
      passed++;
    } else {
      console.log(`❌ ${test.name}`);
      console.log(`   ${fgColor} on ${bgColor} = ${contrastRatio.toFixed(2)}:1 (min: ${test.min}:1)`);
      failed++;
    }
  } catch (error) {
    console.log(`⚠️  ${test.name} - Error: ${error.message}`);
    failed++;
  }
});

console.log(`\n${passed} passed, ${failed} failed`);

if (failed > 0) {
  process.exit(1);
}