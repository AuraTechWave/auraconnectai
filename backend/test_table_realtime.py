"""
Test script for real-time table status updates.

This script tests:
1. WebSocket connection
2. Real-time status updates
3. Turn time tracking
4. Analytics endpoints
"""

import asyncio
import json
import httpx
import websockets
from datetime import datetime, timedelta

# Test configuration
BASE_URL = "http://localhost:8000"
WS_URL = "ws://localhost:8000"
RESTAURANT_ID = 1

# Test JWT token (replace with actual token)
AUTH_TOKEN = "your-test-token-here"


async def test_websocket_connection():
    """Test WebSocket connection and real-time updates"""
    print("\n=== Testing WebSocket Connection ===")
    
    ws_endpoint = f"{WS_URL}/api/v1/tables/ws/tables/{RESTAURANT_ID}?token={AUTH_TOKEN}"
    
    try:
        async with websockets.connect(ws_endpoint) as websocket:
            print("✓ Connected to WebSocket")
            
            # Wait for initial state
            initial_state = await websocket.recv()
            data = json.loads(initial_state)
            print(f"✓ Received initial state: {data['type']}")
            
            # Send heartbeat
            await websocket.send(json.dumps({"type": "heartbeat"}))
            response = await websocket.recv()
            heartbeat_response = json.loads(response)
            print(f"✓ Heartbeat acknowledged: {heartbeat_response['type']}")
            
            # Request update
            await websocket.send(json.dumps({"type": "request_update"}))
            update = await websocket.recv()
            update_data = json.loads(update)
            print(f"✓ Update received: {update_data['type']}")
            
            # Subscribe to specific table
            await websocket.send(json.dumps({
                "type": "subscribe_table",
                "table_id": 1
            }))
            
            print("✓ WebSocket tests passed")
            
    except Exception as e:
        print(f"✗ WebSocket error: {e}")


async def test_analytics_endpoints():
    """Test REST API analytics endpoints"""
    print("\n=== Testing Analytics Endpoints ===")
    
    headers = {"Authorization": f"Bearer {AUTH_TOKEN}"}
    
    async with httpx.AsyncClient() as client:
        # Test current analytics
        try:
            response = await client.get(
                f"{BASE_URL}/api/v1/tables/analytics/current",
                headers=headers
            )
            if response.status_code == 200:
                data = response.json()
                print(f"✓ Current analytics: {data['overview']['occupancy_rate']}% occupancy")
            else:
                print(f"✗ Current analytics failed: {response.status_code}")
        except Exception as e:
            print(f"✗ Current analytics error: {e}")
        
        # Test turn time analytics
        try:
            end_date = datetime.now().date()
            start_date = end_date - timedelta(days=7)
            
            response = await client.get(
                f"{BASE_URL}/api/v1/tables/analytics/turn-times",
                params={
                    "start_date": start_date.isoformat(),
                    "end_date": end_date.isoformat(),
                    "group_by": "day"
                },
                headers=headers
            )
            if response.status_code == 200:
                data = response.json()
                print(f"✓ Turn time analytics: {len(data['analytics'])} days analyzed")
            else:
                print(f"✗ Turn time analytics failed: {response.status_code}")
        except Exception as e:
            print(f"✗ Turn time analytics error: {e}")
        
        # Test peak hours analysis
        try:
            response = await client.get(
                f"{BASE_URL}/api/v1/tables/analytics/peak-hours",
                params={"lookback_days": 30},
                headers=headers
            )
            if response.status_code == 200:
                data = response.json()
                if data['peak_hours']:
                    print(f"✓ Peak hours: {data['peak_hours'][0]['hour']}")
                else:
                    print("✓ Peak hours: No data available")
            else:
                print(f"✗ Peak hours failed: {response.status_code}")
        except Exception as e:
            print(f"✗ Peak hours error: {e}")
        
        # Test heat map data
        try:
            response = await client.get(
                f"{BASE_URL}/api/v1/tables/analytics/heat-map",
                params={"period_days": 7},
                headers=headers
            )
            if response.status_code == 200:
                data = response.json()
                print(f"✓ Heat map: {len(data['data'])} tables analyzed")
            else:
                print(f"✗ Heat map failed: {response.status_code}")
        except Exception as e:
            print(f"✗ Heat map error: {e}")


async def test_table_status_update():
    """Test updating table status through WebSocket"""
    print("\n=== Testing Table Status Update ===")
    
    ws_endpoint = f"{WS_URL}/api/v1/tables/ws/tables/{RESTAURANT_ID}?token={AUTH_TOKEN}"
    
    try:
        async with websockets.connect(ws_endpoint) as websocket:
            # Wait for initial connection
            await websocket.recv()
            
            print("✓ Connected for status update test")
            
            # In a real scenario, status updates would be triggered by API calls
            # Here we're just testing the WebSocket receives updates
            
            # Listen for any updates for 5 seconds
            print("Listening for updates for 5 seconds...")
            try:
                while True:
                    message = await asyncio.wait_for(websocket.recv(), timeout=5.0)
                    data = json.loads(message)
                    if data['type'] in ['table_update', 'turn_time_update', 'heat_map_update']:
                        print(f"✓ Received update: {data['type']}")
            except asyncio.TimeoutError:
                print("✓ Timeout reached (expected)")
                
    except Exception as e:
        print(f"✗ Status update test error: {e}")


async def main():
    """Run all tests"""
    print("Starting Real-Time Table Status Tests")
    print("=====================================")
    print(f"Base URL: {BASE_URL}")
    print(f"WebSocket URL: {WS_URL}")
    print(f"Restaurant ID: {RESTAURANT_ID}")
    
    # Note: Update AUTH_TOKEN before running
    if AUTH_TOKEN == "your-test-token-here":
        print("\n⚠️  WARNING: Please update AUTH_TOKEN with a valid JWT token")
        print("You can get a token by logging in through the API")
        return
    
    await test_analytics_endpoints()
    await test_websocket_connection()
    await test_table_status_update()
    
    print("\n✅ All tests completed!")


if __name__ == "__main__":
    asyncio.run(main())