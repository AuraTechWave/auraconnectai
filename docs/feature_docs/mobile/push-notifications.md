# Push Notifications Setup Guide

## Overview

AuraConnect uses Firebase Cloud Messaging (FCM) for push notifications on both iOS and Android platforms. The system supports order updates, promotional messages, and system announcements with advanced features like Do Not Disturb scheduling and quick actions.

## Prerequisites

- React Native project setup
- Firebase project created
- Apple Developer account (for iOS)
- Google Play Console access (for Android production)

## Installation

### 1. Install Dependencies

```bash
# Core dependencies
yarn add @react-native-firebase/app @react-native-firebase/messaging
yarn add @notifee/react-native
yarn add react-native-push-notification

# iOS specific
cd ios && pod install
```

### 2. Firebase Configuration

#### Android Setup

1. Download `google-services.json` from Firebase Console
2. Place it in `android/app/`
3. Update `android/build.gradle`:

```gradle
buildscript {
    dependencies {
        classpath 'com.google.gms:google-services:4.3.15'
    }
}
```

4. Update `android/app/build.gradle`:

```gradle
apply plugin: 'com.google.gms.google-services'
```

#### iOS Setup

1. Download `GoogleService-Info.plist` from Firebase Console
2. Add to iOS project via Xcode
3. Update `AppDelegate.m`:

```objc
#import <Firebase.h>

- (BOOL)application:(UIApplication *)application didFinishLaunchingWithOptions:(NSDictionary *)launchOptions {
    [FIRApp configure];
    // ... rest of your code
}
```

### 3. iOS Specific Configuration

#### Enable Push Notifications Capability

1. Open project in Xcode
2. Select your target
3. Go to "Signing & Capabilities"
4. Add "Push Notifications" capability
5. Add "Background Modes" capability
6. Enable "Remote notifications" under Background Modes

#### Configure APNs

1. Generate APNs Authentication Key in Apple Developer Portal
2. Upload to Firebase Console under Project Settings > Cloud Messaging
3. Enter Key ID and Team ID

#### Info.plist Updates

Add the following to `Info.plist`:

```xml
<key>UIBackgroundModes</key>
<array>
    <string>remote-notification</string>
    <string>fetch</string>
</array>
```

### 4. Android Specific Configuration

#### Notification Channels

Channels are automatically created by the app:
- `order_updates`: High priority order notifications
- `promotions`: Default priority promotional messages
- `system`: High priority system notifications

#### AndroidManifest.xml Updates

```xml
<!-- Firebase Messaging Service -->
<service
    android:name="com.google.firebase.messaging.FirebaseMessagingService"
    android:exported="false">
    <intent-filter>
        <action android:name="com.google.firebase.MESSAGING_EVENT" />
    </intent-filter>
</service>

<!-- Notification permissions -->
<uses-permission android:name="android.permission.VIBRATE" />
<uses-permission android:name="android.permission.RECEIVE_BOOT_COMPLETED" />
```

## Implementation

### 1. Initialize Notification Service

```typescript
import { NotificationService } from '@services/notifications/NotificationService';

// In your app initialization
const notificationService = NotificationService.getInstance();
await notificationService.initialize();
```

### 2. Handle Token Registration

```typescript
// Listen for token updates
notificationService.on('registerToken', async (token) => {
    // Send token to your backend
    await api.registerDeviceToken(token);
});

// Token refresh handling is automatic
notificationService.on('tokenRefresh', async (newToken) => {
    await api.updateDeviceToken(newToken);
});
```

### 3. Display Custom Notifications

```typescript
// Display a notification
await notificationService.displayNotification({
    id: 'custom-123',
    title: 'Order Ready',
    body: 'Order #123 is ready for pickup',
    data: {
        orderId: '123',
        type: 'order_ready'
    }
});

// Schedule a notification
await notificationService.scheduleNotification(
    notification,
    Date.now() + 60000 // 1 minute from now
);
```

### 4. Handle User Preferences

```typescript
// Update preferences
await notificationService.savePreferences({
    orderUpdates: true,
    promotions: false,
    doNotDisturb: {
        enabled: true,
        startTime: '22:00',
        endTime: '08:00'
    }
});

// Get current preferences
const preferences = notificationService.getPreferences();
```

## Backend Integration

### Payload Structure

#### Order Notifications

```json
{
    "notification": {
        "title": "Order Update",
        "body": "Your order #123 is being prepared"
    },
    "data": {
        "type": "order_preparing",
        "orderId": "123",
        "orderNumber": "ORD-001",
        "customerName": "John Doe",
        "items": "2x Burger, 1x Fries", // Optional for big text style
        "timestamp": "1234567890"
    },
    "android": {
        "priority": "high"
    },
    "apns": {
        "payload": {
            "aps": {
                "sound": "default",
                "badge": 1
            }
        }
    }
}
```

