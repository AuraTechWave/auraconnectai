const StyleDictionary = require('style-dictionary');

// Custom transforms
StyleDictionary.registerTransform({
  name: 'size/dp',
  type: 'value',
  matcher: (token) => token.attributes.category === 'size',
  transformer: (token) => `${token.value}dp`,
});

StyleDictionary.registerTransform({
  name: 'time/ms',
  type: 'value',
  matcher: (token) => token.attributes.category === 'time',
  transformer: (token) => `${token.value}ms`,
});

// Custom format for React Native
StyleDictionary.registerFormat({
  name: 'javascript/module-flat',
  formatter: function ({ dictionary }) {
    return `export const tokens = ${JSON.stringify(dictionary.allTokens.reduce((acc, token) => {
      acc[token.name] = token.value;
      return acc;
    }, {}), null, 2)};`;
  },
});

// Configuration
module.exports = {
  source: ['tokens/**/*.json'],
  platforms: {
    // TypeScript definitions
    typescript: {
      transformGroup: 'js',
      buildPath: 'build/ts/',
      files: [
        {
          destination: 'index.d.ts',
          format: 'typescript/es6-declarations',
        },
      ],
    },
    // React Native
    reactNative: {
      transformGroup: 'js',
      buildPath: '../src/constants/generated/',
      files: [
        {
          destination: 'tokens.js',
          format: 'javascript/module-flat',
        },
      ],
    },
    // iOS
    ios: {
      transformGroup: 'ios',
      buildPath: 'build/ios/',
      files: [
        {
          destination: 'DesignTokens.h',
          format: 'ios/macros',
        },
        {
          destination: 'DesignTokens.m',
          format: 'ios/singleton.m',
        },
      ],
    },
    // Android
    android: {
      transformGroup: 'android',
      buildPath: 'build/android/',
      files: [
        {
          destination: 'design_tokens_colors.xml',
          format: 'android/colors',
        },
        {
          destination: 'design_tokens_dimens.xml',
          format: 'android/dimens',
        },
      ],
    },
    // Documentation
    docs: {
      transformGroup: 'js',
      buildPath: 'build/docs/',
      files: [
        {
          destination: 'tokens.md',
          format: 'markdown/table',
        },
      ],
    },
  },
};