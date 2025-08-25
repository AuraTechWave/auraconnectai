#!/bin/bash

# AuraConnect - API Testing Script
# Quick tests to verify API endpoints are working

set -e

# Base URL
BASE_URL="http://localhost:8000"
API_URL="$BASE_URL/api/v1"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

echo "🧪 AuraConnect API Tester"
echo "========================"
echo ""

# Check if backend is running
if ! curl -s "$BASE_URL" >/dev/null; then
    echo -e "${RED}❌ Backend is not running!${NC}"
    echo "Start it with: ./start-all.sh or ./dev-helper.sh"
    exit 1
fi

# Variables to store tokens
ACCESS_TOKEN=""
REFRESH_TOKEN=""

# Function to test endpoint
test_endpoint() {
    local method=$1
    local endpoint=$2
    local description=$3
    local data=$4
    local auth=$5
    
    echo -ne "Testing $description... "
    
    # Build curl command
    CURL_CMD="curl -s -X $method \"$API_URL$endpoint\""
    
    if [ "$auth" = "true" ] && [ -n "$ACCESS_TOKEN" ]; then
        CURL_CMD="$CURL_CMD -H \"Authorization: Bearer $ACCESS_TOKEN\""
    fi
    
    if [ -n "$data" ]; then
        CURL_CMD="$CURL_CMD -H \"Content-Type: application/json\" -d '$data'"
    fi
    
    # Execute and check response
    RESPONSE=$(eval "$CURL_CMD")
    HTTP_CODE=$(eval "$CURL_CMD -w '\n%{http_code}'" | tail -n1)
    
    if [[ "$HTTP_CODE" =~ ^2[0-9][0-9]$ ]]; then
        echo -e "${GREEN}✓${NC} ($HTTP_CODE)"
        if [ "$endpoint" = "/auth/login" ]; then
            # Extract tokens from login response
            ACCESS_TOKEN=$(echo "$RESPONSE" | python -c "import sys, json; print(json.load(sys.stdin)['access_token'])" 2>/dev/null || echo "")
            REFRESH_TOKEN=$(echo "$RESPONSE" | python -c "import sys, json; print(json.load(sys.stdin)['refresh_token'])" 2>/dev/null || echo "")
        fi
    else
        echo -e "${RED}✗${NC} ($HTTP_CODE)"
        echo "Response: $RESPONSE"
    fi
}

echo -e "${BLUE}1. Public Endpoints${NC}"
echo "-------------------"
test_endpoint "GET" "/health/" "Health Check" "" "false"
test_endpoint "GET" "/health/ready" "Readiness Check" "" "false"

echo ""
echo -e "${BLUE}2. Authentication${NC}"
echo "-----------------"
test_endpoint "POST" "/auth/login" "Login (admin)" '{"username":"admin","password":"admin123"}' "false"

if [ -n "$ACCESS_TOKEN" ]; then
    echo ""
    echo -e "${BLUE}3. Protected Endpoints${NC}"
    echo "----------------------"
    test_endpoint "GET" "/auth/me" "Current User" "" "true"
    test_endpoint "GET" "/staff/" "List Staff" "" "true"
    test_endpoint "GET" "/menu/categories" "Menu Categories" "" "true"
    test_endpoint "GET" "/menu/items" "Menu Items" "" "true"
    test_endpoint "GET" "/inventory/" "Inventory Items" "" "true"
    test_endpoint "GET" "/orders/" "Orders" "" "true"
    test_endpoint "GET" "/customers/" "Customers" "" "true"
    test_endpoint "GET" "/tables/" "Tables" "" "true"
    test_endpoint "GET" "/settings/" "Settings" "" "true"
    test_endpoint "GET" "/analytics/dashboard" "Analytics Dashboard" "" "true"
    
    echo ""
    echo -e "${BLUE}4. Health Monitoring${NC}"
    echo "--------------------"
    test_endpoint "GET" "/health/metrics" "Health Metrics" "" "true"
    test_endpoint "GET" "/health/system" "System Status" "" "true"
    test_endpoint "GET" "/health/errors" "Error Logs" "" "true"
else
    echo -e "${RED}❌ Login failed - cannot test protected endpoints${NC}"
fi

echo ""
echo -e "${BLUE}5. WebSocket Test${NC}"
echo "-----------------"
echo -ne "Testing WebSocket connection... "

# Simple WebSocket test using Python
python3 - << EOF 2>/dev/null
import asyncio
import websockets
import json

async def test_websocket():
    try:
        uri = "ws://localhost:8000/ws"
        async with websockets.connect(uri) as websocket:
            # Send auth message if we have a token
            if "$ACCESS_TOKEN":
                await websocket.send(json.dumps({
                    "type": "auth",
                    "token": "$ACCESS_TOKEN"
                }))
            
            # Send a ping
            await websocket.send(json.dumps({"type": "ping"}))
            
            # Wait for response with timeout
            response = await asyncio.wait_for(websocket.recv(), timeout=5.0)
            data = json.loads(response)
            
            if data.get("type") == "pong":
                print("✓")
                return True
    except Exception as e:
        print("✗")
        print(f"Error: {e}")
        return False

asyncio.run(test_websocket())
EOF

if [ $? -ne 0 ]; then
    echo -e "${YELLOW}WebSocket test requires 'websockets' library${NC}"
    echo "Install with: pip install websockets"
fi

echo ""
echo "========================"
echo -e "${GREEN}API testing complete!${NC}"
echo ""
echo "For detailed API documentation, visit:"
echo "- Swagger UI: $BASE_URL/docs"
echo "- ReDoc: $BASE_URL/redoc"