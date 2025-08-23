# AuraConnect Mobile Design System

## Overview

The AuraConnect Mobile Design System provides a comprehensive set of React Native components that ensure visual consistency and accessibility across the mobile application. This system is built with performance, accessibility, and developer experience in mind.

## Core Principles

1. **Consistency**: All components follow the same design patterns and visual language
2. **Accessibility**: WCAG AA compliant with full screen reader support
3. **Performance**: Optimized for React Native with minimal re-renders
4. **Flexibility**: Components are composable and customizable
5. **Type Safety**: Full TypeScript support with proper type definitions

## Components

### Button

A versatile button component with multiple variants and states.

```tsx
import { Button } from '@/components/ui';

// Basic usage
<Button title="Click me" onPress={handlePress} />

// With variants
<Button 
  title="Primary Action" 
  variant="primary"
  size="large"
  icon="check"
  iconPosition="left"
  loading={isLoading}
  disabled={isDisabled}
  fullWidth
  accessibilityLabel="Confirm your order"
  accessibilityHint="Double tap to place the order"
/>
```

**Props:**
- `variant`: 'primary' | 'secondary' | 'tertiary' | 'danger' | 'ghost' | 'outline'
- `size`: 'small' | 'medium' | 'large'
- `icon`: Material Community Icons name
- `iconPosition`: 'left' | 'right'
- `loading`: Shows loading spinner
- `disabled`: Disables interaction
- `fullWidth`: Takes full container width
- `accessibilityLabel`: Screen reader label
- `accessibilityHint`: Screen reader hint

### Input

A flexible input component with built-in validation states and accessibility.

```tsx
import { Input } from '@/components/ui';

// Basic usage
<Input 
  label="Email"
  placeholder="Enter your email"
  value={email}
  onChangeText={setEmail}
  error={emailError}
  helper="We'll never share your email"
  leftIcon="email"
  variant="outlined"
  accessibilityLabel="Email address input"
/>
```

**Props:**
- `variant`: 'outlined' | 'filled' | 'underlined'
- `size`: 'small' | 'medium' | 'large'
- `label`: Floating label text
- `error`: Error message (shows in red)
- `helper`: Helper text (shows below input)
- `leftIcon`/`rightIcon`: Material Community Icons
- `disabled`: Disables input
- Full TextInput props support

### Badge

A notification badge component for displaying counts or status indicators.

```tsx
import { Badge, BadgeContainer } from '@/components/ui';

// Simple badge
<Badge label="3" variant="primary" />

// Badge with container
<BadgeContainer badge={<Badge label="New" variant="success" />}>
  <Icon name="bell" size={24} />
</BadgeContainer>
```

**Props:**
- `variant`: 'default' | 'primary' | 'secondary' | 'success' | 'warning' | 'error' | 'info'
- `size`: 'small' | 'medium' | 'large'
- `dot`: Shows as a dot without label
- `position`: 'top-left' | 'top-right' | 'bottom-left' | 'bottom-right'

### Card

A container component with optional header and footer sections.

```tsx
import { Card } from '@/components/ui';

<Card onPress={handleCardPress}>
  <Card.Header>
    <Text>Card Title</Text>
  </Card.Header>
  <Card.Content>
    <Text>Card content goes here</Text>
  </Card.Content>
  <Card.Footer>
    <Button title="Action" size="small" />
  </Card.Footer>
</Card>
```

### Avatar

User avatar component with image or initials support.

```tsx
import { Avatar } from '@/components/ui';

// With image
<Avatar 
  source={{ uri: userImageUrl }}
  size="large"
  onPress={handleAvatarPress}
/>

// With initials
<Avatar 
  name="John Doe"
  size="medium"
  backgroundColor={colors.primary[500]}
/>
```

## Design Tokens

The design system uses a centralized token system defined in `constants/designSystem.ts`:

### Colors
- **Primary**: Brand colors for main actions
- **Secondary**: Supporting brand colors
- **Neutral**: Grays for backgrounds and borders
- **Semantic**: Success, warning, error, info colors
- **Text**: Hierarchical text colors

### Spacing
- `xxs`: 2px
- `xs`: 4px
- `sm`: 8px
- `md`: 16px
- `lg`: 24px
- `xl`: 32px
- `xxl`: 48px

### Typography
- Font sizes: tiny (10px) to display (48px)
- Font weights: light (300) to bold (700)
- Line heights: Calculated for optimal readability

### Border Radius
- `none`: 0px
- `sm`: 4px
- `md`: 8px
- `lg`: 12px
- `xl`: 16px
- `full`: 9999px

### Shadows
Pre-defined elevation levels for consistent depth perception.

## Accessibility

All components include:

1. **Screen Reader Support**
   - Proper `accessibilityRole` attributes
   - Customizable `accessibilityLabel` and `accessibilityHint`
   - Dynamic `accessibilityState` for interactive elements

2. **Touch Targets**
   - Minimum 44x44 touch targets
   - Proper hit slop for smaller elements

3. **Visual Indicators**
   - Focus states
   - Loading states
   - Disabled states with reduced opacity

4. **Semantic HTML**
   - Proper role assignments
   - Live regions for dynamic content

## Performance Considerations

1. **Memoization**: Components use React.memo where appropriate
2. **Optimized Styles**: Styles are pre-computed and cached
3. **Lazy Loading**: Icons are loaded on demand
4. **Minimal Re-renders**: Proper prop comparison and state management

## Theming

The design system supports multiple themes:

```tsx
// In your app root
import { ThemeProvider } from '@/components/ui';
import { lightTheme, darkTheme } from '@/constants/themes';

<ThemeProvider theme={isDarkMode ? darkTheme : lightTheme}>
  <App />
</ThemeProvider>
```

## Migration Guide

### From Legacy Components

| Legacy Component | New Component | Migration Notes |
|-----------------|---------------|-----------------|
| `OldButton` | `Button` | Update variant names, add accessibility props |
| `TextInput` | `Input` | Add label, use variant prop instead of style |
| `BadgeView` | `Badge` | Use BadgeContainer for positioning |

### Example Migration

```tsx
// Before
<TouchableOpacity style={styles.button} onPress={onPress}>
  <Text style={styles.buttonText}>Submit</Text>
</TouchableOpacity>

// After
<Button 
  title="Submit" 
  variant="primary"
  onPress={onPress}
  accessibilityLabel="Submit form"
/>
```

## Best Practices

1. **Always provide accessibility labels** for interactive elements
2. **Use semantic variants** instead of custom colors
3. **Prefer composition** over prop drilling
4. **Test on both platforms** (iOS and Android)
5. **Use proper loading states** for async operations

## Testing

Components include comprehensive test coverage:

```bash
# Run all UI component tests
npm test src/components/ui

# Run specific component tests
npm test src/components/ui/__tests__/Button.test.tsx
```

## Contributing

When adding new components:

1. Follow the existing component structure
2. Include TypeScript definitions
3. Add comprehensive tests
4. Document all props
5. Ensure accessibility compliance
6. Add examples to this README

## Future Enhancements

- [ ] Style Dictionary integration for multi-platform token generation
- [ ] Storybook for web documentation
- [ ] Visual regression testing with Percy
- [ ] Animation presets
- [ ] Haptic feedback integration
- [ ] Dark mode optimizations