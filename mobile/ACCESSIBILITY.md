# React Native Accessibility Guidelines

## Overview

This document provides accessibility guidelines for the AuraConnect mobile application to ensure it's usable by everyone, including people with disabilities.

## Core Principles

1. **Perceivable** - Information must be presentable in ways users can perceive
2. **Operable** - Interface components must be operable
3. **Understandable** - Information and UI operation must be understandable
4. **Robust** - Content must be robust enough for various assistive technologies

## Required Accessibility Props

### Interactive Elements

All interactive elements (buttons, links, touchables) MUST have:

```tsx
<TouchableOpacity
  accessible={true}
  accessibilityLabel="Submit order"
  accessibilityHint="Double tap to submit the current order"
  accessibilityRole="button"
>
```

### Form Inputs

All form inputs MUST have:

```tsx
<TextInput
  accessible={true}
  accessibilityLabel="Email address"
  accessibilityHint="Enter your email address"
  placeholder="email@example.com"
/>
```

### Images

All images MUST have either:
- `accessibilityLabel` for informative images
- `accessibilityElementsHidden={true}` for decorative images

```tsx
// Informative image
<Image
  source={orderIcon}
  accessibilityLabel="Order status: preparing"
/>

// Decorative image
<Image
  source={backgroundPattern}
  accessibilityElementsHidden={true}
  importantForAccessibility="no"
/>
```

## Minimum Touch Target Size

All interactive elements must have a minimum touch target size of 44x44 points:

```tsx
const styles = StyleSheet.create({
  button: {
    minHeight: 44,
    minWidth: 44,
    // ... other styles
  }
});
```

## Color Contrast Requirements

- **Normal text**: 4.5:1 contrast ratio
- **Large text** (18pt+): 3:1 contrast ratio
- **UI components**: 3:1 contrast ratio

Use the design system colors which are pre-validated for accessibility:

```tsx
import { colors } from '../constants/designSystem';

// Use validated color combinations
<Text style={{ color: colors.text.primary, backgroundColor: colors.background.primary }}>
```

## Dynamic Content

For content that updates dynamically, use `accessibilityLiveRegion`:

```tsx
<View accessibilityLiveRegion="polite">
  <Text>{orderStatus}</Text>
</View>
```

## Focus Management

For modals and overlays, use `accessibilityViewIsModal` (iOS):

```tsx
<Modal
  visible={isVisible}
  accessibilityViewIsModal={true}
>
```

## State Communication

Communicate component state to screen readers:

```tsx
<Switch
  value={isEnabled}
  accessibilityLabel="Notifications"
  accessibilityState={{
    checked: isEnabled,
    disabled: false,
  }}
/>
```

## Grouping Related Content

Group related elements for better navigation:

```tsx
<View accessible={true} accessibilityLabel="Order #123, 2 items, $25.99">
  <Text>Order #123</Text>
  <Text>2 items</Text>
  <Text>$25.99</Text>
</View>
```

## Testing Accessibility

### iOS (VoiceOver)
1. Settings → Accessibility → VoiceOver
2. Triple-click home/side button to toggle
3. Swipe right/left to navigate
4. Double-tap to activate

### Android (TalkBack)
1. Settings → Accessibility → TalkBack
2. Volume key shortcut to toggle
3. Swipe right/left to navigate
4. Double-tap to activate

### Automated Testing

Run accessibility tests:
```bash
npm run lint
```

Use accessibility test utilities:
```tsx
import { a11yTestHelpers } from '../utils/accessibility';

// In tests
expect(a11yTestHelpers.hasMinimumAccessibility(props)).toBe(true);
expect(a11yTestHelpers.hasMinimumTouchTarget(styles)).toBe(true);
```

## Common Patterns

### Loading States
```tsx
<View accessibilityLiveRegion="polite">
  {loading ? (
    <ActivityIndicator accessibilityLabel="Loading orders" />
  ) : (
    <OrderList />
  )}
</View>
```

### Error Messages
```tsx
{error && (
  <Text
    accessibilityLiveRegion="assertive"
    accessibilityRole="alert"
    style={styles.error}
  >
    {error}
  </Text>
)}
```

### Lists
```tsx
<FlatList
  data={orders}
  renderItem={({ item, index }) => (
    <OrderItem
      order={item}
      accessibilityLabel={`Order ${index + 1} of ${orders.length}`}
    />
  )}
/>
```

## Utility Functions

Use the provided accessibility utilities:

```tsx
import {
  createAccessibilityLabel,
  createAccessibleButtonProps,
  announceForAccessibility,
} from '../utils/accessibility';

// Create complex labels
const label = createAccessibilityLabel('Order', '#123', 'Preparing');

// Button props helper
const buttonProps = createAccessibleButtonProps(
  'Submit order',
  'Double tap to submit the current order'
);

// Announce changes
announceForAccessibility('Order submitted successfully');
```

## Checklist

Before submitting code, ensure:

- [ ] All interactive elements have `accessibilityLabel`
- [ ] Complex interactions have `accessibilityHint`
- [ ] Touch targets are at least 44x44 points
- [ ] Colors meet contrast requirements
- [ ] Dynamic content uses `accessibilityLiveRegion`
- [ ] Related content is properly grouped
- [ ] Tested with VoiceOver/TalkBack
- [ ] No ESLint accessibility warnings

## Resources

- [React Native Accessibility Docs](https://reactnative.dev/docs/accessibility)
- [iOS Accessibility Guidelines](https://developer.apple.com/accessibility/)
- [Android Accessibility Guidelines](https://developer.android.com/guide/topics/ui/accessibility)
- [WCAG 2.1 Guidelines](https://www.w3.org/WAI/WCAG21/quickref/)