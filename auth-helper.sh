#!/bin/bash

# Enhanced authentication helper script

# Colors for output
GREEN='\033[0;32m'
RED='\033[0;31m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Function to login and save tokens
login() {
    local USERNAME="${1:-admin}"
    local PASSWORD="${2:-secret}"
    
    echo -e "${BLUE}Logging in as $USERNAME...${NC}"
    
    # Login and save full response
    RESPONSE=$(curl -s -X POST "http://localhost:8000/auth/login" \
      -H "Content-Type: application/x-www-form-urlencoded" \
      -d "username=$USERNAME&password=$PASSWORD")
    
    # Check if login was successful
    if echo "$RESPONSE" | grep -q "access_token"; then
        # Parse and save tokens
        echo "$RESPONSE" | python3 -c "
import sys, json
data = json.load(sys.stdin)

# Save tokens
with open('.access_token', 'w') as f:
    f.write(data['access_token'])
with open('.refresh_token', 'w') as f:
    f.write(data['refresh_token'])

# Save full response for reference
with open('.auth_response.json', 'w') as f:
    json.dump(data, f, indent=2)

print(f\"✅ Login successful!\")
print(f\"  User: {data['user_info']['username']}\")
print(f\"  Roles: {', '.join(data['user_info']['roles'])}\")
print(f\"  Access expires in: {data['access_expires_in']} seconds\")
print(f\"  Refresh expires in: {data['refresh_expires_in']} seconds\")
"
        echo -e "${GREEN}Tokens saved to .access_token and .refresh_token${NC}"
        return 0
    else
        echo -e "${RED}❌ Login failed!${NC}"
        echo "$RESPONSE" | python3 -m json.tool
        return 1
    fi
}

# Function to refresh access token
refresh() {
    if [ ! -f .refresh_token ]; then
        echo -e "${RED}No refresh token found. Please login first.${NC}"
        return 1
    fi
    
    REFRESH_TOKEN=$(cat .refresh_token)
    echo -e "${BLUE}Refreshing access token...${NC}"
    
    RESPONSE=$(curl -s -X POST "http://localhost:8000/auth/refresh" \
      -H "Content-Type: application/json" \
      -d "{\"refresh_token\": \"$REFRESH_TOKEN\"}")
    
    if echo "$RESPONSE" | grep -q "access_token"; then
        # Save new access token
        echo "$RESPONSE" | python3 -c "
import sys, json
data = json.load(sys.stdin)
with open('.access_token', 'w') as f:
    f.write(data['access_token'])
print('✅ Access token refreshed!')
"
        return 0
    else
        echo -e "${RED}❌ Token refresh failed!${NC}"
        echo "$RESPONSE" | python3 -m json.tool
        return 1
    fi
}

# Function to make authenticated request
auth_request() {
    if [ ! -f .access_token ]; then
        echo -e "${RED}No access token found. Please login first.${NC}"
        return 1
    fi
    
    ACCESS_TOKEN=$(cat .access_token)
    METHOD="${1:-GET}"
    ENDPOINT="${2:-/auth/me}"
    DATA="${3:-}"
    
    echo -e "${BLUE}Making $METHOD request to $ENDPOINT...${NC}"
    
    if [ -z "$DATA" ]; then
        curl -s -X "$METHOD" "http://localhost:8000$ENDPOINT" \
          -H "Authorization: Bearer $ACCESS_TOKEN" | python3 -m json.tool
    else
        curl -s -X "$METHOD" "http://localhost:8000$ENDPOINT" \
          -H "Authorization: Bearer $ACCESS_TOKEN" \
          -H "Content-Type: application/json" \
          -d "$DATA" | python3 -m json.tool
    fi
}

# Function to show current auth status
status() {
    if [ -f .auth_response.json ]; then
        echo -e "${BLUE}Current authentication status:${NC}"
        python3 -c "
import json
import time
from datetime import datetime

with open('.auth_response.json', 'r') as f:
    data = json.load(f)

# Check if tokens exist
access_exists = False
refresh_exists = False
try:
    with open('.access_token', 'r') as f:
        access_token = f.read().strip()
        access_exists = bool(access_token)
    with open('.refresh_token', 'r') as f:
        refresh_token = f.read().strip()
        refresh_exists = bool(refresh_token)
except:
    pass

print(f\"  User: {data['user_info']['username']}\")
print(f\"  Roles: {', '.join(data['user_info']['roles'])}\")
print(f\"  Session ID: {data['session_id']}\")
print(f\"  Access token exists: {'✅' if access_exists else '❌'}\")
print(f\"  Refresh token exists: {'✅' if refresh_exists else '❌'}\")

# Try to decode access token to check expiration
if access_exists:
    try:
        from jose import jwt
        payload = jwt.get_unverified_claims(access_token)
        exp = payload.get('exp', 0)
        now = time.time()
        if exp > now:
            remaining = int(exp - now)
            print(f\"  Access token expires in: {remaining} seconds ({remaining//60} minutes)\")
        else:
            print(f\"  Access token: EXPIRED\")
    except:
        print(f\"  Access token expiration: Unable to check\")
"
    else
        echo -e "${RED}No authentication data found. Please login first.${NC}"
    fi
}

# Main command handler
case "${1:-help}" in
    login)
        login "${2:-admin}" "${3:-secret}"
        ;;
    refresh)
        refresh
        ;;
    get)
        auth_request "GET" "${2:-/auth/me}"
        ;;
    post)
        auth_request "POST" "$2" "$3"
        ;;
    put)
        auth_request "PUT" "$2" "$3"
        ;;
    delete)
        auth_request "DELETE" "$2"
        ;;
    status)
        status
        ;;
    test)
        # Quick test of auth
        auth_request "GET" "/auth/me"
        ;;
    *)
        echo "AuraConnect Authentication Helper"
        echo ""
        echo "Usage: ./auth-helper.sh [command] [args]"
        echo ""
        echo "Commands:"
        echo "  login [username] [password]  - Login and save tokens (default: admin/secret)"
        echo "  refresh                      - Refresh access token using refresh token"
        echo "  status                       - Show current authentication status"
        echo "  test                         - Test authentication with /auth/me"
        echo "  get [endpoint]               - Make authenticated GET request"
        echo "  post [endpoint] [data]       - Make authenticated POST request"
        echo "  put [endpoint] [data]        - Make authenticated PUT request"
        echo "  delete [endpoint]            - Make authenticated DELETE request"
        echo ""
        echo "Examples:"
        echo "  ./auth-helper.sh login"
        echo "  ./auth-helper.sh login manager secret"
        echo "  ./auth-helper.sh get /payrolls/1"
        echo "  ./auth-helper.sh post /payrolls/run '{\"staff_ids\":[1,2,3]}'"
        echo ""
        echo "Token files:"
        echo "  .access_token       - Current access token"
        echo "  .refresh_token      - Current refresh token"
        echo "  .auth_response.json - Full login response"
        ;;
esac