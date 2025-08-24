const wcagContrast = require('wcag-contrast');

// Direct color values for testing
const tests = [
  // Text on backgrounds - AA (4.5:1)
  { name: 'Primary text on white', fg: '#1E293B', bg: '#FFFFFF', min: 4.5 },
  { name: 'Secondary text on white', fg: '#64748B', bg: '#FFFFFF', min: 4.5 },
  { name: 'Primary text on secondary bg', fg: '#1E293B', bg: '#FAFAFA', min: 4.5 },
  
  // Button text - AA (4.5:1)
  { name: 'White on primary button', fg: '#FFFFFF', bg: '#5D87FF', min: 4.5 },
  { name: 'White on secondary button', fg: '#FFFFFF', bg: '#3AA0E0', min: 4.5 },
  { name: 'White on success button', fg: '#FFFFFF', bg: '#2FA96A', min: 4.5 },
  { name: 'Dark on warning button', fg: '#1E293B', bg: '#F9B800', min: 4.5 },
  { name: 'White on error button', fg: '#FFFFFF', bg: '#E55865', min: 4.5 },
  
  // UI elements - AA (3:1)
  { name: 'Default border on white', fg: '#E5EAEF', bg: '#FFFFFF', min: 3 },
  { name: 'Focus border on white', fg: '#5D87FF', bg: '#FFFFFF', min: 3 },
  
  // State colors on white background
  { name: 'Success color on white', fg: '#2FA96A', bg: '#FFFFFF', min: 3 },
  { name: 'Warning color on white', fg: '#F9B800', bg: '#FFFFFF', min: 3 },
  { name: 'Error color on white', fg: '#E55865', bg: '#FFFFFF', min: 3 },
];

// Run tests
console.log('Running WCAG contrast tests...\n');

let passed = 0;
let failed = 0;

tests.forEach(test => {
  try {
    const contrastRatio = wcagContrast.hex(test.fg, test.bg);
    const passes = contrastRatio >= test.min;
    
    if (passes) {
      console.log(`✅ ${test.name}`);
      console.log(`   ${test.fg} on ${test.bg} = ${contrastRatio.toFixed(2)}:1 (min: ${test.min}:1)`);
      passed++;
    } else {
      console.log(`❌ ${test.name}`);
      console.log(`   ${test.fg} on ${test.bg} = ${contrastRatio.toFixed(2)}:1 (min: ${test.min}:1)`);
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