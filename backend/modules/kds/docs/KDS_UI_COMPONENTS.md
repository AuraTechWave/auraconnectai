# KDS UI Component Specifications

## Overview
This document outlines the UI components needed for the Kitchen Display System touchscreen interface. The components are designed for kitchen environments with:
- Large touch targets (minimum 44x44px)
- High contrast for visibility
- Clear visual feedback
- Minimal text input
- Gesture support

## Core Components

### 1. KDSItemTile

**Purpose**: Display individual order items with touch interactions

```typescript
interface KDSItemTileProps {
  item: {
    id: number;
    orderNumber: string;
    tableNumber?: number;
    displayName: string;
    quantity: number;
    modifiers: string[];
    specialInstructions?: string;
    status: 'pending' | 'in_progress' | 'ready' | 'recalled';
    priority: 'normal' | 'high' | 'urgent';
    courseNumber: number;
    elapsedTime: number; // seconds
    targetTime?: number; // seconds
  };
  
  onStatusChange: (itemId: number, newStatus: string) => void;
  onExpand: (itemId: number) => void;
  
  config: {
    size: 'small' | 'medium' | 'large' | 'xl';
    showTimers: boolean;
    colorScheme: ColorScheme;
  };
}
```

**Visual Design**:
```
┌─────────────────────────────────┐
│ #234  Table 5      🕐 5:23      │  <- Header (order, table, timer)
├─────────────────────────────────┤
│ 2x Cheeseburger                 │  <- Item name & quantity
│ • No onions                     │  <- Modifiers
│ • Extra cheese                  │
│ • Medium rare                   │
├─────────────────────────────────┤
│ "Gluten free bun please"        │  <- Special instructions
└─────────────────────────────────┘
```

**States**:
- **Pending**: Gray background, pulsing border
- **In Progress**: Blue background, solid border
- **Ready**: Green background, checkmark icon
- **Late**: Orange background, warning icon
- **Critical**: Red background, alert icon

**Gestures**:
- **Tap**: Expand for details
- **Swipe Right**: Mark as complete
- **Swipe Left**: Show actions menu
- **Long Press**: Quick status change

### 2. KDSStationHeader

**Purpose**: Display station information and statistics

```typescript
interface KDSStationHeaderProps {
  station: {
    id: number;
    name: string;
    type: string;
    status: 'active' | 'busy' | 'offline';
    currentStaff?: string;
    activeItems: number;
    pendingItems: number;
    averagePrepTime: number; // minutes
  };
  
  onStaffChange: () => void;
  onFilterToggle: () => void;
}
```

**Visual Design**:
```
┌────────────────────────────────────────────┐
│ 🍳 GRILL STATION 1          Chef: Maria    │
│ Active: 5  Pending: 8  Avg: 12min         │
└────────────────────────────────────────────┘
```

### 3. KDSFilterBar

**Purpose**: Quick filtering and sorting options

```typescript
interface KDSFilterBarProps {
  filters: {
    status: string[];
    course: number[];
    priority: string[];
    server?: string;
  };
  
  onFilterChange: (filters: Filters) => void;
  onSortChange: (sortBy: string) => void;
  onSearch: (query: string) => void;
}
```

**Visual Design**:
```
┌─────────────────────────────────────────────────┐
│ [All] [Pending] [Active] [Ready] | 🔍 Search    │
│ [Course 1] [Course 2] [Course 3] | Sort: Time ▼ │
└─────────────────────────────────────────────────┘
```

### 4. KDSActionSheet

**Purpose**: Quick actions for items

```typescript
interface KDSActionSheetProps {
  itemId: number;
  currentStatus: string;
  
  actions: Array<{
    label: string;
    icon: string;
    action: string;
    destructive?: boolean;
  }>;
  
  onAction: (itemId: number, action: string) => void;
  onDismiss: () => void;
}
```

**Actions**:
- Start Cooking (for pending items)
- Mark Ready (for in-progress items)
- Recall (for completed items)
- Add Note
- Print Ticket
- Cancel Item

### 5. KDSTimerDisplay

**Purpose**: Show elapsed and remaining time

```typescript
interface KDSTimerDisplayProps {
  elapsedTime: number; // seconds
  targetTime?: number; // seconds
  
  warningThreshold: number; // minutes
  criticalThreshold: number; // minutes
  
  size: 'small' | 'large';
  showTargetTime: boolean;
}
```

