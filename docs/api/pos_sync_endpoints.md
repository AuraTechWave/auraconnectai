# POS Sync API Documentation

## Overview

The POS Sync API provides endpoints for Point of Sale terminals to manually trigger order synchronization with the cloud system. This allows POS terminals to control when orders are synced, useful for handling network issues or batch processing.

## Base URL

```
/api/pos
```

## Authentication

All endpoints require authentication. Include the authentication token in the Authorization header:

```
Authorization: Bearer <token>
```

## Endpoints

### 1. Trigger Manual Sync

Initiates synchronization of orders from the POS terminal to the cloud.

**Endpoint:** `POST /pos/sync`

**Request Body:**

```json
{
  "terminal_id": "POS-001",  // Optional, defaults to configured terminal ID
  "order_ids": [123, 124, 125],  // Optional, specific orders to sync
  "sync_all_pending": true,  // Default: true, sync all pending if no order_ids
  "include_recent": false  // Default: false, include recently synced orders (last 24h)
}
```

**Response:**

```json
{
  "status": "initiated",  // initiated, completed, or failed
  "terminal_id": "POS-001",
  "sync_batch_id": "manual_20250731_143022",  // Optional batch ID
  "orders_queued": 15,
  "orders_synced": 0,  // Always 0 for async processing
  "orders_failed": 0,  // Always 0 for async processing
  "message": "Sync initiated for 15 pending orders",
  "timestamp": "2025-07-31T14:30:22.123Z",
  "details": {
    "sync_type": "scheduled_batch",
    "include_recent": false
  }
}
```

**Example: Sync Specific Orders**

```bash
curl -X POST https://api.auraconnect.ai/api/pos/sync \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{
    "terminal_id": "POS-001",
    "order_ids": [1001, 1002, 1003]
  }'
```

**Example: Sync All Pending Orders**

```bash
curl -X POST https://api.auraconnect.ai/api/pos/sync \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{
    "terminal_id": "POS-001",
    "sync_all_pending": true
  }'
```

### 2. Get Sync Status

Retrieves the current synchronization status for the POS terminal.

**Endpoint:** `GET /pos/sync/status`

**Query Parameters:**

- `terminal_id` (optional): Specific terminal ID, defaults to configured terminal

**Response:**

```json
{
  "sync_status_counts": {
    "pending": 12,
    "in_progress": 3,
    "synced": 145,
    "failed": 2,
    "retry": 1,
    "conflict": 0
  },
  "unsynced_orders": 15,
  "pending_conflicts": 0,
  "last_batch": {
    "batch_id": "auto_20250731_140000",
    "started_at": "2025-07-31T14:00:00Z",
    "completed_at": "2025-07-31T14:02:15Z",
    "total_orders": 25,
    "successful_syncs": 23,
    "failed_syncs": 2
  },
  "scheduler": {
    "running": true,
    "next_run": "2025-07-31T14:10:00Z"
  },
  "configuration": {
    "sync_enabled": true,
    "sync_interval_minutes": 10,
    "terminal_id": "POS-001",
    "cloud_endpoint": "https://api.auraconnect.ai/sync"
  }
}
```

**Example:**

```bash
curl -X GET https://api.auraconnect.ai/api/pos/sync/status \
  -H "Authorization: Bearer <token>"
```

## Status Codes

| Status Code | Description |
|-------------|-------------|
| 200 | Success (GET requests) |
| 202 | Accepted - Sync initiated in background |
| 400 | Bad Request - Invalid input parameters |
| 401 | Unauthorized - Invalid or missing authentication |
| 404 | Not Found - Requested orders not found |
| 422 | Validation Error - Invalid request data format |
| 503 | Service Unavailable - Sync scheduler not available |
| 500 | Internal Server Error |

## Sync Status Values

| Status | Description |
|--------|-------------|
| `pending` | Order is queued for synchronization |
| `in_progress` | Synchronization is currently running |
| `synced` | Order successfully synchronized |
| `failed` | Synchronization failed after all retries |
| `retry` | Failed but will be retried |
| `conflict` | Conflict detected, requires resolution |

## Error Responses

All error responses follow this format:

```json
{
  "detail": "Error message describing what went wrong"
}
```

### Example Error Responses

