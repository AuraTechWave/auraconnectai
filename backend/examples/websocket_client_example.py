"""
WebSocket client examples for AuraConnect.

Demonstrates secure WebSocket connections with JWT authentication for both
development and production environments.
"""

import asyncio
import websockets
import json
import ssl
import os
from typing import Optional, Dict, Any
from datetime import datetime


class WebSocketClient:
    """Production-ready WebSocket client with secure authentication"""
    
    def __init__(self, token: str, environment: str = "development"):
        self.token = token
        self.websocket = None
        self.environment = environment
        self.reconnect_attempts = 0
        self.max_reconnect_attempts = 3
        self.reconnect_delay = 1.0  # seconds
        
    async def connect(self, endpoint: str, use_ssl: bool = None) -> websockets.WebSocketClientProtocol:
        """
        Connect to WebSocket endpoint with appropriate authentication method.
        
        Args:
            endpoint: WebSocket endpoint path
            use_ssl: Whether to use SSL/TLS (auto-detected in production)
            
        Returns:
            Connected WebSocket instance
        """
        if use_ssl is None:
            use_ssl = self.environment == "production"
            
        if self.environment == "production":
            return await self.connect_production(endpoint, use_ssl)
        else:
            return await self.connect_development(endpoint)
    
    async def connect_development(self, endpoint: str):
        """Connect using query parameter authentication (development only)"""
        uri = f"ws://localhost:8000{endpoint}?token={self.token}"
        
        try:
            self.websocket = await websockets.connect(uri)
            print(f"[DEV] Connected to {endpoint}")
            
            # Wait for connection confirmation
            response = await self.websocket.recv()
            data = json.loads(response)
            
            if data.get("type") == "connection_established":
                print(f"[DEV] Authentication successful: {data.get('user', {}).get('username')}")
            
            return self.websocket
            
        except websockets.exceptions.WebSocketException as e:
            print(f"[DEV] WebSocket error: {e}")
            raise
    
    async def connect_production(self, endpoint: str, use_ssl: bool = True):
        """Connect using first message authentication (production safe)"""
        protocol = "wss" if use_ssl else "ws"
        host = os.getenv("WEBSOCKET_HOST", "api.auraconnect.ai")
        uri = f"{protocol}://{host}{endpoint}"
        
        # SSL context for production
        ssl_context = None
        if use_ssl:
            ssl_context = ssl.create_default_context()
            ssl_context.check_hostname = True
            ssl_context.verify_mode = ssl.CERT_REQUIRED
        
        try:
            self.websocket = await websockets.connect(
                uri,
                ssl=ssl_context,
                ping_interval=30,  # Keep connection alive
                ping_timeout=10,
                close_timeout=10
            )
            
            # Send authentication message immediately
            auth_msg = json.dumps({
                "type": "auth",
                "token": self.token
            })
            await self.websocket.send(auth_msg)
            
            # Wait for connection confirmation with timeout
            try:
                response = await asyncio.wait_for(
                    self.websocket.recv(),
                    timeout=5.0
                )
                data = json.loads(response)
                
                if data.get("type") == "connection_established":
                    print(f"[PROD] Authentication successful: {data.get('user', {}).get('username')}")
                    self.reconnect_attempts = 0  # Reset on successful connection
                else:
                    raise Exception(f"Unexpected response: {data}")
                    
            except asyncio.TimeoutError:
                await self.websocket.close()
                raise Exception("Authentication timeout")
            
            return self.websocket
            
        except websockets.exceptions.WebSocketException as e:
            print(f"[PROD] WebSocket error: {e}")
            if e.code == 1008:  # Policy violation
                print("[PROD] Authentication failed - check token validity")
            raise
    
    async def reconnect_with_backoff(self, endpoint: str):
        """Reconnect with exponential backoff strategy"""
        while self.reconnect_attempts < self.max_reconnect_attempts:
            try:
                delay = self.reconnect_delay * (2 ** self.reconnect_attempts)
                print(f"Reconnecting in {delay} seconds (attempt {self.reconnect_attempts + 1}/{self.max_reconnect_attempts})")
                await asyncio.sleep(delay)
                
                self.reconnect_attempts += 1
                return await self.connect(endpoint)
                
            except Exception as e:
                print(f"Reconnection failed: {e}")
                if self.reconnect_attempts >= self.max_reconnect_attempts:
                    raise Exception("Max reconnection attempts reached")
        
        raise Exception("Failed to reconnect")
    
    async def send_message(self, message: Dict[str, Any]):
        """Send a message to the WebSocket server"""
        if self.websocket and not self.websocket.closed:
            await self.websocket.send(json.dumps(message))
        else:
            raise Exception("WebSocket is not connected")
    
    async def close(self):
        """Close the WebSocket connection gracefully"""
        if self.websocket and not self.websocket.closed:
            await self.websocket.close()
            print("WebSocket connection closed")


