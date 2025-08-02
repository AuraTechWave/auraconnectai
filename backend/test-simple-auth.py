#!/usr/bin/env python3
"""
Simple test to verify authentication is working without database
"""

import requests
import json

# Base URL
BASE_URL = "http://localhost:8000"

print("Testing AuraConnect Authentication")
print("=" * 50)

# Test root endpoint
try:
    response = requests.get(f"{BASE_URL}/")
    print(f"✓ Server is running: {response.json()['message']}")
except Exception as e:
    print(f"✗ Server not accessible: {e}")
    exit(1)

# Test login with in-memory user
print("\nTesting login with in-memory admin user...")
login_data = {
    "username": "admin",
    "password": "admin123"
}

response = requests.post(
    f"{BASE_URL}/auth/login",
    data=login_data
)

if response.status_code == 200:
    tokens = response.json()
    print(f"✓ Login successful!")
    print(f"  Access token: {tokens['access_token'][:50]}...")
    print(f"  Refresh token: {tokens['refresh_token'][:50]}...")
    
    # Test /auth/me endpoint
    headers = {"Authorization": f"Bearer {tokens['access_token']}"}
    me_response = requests.get(f"{BASE_URL}/auth/me", headers=headers)
    
    if me_response.status_code == 200:
        user_info = me_response.json()
        print(f"\n✓ User info retrieved:")
        print(f"  Username: {user_info['username']}")
        print(f"  Roles: {user_info.get('roles', [])}")
        print(f"  Tenant IDs: {user_info.get('tenant_ids', [])}")
    else:
        print(f"\n✗ Failed to get user info: {me_response.json()}")
        
    # Test sessions endpoint
    sessions_response = requests.get(f"{BASE_URL}/auth/sessions", headers=headers)
    if sessions_response.status_code == 200:
        sessions = sessions_response.json()
        print(f"\n✓ Sessions retrieved:")
        print(f"  Count: {sessions['count']}")
        print(f"  Sessions: {len(sessions['sessions'])}")
    else:
        print(f"\n✗ Failed to get sessions: {sessions_response.json()}")
        
else:
    print(f"✗ Login failed: {response.json()}")
    print("\nNote: The backend uses in-memory users when database is not available.")
    print("Default users should be created in core/auth.py")