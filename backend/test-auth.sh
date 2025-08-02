#!/bin/bash

# Login as admin
echo "Logging in as admin..."
response=$(curl -s -X POST "http://localhost:8000/auth/login" \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=admin&password=secret")

# Extract tokens
access_token=$(echo $response | jq -r '.access_token')
refresh_token=$(echo $response | jq -r '.refresh_token')

echo "Access token: ${access_token:0:50}..."
echo "Refresh token: ${refresh_token:0:50}..."

# Get user info
echo -e "\nGetting user info..."
curl -s -X GET "http://localhost:8000/auth/me" \
  -H "Authorization: Bearer $access_token" | jq

# Check sessions
echo -e "\nChecking sessions..."
curl -s -X GET "http://localhost:8000/auth/sessions" \
  -H "Authorization: Bearer $access_token" | jq