# Webhook Documentation

## Overview

AuraConnect provides webhook notifications for real-time event updates. Webhooks allow your application to receive HTTP callbacks when specific events occur in the system.

## Webhook Configuration

### Registering a Webhook

```http
POST /api/v1/webhooks
Authorization: Bearer {access_token}
Content-Type: application/json

{
  "url": "https://your-app.com/webhooks/auraconnect",
  "events": ["order.created", "order.updated", "payment.completed"],
  "secret": "your-webhook-secret",
  "active": true,
  "description": "Production webhook endpoint"
}

Response:
{
  "id": "webhook_123",
  "url": "https://your-app.com/webhooks/auraconnect",
  "events": ["order.created", "order.updated", "payment.completed"],
  "secret": "webhook_secret_***",
  "active": true,
  "created_at": "2025-08-08T10:00:00Z"
}
```

### Webhook Security

All webhook payloads are signed using HMAC-SHA256. Verify the signature to ensure the webhook is from AuraConnect:

```python
import hmac
import hashlib

def verify_webhook_signature(payload, signature, secret):
    expected_signature = hmac.new(
        secret.encode('utf-8'),
        payload.encode('utf-8'),
        hashlib.sha256
    ).hexdigest()
    
    return hmac.compare_digest(expected_signature, signature)

# In your webhook handler
@app.post("/webhooks/auraconnect")
async def handle_webhook(request: Request):
    payload = await request.body()
    signature = request.headers.get("X-AuraConnect-Signature")
    
    if not verify_webhook_signature(payload, signature, webhook_secret):
        raise HTTPException(status_code=401, detail="Invalid signature")
    
    # Process webhook...
```

## Webhook Events

### Order Events

#### order.created
Triggered when a new order is created.

```json
{
  "id": "evt_123",
  "type": "order.created",
  "created": "2025-08-08T10:00:00Z",
  "data": {
    "object": {
      "id": 1001,
      "order_number": "ORD-2025-001",
      "restaurant_id": 1,
      "customer_id": 456,
      "status": "pending",
      "total_amount": 45.99,
      "items": [
        {
          "id": 1,
          "menu_item_id": 10,
          "quantity": 2,
          "price": 12.99,
          "modifiers": []
        }
      ],
      "created_at": "2025-08-08T10:00:00Z"
    }
  }
}
```

#### order.updated
Triggered when an order is updated (status change, items modified, etc.).

```json
{
  "id": "evt_124",
  "type": "order.updated",
  "created": "2025-08-08T10:05:00Z",
  "data": {
    "object": {
      "id": 1001,
      "order_number": "ORD-2025-001",
      "status": "preparing",
      "previous_status": "pending",
      "updated_fields": ["status", "preparation_time"],
      "preparation_time": 15,
      "updated_at": "2025-08-08T10:05:00Z"
    }
  }
}
```

#### order.completed
Triggered when an order is marked as completed.

```json
{
  "id": "evt_125",
  "type": "order.completed",
  "created": "2025-08-08T10:20:00Z",
  "data": {
    "object": {
      "id": 1001,
      "order_number": "ORD-2025-001",
      "status": "completed",
      "completed_at": "2025-08-08T10:20:00Z",
      "total_time_minutes": 20
    }
  }
}
```

### Payment Events

#### payment.completed
Triggered when a payment is successfully processed.

```json
{
  "id": "evt_126",
  "type": "payment.completed",
  "created": "2025-08-08T10:21:00Z",
  "data": {
    "object": {
      "id": 2001,
      "order_id": 1001,
      "amount": 45.99,
      "payment_method": "card",
      "status": "completed",
      "processor": "stripe",
      "processor_payment_id": "pi_1234567890",
      "processed_at": "2025-08-08T10:21:00Z"
    }
  }
}
```

#### payment.refunded
Triggered when a payment is refunded.

```json
{
  "id": "evt_127",
  "type": "payment.refunded",
  "created": "2025-08-08T11:00:00Z",
  "data": {
    "object": {
      "id": 2001,
      "order_id": 1001,
      "refund_amount": 45.99,
      "refund_reason": "customer_request",
      "refund_id": "ref_987654321",
      "refunded_at": "2025-08-08T11:00:00Z"
    }
  }
}
```

### Inventory Events

#### inventory.low_stock
Triggered when inventory falls below configured threshold.

```json
{
  "id": "evt_128",
  "type": "inventory.low_stock",
  "created": "2025-08-08T12:00:00Z",
  "data": {
    "object": {
      "item_id": 301,
      "item_name": "Tomatoes",
      "current_quantity": 5.0,
      "unit": "kg",
      "threshold": 10.0,
      "restaurant_id": 1
    }
  }
}
```

#### inventory.out_of_stock
Triggered when inventory reaches zero.

```json
{
  "id": "evt_129",
  "type": "inventory.out_of_stock",
  "created": "2025-08-08T12:30:00Z",
  "data": {
    "object": {
      "item_id": 301,
      "item_name": "Tomatoes",
      "affected_menu_items": [10, 15, 22],
      "restaurant_id": 1
    }
  }
}
```

### Staff Events

#### staff.clocked_in
Triggered when staff member clocks in.

```json
{
  "id": "evt_130",
  "type": "staff.clocked_in",
  "created": "2025-08-08T08:00:00Z",
  "data": {
    "object": {
      "staff_id": 101,
      "staff_name": "John Doe",
      "clock_in_time": "2025-08-08T08:00:00Z",
      "scheduled_start": "2025-08-08T08:00:00Z",
      "restaurant_id": 1
    }
  }
}
```

#### staff.shift_alert
Triggered for shift-related alerts (late arrival, no-show, etc.).

