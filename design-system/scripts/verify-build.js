#!/usr/bin/env node

const fs = require('fs');
const path = require('path');

console.log('🔍 Verifying AuraConnect Design System Build...\n');

const checks = [
  // Token files
  { path: 'tokens/colors.json', type: 'Token file' },
  { path: 'tokens/typography.json', type: 'Token file' },
  { path: 'tokens/spacing.json', type: 'Token file' },
  { path: 'tokens/shadows.json', type: 'Token file' },
  { path: 'tokens/borders.json', type: 'Token file' },
  { path: 'tokens/animations.json', type: 'Token file' },
  { path: 'tokens/z-index.json', type: 'Token file' },
  
  // Theme files
  { path: 'themes/base.json', type: 'Theme file' },
  { path: 'themes/light.json', type: 'Theme file' },
  { path: 'themes/dark.json', type: 'Theme file' },
  
  // Build configuration
  { path: 'style-dictionary.config.js', type: 'Build config' },
  { path: 'package.json', type: 'Package manifest' },
  
  // Scripts
  { path: 'scripts/build-exports.js', type: 'Build script' },
  { path: 'scripts/generate-css.js', type: 'Build script' },
  { path: 'scripts/theme-validator.js', type: 'Validation script' },
  
  // Examples
  { path: 'examples/react/Button.tsx', type: 'React component' },
  { path: 'examples/react/Modal.tsx', type: 'React component' },
  { path: 'examples/react/Tabs.tsx', type: 'React component' },
];

let allPassed = true;

// Check source files
console.log('📁 Checking source files:');
checks.forEach(({ path: filePath, type }) => {
  const exists = fs.existsSync(path.join(__dirname, '..', filePath));
  console.log(`  ${exists ? '✅' : '❌'} ${type}: ${filePath}`);
  if (!exists) allPassed = false;
});

// Check if dist exists (after build)
console.log('\n📦 Checking build outputs:');
const distChecks = [
  'dist/css/tokens.css',
  'dist/js/tokens.js',
  'dist/js/tokens.d.ts',
  'dist/resolver.js',
  'dist/tailwind.preset.js',
];

const distExists = fs.existsSync(path.join(__dirname, '../dist'));
if (distExists) {
  distChecks.forEach(filePath => {
    const exists = fs.existsSync(path.join(__dirname, '..', filePath));
    console.log(`  ${exists ? '✅' : '❌'} ${filePath}`);
  });
} else {
  console.log('  ⚠️  No dist/ directory found. Run "npm run build" to generate outputs.');
}

// Verify token references will be resolved
console.log('\n🔗 Token reference resolution:');
try {
  const buttonSpec = JSON.parse(
    fs.readFileSync(path.join(__dirname, '../components/button.json'), 'utf8')
  );
  const hasTokenRefs = JSON.stringify(buttonSpec).includes('$');
  console.log(`  ${hasTokenRefs ? '✅' : '⚠️ '} Component files use token references (e.g., $borders.radius.md)`);
  console.log('  ℹ️  These references are resolved during build to actual values');
} catch (e) {
  console.log('  ❌ Could not verify token references');
}

// Summary
console.log('\n📊 Summary:');
if (allPassed) {
  console.log('  ✅ All source files present and correct!');
  console.log('  ℹ️  Run "npm install && npm run build" to generate distribution files');
} else {
  console.log('  ❌ Some files are missing. Please check the errors above.');
}

console.log('\n💡 To test the complete build pipeline:');
console.log('  1. npm install');
console.log('  2. npm run build');
console.log('  3. npm run validate');
console.log('  4. npm run test:contrast');