**400 Bad Request - Empty order_ids:**
```json
{
  "detail": "order_ids cannot be empty when provided"
}
```

**404 Not Found - Invalid order IDs:**
```json
{
  "detail": "No valid orders found for IDs: [9999, 10000]"
}
```

**422 Validation Error - Invalid data type:**
```json
{
  "detail": [
    {
      "loc": ["body", "order_ids"],
      "msg": "value is not a valid list",
      "type": "type_error.list"
    }
  ]
}
```

**503 Service Unavailable - Scheduler offline:**
```json
{
  "detail": "Sync scheduler is unavailable"
}
```

## Usage Scenarios

### 1. Network Recovery

After network connectivity is restored, trigger a sync of all pending orders:

```json
POST /pos/sync
{
  "sync_all_pending": true
}
```

### 2. Specific Order Sync

Sync specific orders that failed previously:

```json
POST /pos/sync
{
  "order_ids": [1001, 1002, 1003]
}
```

### 3. Daily Reconciliation

Include recently synced orders to ensure all data is up-to-date:

```json
POST /pos/sync
{
  "sync_all_pending": true,
  "include_recent": true
}
```

### 4. Check Sync Health

Regularly check sync status to monitor for issues:

```bash
GET /pos/sync/status
```

## Best Practices

1. **Regular Status Checks**: Poll `/pos/sync/status` periodically to monitor sync health
2. **Batch Processing**: Use specific order IDs for targeted syncing of problematic orders
3. **Error Handling**: Check the `status` field in responses and handle failures appropriately
4. **Rate Limiting**: The sync endpoints are rate-limited to 1 request per minute per terminal. Implement exponential backoff for retries
5. **Monitoring**: Track failed syncs and conflicts for manual intervention

### Rate Limiting

The POS sync endpoints enforce the following rate limits:
- **POST /pos/sync**: 1 request per minute per terminal ID
- **GET /pos/sync/status**: 60 requests per minute (standard API rate limit)

When rate limit is exceeded, you'll receive a 429 response:
```json
{
  "detail": "Rate limit exceeded. Please wait before retrying."
}
```

Implement exponential backoff in your client:
```python
import time

def sync_with_retry(client, max_retries=3):
    for attempt in range(max_retries):
        try:
            response = client.trigger_sync()
            if response.status_code == 429:
                wait_time = 2 ** attempt * 60  # 1min, 2min, 4min
                time.sleep(wait_time)
                continue
            return response
        except Exception as e:
            if attempt == max_retries - 1:
                raise
            time.sleep(2 ** attempt)
```

## Integration Example

```python
import requests
import time

class POSSyncClient:
    def __init__(self, base_url, auth_token):
        self.base_url = base_url
        self.headers = {
            "Authorization": f"Bearer {auth_token}",
            "Content-Type": "application/json"
        }
    
    def trigger_sync(self, order_ids=None, sync_all=True):
        """Trigger manual sync"""
        payload = {
            "terminal_id": "POS-001",
            "sync_all_pending": sync_all
        }
        
        if order_ids:
            payload["order_ids"] = order_ids
            payload["sync_all_pending"] = False
        
        response = requests.post(
            f"{self.base_url}/pos/sync",
            json=payload,
            headers=self.headers
        )
        response.raise_for_status()
        return response.json()
    
    def get_sync_status(self):
        """Get current sync status"""
        response = requests.get(
            f"{self.base_url}/pos/sync/status",
            headers=self.headers
        )
        response.raise_for_status()
        return response.json()
    
    def wait_for_sync_completion(self, timeout=300):
        """Wait for all pending syncs to complete"""
        start_time = time.time()
        
        while time.time() - start_time < timeout:
            status = self.get_sync_status()
            pending = status["sync_status_counts"]["pending"]
            in_progress = status["sync_status_counts"]["in_progress"]
            
            if pending == 0 and in_progress == 0:
                return True
            
            time.sleep(5)  # Check every 5 seconds
        
        return False

# Usage
client = POSSyncClient("https://api.auraconnect.ai/api", "your-auth-token")

# Trigger sync
result = client.trigger_sync()
print(f"Sync initiated: {result['orders_queued']} orders queued")

# Wait for completion
if client.wait_for_sync_completion():
    print("All orders synced successfully")
else:
    print("Sync timeout - check status for details")
```