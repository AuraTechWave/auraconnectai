#!/usr/bin/env python3
"""Test if the app can import properly"""

try:
    print("Testing import of app.main...")
    from app.main import app
    print("✓ Import successful!")
    print(f"✓ App type: {type(app)}")
    print(f"✓ App title: {app.title}")
    print(f"✓ App version: {app.version}")
    print("\nBackend is ready to start!")
except Exception as e:
    print(f"✗ Import failed: {type(e).__name__}: {e}")
    import traceback
    traceback.print_exc()