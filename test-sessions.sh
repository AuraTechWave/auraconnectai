#!/bin/bash

# Test session management

echo "=== Testing Session Management ==="

# Get current token
if [ -z "$ACCESS_TOKEN" ]; then
    if [ -f .access_token ]; then
        ACCESS_TOKEN=$(cat .access_token)
    else
        echo "No access token found. Please login first."
        exit 1
    fi
fi

# 1. Get current session info
echo -e "\n1. Current sessions:"
curl -s -X GET "http://localhost:8000/auth/sessions" \
  -H "Authorization: Bearer $ACCESS_TOKEN" | python3 -m json.tool

# 2. Extract session ID from token (if available in response)
echo -e "\n2. Current token info:"
./auth-helper.sh status

# 3. Show how to logout current session
echo -e "\n3. To logout current session:"
echo "curl -X POST \"http://localhost:8000/auth/logout\" \\"
echo "  -H \"Authorization: Bearer \$ACCESS_TOKEN\" \\"
echo "  -H \"Content-Type: application/json\" \\"
echo "  -d '{\"logout_all_sessions\": false}'"

# 4. Show how to logout all sessions
echo -e "\n4. To logout ALL sessions:"
echo "curl -X POST \"http://localhost:8000/auth/logout\" \\"
echo "  -H \"Authorization: Bearer \$ACCESS_TOKEN\" \\"
echo "  -H \"Content-Type: application/json\" \\"
echo "  -d '{\"logout_all_sessions\": true}'"

# 5. Get session ID from auth response if available
if [ -f .auth_response.json ]; then
    SESSION_ID=$(python3 -c "import json; data=json.load(open('.auth_response.json')); print(data.get('session_id', 'not found'))")
    echo -e "\n5. Your current session ID: $SESSION_ID"
    
    if [ "$SESSION_ID" != "not found" ]; then
        echo -e "\nTo revoke THIS specific session:"
        echo "curl -X DELETE \"http://localhost:8000/auth/sessions/$SESSION_ID\" \\"
        echo "  -H \"Authorization: Bearer \$ACCESS_TOKEN\""
    fi
fi