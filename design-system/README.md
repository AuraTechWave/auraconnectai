# AuraConnect Design System

A comprehensive design system for the AuraConnect Admin Dashboard, built with scalability, accessibility, and developer experience in mind.

## Overview

This design system provides a centralized source of truth for all UI components, design tokens, and patterns used across the AuraConnect platform. It ensures consistency, improves development velocity, and maintains WCAG 2.1 AA accessibility compliance.

## Directory Structure

```
design-system/
├── tokens/                 # Design tokens (colors, typography, spacing, etc.)
│   ├── colors.json        # Color palette and semantic colors
│   ├── typography.json    # Font families, sizes, and text styles
│   ├── spacing.json       # Spacing scale and layout values
│   ├── shadows.json       # Elevation and shadow definitions
│   ├── borders.json       # Border radius and styles
│   └── animations.json    # Animation timing and easing
├── components/            # Component specifications
│   ├── button.json       # Button component specs
│   ├── card.json         # Card component specs
│   ├── table.json        # Table component specs
│   ├── tabs.json         # Tabs component specs
│   ├── input.json        # Input/form field specs
│   ├── select.json       # Select/dropdown specs
│   ├── modal.json        # Modal/dialog specs
│   └── notification.json # Alert/toast specs
├── themes/               # Theme configurations
│   ├── light.json       # Default light theme
│   ├── dark.json        # Dark theme
│   ├── blue-brand.json  # Example custom brand theme
│   └── index.json       # Theme registry and config
├── accessibility.md      # Accessibility guidelines
└── README.md            # This file
```

## Quick Start

### For Designers

1. **Design Tokens**: Start with the tokens in the `tokens/` directory. These define the foundational visual language.
2. **Component Specs**: Reference the `components/` directory for detailed component anatomy and behavior.
3. **Themes**: Check `themes/` for available theme variations.

### For Developers

#### 1. Import Design Tokens

```javascript
// Import all tokens
import * as tokens from '@auraconnect/design-system/tokens';

// Import specific tokens
import colors from '@auraconnect/design-system/tokens/colors.json';
import typography from '@auraconnect/design-system/tokens/typography.json';
```

#### 2. Apply Theme

```javascript
import { themes } from '@auraconnect/design-system/themes';

// Apply light theme
const theme = themes.light;

// Apply to CSS variables
Object.entries(theme.colors.semantic).forEach(([key, value]) => {
  document.documentElement.style.setProperty(`--color-${key}`, value);
});
```

#### 3. Use Component Specifications

```javascript
import buttonSpec from '@auraconnect/design-system/components/button.json';

// Example React component
const Button = ({ variant = 'contained', size = 'medium', color = 'primary', ...props }) => {
  const styles = {
    ...buttonSpec.button.variants[variant].styles.base,
    ...buttonSpec.button.sizes[size],
    ...buttonSpec.button.colors[color][variant],
  };
  
  return <button style={styles} {...props} />;
};
```

## Design Tokens

### Colors
- **Primitive Colors**: Base color palette (gray, blue, green, etc.)
- **Semantic Colors**: Purpose-driven colors (primary, success, error, etc.)
- **Theme-aware**: Automatic adjustments for light/dark themes

### Typography
- **Font Families**: Primary (Plus Jakarta Sans), Secondary (Inter), Monospace
- **Type Scale**: From xs (0.75rem) to 6xl (3.75rem)
- **Variants**: Predefined styles for headings, body, captions, etc.

### Spacing
- **8px Base Unit**: Consistent spacing scale
- **Component Spacing**: Padding, margin, and gap values
- **Layout Spacing**: Container and section spacing

### Other Tokens
- **Shadows**: 10-level elevation scale
- **Borders**: Radius scale and border styles
- **Animations**: Duration and easing functions

## Components

Each component specification includes:

- **Anatomy**: Structural breakdown of the component
- **Variants**: Different visual styles
- **States**: Interactive states (hover, focus, disabled)
- **Sizes**: Size variations
- **Accessibility**: ARIA requirements and keyboard navigation

### Core Components

1. **Button**: Primary interactive element
2. **Card**: Content container
3. **Table**: Data display with sorting and filtering
4. **Tabs**: Navigation between content sections
5. **Input**: Form text input
6. **Select**: Dropdown selection
7. **Modal**: Overlay dialogs
8. **Notification**: Alerts and toasts

## Theming

### Available Themes
- **Light**: Default light theme
- **Dark**: Dark mode optimized for low-light
- **Blue Brand**: Example custom brand theme

### Creating Custom Themes

```json
{
  "name": "Custom Theme",
  "extends": "./light",
  "overrides": {
    "colors": {
      "semantic": {
        "primary": {
          "base": "#YOUR_COLOR"
        }
      }
    }
  }
}
```

### White-labeling

The design system supports white-labeling through theme overrides with built-in security:

```javascript
import { applyTheme, validateTheme } from '@auraconnect/design-system';

// Theme validation ensures only allowed properties are modified
const whiteLabelTheme = {
  name: 'Client Brand',
  extends: 'light',
  overrides: {
    colors: {
      semantic: {
        primary: {
          base: '#0066CC', // Must be valid hex color
          light: '#E6F0FF',
          dark: '#0052A3',
          contrast: '#FFFFFF'
        }
      }
    },
    typography: {
      fontFamily: {
        primary: 'Inter, -apple-system, sans-serif' // Sanitized
      }
    }
  }
};

// Validate and apply theme
if (validateTheme(whiteLabelTheme)) {
  applyTheme(whiteLabelTheme);
}
```

