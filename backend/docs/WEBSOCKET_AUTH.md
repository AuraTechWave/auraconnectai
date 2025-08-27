# WebSocket Authentication Documentation

## Overview

All WebSocket endpoints in the AuraConnect system now require JWT-based authentication. This ensures that real-time connections are secure and properly authorized.

## Authentication Methods

### 1. Query Parameter (Recommended)

Pass the JWT token as a query parameter when establishing the WebSocket connection:

```
ws://localhost:8000/analytics/realtime/dashboard?token=<JWT_TOKEN>
```

**Example (JavaScript):**
```javascript
const token = localStorage.getItem('jwt_token');
const ws = new WebSocket(`ws://localhost:8000/analytics/realtime/dashboard?token=${token}`);
```

### 2. First Message Authentication

If you cannot send query parameters, you can authenticate by sending an authentication message as the first message after connection:

```json
{
  "type": "auth",
  "token": "<JWT_TOKEN>"
}
```

**Example (JavaScript):**
```javascript
const ws = new WebSocket('ws://localhost:8000/analytics/realtime/dashboard');
ws.onopen = () => {
  ws.send(JSON.stringify({
    type: "auth",
    token: localStorage.getItem('jwt_token')
  }));
};
```

## Updated WebSocket Endpoints

### 1. Analytics Real-time Dashboard
- **Endpoint**: `/analytics/realtime/dashboard`
- **Required Permissions**: `analytics.view_dashboard`
- **Roles**: `admin`, `manager`, `analytics_viewer`

### 2. Analytics Metrics
- **Endpoint**: `/analytics/realtime/metrics/{metric_name}`
- **Required Permissions**: `analytics.view_sales_reports`
- **Roles**: `admin`, `manager`, `analytics_viewer`

### 3. Kitchen Display System (KDS)
- **Endpoint**: `/api/v1/kds/ws/{station_id}`
- **Required Permissions**: Kitchen/KDS access
- **Roles**: `admin`, `manager`, `kitchen_staff`, `chef`, `cook`

### 4. Table Management
- **Endpoint**: `/api/v1/tables/ws/tables/{restaurant_id}`
- **Required Permissions**: Table management access
- **Roles**: `admin`, `manager`, `host`, `server`, `staff`
- **Additional Check**: User must have access to the specific restaurant

### 5. Order Queue
- **Endpoint**: `/api/v1/queues/ws/{queue_id}`
- **Required Permissions**: Order management
- **Roles**: `admin`, `manager`, `staff`, `server`, `kitchen_staff`, `cashier`

### 6. Order Queue Bulk Subscribe
- **Endpoint**: `/api/v1/queues/ws/subscribe`
- **Required Permissions**: Order management
- **Roles**: `admin`, `manager`, `staff`, `server`, `kitchen_staff`, `cashier`

## Connection Flow

1. **Client initiates connection** with JWT token
2. **Server validates token** and extracts user information
3. **Server checks permissions** based on endpoint requirements
4. **If authorized**: Connection accepted, welcome message sent
5. **If unauthorized**: Connection closed with appropriate error code

## Response Messages

### Success Response
```json
{
  "type": "connection_established",
  "client_id": "unique-client-id",
  "user": {
    "id": 1,
    "username": "john.doe",
    "permissions": ["analytics.view_dashboard", "analytics.view_sales_reports"]
  },
  "timestamp": "2024-01-15T10:30:00.000Z"
}
```

### Error Codes

- **1008 (Policy Violation)**: Authentication failed or insufficient permissions
- **1011 (Internal Error)**: Server error during processing
- **4001**: Invalid token (custom code)
- **4003**: Unauthorized access to resource (custom code)

## Client Implementation Examples

### JavaScript/TypeScript
```typescript
class AuthWebSocketClient {
  private ws: WebSocket | null = null;
  private token: string;
  
  constructor(token: string) {
    this.token = token;
  }
  
  connect(endpoint: string) {
    const url = `ws://localhost:8000${endpoint}?token=${this.token}`;
    this.ws = new WebSocket(url);
    
    this.ws.onopen = () => {
      console.log('WebSocket connected');
    };
    
    this.ws.onmessage = (event) => {
      const data = JSON.parse(event.data);
      if (data.type === 'connection_established') {
        console.log('Authenticated as:', data.user);
      }
    };
    
    this.ws.onerror = (error) => {
      console.error('WebSocket error:', error);
    };
    
    this.ws.onclose = (event) => {
      if (event.code === 1008) {
        console.error('Authentication failed:', event.reason);
        // Handle re-authentication
      }
    };
  }
}
```

### Python
```python
import asyncio
import websockets
import json

async def connect_with_auth(endpoint: str, token: str):
    uri = f"ws://localhost:8000{endpoint}?token={token}"
    
    async with websockets.connect(uri) as websocket:
        # Wait for connection confirmation
        response = await websocket.recv()
        data = json.loads(response)
        
        if data['type'] == 'connection_established':
            print(f"Connected as: {data['user']['username']}")
            
            # Subscribe to updates
            await websocket.send(json.dumps({
                "type": "subscribe",
                "data": {"subscription_type": "dashboard"}
            }))
            
            # Receive updates
            async for message in websocket:
                print(f"Update: {message}")
```

## Security Considerations

1. **Token Expiration**: WebSocket connections will be terminated when the JWT token expires
2. **Token Refresh**: Clients should handle token refresh before expiration
3. **Secure Transport**: Use WSS (WebSocket Secure) in production
4. **Rate Limiting**: Consider implementing rate limiting for WebSocket connections
5. **Connection Limits**: Limit concurrent connections per user

## Migration Guide

For existing WebSocket clients:

1. **Obtain JWT token** from the authentication endpoint
2. **Update connection URL** to include token parameter
3. **Handle new response format** with connection confirmation
4. **Implement reconnection logic** with fresh tokens

## Troubleshooting

### Common Issues

1. **"Invalid or expired token"**
   - Ensure token is valid and not expired
   - Check token format (should be a valid JWT)

2. **"Insufficient permissions"**
   - Verify user has required role for the endpoint
   - Check tenant/restaurant access for multi-tenant endpoints

3. **"No authentication token provided"**
   - Ensure token is included in query parameter or first message
   - Check for typos in parameter name

### Debug Tips

1. Decode JWT token to verify claims:
   ```javascript
   const payload = JSON.parse(atob(token.split('.')[1]));
   console.log('Token claims:', payload);
   ```

2. Check WebSocket close event for error details:
   ```javascript
   ws.onclose = (event) => {
     console.log(`Closed: ${event.code} - ${event.reason}`);
   };
   ```

3. Enable debug logging on server for detailed auth flow

## Best Practices

1. **Store tokens securely** (HttpOnly cookies or secure storage)
2. **Implement token refresh** before establishing long-lived connections
3. **Handle disconnections gracefully** with exponential backoff
4. **Clean up connections** when component unmounts or page unloads
5. **Use connection pooling** for multiple subscriptions
6. **Monitor connection health** with periodic heartbeats