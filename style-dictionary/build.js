const StyleDictionary = require('style-dictionary');

console.log('Building design tokens...');

// Custom format for TypeScript module
StyleDictionary.registerFormat({
  name: 'typescript/module',
  formatter: function(dictionary, config) {
    return `// Auto-generated design tokens
// Do not edit directly
// Generated on ${new Date().toISOString()}

export const tokens = ${JSON.stringify(dictionary.properties, null, 2)};

export type DesignTokens = typeof tokens;
`;
  }
});

// Custom format for TypeScript declarations
StyleDictionary.registerFormat({
  name: 'typescript/module-declarations',
  formatter: function(dictionary, config) {
    return `// Auto-generated design token types
// Do not edit directly
// Generated on ${new Date().toISOString()}

declare module '@/constants/tokens' {
  export interface DesignTokens {
    color: {
      primary: Record<string, { value: string }>;
      secondary: Record<string, { value: string }>;
      accent: Record<string, { value: string }>;
      neutral: Record<string, { value: string }>;
      success: Record<string, { value: string }>;
      warning: Record<string, { value: string }>;
      error: Record<string, { value: string }>;
      text: Record<string, { value: string }>;
      background: Record<string, { value: string }>;
      border: Record<string, { value: string }>;
    };
    spacing: Record<string, { value: number }>;
    typography: {
      fontFamily: Record<string, { value: string }>;
      fontSize: Record<string, { value: number }>;
      fontWeight: Record<string, { value: string }>;
      lineHeight: Record<string, { value: number }>;
      letterSpacing: Record<string, { value: number }>;
    };
    borderRadius: Record<string, { value: number }>;
    shadows: Record<string, {
      shadowColor: { value: string };
      shadowOffset: { width: { value: number }; height: { value: number } };
      shadowOpacity: { value: number };
      shadowRadius: { value: number };
      elevation: { value: number };
    }>;
  }
  
  export const tokens: DesignTokens;
}
`;
  }
});

// Custom transform for React Native
StyleDictionary.registerTransformGroup({
  name: 'react-native',
  transforms: [
    'attribute/cti',
    'name/cti/camel',
    'color/hex',
    'size/object',
    'size/remToPx',
  ]
});

const StyleDictionaryExtended = StyleDictionary.extend('./config.json');

StyleDictionaryExtended.buildAllPlatforms();

console.log('\n✅ Design tokens built successfully!');
console.log('\nGenerated files:');
console.log('  - build/scss/_variables.scss');
console.log('  - build/css/variables.css');
console.log('  - build/js/tokens.js');
console.log('  - build/ts/tokens.ts');
console.log('  - build/react-native/tokens.js');
console.log('  - build/react-native/tokens.d.ts');
console.log('  - build/ios/ (Swift/Objective-C files)');
console.log('  - build/android/ (XML resource files)');
console.log('\nIntegrate these tokens into your build process for consistent design across platforms.');