#### Supported Order Types

- `order_created`: New order received
- `order_accepted`: Order accepted by restaurant
- `order_preparing`: Order being prepared
- `order_ready`: Order ready for pickup/delivery
- `order_completed`: Order completed
- `order_cancelled`: Order cancelled

### API Endpoints

```typescript
// Register device token
POST /api/v1/devices/register
{
    "token": "fcm-token",
    "platform": "ios|android",
    "deviceId": "unique-device-id"
}

// Send notification
POST /api/v1/notifications/send
{
    "userId": "user-123",
    "type": "order_update",
    "data": {
        "orderId": "order-123",
        "status": "ready"
    }
}
```

## Testing

### 1. Test Push Notifications

```typescript
// Test notification display
const testNotification = () => {
    notificationService.displayNotification({
        id: 'test-' + Date.now(),
        title: 'Test Notification',
        body: 'This is a test notification',
        data: { test: true }
    });
};

// Test with different channels
const testChannels = async () => {
    // Order notification
    await notificationService.displayNotification(
        NotificationFactory.createOrderNotification(
            'order_created',
            { orderId: 'test-123' },
            { title: 'Test Order', body: 'Test order notification' }
        )
    );
    
    // Promotion notification
    await notificationService.displayNotification(
        NotificationFactory.createPromotionNotification(
            'promo-test',
            'Test Promotion',
            '50% off test',
            { promoCode: 'TEST50' }
        )
    );
};
```

### 2. Test via Firebase Console

1. Go to Firebase Console > Cloud Messaging
2. Click "Send your first message"
3. Enter notification details
4. Target your test device by FCM token
5. Add custom data fields as needed

### 3. Test via cURL

```bash
curl -X POST https://fcm.googleapis.com/fcm/send \
  -H "Authorization: key=YOUR_SERVER_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "to": "DEVICE_FCM_TOKEN",
    "notification": {
      "title": "Test Order",
      "body": "Order #123 is ready"
    },
    "data": {
      "type": "order_ready",
      "orderId": "123"
    }
  }'
```

## Troubleshooting

### Common Issues

#### 1. Notifications not received on iOS

- Verify APNs configuration in Firebase
- Check device has notifications enabled
- Ensure app has proper capabilities
- Test with development APNs certificate first

#### 2. Notifications not received on Android

- Check google-services.json is correct
- Verify Firebase project matches app
- Ensure notification channels are created
- Check device manufacturer battery optimization

#### 3. Token registration fails

- Check network connectivity
- Verify Firebase initialization
- Look for errors in logs
- Try clearing app data and reinstalling

#### 4. Background notifications not working

- iOS: Ensure content-available is set
- Android: Use high priority
- Check background fetch is enabled
- Verify background handlers are registered

### Debug Logging

Enable verbose logging:

```typescript
// In development only
if (__DEV__) {
    messaging().setLogLevel('debug');
}
```

### Security Best Practices

1. **Never log FCM tokens in production**
2. **Always encrypt stored tokens**
3. **Validate notification payloads**
4. **Implement rate limiting on backend**
5. **Use topic subscriptions for broadcasts**
6. **Rotate server keys periodically**

## Performance Optimization

1. **Limit notification history**: Maximum 100 stored notifications
2. **Batch operations**: Trim history in batches of 10
3. **Debounce token updates**: Avoid frequent API calls
4. **Use channels wisely**: Don't create too many channels
5. **Optimize payload size**: Keep data minimal

## Advanced Features

### Quick Actions

```typescript
// Define notification with actions
const notification = {
    // ... other properties
    android: {
        actions: [
            {
                title: 'Accept Order',
                pressAction: { id: 'accept_order' }
            },
            {
                title: 'Reject Order',
                pressAction: { id: 'reject_order' }
            }
        ]
    }
};
```

### Rich Media (Future Enhancement)

```typescript
// Image notifications (requires additional setup)
const richNotification = {
    // ... other properties
    android: {
        largeIcon: 'https://example.com/icon.png',
        picture: 'https://example.com/image.png'
    },
    ios: {
        attachments: [{
            url: 'https://example.com/image.png'
        }]
    }
};
```

## Monitoring

### Analytics Integration

```typescript
// Track notification metrics
notificationService.on('notificationDisplayed', (notification) => {
    analytics.track('Notification Displayed', {
        type: notification.data?.type,
        notificationId: notification.id
    });
});

notificationService.on('notificationPress', (notification) => {
    analytics.track('Notification Opened', {
        type: notification.data?.type,
        notificationId: notification.id
    });
});
```

### Error Tracking

```typescript
// Centralized error handling
NotificationErrorHandler.handleNotificationError = (error, context) => {
    // Send to error tracking service
    Sentry.captureException(error, {
        tags: { feature: 'notifications', context }
    });
};
```