class RobustWebSocketClient(WebSocketClient):
    """WebSocket client with automatic reconnection and token refresh"""
    
    def __init__(self, token_provider, environment: str = "development"):
        """
        Initialize with a token provider function for automatic refresh.
        
        Args:
            token_provider: Async function that returns a fresh JWT token
            environment: "development" or "production"
        """
        self.token_provider = token_provider
        super().__init__(token="", environment=environment)
        
    async def connect_with_auto_refresh(self, endpoint: str):
        """Connect with automatic token refresh on expiration"""
        # Get fresh token
        self.token = await self.token_provider()
        
        try:
            websocket = await self.connect(endpoint)
            
            # Handle messages with automatic reconnection
            while True:
                try:
                    message = await websocket.recv()
                    data = json.loads(message)
                    
                    # Handle different message types
                    if data.get("type") == "error" and "expired" in data.get("message", "").lower():
                        print("Token expired, refreshing...")
                        await websocket.close()
                        self.token = await self.token_provider()
                        websocket = await self.reconnect_with_backoff(endpoint)
                    else:
                        yield data
                        
                except websockets.exceptions.ConnectionClosed as e:
                    if e.code == 1008:  # Policy violation (auth failure)
                        print("Authentication failed, refreshing token...")
                        self.token = await self.token_provider()
                        websocket = await self.reconnect_with_backoff(endpoint)
                    else:
                        raise
                        
        except Exception as e:
            print(f"Fatal error in WebSocket client: {e}")
            raise


# Example usage
async def example_dashboard_client():
    """Example: Connect to analytics dashboard"""
    
    # In production, you would get this from your auth service
    async def get_fresh_token():
        # Simulate token refresh
        return "your-jwt-token-here"
    
    client = RobustWebSocketClient(
        token_provider=get_fresh_token,
        environment="development"  # Change to "production" for production use
    )
    
    try:
        async for message in client.connect_with_auto_refresh("/analytics/realtime/dashboard"):
            print(f"Received: {message.get('type')}")
            
            # Handle different message types
            if message.get("type") == "dashboard_update":
                # Process dashboard data
                metrics = message.get("data", {}).get("metrics", {})
                print(f"Revenue: ${metrics.get('revenue_current', 0)}")
                print(f"Orders: {metrics.get('orders_current', 0)}")
                
            elif message.get("type") == "alert_notification":
                # Handle alerts
                alert = message.get("data", {})
                print(f"ALERT: {alert.get('message')}")
                
    except KeyboardInterrupt:
        print("\nShutting down...")
        await client.close()


async def example_order_queue_client():
    """Example: Connect to order queue with subscription"""
    
    token = "your-jwt-token-here"
    client = WebSocketClient(token, environment="development")
    
    try:
        websocket = await client.connect("/api/v1/queues/ws/main-queue")
        
        # Subscribe to order updates
        await client.send_message({
            "type": "subscribe",
            "data": {
                "queue_id": "main-queue",
                "events": ["order_added", "order_updated", "order_completed"]
            }
        })
        
        # Process messages
        while True:
            message = await websocket.recv()
            data = json.loads(message)
            
            if data.get("type") == "order_event":
                event = data.get("data", {})
                print(f"Order {event.get('order_id')}: {event.get('status')}")
                
    except websockets.exceptions.ConnectionClosed:
        print("Connection closed")
    finally:
        await client.close()


