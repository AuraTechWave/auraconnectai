"""
Example WebSocket client with JWT authentication.

This demonstrates how to connect to authenticated WebSocket endpoints.
"""

import asyncio
import json
import websockets
from typing import Optional


class AuthenticatedWebSocketClient:
    """WebSocket client with JWT authentication support."""
    
    def __init__(self, base_url: str, jwt_token: str):
        self.base_url = base_url.rstrip('/')
        self.jwt_token = jwt_token
        
    async def connect_with_query_param(self, endpoint: str):
        """
        Connect using JWT token as query parameter.
        
        Example: ws://localhost:8000/analytics/realtime/dashboard?token=<JWT>
        """
        url = f"{self.base_url}{endpoint}?token={self.jwt_token}"
        
        async with websockets.connect(url) as websocket:
            # Wait for connection confirmation
            response = await websocket.recv()
            print(f"Connected: {response}")
            
            # Send subscription
            await websocket.send(json.dumps({
                "type": "subscribe",
                "data": {
                    "subscription_type": "dashboard"
                }
            }))
            
            # Receive updates
            while True:
                try:
                    message = await websocket.recv()
                    print(f"Received: {message}")
                except websockets.exceptions.ConnectionClosed:
                    print("Connection closed")
                    break
    
    async def connect_with_auth_message(self, endpoint: str):
        """
        Connect and authenticate using first message.
        
        This is useful when you can't send query parameters.
        """
        url = f"{self.base_url}{endpoint}"
        
        async with websockets.connect(url) as websocket:
            # Send authentication message
            auth_msg = json.dumps({
                "type": "auth",
                "token": self.jwt_token
            })
            await websocket.send(auth_msg)
            
            # Wait for connection confirmation
            response = await websocket.recv()
            print(f"Connected: {response}")
            
            # Continue with normal messages
            await websocket.send(json.dumps({
                "type": "heartbeat",
                "data": {}
            }))
            
            # Receive updates
            while True:
                try:
                    message = await websocket.recv()
                    print(f"Received: {message}")
                except websockets.exceptions.ConnectionClosed:
                    print("Connection closed")
                    break


# Example usage
async def main():
    # First, get a JWT token from the login endpoint
    # This is just an example - in real usage, you'd get this from your auth flow
    jwt_token = "your-jwt-token-here"
    
    # Create client
    client = AuthenticatedWebSocketClient(
        base_url="ws://localhost:8000",
        jwt_token=jwt_token
    )
    
    # Example 1: Analytics dashboard
    print("Connecting to analytics dashboard...")
    try:
        await client.connect_with_query_param("/analytics/realtime/dashboard")
    except Exception as e:
        print(f"Dashboard connection failed: {e}")
    
    # Example 2: KDS station updates
    print("\nConnecting to KDS station 1...")
    try:
        await client.connect_with_query_param("/api/v1/kds/ws/1")
    except Exception as e:
        print(f"KDS connection failed: {e}")
    
    # Example 3: Order queue updates
    print("\nConnecting to order queue...")
    try:
        await client.connect_with_query_param("/api/v1/queues/ws/main-queue")
    except Exception as e:
        print(f"Queue connection failed: {e}")


# JavaScript/TypeScript example
JAVASCRIPT_EXAMPLE = """
// JavaScript WebSocket client with JWT authentication

class AuthenticatedWebSocketClient {
    constructor(baseUrl, jwtToken) {
        this.baseUrl = baseUrl;
        this.jwtToken = jwtToken;
        this.ws = null;
    }
    
    connect(endpoint) {
        const url = `${this.baseUrl}${endpoint}?token=${this.jwtToken}`;
        
        this.ws = new WebSocket(url);
        
        this.ws.onopen = () => {
            console.log('Connected to WebSocket');
            
            // Subscribe to updates
            this.ws.send(JSON.stringify({
                type: 'subscribe',
                data: {
                    subscription_type: 'dashboard'
                }
            }));
        };
        
        this.ws.onmessage = (event) => {
            const data = JSON.parse(event.data);
            console.log('Received:', data);
            
            // Handle different message types
            switch (data.type) {
                case 'connection_established':
                    console.log('Connection confirmed:', data.user);
                    break;
                case 'dashboard_update':
                    this.handleDashboardUpdate(data);
                    break;
                case 'error':
                    console.error('Error:', data.message);
                    break;
            }
        };
        
        this.ws.onerror = (error) => {
            console.error('WebSocket error:', error);
        };
        
        this.ws.onclose = (event) => {
            console.log('WebSocket closed:', event.code, event.reason);
            if (event.code === 1008) {
                console.error('Authentication failed');
            }
        };
    }
    
    disconnect() {
        if (this.ws) {
            this.ws.close();
        }
    }
    
    send(message) {
        if (this.ws && this.ws.readyState === WebSocket.OPEN) {
            this.ws.send(JSON.stringify(message));
        }
    }
    
    handleDashboardUpdate(data) {
        // Update your UI with the dashboard data
        console.log('Dashboard update:', data);
    }
}

// Usage
const token = localStorage.getItem('jwt_token');
const client = new AuthenticatedWebSocketClient('ws://localhost:8000', token);
client.connect('/analytics/realtime/dashboard');
"""


if __name__ == "__main__":
    asyncio.run(main())