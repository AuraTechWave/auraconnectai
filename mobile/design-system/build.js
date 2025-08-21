const StyleDictionary = require('style-dictionary');
const config = require('./config');

console.log('Building design tokens...');

// Build all platforms
const styleDictionary = StyleDictionary.extend(config);
styleDictionary.buildAllPlatforms();

console.log('✅ Design tokens built successfully!');

// Generate summary
const platforms = Object.keys(config.platforms);
console.log(`\nGenerated tokens for ${platforms.length} platforms:`);
platforms.forEach(platform => {
  console.log(`  - ${platform}`);
});