# JavaScript/TypeScript example for production
JAVASCRIPT_PRODUCTION_EXAMPLE = """
// Production-ready WebSocket client with security best practices

class SecureWebSocketClient {
    constructor(tokenProvider, environment = 'production') {
        this.tokenProvider = tokenProvider;
        this.environment = environment;
        this.ws = null;
        this.reconnectAttempts = 0;
        this.maxReconnectAttempts = 3;
        this.reconnectDelay = 1000; // ms
        this.messageQueue = [];
        this.isAuthenticated = false;
    }
    
    async connect(endpoint) {
        const token = await this.tokenProvider();
        
        if (this.environment === 'production') {
            return this.connectProduction(endpoint, token);
        } else {
            return this.connectDevelopment(endpoint, token);
        }
    }
    
    connectDevelopment(endpoint, token) {
        const url = `ws://localhost:8000${endpoint}?token=${token}`;
        this.ws = new WebSocket(url);
        this.setupEventHandlers();
        return this.waitForConnection();
    }
    
    connectProduction(endpoint, token) {
        const host = process.env.REACT_APP_WS_HOST || 'wss://api.auraconnect.ai';
        const url = `${host}${endpoint}`;
        
        this.ws = new WebSocket(url);
        
        this.ws.onopen = () => {
            console.log('[PROD] WebSocket opened, sending auth...');
            
            // Send auth message immediately
            this.ws.send(JSON.stringify({
                type: 'auth',
                token: token
            }));
        };
        
        this.setupEventHandlers();
        return this.waitForConnection();
    }
    
    setupEventHandlers() {
        this.ws.onmessage = (event) => {
            const data = JSON.parse(event.data);
            
            if (data.type === 'connection_established') {
                console.log('Authentication successful:', data.user);
                this.isAuthenticated = true;
                this.reconnectAttempts = 0;
                
                // Send queued messages
                while (this.messageQueue.length > 0) {
                    const msg = this.messageQueue.shift();
                    this.send(msg);
                }
            }
            
            // Notify listeners
            this.onMessage(data);
        };
        
        this.ws.onerror = (error) => {
            console.error('WebSocket error:', error);
            this.onError(error);
        };
        
        this.ws.onclose = async (event) => {
            console.log(`WebSocket closed: ${event.code} - ${event.reason}`);
            this.isAuthenticated = false;
            
            if (event.code === 1008) {
                // Authentication failure - refresh token
                console.log('Auth failed, refreshing token...');
                await this.reconnectWithNewToken();
            } else if (event.code !== 1000) {
                // Abnormal closure - try reconnect
                await this.reconnectWithBackoff();
            }
            
            this.onClose(event);
        };
    }
    
    async reconnectWithBackoff() {
        if (this.reconnectAttempts >= this.maxReconnectAttempts) {
            console.error('Max reconnection attempts reached');
            return;
        }
        
        const delay = this.reconnectDelay * Math.pow(2, this.reconnectAttempts);
        console.log(`Reconnecting in ${delay}ms...`);
        
        this.reconnectAttempts++;
        
        setTimeout(async () => {
            try {
                await this.connect(this.endpoint);
            } catch (error) {
                console.error('Reconnection failed:', error);
            }
        }, delay);
    }
    
    async reconnectWithNewToken() {
        try {
            const newToken = await this.tokenProvider();
            await this.connect(this.endpoint);
        } catch (error) {
            console.error('Token refresh failed:', error);
        }
    }
    
    send(message) {
        if (this.ws.readyState === WebSocket.OPEN) {
            if (this.isAuthenticated) {
                this.ws.send(JSON.stringify(message));
            } else {
                // Queue message until authenticated
                this.messageQueue.push(message);
            }
        } else {
            throw new Error('WebSocket is not connected');
        }
    }
    
    close() {
        if (this.ws) {
            this.ws.close(1000, 'Client closing connection');
        }
    }
    
    // Override these in your implementation
    onMessage(data) {}
    onError(error) {}
    onClose(event) {}
    
    waitForConnection() {
        return new Promise((resolve, reject) => {
            const checkInterval = setInterval(() => {
                if (this.isAuthenticated) {
                    clearInterval(checkInterval);
                    resolve(this.ws);
                }
            }, 100);
            
            setTimeout(() => {
                clearInterval(checkInterval);
                reject(new Error('Connection timeout'));
            }, 10000);
        });
    }
}

// Usage example with React
function useDashboardWebSocket() {
    const [metrics, setMetrics] = useState(null);
    const [connected, setConnected] = useState(false);
    const clientRef = useRef(null);
    
    useEffect(() => {
        const tokenProvider = async () => {
            // Get fresh token from your auth service
            return await authService.getAccessToken();
        };
        
        const client = new SecureWebSocketClient(tokenProvider);
        
        client.onMessage = (data) => {
            if (data.type === 'dashboard_update') {
                setMetrics(data.data.metrics);
            }
        };
        
        client.onClose = () => {
            setConnected(false);
        };
        
        client.connect('/analytics/realtime/dashboard')
            .then(() => {
                setConnected(true);
                
                // Subscribe to dashboard updates
                client.send({
                    type: 'subscribe',
                    data: { subscription_type: 'dashboard' }
                });
            })
            .catch(console.error);
        
        clientRef.current = client;
        
        return () => {
            client.close();
        };
    }, []);
    
    return { metrics, connected, client: clientRef.current };
}
"""


if __name__ == "__main__":
    # Run example
    asyncio.run(example_dashboard_client())