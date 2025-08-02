#!/bin/bash

# Login and get fresh token
echo "Getting fresh authentication token..."
RESPONSE=$(curl -s -X POST "http://localhost:8000/auth/login" \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=admin&password=secret")

TOKEN=$(echo $RESPONSE | jq -r '.access_token')

if [ "$TOKEN" == "null" ]; then
    echo "Failed to authenticate"
    echo $RESPONSE | jq
    exit 1
fi

echo "Successfully authenticated"

# Test payroll run
echo -e "\nTesting payroll run..."
curl -X POST "http://localhost:8000/payrolls/run" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "pay_period_start": "2025-01-15",
    "pay_period_end": "2025-01-31", 
    "tenant_id": 1,
    "force_recalculate": false
  }' -s | jq

# If successful, check the status
echo -e "\nChecking payroll endpoints..."
curl -X GET "http://localhost:8000/api/payroll/health" \
  -H "Authorization: Bearer $TOKEN" -s | jq