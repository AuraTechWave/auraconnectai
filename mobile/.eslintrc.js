module.exports = {
  root: true,
  extends: [
    '@react-native',
    'eslint:recommended',
    'plugin:@typescript-eslint/recommended',
    'plugin:react/recommended',
    'plugin:react-hooks/recommended',
    'plugin:jsx-a11y/recommended',
    'prettier',
  ],
  parser: '@typescript-eslint/parser',
  plugins: ['@typescript-eslint', 'react', 'react-hooks', 'jsx-a11y', 'prettier', 'unused-imports'],
  parserOptions: {
    ecmaFeatures: {
      jsx: true,
    },
    ecmaVersion: 2021,
    sourceType: 'module',
  },
  rules: {
    'prettier/prettier': 'error',
    'react/react-in-jsx-scope': 'off',
    'react/prop-types': 'off',
    '@typescript-eslint/explicit-module-boundary-types': 'off',
    '@typescript-eslint/no-explicit-any': 'warn',
    '@typescript-eslint/no-unused-vars': 'off', // Handled by unused-imports
    'unused-imports/no-unused-imports': 'error',
    'unused-imports/no-unused-vars': [
      'warn',
      {
        vars: 'all',
        varsIgnorePattern: '^_',
        args: 'after-used',
        argsIgnorePattern: '^_',
      },
    ],
    'no-console': ['warn', { allow: ['warn', 'error'] }],
    'react-hooks/rules-of-hooks': 'error',
    'react-hooks/exhaustive-deps': 'warn',
    // Accessibility rules for React Native
    'jsx-a11y/accessible-emoji': 'off', // Not applicable to React Native
    'jsx-a11y/alt-text': 'off', // React Native uses source prop
    'jsx-a11y/anchor-has-content': 'off', // No anchors in React Native
    'jsx-a11y/anchor-is-valid': 'off', // No anchors in React Native
    'jsx-a11y/aria-activedescendant-has-tabindex': 'off', // Not applicable
    'jsx-a11y/aria-props': 'off', // React Native uses accessibility props
    'jsx-a11y/aria-proptypes': 'off', // React Native uses accessibility props
    'jsx-a11y/aria-role': 'off', // React Native uses accessibilityRole
    'jsx-a11y/aria-unsupported-elements': 'off', // Not applicable
    'jsx-a11y/click-events-have-key-events': 'off', // Touch events in React Native
    'jsx-a11y/control-has-associated-label': 'off', // Use accessibilityLabel
    'jsx-a11y/heading-has-content': 'off', // No heading elements
    'jsx-a11y/html-has-lang': 'off', // Not applicable
    'jsx-a11y/iframe-has-title': 'off', // No iframes
    'jsx-a11y/img-redundant-alt': 'off', // No img elements
    'jsx-a11y/interactive-supports-focus': 'off', // Touch-based
    'jsx-a11y/label-has-associated-control': 'off', // No labels
    'jsx-a11y/media-has-caption': 'off', // Handle separately
    'jsx-a11y/mouse-events-have-key-events': 'off', // Touch events
    'jsx-a11y/no-access-key': 'off', // Not applicable
    'jsx-a11y/no-autofocus': 'warn', // Still relevant
    'jsx-a11y/no-distracting-elements': 'off', // Not applicable
    'jsx-a11y/no-interactive-element-to-noninteractive-role': 'off',
    'jsx-a11y/no-noninteractive-element-interactions': 'off',
    'jsx-a11y/no-noninteractive-element-to-interactive-role': 'off',
    'jsx-a11y/no-noninteractive-tabindex': 'off',
    'jsx-a11y/no-redundant-roles': 'off',
    'jsx-a11y/no-static-element-interactions': 'off',
    'jsx-a11y/role-has-required-aria-props': 'off',
    'jsx-a11y/role-supports-aria-props': 'off',
    'jsx-a11y/scope': 'off',
    'jsx-a11y/tabindex-no-positive': 'off',
    // Custom React Native accessibility rules
    'react-native/no-unused-styles': 'error',
    'react-native/no-inline-styles': 'warn',
    'react-native/no-color-literals': 'off',
    'react-native/no-raw-text': 'off',
    // Performance-related rules
    'react/jsx-no-bind': [
      'warn',
      {
        allowArrowFunctions: true,
        allowBind: false,
        ignoreRefs: true,
      },
    ],
    'react/no-did-mount-set-state': 'error',
    'react/no-did-update-set-state': 'error',
  },
  settings: {
    react: {
      version: 'detect',
    },
  },
};
