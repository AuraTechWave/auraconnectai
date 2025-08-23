# Design System Migration Guide

This guide helps you migrate from legacy components to the new AuraConnect Design System.

## Overview

The new design system provides:
- ✅ Consistent visual language across all platforms
- ✅ Full accessibility support (WCAG AA compliant)
- ✅ Type-safe components with TypeScript
- ✅ Performance optimizations
- ✅ Centralized design tokens

## Migration Steps

### 1. Update Imports

Replace individual component imports with the centralized UI module:

```tsx
// Before
import Button from '../components/Button';
import TextInput from '../components/TextInput';
import Badge from '../components/Badge';

// After
import { Button, Input, Badge } from '@/components/ui';
```

### 2. Component Mapping

#### Button Migration

```tsx
// Before
<TouchableOpacity 
  style={[styles.button, styles.primaryButton]} 
  onPress={handlePress}
>
  <Text style={styles.buttonText}>Submit</Text>
</TouchableOpacity>

// After
<Button 
  title="Submit"
  variant="primary"
  onPress={handlePress}
  accessibilityLabel="Submit form"
/>
```

**Key Changes:**
- Use `variant` prop instead of custom styles
- Add accessibility props
- Icon support built-in
- Loading state handled automatically

#### Input Migration

```tsx
// Before
<TextInput
  style={styles.input}
  placeholder="Enter email"
  value={email}
  onChangeText={setEmail}
/>
{emailError && <Text style={styles.error}>{emailError}</Text>}

// After
<Input
  label="Email"
  placeholder="Enter email"
  value={email}
  onChangeText={setEmail}
  error={emailError}
  leftIcon="email"
  keyboardType="email-address"
  accessibilityLabel="Email address"
/>
```

**Key Changes:**
- Built-in label animation
- Error/helper text included
- Icon support
- Variants for different styles

#### Badge Migration

```tsx
// Before
<View style={styles.badge}>
  <Text style={styles.badgeText}>3</Text>
</View>

// After
<Badge label="3" variant="primary" size="medium" />

// With container
<BadgeContainer badge={<Badge label="3" variant="error" />}>
  <Icon name="bell" size={24} />
</BadgeContainer>
```

### 3. Style Migration

Replace hardcoded values with design tokens:

```tsx
// Before
const styles = StyleSheet.create({
  container: {
    padding: 16,
    backgroundColor: '#FFFFFF',
    borderRadius: 8,
  },
  text: {
    fontSize: 14,
    color: '#333333',
    marginBottom: 8,
  },
});

// After
import { colors, spacing, typography, borderRadius } from '@/components/ui';

const styles = StyleSheet.create({
  container: {
    padding: spacing.md,
    backgroundColor: colors.background.primary,
    borderRadius: borderRadius.md,
  },
  text: {
    fontSize: typography.fontSize.body,
    color: colors.text.primary,
    marginBottom: spacing.sm,
  },
});
```

### 4. Accessibility Updates

Add proper accessibility attributes to all interactive elements:

```tsx
// Before
<TouchableOpacity onPress={handleDelete}>
  <Icon name="trash" color="red" />
</TouchableOpacity>

// After
<TouchableOpacity 
  onPress={handleDelete}
  accessible={true}
  accessibilityRole="button"
  accessibilityLabel="Delete item"
  accessibilityHint="Double tap to delete this item permanently"
>
  <Icon name="trash" color={colors.error[500]} />
</TouchableOpacity>
```

### 5. Form Migration Example

Complete form migration example:

```tsx
// Before
const OldLoginForm = () => {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [errors, setErrors] = useState({});
  const [loading, setLoading] = useState(false);

  return (
    <View style={styles.form}>
      <Text style={styles.label}>Email</Text>
      <TextInput
        style={[styles.input, errors.email && styles.inputError]}
        placeholder="Enter email"
        value={email}
        onChangeText={setEmail}
        keyboardType="email-address"
      />
      {errors.email && <Text style={styles.error}>{errors.email}</Text>}
      
      <Text style={styles.label}>Password</Text>
      <TextInput
        style={[styles.input, errors.password && styles.inputError]}
        placeholder="Enter password"
        value={password}
        onChangeText={setPassword}
        secureTextEntry
      />
      {errors.password && <Text style={styles.error}>{errors.password}</Text>}
      
      <TouchableOpacity 
        style={[styles.button, loading && styles.buttonDisabled]}
        onPress={handleSubmit}
        disabled={loading}
      >
        {loading ? (
          <ActivityIndicator color="white" />
        ) : (
          <Text style={styles.buttonText}>Sign In</Text>
        )}
      </TouchableOpacity>
    </View>
  );
};

// After
const NewLoginForm = () => {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [errors, setErrors] = useState({});
  const [loading, setLoading] = useState(false);

  return (
    <View style={styles.form}>
      <Input
        label="Email"
        placeholder="Enter your email"
        value={email}
        onChangeText={setEmail}
        error={errors.email}
        leftIcon="email"
        keyboardType="email-address"
        autoCapitalize="none"
        accessibilityLabel="Email address"
        style={styles.input}
      />
      
      <Input
        label="Password"
        placeholder="Enter your password"
        value={password}
        onChangeText={setPassword}
        error={errors.password}
        leftIcon="lock"
        rightIcon={showPassword ? "eye-off" : "eye"}
        onRightIconPress={() => setShowPassword(!showPassword)}
        secureTextEntry={!showPassword}
        accessibilityLabel="Password"
        style={styles.input}
      />
      
      <Button
        title="Sign In"
        variant="primary"
        size="large"
        fullWidth
        loading={loading}
        onPress={handleSubmit}
        accessibilityLabel="Sign in to your account"
        style={styles.button}
      />
    </View>
  );
};
```