**Visual States**:
- **Normal**: Green text (0-5 min)
- **Warning**: Orange text (5-10 min)
- **Critical**: Red text, blinking (10+ min)

## Layout Templates

### Grid Layout (Default)
```
┌─────────┬─────────┬─────────┐
│  Item   │  Item   │  Item   │
├─────────┼─────────┼─────────┤
│  Item   │  Item   │  Item   │
└─────────┴─────────┴─────────┘
```

### List Layout
```
┌─────────────────────────────┐
│  Item 1                     │
├─────────────────────────────┤
│  Item 2                     │
├─────────────────────────────┤
│  Item 3                     │
└─────────────────────────────┘
```

### Single Item Focus
```
┌─────────────────────────────┐
│                             │
│       Large Item View       │
│                             │
└─────────────────────────────┘
```

## Color Schemes

### Default Theme
```css
:root {
  --kds-pending: #6B7280;      /* Gray */
  --kds-in-progress: #3B82F6;  /* Blue */
  --kds-ready: #10B981;        /* Green */
  --kds-late: #F59E0B;         /* Orange */
  --kds-critical: #EF4444;     /* Red */
  --kds-recalled: #8B5CF6;     /* Purple */
}
```

### High Contrast Theme
```css
:root {
  --kds-pending: #000000;      /* Black */
  --kds-in-progress: #0000FF;  /* Blue */
  --kds-ready: #00FF00;        /* Green */
  --kds-late: #FFFF00;         /* Yellow */
  --kds-critical: #FF0000;     /* Red */
  --kds-recalled: #FF00FF;     /* Magenta */
}
```

## Accessibility Features

1. **Touch Targets**: Minimum 44x44px
2. **Font Sizes**: 
   - Normal: 16px minimum
   - Large: 20px
   - XL: 24px
3. **Contrast Ratios**: WCAG AA compliant
4. **Audio Feedback**: Optional beeps for new orders
5. **Screen Reader**: ARIA labels for all actions

## Animation Guidelines

1. **Status Changes**: 300ms fade transition
2. **New Items**: Slide in from top with bounce
3. **Completed Items**: Fade out after delay
4. **Urgent Items**: Subtle pulse animation
5. **Touch Feedback**: Immediate visual response

## Implementation Example (React)

```tsx
const KDSItemTile: React.FC<KDSItemTileProps> = ({ item, onStatusChange, config }) => {
  const statusColor = getStatusColor(item.status, item.elapsedTime);
  
  return (
    <TouchableOpacity 
      onPress={() => handleTap(item.id)}
      onLongPress={() => handleLongPress(item.id)}
      style={[styles.tile, { backgroundColor: statusColor }]}
    >
      <View style={styles.header}>
        <Text style={styles.orderNumber}>#{item.orderNumber}</Text>
        {item.tableNumber && (
          <Text style={styles.table}>Table {item.tableNumber}</Text>
        )}
        <KDSTimerDisplay 
          elapsedTime={item.elapsedTime}
          targetTime={item.targetTime}
        />
      </View>
      
      <View style={styles.content}>
        <Text style={styles.itemName}>
          {item.quantity}x {item.displayName}
        </Text>
        
        {item.modifiers.map((mod, idx) => (
          <Text key={idx} style={styles.modifier}>• {mod}</Text>
        ))}
        
        {item.specialInstructions && (
          <Text style={styles.instructions}>
            "{item.specialInstructions}"
          </Text>
        )}
      </View>
    </TouchableOpacity>
  );
};
```

## Performance Considerations

1. **Virtualization**: Use virtual scrolling for large lists
2. **Memoization**: Prevent unnecessary re-renders
3. **Batch Updates**: Group WebSocket updates
4. **Image Optimization**: Lazy load item images
5. **Offline Support**: Cache recent items locally

## Testing Requirements

1. **Touch Testing**: Verify all gestures work reliably
2. **Stress Testing**: Handle 100+ items smoothly
3. **Network Testing**: Handle connection drops gracefully
4. **Device Testing**: Test on various screen sizes
5. **Kitchen Testing**: Test in actual kitchen environment with:
   - Wet/greasy fingers
   - Bright lighting conditions
   - Busy/noisy environment