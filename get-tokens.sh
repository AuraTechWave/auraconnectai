#!/bin/bash

# Script to login and save both access and refresh tokens

# Default credentials
USERNAME="${1:-admin}"
PASSWORD="${2:-secret}"

# Login and get tokens
echo "Logging in as $USERNAME..."
RESPONSE=$(curl -s -X POST "http://localhost:8000/auth/login" \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=$USERNAME&password=$PASSWORD")

# Check if login was successful
if echo "$RESPONSE" | grep -q "access_token"; then
    # Extract tokens
    ACCESS_TOKEN=$(echo "$RESPONSE" | python3 -c "import sys, json; print(json.load(sys.stdin)['access_token'])")
    REFRESH_TOKEN=$(echo "$RESPONSE" | python3 -c "import sys, json; print(json.load(sys.stdin)['refresh_token'])")
    
    # Save to files
    echo "$ACCESS_TOKEN" > .access_token
    echo "$REFRESH_TOKEN" > .refresh_token
    
    # Also export as environment variables
    export ACCESS_TOKEN="$ACCESS_TOKEN"
    export REFRESH_TOKEN="$REFRESH_TOKEN"
    
    echo "✅ Login successful!"
    echo "Access token saved to: .access_token"
    echo "Refresh token saved to: .refresh_token"
    echo ""
    echo "To use the tokens:"
    echo "  ACCESS_TOKEN=\$(cat .access_token)"
    echo "  REFRESH_TOKEN=\$(cat .refresh_token)"
    echo ""
    echo "Or source this script to set environment variables:"
    echo "  source ./get-tokens.sh"
    echo ""
    echo "Example usage:"
    echo "  curl -H \"Authorization: Bearer \$ACCESS_TOKEN\" http://localhost:8000/auth/me"
    
    # Show token info
    echo ""
    echo "Token info:"
    echo "$RESPONSE" | python3 -c "
import sys, json
data = json.load(sys.stdin)
print(f\"  Access expires in: {data['access_expires_in']} seconds\")
print(f\"  Refresh expires in: {data['refresh_expires_in']} seconds\")
print(f\"  Session ID: {data['session_id']}\")
print(f\"  User: {data['user_info']['username']} (ID: {data['user_info']['id']})\")
print(f\"  Roles: {', '.join(data['user_info']['roles'])}\")
"
else
    echo "❌ Login failed!"
    echo "$RESPONSE" | python3 -m json.tool
    exit 1
fi