# Push Notifications Implementation for AuraConnect Mobile

## Overview

This document describes the comprehensive push notification implementation for the AuraConnect mobile application, enabling real-time order updates and engagement with staff members.

## Architecture

### Technology Stack

1. **Firebase Cloud Messaging (FCM)** - Cross-platform push notification delivery
2. **Notifee** - Advanced local notification features and customization
3. **React Native Push Notification** - Additional local notification support
4. **AsyncStorage** - Notification preferences and history persistence

### System Components

```
┌─────────────────┐     ┌──────────────────┐     ┌─────────────────┐
│  Backend API    │────▶│  Firebase Cloud  │────▶│  Mobile Device  │
│                 │     │    Messaging     │     │                 │
└─────────────────┘     └──────────────────┘     └────────┬────────┘
                                                           │
                              ┌────────────────────────────┼────────────────────────────┐
                              │                            ▼                            │
                              │  ┌──────────────────┐  ┌──────────────────┐           │
                              │  │ Notification     │  │ Notification     │           │
                              │  │ Service          │  │ Handler          │           │
                              │  └──────────────────┘  └──────────────────┘           │
                              │           │                      │                      │
                              │           ▼                      ▼                      │
                              │  ┌──────────────────┐  ┌──────────────────┐           │
                              │  │ Local Storage    │  │ UI Components    │           │
                              │  │ (Preferences)    │  │ (Badge, List)    │           │
                              │  └──────────────────┘  └──────────────────┘           │
                              └────────────────────────────────────────────────────────┘
```

## Implementation Details

### 1. Notification Service

**Location**: `/mobile/src/services/notifications/NotificationService.ts`

**Key Features**:
- FCM token management and registration
- Permission handling for iOS and Android
- Notification channel creation (Android)
- Foreground/background message handling
- Do Not Disturb scheduling
- Notification history management

### 2. Notification Types

**Location**: `/mobile/src/services/notifications/types.ts`

#### Order Notifications
- `ORDER_CREATED` - New order received
- `ORDER_ACCEPTED` - Order accepted by staff
- `ORDER_PREPARING` - Order being prepared
- `ORDER_READY` - Order ready for pickup
- `ORDER_COMPLETED` - Order completed
- `ORDER_CANCELLED` - Order cancelled

#### Other Notifications
- `PROMOTION` - Marketing and promotional messages
- `SYSTEM_UPDATE` - App updates and maintenance

### 3. Notification Channels (Android)

- **Order Updates** (High Priority)
  - Sound: Custom order notification sound
  - Vibration: Enabled
  - Badge: Enabled

- **Promotions** (Default Priority)
  - Sound: Default
  - Vibration: Disabled
  - Badge: Disabled

- **System** (High Priority)
  - Sound: Default
  - Vibration: Enabled
  - Badge: Enabled

### 4. Notification Actions

Order notifications support quick actions:

- **New Order**:
  - View Order
  - Accept Order
  - Reject Order

- **Order Ready**:
  - View Order
  - Notify Customer

### 5. Notification Preferences

Users can configure:
- Enable/disable all notifications
- Toggle specific notification types
- Sound and vibration settings
- Do Not Disturb schedule

## Integration Guide

### 1. Firebase Setup

#### Android
1. Add `google-services.json` to `/android/app/`
2. Update with your Firebase project credentials
3. Ensure package name matches: `com.auraconnect.mobile`

#### iOS
1. Add `GoogleService-Info.plist` to iOS project
2. Update with your Firebase project credentials
3. Ensure bundle ID matches: `com.auraconnect.mobile`

### 2. Backend Integration

#### Send Order Notification

```typescript
// Backend API endpoint
POST /api/notifications/send

{
  "to": "FCM_TOKEN",
  "notification": {
    "title": "New Order #12345",
    "body": "Order from John Doe - Table 5"
  },
  "data": {
    "type": "order_created",
    "orderId": "order_123",
    "orderNumber": "12345",
    "customerName": "John Doe",
    "tableNumber": "5"
  },
  "android": {
    "priority": "high",
    "notification": {
      "channel_id": "order_updates"
    }
  },
  "apns": {
    "headers": {
      "apns-priority": "10"
    },
    "payload": {
      "aps": {
        "category": "ORDER_ACTIONS"
      }
    }
  }
}
```

### 3. App Integration

#### Initialize Notifications

```typescript
// In App.tsx
import { notificationService } from '@services/notifications';

useEffect(() => {
  notificationService.initialize().catch(error => {
    console.error('Failed to initialize notifications:', error);
  });
}, []);
```

#### Handle Order Updates

