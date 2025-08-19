const wcagContrast = require('wcag-contrast');
const fs = require('fs');
const path = require('path');

// Load color tokens
const colorsPath = path.join(__dirname, '../tokens/colors.json');
const { colors } = JSON.parse(fs.readFileSync(colorsPath, 'utf8'));

// Test configurations
const tests = [
  // Text on backgrounds - AA (4.5:1)
  { name: 'Primary text on white', fg: colors.semantic.text.primary, bg: colors.semantic.background.primary, min: 4.5 },
  { name: 'Secondary text on white', fg: colors.semantic.text.secondary, bg: colors.semantic.background.primary, min: 4.5 },
  
  // Button text - AA (4.5:1)
  { name: 'Primary button', fg: colors.semantic.primary.contrast, bg: colors.semantic.primary.base, min: 4.5 },
  { name: 'Secondary button', fg: colors.semantic.secondary.contrast, bg: colors.semantic.secondary.base, min: 4.5 },
  { name: 'Success button', fg: colors.semantic.success.contrast, bg: colors.semantic.success.base, min: 4.5 },
  { name: 'Warning button', fg: colors.semantic.warning.contrast, bg: colors.semantic.warning.base, min: 4.5 },
  { name: 'Error button', fg: colors.semantic.error.contrast, bg: colors.semantic.error.base, min: 4.5 },
  
  // UI elements - AA (3:1)
  { name: 'Border on white', fg: colors.semantic.border.default, bg: colors.semantic.background.primary, min: 3 },
  { name: 'Primary color on light bg', fg: colors.semantic.primary.base, bg: colors.semantic.primary.light, min: 3 },
];

// Run tests
console.log('Running WCAG contrast tests...\n');

let passed = 0;
let failed = 0;

tests.forEach(test => {
  try {
    const ratio = wcagContrast.ratio(test.fg, test.bg);
    const passes = ratio >= test.min;
    
    if (passes) {
      console.log(`✅ ${test.name}`);
      console.log(`   ${test.fg} on ${test.bg} = ${ratio.toFixed(2)}:1 (min: ${test.min}:1)`);
      passed++;
    } else {
      console.log(`❌ ${test.name}`);
      console.log(`   ${test.fg} on ${test.bg} = ${ratio.toFixed(2)}:1 (min: ${test.min}:1)`);
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