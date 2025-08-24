#!/usr/bin/env python3
"""Test backend startup without running the full server"""

import sys
import os
import traceback

# Add backend directory to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def test_startup():
    """Test backend startup and identify issues"""
    print("Testing backend startup...")
    print("=" * 60)
    
    try:
        # Import main app
        from app.main import app
        print("✅ Successfully imported FastAPI app")
        
        # Test that app is properly configured
        print(f"App title: {app.title}")
        print(f"App version: {app.version}")
        
        # List all routes
        print("\nRegistered routes:")
        for route in app.routes:
            if hasattr(route, 'path'):
                print(f"  {route.path}")
        
        print("\n✅ Backend startup successful!")
        return True
        
    except Exception as e:
        print(f"\n❌ Backend startup failed!")
        print(f"Error type: {type(e).__name__}")
        print(f"Error message: {str(e)}")
        print("\nTraceback:")
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = test_startup()
    sys.exit(0 if success else 1)