```typescript
import { OrderNotificationService } from '@services/notifications/OrderNotificationService';

const orderNotificationService = OrderNotificationService.getInstance();

// When order status changes
await orderNotificationService.notifyOrderStatusChange(order, previousStatus);

// For order ready with special alert
await orderNotificationService.notifyOrderReady(order);
```

#### Listen for Navigation Events

```typescript
notificationService.on('navigateToOrder', (orderId: string) => {
  navigation.navigate('OrderDetails', { orderId });
});

notificationService.on('notifyCustomer', (orderId: string) => {
  // Handle customer notification
});
```

## User Experience

### 1. Permission Flow

1. On first app launch, request notification permissions
2. Explain value proposition before requesting
3. Handle permission denial gracefully
4. Provide settings to re-enable later

### 2. Notification Display

#### Foreground
- Show in-app toast/banner
- Update notification badge
- Play subtle sound (if enabled)

#### Background
- System notification with custom styling
- App badge update
- Custom sound for order ready

### 3. Notification Center

- Chronological list of all notifications
- Unread indicator and count
- Swipe to mark as read
- Clear all functionality
- Pull to refresh

## Configuration

### Constants

**Location**: `/mobile/src/constants/config.ts`

```typescript
export const NOTIFICATION_CONFIG = {
  MAX_STORED_NOTIFICATIONS: 100,
  NOTIFICATION_SOUND: 'order_notification',
  DEFAULT_VIBRATION_PATTERN: [0, 250, 250, 250],
  ORDER_NOTIFICATION_PRIORITY: 'high',
  PROMOTION_NOTIFICATION_PRIORITY: 'normal',
  SYSTEM_NOTIFICATION_PRIORITY: 'high',
  AUTO_CANCEL_TIMEOUT: 30000, // 30 seconds
};
```

## Testing

### 1. Local Testing

```typescript
// Test local notification
const testNotification = {
  id: 'test_123',
  title: 'Test Order Ready',
  body: 'Order #12345 is ready for pickup',
  data: {
    type: 'order_ready',
    orderId: 'test_order_123',
  },
};

await notificationService.displayNotification(testNotification);
```

### 2. FCM Testing

Use Firebase Console or curl:

```bash
curl -X POST https://fcm.googleapis.com/fcm/send \
  -H "Authorization: key=YOUR_SERVER_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "to": "DEVICE_FCM_TOKEN",
    "notification": {
      "title": "Test Notification",
      "body": "This is a test"
    },
    "data": {
      "type": "order_created",
      "orderId": "test_123"
    }
  }'
```

### 3. Test Scenarios

1. **Permission Handling**
   - First time permission request
   - Permission denied scenario
   - Re-enable from settings

2. **Notification Delivery**
   - App in foreground
   - App in background
   - App killed
   - Device offline/online transition

3. **User Interactions**
   - Tap notification to navigate
   - Use quick actions
   - Clear notifications
   - Do Not Disturb schedule

## Security Considerations

1. **Token Management**
   - Store FCM tokens securely
   - Refresh tokens on app update
   - Remove tokens on logout

2. **Data Privacy**
   - Don't include sensitive data in notifications
   - Use data payload for IDs only
   - Fetch full details from API

3. **Rate Limiting**
   - Implement notification throttling
   - Batch similar notifications
   - Respect user preferences

## Troubleshooting

### Common Issues

1. **Notifications not received**
   - Check FCM token registration
   - Verify Firebase configuration
   - Check notification permissions
   - Test with Firebase Console

2. **iOS specific issues**
   - Ensure APNS certificates are configured
   - Check provisioning profiles
   - Verify push notification capability

3. **Android specific issues**
   - Check notification channels exist
   - Verify google-services.json
   - Test on different Android versions

### Debug Logging

```typescript
// Enable verbose logging
logger.setLevel('debug');

// Monitor notification events
notificationService.on('notificationDisplayed', (notification) => {
  console.log('Notification displayed:', notification);
});

notificationService.on('tokenRefresh', (token) => {
  console.log('New FCM token:', token);
});
```

## Performance Optimization

1. **Notification Batching**
   - Group similar notifications
   - Implement cooldown periods
   - Use notification channels effectively

2. **Storage Management**
   - Limit notification history size
   - Implement automatic cleanup
   - Compress notification data

3. **Battery Optimization**
   - Respect device power saving modes
   - Use appropriate priority levels
   - Minimize background processing

## Future Enhancements

1. **Rich Media Notifications**
   - Order item images
   - Interactive order cards
   - Progress indicators

2. **Smart Notifications**
   - ML-based notification timing
   - Personalized notification preferences
   - Predictive notification muting

3. **Advanced Actions**
   - Quick reply to customers
   - Update order status from notification
   - Snooze notifications

4. **Analytics**
   - Notification delivery rates
   - User engagement metrics
   - A/B testing support