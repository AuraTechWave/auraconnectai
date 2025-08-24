#!/usr/bin/env python3
"""
Test backend startup and report the first error
"""

import sys
import os
import subprocess
import time

# Add backend to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'backend'))

# Set required environment variables
os.environ['DATABASE_URL'] = 'postgresql://auraconnect:auraconnect123@localhost:5432/auraconnect_dev'
os.environ['JWT_SECRET_KEY'] = 'your-super-secret-key-change-this-in-production'
os.environ['REDIS_URL'] = 'redis://localhost:6379/0'
os.environ['ENVIRONMENT'] = 'development'
os.environ['SESSION_SECRET'] = 'development-session-secret-change-in-production'
os.environ['SECRET_KEY'] = 'development-secret-key-change-in-production'

print("Testing backend startup...")
print("=" * 50)

try:
    # Try to import the app
    from app.main import app
    print("✅ Backend imported successfully!")
    print(f"   App title: {app.title}")
    print(f"   App version: {app.version}")
    
    # Try to run with uvicorn
    print("\nAttempting to start server...")
    cmd = [
        sys.executable, "-m", "uvicorn",
        "app.main:app",
        "--host", "0.0.0.0",
        "--port", "8000",
        "--reload"
    ]
    
    # Start the process
    proc = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        cwd=os.path.join(os.path.dirname(__file__), 'backend')
    )
    
    # Wait a bit for startup
    time.sleep(5)
    
    # Check if process is still running
    if proc.poll() is None:
        print("✅ Server appears to be running!")
        print("   URL: http://localhost:8000")
        print("   Docs: http://localhost:8000/docs")
        print("\nTerminating test server...")
        proc.terminate()
        proc.wait()
    else:
        stdout, stderr = proc.communicate()
        print("❌ Server failed to start")
        if stderr:
            print("\nError output:")
            print(stderr)
    
except Exception as e:
    print(f"❌ Error: {type(e).__name__}: {e}")
    import traceback
    traceback.print_exc()
    
    # Try to identify the specific issue
    error_msg = str(e)
    if "cannot import name" in error_msg:
        print(f"\n💡 Suggestion: Fix the import error for {error_msg.split('cannot import name')[1].split('from')[0].strip()}")
    elif "No module named" in error_msg:
        print(f"\n💡 Suggestion: Create or fix the module {error_msg.split('No module named')[1].strip()}")
    
    sys.exit(1)