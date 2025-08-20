# Platform-Specific Adaptations Guide

> Guidelines for adapting the unified design language across Web, iOS, and Android platforms

## Table of Contents
1. [Platform Philosophy](#platform-philosophy)
2. [Admin Dashboard (Web)](#admin-dashboard-web)
3. [Mobile Apps (iOS/Android)](#mobile-apps-iosandroid)
4. [Customer Web (Responsive)](#customer-web-responsive)
5. [Cross-Platform Considerations](#cross-platform-considerations)

---

## Platform Philosophy

### Principle: Familiarity Over Consistency

While maintaining brand coherence, we prioritize platform conventions to ensure users feel at home in each environment.

```
Universal Brand Elements    Platform-Specific Elements
├── Colors                  ├── Navigation patterns
├── Typography scale        ├── Gesture interactions
├── Iconography            ├── System controls
├── Content tone           ├── Animation style
└── Core workflows         └── Native components
```

---

## Admin Dashboard (Web)

### Design Characteristics
- **Information density**: High
- **Interaction**: Mouse/keyboard primary
- **Screen size**: 1024px minimum
- **Context**: Professional environment

### Layout Specifications

#### Desktop Grid
```scss
.admin-layout {
  display: grid;
  grid-template-columns: 260px 1fr; // Sidebar + Content
  grid-template-rows: 64px 1fr;     // Header + Content
  min-height: 100vh;
  
  @media (max-width: 1024px) {
    grid-template-columns: 72px 1fr; // Collapsed sidebar
  }
  
  @media (max-width: 768px) {
    grid-template-columns: 1fr;      // Hidden sidebar
  }
}
```

#### Component Density
```javascript
const densityLevels = {
  comfortable: {
    rowHeight: 56,
    fontSize: 14,
    padding: 16
  },
  compact: {
    rowHeight: 44,
    fontSize: 13,
    padding: 12
  },
  dense: {
    rowHeight: 36,
    fontSize: 12,
    padding: 8
  }
};
```

### Navigation Patterns

#### Primary Navigation
```jsx
<Sidebar width={260} collapsible>
  <SidebarHeader>
    <Logo />
    <RestaurantName />
  </SidebarHeader>
  
  <SidebarNav>
    <NavGroup label="Operations">
      <NavItem icon="dashboard" label="Dashboard" badge={3} />
      <NavItem icon="orders" label="Orders" active />
      <NavItem icon="menu" label="Menu Management" />
    </NavGroup>
    
    <NavGroup label="Management">
      <NavItem icon="staff" label="Staff" />
      <NavItem icon="inventory" label="Inventory" />
      <NavItem icon="analytics" label="Analytics" />
    </NavGroup>
  </SidebarNav>
  
  <SidebarFooter>
    <UserProfile />
    <ThemeToggle />
  </SidebarFooter>
</Sidebar>
```

### Data Visualization

#### Table Enhancements
```jsx
<DataTable
  // Desktop-specific features
  columns={columns}
  data={data}
  
  // Advanced features
  columnResize
  columnReorder
  multiSort
  advancedFilters
  exportOptions={['CSV', 'PDF', 'Excel']}
  
  // Bulk operations
  bulkActions={[
    { label: 'Delete', icon: 'delete', action: bulkDelete },
    { label: 'Export', icon: 'download', action: bulkExport }
  ]}
  
  // Inline editing
  editable
  onCellEdit={handleCellEdit}
/>
```

#### Dashboard Widgets
```jsx
<DashboardGrid>
  <Widget span={[1, 2]}> {/* 1 row, 2 columns */}
    <RevenueChart />
  </Widget>
  
  <Widget>
    <MetricCard
      title="Today's Orders"
      value={156}
      change="+12%"
      sparkline={orderTrend}
    />
  </Widget>
  
  <Widget span={[2, 3]} resizable>
    <OrdersTable mini />
  </Widget>
</DashboardGrid>
```

### Keyboard Interactions

```javascript
const keyboardShortcuts = {
  'cmd+k': 'Open command palette',
  'cmd+/': 'Toggle search',
  'cmd+b': 'Toggle sidebar',
  'cmd+n': 'New order',
  'esc': 'Close modal/drawer',
  'tab': 'Navigate forward',
  'shift+tab': 'Navigate backward',
  'enter': 'Confirm action',
  'space': 'Toggle selection'
};
```

---

## Mobile Apps (iOS/Android)

### Design Characteristics
- **Information density**: Medium
- **Interaction**: Touch primary
- **Screen size**: 360px - 428px typical
- **Context**: On-the-go usage

### Platform Differentiation

#### iOS Specific
```javascript
const iosStyles = {
  // Navigation
  headerHeight: 44,
  headerLargeTitleHeight: 96,
  tabBarHeight: 49,
  
  // Typography
  fontFamily: 'System',
  textAlign: 'natural', // Respects RTL
  
  // Components
  switchStyle: 'ios',
  datePickerStyle: 'spinner',
  actionSheetStyle: 'ios',
  
  // Gestures
  swipeBackEnabled: true,
  pullToRefreshStyle: 'ios',
  
  // Haptics
  hapticFeedback: {
    selection: 'light',
    impact: 'medium',
    notification: 'success'
  }
};
```

#### Android Specific
```javascript
const androidStyles = {
  // Navigation
  headerHeight: 56,
  statusBarTranslucent: true,
  tabBarHeight: 56,
  
  // Typography
  fontFamily: 'Roboto',
  textAlign: 'left',
  
  // Components
  switchStyle: 'android',
  datePickerStyle: 'calendar',
  actionSheetStyle: 'bottomSheet',
  
  // Gestures
  swipeBackEnabled: false,
  pullToRefreshStyle: 'android',
  
  // Ripple effect
  rippleColor: 'rgba(0,0,0,0.12)',
  rippleBorderless: false
};
```

### Navigation Architecture

#### Tab Navigation
```jsx
// iOS Bottom Tabs
<TabNavigator
  screenOptions={{
    tabBarStyle: {
      height: 49,
      paddingBottom: 0
    },
    tabBarActiveTintColor: colors.primary,
    tabBarInactiveTintColor: colors.neutral
  }}
>
  <Tab.Screen name="Home" component={HomeScreen} />
  <Tab.Screen name="Orders" component={OrdersScreen} />
  <Tab.Screen name="Menu" component={MenuScreen} />
  <Tab.Screen name="More" component={MoreScreen} />
</TabNavigator>

// Android Bottom Navigation
<BottomNavigation
  shifting={false}
  labeled={true}
  activeColor={colors.primary}
  inactiveColor={colors.neutral}
  barStyle={{ height: 56 }}
/>
```

### Touch Targets

```javascript
const touchTargets = {
  minimum: 44, // iOS HIG minimum
  recommended: 48, // Comfortable for most users
  large: 56, // Accessibility mode
  
  // Spacing between targets
  spacing: 8,
  
  // Hit slop for small elements
  hitSlop: {
    top: 10,
    bottom: 10,
    left: 10,
    right: 10
  }
};
```

### Gesture Patterns

```jsx
// Swipeable List Items
<SwipeableRow
  leftActions={[
    {
      icon: 'check',
      color: 'success',
      onPress: markComplete,
      width: 75
    }
  ]}
  rightActions={[
    {
      icon: 'delete',
      color: 'error',
      onPress: deleteItem,
      width: 75
    }
  ]}
>
  <OrderItem />
</SwipeableRow>

// Pull to Refresh
<ScrollView
  refreshControl={
    <RefreshControl
      refreshing={refreshing}
      onRefresh={onRefresh}
      colors={[colors.primary]} // Android
      tintColor={colors.primary} // iOS
    />
  }
>
  {content}
</ScrollView>
```

### Offline Considerations

```jsx
<OfflineNotice>
  <View style={styles.offlineBanner}>
    <Icon name="wifi-off" />
    <Text>You're offline</Text>
    <Text style={styles.subtitle}>
      Changes will sync when connected
    </Text>
  </View>
</OfflineNotice>
```

---

## Customer Web (Responsive)

### Design Characteristics
- **Information density**: Variable
- **Interaction**: Touch + Mouse
- **Screen size**: 320px - 2560px
- **Context**: Consumer browsing

### Responsive Breakpoints

```scss
$breakpoints: (
  xs: 0,      // Phones portrait
  sm: 576px,  // Phones landscape
  md: 768px,  // Tablets portrait
  lg: 1024px, // Tablets landscape / Desktop
  xl: 1440px, // Large desktop
  xxl: 1920px // Extra large screens
);

@mixin respond-to($breakpoint) {
  @media (min-width: map-get($breakpoints, $breakpoint)) {
    @content;
  }
}
```

### Mobile-First Components

#### Responsive Card Grid
```scss
.menu-grid {
  display: grid;
  gap: 16px;
  grid-template-columns: 1fr;
  
  @include respond-to(sm) {
    grid-template-columns: repeat(2, 1fr);
  }
  
  @include respond-to(md) {
    gap: 24px;
    grid-template-columns: repeat(3, 1fr);
  }
  
  @include respond-to(lg) {
    grid-template-columns: repeat(4, 1fr);
  }
}
```

#### Progressive Enhancement
```jsx
// Base experience (works everywhere)
<MenuCard>
  <Image src={item.image} alt={item.name} />
  <Title>{item.name}</Title>
  <Description>{item.description}</Description>
  <Price>{item.price}</Price>
  <AddToCartButton />
</MenuCard>

// Enhanced experience (modern browsers)
if ('IntersectionObserver' in window) {
  // Lazy load images
  lazyLoadImages();
}

if ('serviceWorker' in navigator) {
  // Enable offline mode
  registerServiceWorker();
}

if (window.matchMedia('(hover: hover)').matches) {
  // Add hover effects for mouse users
  enableHoverEffects();
}
```

### Touch-Friendly Design

```scss
// Increase touch targets on touch devices
@media (pointer: coarse) {
  .button {
    min-height: 48px;
    padding: 12px 24px;
  }
  
  .link {
    padding: 8px;
    margin: -8px;
  }
  
  .input {
    height: 48px;
    font-size: 16px; // Prevents zoom on iOS
  }
}

// Disable hover effects on touch
@media (hover: none) {
  .card:hover {
    transform: none;
    box-shadow: none;
  }
}
```

### Performance Optimization

#### Critical CSS
```html
<style>
  /* Inline critical styles */
  .header { height: 64px; background: #fff; }
  .hero { min-height: 400px; }
  .menu-grid { display: grid; }
</style>

<!-- Load non-critical CSS asynchronously -->
<link rel="preload" href="styles.css" as="style" onload="this.onload=null;this.rel='stylesheet'">
```

#### Image Optimization
```jsx
<Picture>
  <source
    media="(max-width: 768px)"
    srcSet="image-mobile.webp"
    type="image/webp"
  />
  <source
    media="(max-width: 768px)"
    srcSet="image-mobile.jpg"
    type="image/jpeg"
  />
  <source
    srcSet="image-desktop.webp"
    type="image/webp"
  />
  <img
    src="image-desktop.jpg"
    alt="Description"
    loading="lazy"
    decoding="async"
  />
</Picture>
```

---

## Cross-Platform Considerations

### Shared Design Tokens

```javascript
// tokens/index.js - Shared across all platforms
export const tokens = {
  colors: {
    primary: '#5D87FF',
    // ... platform agnostic colors
  },
  spacing: {
    small: 8,
    medium: 16,
    large: 24
  },
  typography: {
    scale: [12, 14, 16, 18, 20, 24, 30, 36, 48]
  }
};

// Platform-specific exports
export const webTokens = {
  ...tokens,
  spacing: mapToRem(tokens.spacing)
};

export const mobileTokens = {
  ...tokens,
  typography: {
    ...tokens.typography,
    fontFamily: Platform.select({
      ios: 'System',
      android: 'Roboto'
    })
  }
};
```

### Component API Consistency

```typescript
// Shared component interface
interface ButtonProps {
  variant: 'primary' | 'secondary' | 'danger';
  size: 'small' | 'medium' | 'large';
  disabled?: boolean;
  loading?: boolean;
  fullWidth?: boolean;
  onPress: () => void;
  children: React.ReactNode;
}

// Web implementation
export const WebButton: React.FC<ButtonProps> = (props) => {
  return <button className={getClassName(props)} {...props} />;
};

// Mobile implementation
export const MobileButton: React.FC<ButtonProps> = (props) => {
  return <TouchableOpacity style={getStyle(props)} {...props} />;
};
```

### Accessibility Standards

```javascript
const a11yStandards = {
  // Color contrast
  textContrast: {
    normal: 4.5, // WCAG AA
    large: 3.0,  // WCAG AA for large text
    enhanced: 7.0 // WCAG AAA
  },
  
  // Touch targets
  touchTarget: {
    ios: 44,
    android: 48,
    web: 44
  },
  
  // Focus indicators
  focusIndicator: {
    width: 3,
    color: tokens.colors.primary,
    offset: 2
  },
  
  // Screen reader support
  semanticHTML: true,
  ariaLabels: true,
  roleAttributes: true
};
```

### Testing Strategy

```javascript
// Visual regression testing
const visualTests = {
  platforms: ['web-chrome', 'web-safari', 'ios', 'android'],
  viewports: [
    { width: 375, height: 667 },  // iPhone 8
    { width: 414, height: 896 },  // iPhone 11
    { width: 768, height: 1024 }, // iPad
    { width: 1440, height: 900 }  // Desktop
  ],
  themes: ['light', 'dark']
};

// Interaction testing
const interactionTests = {
  touch: ['tap', 'swipe', 'pinch', 'long-press'],
  mouse: ['click', 'hover', 'right-click', 'drag'],
  keyboard: ['tab', 'enter', 'escape', 'arrows']
};
```

---

## Platform Feature Matrix

| Feature | Admin Web | Mobile iOS | Mobile Android | Customer Web |
|---------|-----------|------------|----------------|--------------|
| Dark Mode | ✅ | ✅ | ✅ | ✅ |
| Offline Support | Partial | ✅ | ✅ | ✅ PWA |
| Push Notifications | Browser | ✅ | ✅ | Browser |
| Biometric Auth | ❌ | ✅ | ✅ | WebAuthn |
| Keyboard Shortcuts | ✅ | ❌ | ❌ | ✅ |
| Drag & Drop | ✅ | Limited | Limited | Touch/Mouse |
| File Upload | ✅ | Camera/Gallery | Camera/Gallery | ✅ |
| Printing | ✅ | AirPrint | Cloud Print | ✅ |
| Deep Linking | ✅ | ✅ | ✅ | ✅ |
| Analytics | Full | Full | Full | Full |

---

*Platform Adaptations Guide v1.0.0*
*Last Updated: August 19, 2025*