### 6. Screen Migration Example

```tsx
// After migration
import React from 'react';
import {
  SafeAreaView,
  ScrollView,
  View,
  Text,
} from 'react-native';
import {
  Button,
  Input,
  Card,
  Badge,
  colors,
  spacing,
  typography,
} from '@/components/ui';

const OrdersScreen = () => {
  return (
    <SafeAreaView style={styles.container}>
      <ScrollView>
        <View style={styles.header}>
          <Text style={styles.title}>Orders</Text>
          <Badge label="3 New" variant="primary" />
        </View>
        
        {orders.map(order => (
          <Card 
            key={order.id} 
            onPress={() => navigateToOrder(order.id)}
            style={styles.orderCard}
          >
            <Card.Header>
              <View style={styles.orderHeader}>
                <Text style={styles.orderId}>#{order.id}</Text>
                <Badge 
                  label={order.status} 
                  variant={getStatusVariant(order.status)}
                  size="small"
                />
              </View>
            </Card.Header>
            <Card.Content>
              <Text style={styles.customerName}>{order.customerName}</Text>
              <Text style={styles.orderTotal}>${order.total}</Text>
            </Card.Content>
            <Card.Footer>
              <Button
                title="View Details"
                variant="outline"
                size="small"
                icon="chevron-right"
                iconPosition="right"
              />
            </Card.Footer>
          </Card>
        ))}
      </ScrollView>
    </SafeAreaView>
  );
};

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: colors.background.primary,
  },
  header: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    padding: spacing.lg,
  },
  title: {
    fontSize: typography.fontSize.h4,
    fontWeight: typography.fontWeight.bold,
    color: colors.text.primary,
  },
  orderCard: {
    marginHorizontal: spacing.lg,
    marginBottom: spacing.md,
  },
  orderHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
  },
  orderId: {
    fontSize: typography.fontSize.body,
    fontWeight: typography.fontWeight.semiBold,
    color: colors.text.primary,
  },
  customerName: {
    fontSize: typography.fontSize.body,
    color: colors.text.secondary,
    marginBottom: spacing.xs,
  },
  orderTotal: {
    fontSize: typography.fontSize.bodyLarge,
    fontWeight: typography.fontWeight.semiBold,
    color: colors.text.primary,
  },
});
```

## Migration Checklist

- [ ] Update all component imports
- [ ] Replace custom buttons with Button component
- [ ] Replace TextInput with Input component
- [ ] Update badge implementations
- [ ] Replace hardcoded colors with design tokens
- [ ] Replace hardcoded spacing with design tokens
- [ ] Add accessibility props to all interactive elements
- [ ] Test with screen reader (iOS VoiceOver / Android TalkBack)
- [ ] Verify touch targets are at least 44x44
- [ ] Update form validations to use built-in error states
- [ ] Test on both iOS and Android
- [ ] Update unit tests
- [ ] Update documentation

## Common Pitfalls

1. **Don't mix old and new styles** - Fully migrate components rather than partial updates
2. **Don't skip accessibility** - It's required, not optional
3. **Use semantic variants** - Don't override component colors directly
4. **Test loading states** - Ensure loading indicators work correctly
5. **Verify icon names** - Material Community Icons may have different names

## Getting Help

- Review the [Component Documentation](./mobile/src/components/ui/README.md)
- Check the [Component Showcase](./mobile/src/screens/showcase/ComponentShowcaseScreen.tsx)
- Run tests: `npm test src/components/ui`
- Ask in #design-system Slack channel

## Gradual Migration Strategy

If you can't migrate everything at once:

1. **Phase 1**: Migrate shared components (buttons, inputs)
2. **Phase 2**: Migrate screen layouts and navigation
3. **Phase 3**: Update forms and complex interactions
4. **Phase 4**: Polish with animations and micro-interactions

Track progress with:
```bash
# Find components still using old patterns
grep -r "TouchableOpacity" src/ | grep -v "components/ui"
grep -r "TextInput" src/ | grep -v "components/ui"
```

## Performance Improvements

The new design system includes:
- Memoized style calculations
- Optimized re-renders
- Lazy-loaded icons
- Reduced bundle size through tree-shaking

Measure improvements:
```tsx
// Add performance monitoring
import { PerformanceObserver } from 'react-native-performance';

// Before migration
const beforeMetrics = await measureComponentRender(<OldComponent />);

// After migration  
const afterMetrics = await measureComponentRender(<NewComponent />);

console.log('Render time improvement:', 
  ((beforeMetrics - afterMetrics) / beforeMetrics * 100).toFixed(2) + '%'
);
```