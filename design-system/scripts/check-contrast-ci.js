#!/usr/bin/env node

const wcagContrast = require('wcag-contrast');
const fs = require('fs');
const path = require('path');

// Load compiled tokens from build output
const tokensPath = path.join(__dirname, '../dist/json/tokens.json');

if (!fs.existsSync(tokensPath)) {
  console.error('❌ Error: Tokens not built. Run "npm run build" first.');
  process.exit(1);
}

const tokens = JSON.parse(fs.readFileSync(tokensPath, 'utf8'));

// Define contrast requirements
const contrastTests = [
  // Text contrast requirements (WCAG AA = 4.5:1)
  {
    name: 'Text Contrast',
    minRatio: 4.5,
    tests: [
      { fg: '--color-text-primary', bg: '--color-background-primary' },
      { fg: '--color-text-secondary', bg: '--color-background-primary' },
      { fg: '--color-text-primary', bg: '--color-background-secondary' },
    ]
  },
  // UI element contrast (WCAG AA = 3:1)
  {
    name: 'UI Element Contrast',
    minRatio: 3,
    tests: [
      { fg: '--color-border-default', bg: '--color-background-primary' },
      { fg: '--color-border-focus', bg: '--color-background-primary' },
      { fg: '--color-semantic-success', bg: '--color-background-primary' },
      { fg: '--color-semantic-error', bg: '--color-background-primary' },
    ]
  }
];

// Helper to get color value from token
function getColorValue(tokenName) {
  // Remove -- prefix and convert to dot notation
  const path = tokenName.replace('--', '').replace(/-/g, '.');
  const keys = path.split('.');
  
  let value = tokens;
  for (const key of keys) {
    value = value[key];
    if (!value) return null;
  }
  
  return value;
}

// Run tests
console.log('🔍 Checking WCAG Contrast Requirements\n');

let totalPassed = 0;
let totalFailed = 0;
const failedTests = [];

contrastTests.forEach(category => {
  console.log(`\n${category.name} (min ${category.minRatio}:1)`);
  console.log('─'.repeat(50));
  
  category.tests.forEach(test => {
    const fgColor = getColorValue(test.fg);
    const bgColor = getColorValue(test.bg);
    
    if (!fgColor || !bgColor) {
      console.log(`⚠️  ${test.fg} on ${test.bg} - Token not found`);
      totalFailed++;
      return;
    }
    
    try {
      const ratio = wcagContrast.hex(fgColor, bgColor);
      const passes = ratio >= category.minRatio;
      
      if (passes) {
        console.log(`✅ ${test.fg} on ${test.bg}: ${ratio.toFixed(2)}:1`);
        totalPassed++;
      } else {
        console.log(`❌ ${test.fg} on ${test.bg}: ${ratio.toFixed(2)}:1 (needs ${category.minRatio}:1)`);
        totalFailed++;
        failedTests.push({
          fg: test.fg,
          bg: test.bg,
          ratio: ratio.toFixed(2),
          required: category.minRatio
        });
      }
    } catch (error) {
      console.log(`⚠️  ${test.fg} on ${test.bg} - Error: ${error.message}`);
      totalFailed++;
    }
  });
});

// Summary
console.log('\n' + '='.repeat(50));
console.log(`\nSummary: ${totalPassed} passed, ${totalFailed} failed\n`);

if (failedTests.length > 0) {
  console.log('Failed tests that need attention:');
  failedTests.forEach(test => {
    console.log(`  - ${test.fg} on ${test.bg}: ${test.ratio}:1 (needs ${test.required}:1)`);
  });
  console.log('\nConsider adjusting these color combinations to meet WCAG AA standards.');
}

// Exit with error code if any tests failed
process.exit(totalFailed > 0 ? 1 : 0);