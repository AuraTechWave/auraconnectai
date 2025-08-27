# WebSocket Authentication Documentation

## Overview

All WebSocket endpoints in the AuraConnect system require JWT-based authentication with enhanced security measures. This ensures that real-time connections are secure, properly authorized, and protected against common vulnerabilities.

## Security Features

1. **Production Security Mode**: In production environments, query parameter authentication is disabled to prevent token exposure in logs
2. **Rate Limiting**: Authentication attempts are rate-limited to prevent brute force attacks
3. **Token Expiration Checking**: Active connections are terminated when tokens expire
4. **Enhanced JWT Validation**: Includes issuer and audience verification
5. **Generic Error Messages**: Production environments use generic error messages to prevent information leakage
6. **Tenant Validation**: Multi-tenant access control ensures users can only access authorized resources

## Authentication Methods

### 1. Query Parameter (Development Only)

Pass the JWT token as a query parameter when establishing the WebSocket connection:

```
ws://localhost:8000/analytics/realtime/dashboard?token=<JWT_TOKEN>
```

⚠️ **Important**: Query parameter authentication is **disabled in production** to prevent token exposure in server logs. Use the first message authentication method in production environments.

**Example (JavaScript - Development):**
```javascript
const token = localStorage.getItem('jwt_token');
const ws = new WebSocket(`ws://localhost:8000/analytics/realtime/dashboard?token=${token}`);
```

### 2. First Message Authentication (Recommended for Production)

In production environments or when you cannot use query parameters, authenticate by sending an authentication message as the first message after connection:

```json
{
  "type": "auth",
  "token": "<JWT_TOKEN>"
}
```

**Important Security Requirements:**
- Authentication message must be sent within 5 seconds of connection
- Message size must not exceed 4KB
- Only the first message can be an authentication message
- Invalid auth messages result in immediate connection termination

**Example (JavaScript - Production):**
```javascript
const ws = new WebSocket('wss://api.auraconnect.ai/analytics/realtime/dashboard');
ws.onopen = () => {
  // Send auth message immediately
  ws.send(JSON.stringify({
    type: "auth",
    token: localStorage.getItem('jwt_token')
  }));
};

ws.onerror = (error) => {
  console.error('WebSocket error:', error);
};

ws.onclose = (event) => {
  if (event.code === 1008) {
    console.error('Authentication failed - policy violation');
    // Handle re-authentication
  }
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

## Security Configuration

### Environment Variables

Configure these environment variables for enhanced security:

```bash
# Production Environment
ENVIRONMENT=production  # Enables production security features

# JWT Configuration
JWT_SECRET_KEY=your-secret-key  # Strong secret for JWT signing
JWT_ISSUER=auraconnect-api     # Expected JWT issuer
JWT_AUDIENCE=auraconnect-ws    # Expected JWT audience
JWT_LEEWAY_SECONDS=120          # Clock skew tolerance (default: 2 minutes)

# WebSocket Security
WS_AUTH_MESSAGE_TIMEOUT=5       # Timeout for auth message (seconds)
WS_MAX_AUTH_MESSAGE_SIZE=4096   # Max auth message size (bytes)
WS_MAX_AUTH_ATTEMPTS=3          # Max auth attempts per IP
```

### Security Considerations

1. **Token Expiration**: WebSocket connections are automatically terminated when JWT tokens expire
2. **Token Refresh**: Implement token refresh logic before establishing long-lived connections
3. **Secure Transport**: Always use WSS (WebSocket Secure) in production
4. **Rate Limiting**: Authentication attempts are rate-limited per IP address
5. **Connection Limits**: Consider implementing per-user connection limits
6. **Origin Validation**: Implement origin checks for browser-facing endpoints
7. **Message Validation**: All incoming messages are validated and sanitized

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