#!/usr/bin/env python3
"""Test backend startup with minimal environment setup"""

import sys
import os
import traceback

# Add backend directory to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Set minimal required environment variables for testing
os.environ["JWT_SECRET_KEY"] = "test-secret-key-do-not-use-in-production"
os.environ["DATABASE_URL"] = "postgresql://user:pass@localhost/auraconnect"
os.environ["REDIS_URL"] = "redis://localhost:6379"
os.environ["RESTAURANT_NAME"] = "Test Restaurant"
os.environ["RESTAURANT_ID"] = "1"
os.environ["ENVIRONMENT"] = "development"

def test_startup():
    """Test backend startup and identify issues"""
    print("Testing backend startup with environment variables...")
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
        route_count = 0
        for route in app.routes:
            if hasattr(route, 'path'):
                route_count += 1
                if route_count <= 10:  # Show first 10 routes
                    print(f"  {route.path}")
        print(f"  ... and {route_count - 10} more routes" if route_count > 10 else "")
        
        print(f"\nTotal routes: {route_count}")
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