```json
{
  "id": "evt_131",
  "type": "staff.shift_alert",
  "created": "2025-08-08T08:15:00Z",
  "data": {
    "object": {
      "alert_type": "late_arrival",
      "staff_id": 102,
      "staff_name": "Jane Smith",
      "scheduled_start": "2025-08-08T08:00:00Z",
      "minutes_late": 15,
      "restaurant_id": 1
    }
  }
}
```

### POS Integration Events

#### pos.sync_completed
Triggered when POS synchronization completes.

```json
{
  "id": "evt_132",
  "type": "pos.sync_completed",
  "created": "2025-08-08T13:00:00Z",
  "data": {
    "object": {
      "sync_id": "sync_456",
      "pos_system": "square",
      "items_synced": 150,
      "orders_synced": 45,
      "sync_duration_seconds": 12,
      "restaurant_id": 1
    }
  }
}
```

#### pos.sync_failed
Triggered when POS synchronization fails.

```json
{
  "id": "evt_133",
  "type": "pos.sync_failed",
  "created": "2025-08-08T13:01:00Z",
  "data": {
    "object": {
      "sync_id": "sync_457",
      "pos_system": "square",
      "error_code": "POS_CONNECTION_FAILED",
      "error_message": "Unable to connect to Square API",
      "retry_count": 3,
      "restaurant_id": 1
    }
  }
}
```

## Webhook Headers

All webhook requests include these headers:

```
X-AuraConnect-Event: order.created
X-AuraConnect-Signature: sha256=a1b2c3d4e5f6...
X-AuraConnect-Event-Id: evt_123
X-AuraConnect-Timestamp: 1691496000
X-AuraConnect-Webhook-Id: webhook_123
Content-Type: application/json
```

## Retry Policy

- Webhooks are retried up to 5 times with exponential backoff
- Retry intervals: 10s, 30s, 1m, 5m, 30m
- Webhook is marked as failed after 5 unsuccessful attempts
- Only 2xx status codes are considered successful

## Best Practices

### 1. Acknowledge Quickly
Return a 200 status code as soon as possible. Process webhook data asynchronously if needed:

```python
@app.post("/webhooks/auraconnect")
async def handle_webhook(request: Request):
    # Verify signature
    # Queue for processing
    background_tasks.add_task(process_webhook, data)
    return {"received": True}  # Return 200 immediately
```

### 2. Idempotency
Webhooks may be sent multiple times. Use the event ID to ensure idempotent processing:

```python
def process_webhook(event_data):
    event_id = event_data["id"]
    
    # Check if already processed
    if is_event_processed(event_id):
        return
    
    # Process event
    process_event(event_data)
    mark_event_processed(event_id)
```

### 3. Verify Signatures
Always verify webhook signatures to ensure authenticity:

```javascript
const crypto = require('crypto');

function verifyWebhookSignature(payload, signature, secret) {
  const expectedSignature = crypto
    .createHmac('sha256', secret)
    .update(payload)
    .digest('hex');
  
  return crypto.timingSafeEqual(
    Buffer.from(signature),
    Buffer.from(`sha256=${expectedSignature}`)
  );
}
```

### 4. Handle Failures Gracefully
Implement proper error handling and logging:

```python
try:
    process_webhook(data)
except Exception as e:
    logger.error(f"Webhook processing failed: {e}")
    # Return 500 to trigger retry
    return {"error": "Processing failed"}, 500
```

## Testing Webhooks

### Test Webhook Endpoint
```http
POST /api/v1/webhooks/test
Authorization: Bearer {access_token}
Content-Type: application/json

{
  "webhook_id": "webhook_123",
  "event_type": "order.created"
}
```

### Webhook Logs
```http
GET /api/v1/webhooks/{webhook_id}/logs
Authorization: Bearer {access_token}

Response:
{
  "logs": [
    {
      "event_id": "evt_123",
      "event_type": "order.created",
      "status": "success",
      "attempts": 1,
      "response_code": 200,
      "response_time_ms": 150,
      "timestamp": "2025-08-08T10:00:00Z"
    }
  ]
}
```

## Webhook Management

### List Webhooks
```http
GET /api/v1/webhooks
Authorization: Bearer {access_token}
```

### Update Webhook
```http
PUT /api/v1/webhooks/{webhook_id}
Authorization: Bearer {access_token}
Content-Type: application/json

{
  "events": ["order.created", "order.updated"],
  "active": true
}
```

### Delete Webhook
```http
DELETE /api/v1/webhooks/{webhook_id}
Authorization: Bearer {access_token}
```

## Event Subscription Examples

### Subscribe to All Order Events
```json
{
  "events": ["order.*"]
}
```

### Subscribe to Specific Events
```json
{
  "events": [
    "order.created",
    "payment.completed",
    "inventory.low_stock"
  ]
}
```

### Restaurant-Specific Webhooks
```json
{
  "events": ["order.*"],
  "filters": {
    "restaurant_id": 1
  }
}
```

## Troubleshooting

### Common Issues

1. **Webhook not receiving events**
   - Verify webhook is active
   - Check event subscriptions
   - Ensure URL is publicly accessible
   - Review webhook logs

2. **Signature verification failing**
   - Ensure using correct secret
   - Verify payload is raw request body
   - Check signature format

3. **Webhooks timing out**
   - Return 200 status quickly
   - Process asynchronously
   - Check endpoint performance

4. **Duplicate events**
   - Implement idempotency
   - Track processed event IDs
   - Handle gracefully

### Debug Mode
Enable debug mode for detailed webhook information:

```http
PUT /api/v1/webhooks/{webhook_id}
Authorization: Bearer {access_token}

{
  "debug_mode": true
}
```

## Webhook Payload Limits

- Maximum payload size: 256KB
- Events older than 7 days are not retried
- Maximum 100 webhooks per account
- Rate limit: 1000 webhook deliveries per hour