**Security Features:**
- ✓ Whitelist of overridable properties
- ✓ Color format validation (hex, rgb, hsl)
- ✓ Font family sanitization
- ✓ No script execution in theme values
- ✓ JSON schema validation

## Accessibility

All components follow WCAG 2.1 AA guidelines:

- ✓ Color contrast ratios meet requirements
- ✓ Keyboard navigation fully supported
- ✓ Screen reader compatible
- ✓ Focus indicators clearly visible
- ✓ Touch targets meet minimum size

See [accessibility.md](./accessibility.md) for detailed guidelines.

## Implementation Examples

### React Integration

```jsx
// ThemeProvider.jsx
import { ThemeContext } from './context';
import { themes } from '@auraconnect/design-system/themes';

export const ThemeProvider = ({ children, theme = 'light' }) => {
  const currentTheme = themes[theme];
  
  return (
    <ThemeContext.Provider value={currentTheme}>
      <div className={`theme-${theme}`}>
        {children}
      </div>
    </ThemeContext.Provider>
  );
};
```

### CSS Variables

```css
/* Generated from design tokens */
:root {
  /* Colors */
  --color-primary: #5D87FF;
  --color-primary-light: #ECF2FF;
  --color-primary-dark: #4570EA;
  
  /* Typography */
  --font-primary: 'Plus Jakarta Sans', -apple-system, sans-serif;
  --font-size-base: 1rem;
  --font-weight-medium: 500;
  
  /* Spacing */
  --spacing-base: 8px;
  --spacing-md: 16px;
  --spacing-lg: 24px;
  
  /* Shadows */
  --shadow-1: 0px 1px 2px rgba(42, 53, 71, 0.05);
  --shadow-2: 0px 2px 4px rgba(42, 53, 71, 0.08);
}

/* Dark theme overrides */
[data-theme="dark"] {
  --color-primary-light: rgba(93, 135, 255, 0.16);
  --shadow-1: 0px 1px 2px rgba(0, 0, 0, 0.3);
}
```

### Tailwind Config

```javascript
// tailwind.config.js
const tokens = require('@auraconnect/design-system/tokens');

module.exports = {
  theme: {
    extend: {
      colors: tokens.colors.semantic,
      fontFamily: tokens.typography.fontFamily,
      fontSize: tokens.typography.fontSize,
      spacing: tokens.spacing.scale,
      boxShadow: tokens.shadows.elevation,
      borderRadius: tokens.borders.radius,
    }
  }
};
```

## Development Workflow

### For Component Development

1. **Check Specifications**: Review component specs in `components/`
2. **Use Design Tokens**: Apply tokens for all visual properties
3. **Follow Patterns**: Maintain consistency with existing components
4. **Test Accessibility**: Verify keyboard navigation and screen reader support
5. **Support Themes**: Ensure components work in all themes

### For Design Updates

1. **Update Tokens**: Modify token files as needed
2. **Test Impact**: Check all components using modified tokens
3. **Update Themes**: Ensure theme overrides still work
4. **Document Changes**: Update this README and component specs

## Best Practices

### Do's
- ✓ Always use design tokens instead of hard-coded values
- ✓ Test components in all available themes
- ✓ Follow accessibility guidelines for all new components
- ✓ Keep component specifications up to date
- ✓ Use semantic color names (primary, error) not literal (blue, red)

### Don'ts
- ✗ Don't create one-off styles outside the design system
- ✗ Don't override design tokens at the component level
- ✗ Don't skip accessibility testing
- ✗ Don't modify tokens without considering impact
- ✗ Don't use pixel values directly - use spacing tokens

## Tooling Integration

### Figma
- Import design tokens using Token Studio plugin
- Components match specifications exactly
- Automatic theme switching supported

### Storybook
```javascript
// .storybook/preview.js
import { themes } from '@auraconnect/design-system/themes';

export const parameters = {
  themes: {
    default: 'light',
    list: [
      { name: 'light', class: 'theme-light', color: '#ffffff' },
      { name: 'dark', class: 'theme-dark', color: '#1c1f2e' },
    ],
  },
};
```

### VS Code
```json
// .vscode/settings.json
{
  "css.customData": ["./design-system/vscode-css-data.json"],
  "editor.quickSuggestions": {
    "other": true,
    "comments": false,
    "strings": true
  }
}
```

## Migration Guide

### From Legacy Styles

1. **Audit Current Styles**: Identify hard-coded values
2. **Map to Tokens**: Find equivalent design tokens
3. **Replace Values**: Update components to use tokens
4. **Test Thoroughly**: Verify visual consistency
5. **Remove Old Styles**: Clean up legacy code

### Version Updates

When design system updates are released:

1. Review changelog for breaking changes
2. Update token imports
3. Test affected components
4. Update theme overrides if needed
5. Run accessibility tests

## Contributing

### Adding New Tokens

1. Add to appropriate token file
2. Ensure theme compatibility
3. Document usage guidelines
4. Update component specs if needed

### Adding New Components

1. Create component specification
2. Include all required sections
3. Add accessibility requirements
4. Provide usage examples
5. Update this README

## Support

- **Documentation**: This README and component specs
- **Issues**: Report in project issue tracker
- **Questions**: Contact the design system team
- **Updates**: Follow changelog for version updates

## License

This design system is proprietary to AuraConnect. All rights reserved.