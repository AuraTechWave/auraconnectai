#!/usr/bin/env python3
"""Debug authentication issues"""

import os
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Set environment to use in-memory session storage
os.environ["REDIS_URL"] = ""

from core.auth import authenticate_user, create_user_session, verify_password, MOCK_USERS
from core.session_manager import session_manager

print("Testing AuraConnect Authentication System")
print("=" * 50)

# Check available users
print("\nAvailable test users:")
for username, user_data in MOCK_USERS.items():
    print(f"  - {username} (password: secret)")

# Test password verification
print("\nTesting password verification...")
test_password = "secret"
for username, user_data in MOCK_USERS.items():
    result = verify_password(test_password, user_data['hashed_password'])
    print(f"  {username}: {'✓' if result else '✗'}")

# Test authentication
print("\nTesting authenticate_user function...")
user = authenticate_user("admin", "secret")
if user:
    print(f"  ✓ Authentication successful for admin")
    print(f"    ID: {user.id}")
    print(f"    Username: {user.username}")
    print(f"    Roles: {user.roles}")
else:
    print("  ✗ Authentication failed")

# Test session creation
if user:
    print("\nTesting session creation...")
    try:
        session_data = create_user_session(user)
        print("  ✓ Session created successfully")
        print(f"    Session ID: {session_data['session_id']}")
        print(f"    Access token: {session_data['access_token'][:50]}...")
        print(f"    Refresh token: {session_data['refresh_token'][:50]}...")
        
        # Check session in manager
        session = session_manager.get_session(session_data['session_id'])
        if session:
            print("  ✓ Session verified in manager")
        else:
            print("  ✗ Session not found in manager")
            
    except Exception as e:
        print(f"  ✗ Session creation failed: {e}")
        import traceback
        traceback.print_exc()

print("\nSession Manager Info:")
print(f"  Type: {type(session_manager).__name__}")
print(f"  Using Redis: {hasattr(session_manager, 'redis') and session_manager.redis is not None}")