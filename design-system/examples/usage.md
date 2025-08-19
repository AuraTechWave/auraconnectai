# Design System Usage Examples

## Installation

```bash
npm install @auraconnect/design-system
```

## Basic Usage

### 1. Import CSS Variables

```html
<!-- In your HTML -->
<link rel="stylesheet" href="node_modules/@auraconnect/design-system/dist/css/tokens.css">
```

### 2. JavaScript/React Usage

```javascript
import { tokens, lightTheme, darkTheme, applyTheme } from '@auraconnect/design-system';

// Apply light theme
applyTheme(lightTheme);

// Toggle to dark theme
applyTheme(darkTheme);

// Access raw tokens
console.log(tokens.colors.semantic.primary.base); // "#5D87FF"
```

### 3. React Component Example

```jsx
import React from 'react';
import { tokens } from '@auraconnect/design-system';
import buttonSpec from '@auraconnect/design-system/components/button.json';

const Button = ({ 
  variant = 'contained', 
  size = 'medium', 
  color = 'primary',
  children,
  ...props 
}) => {
  const baseStyles = buttonSpec.button.variants[variant].styles.base;
  const sizeStyles = buttonSpec.button.sizes[size];
  const colorStyles = buttonSpec.button.colors[color][variant];
  
  // Resolve token references
  const resolveTokens = (styles) => {
    return Object.entries(styles).reduce((acc, [key, value]) => {
      if (typeof value === 'string' && value.startsWith('$')) {
        // This would be handled by your build process
        // For now, you'd map these to CSS variables
        acc[key] = `var(--${value.replace('$', '').replace(/\./g, '-')})`;
      } else {
        acc[key] = value;
      }
      return acc;
    }, {});
  };
  
  const style = {
    ...resolveTokens(baseStyles),
    ...resolveTokens(sizeStyles),
    ...resolveTokens(colorStyles),
  };
  
  return (
    <button style={style} {...props}>
      {children}
    </button>
  );
};
```

### 4. Tailwind Integration

```javascript
// tailwind.config.js
module.exports = {
  presets: [
    require('@auraconnect/design-system/dist/tailwind.preset.js')
  ],
  // Your custom config...
}
```

### 5. Theme Switching

```javascript
import { lightTheme, darkTheme, applyTheme } from '@auraconnect/design-system';

// Simple theme switcher
function ThemeSwitcher() {
  const [isDark, setIsDark] = useState(false);
  
  useEffect(() => {
    applyTheme(isDark ? darkTheme : lightTheme);
  }, [isDark]);
  
  return (
    <button onClick={() => setIsDark(!isDark)}>
      Switch to {isDark ? 'Light' : 'Dark'} Theme
    </button>
  );
}
```

### 6. CSS Usage

```css
/* Use CSS variables generated from tokens */
.my-component {
  background: var(--colors-semantic-background-primary);
  color: var(--colors-semantic-text-primary);
  padding: var(--spacing-component-padding-md);
  border-radius: var(--borders-radius-md);
  font-family: var(--typography-fontFamily-primary);
}

/* Dark theme automatically handled */
[data-theme="dark"] .my-component {
  /* Variables automatically update */
}
```

### 7. TypeScript Support

```typescript
import { DesignTokens, Theme } from '@auraconnect/design-system';

// Fully typed tokens
const primaryColor: string = tokens.colors.semantic.primary.base;

// Type-safe theme application
function applyCustomTheme(theme: Theme) {
  // Implementation
}
```

## Best Practices

1. **Always use tokens** - Never hard-code values
2. **Support all themes** - Test in light and dark modes
3. **Follow accessibility** - Use proper contrast ratios
4. **Semantic naming** - Use `primary` not `blue`
5. **Component specs** - Follow the anatomy defined in JSON files

## Build Your Own Components

```javascript
// Example: Building a Card component from specs
import cardSpec from '@auraconnect/design-system/components/card.json';

const Card = ({ variant = 'elevated', children }) => {
  const { base, hover } = cardSpec.card.variants[variant].styles;
  
  return (
    <div 
      className="card"
      style={base}
      onMouseEnter={(e) => Object.assign(e.target.style, hover)}
      onMouseLeave={(e) => Object.assign(e.target.style, base)}
    >
      {children}
    </div>
  );
};
```