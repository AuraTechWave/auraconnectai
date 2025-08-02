#!/bin/bash

# Quick authentication script with both tokens

# Login and save response
RESPONSE=$(curl -s -X POST "http://localhost:8000/auth/login" \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=${1:-admin}&password=${2:-secret}")

# Extract and save both tokens
ACCESS_TOKEN=$(echo "$RESPONSE" | python3 -c "import sys, json; print(json.load(sys.stdin)['access_token'])")
REFRESH_TOKEN=$(echo "$RESPONSE" | python3 -c "import sys, json; print(json.load(sys.stdin)['refresh_token'])")

# Export tokens as environment variables
export ACCESS_TOKEN="$ACCESS_TOKEN"
export REFRESH_TOKEN="$REFRESH_TOKEN"

# Also save to files
echo "$ACCESS_TOKEN" > .access_token
echo "$REFRESH_TOKEN" > .refresh_token

# Display results
echo "✅ Authentication successful!"
echo ""
echo "Tokens saved to files:"
echo "  .access_token"
echo "  .refresh_token"
echo ""
echo "Environment variables set:"
echo "  \$ACCESS_TOKEN"
echo "  \$REFRESH_TOKEN"
echo ""
echo "Quick test:"
echo "  curl -H \"Authorization: Bearer \$ACCESS_TOKEN\" http://localhost:8000/auth/me"
echo ""
echo "Or use from files:"
echo "  curl -H \"Authorization: Bearer \$(cat .access_token)\" http://localhost:8000/auth/me"