#!/usr/bin/env python3
"""
Test backend startup in a controlled manner
"""

import sys
import os

# Add backend to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'backend'))

# Set required environment variables
os.environ['DATABASE_URL'] = 'postgresql://auraconnect:auraconnect123@localhost:5432/auraconnect_dev'
os.environ['JWT_SECRET_KEY'] = 'your-super-secret-key-change-this-in-production'
os.environ['REDIS_URL'] = 'redis://localhost:6379/0'
os.environ['ENVIRONMENT'] = 'development'
os.environ['SESSION_SECRET'] = 'development-session-secret-change-in-production'
os.environ['SECRET_KEY'] = 'development-secret-key-change-in-production'

print("Testing backend imports...")

try:
    print("1. Testing FastAPI import...")
    from fastapi import FastAPI
    print("✓ FastAPI imported successfully")
    
    print("2. Testing pydantic imports...")
    from pydantic import BaseModel, Field
    from pydantic_settings import BaseSettings
    print("✓ Pydantic imported successfully")
    
    print("3. Testing core config...")
    from core.config import get_settings
    settings = get_settings()
    print("✓ Core config loaded successfully")
    
    print("4. Testing database connection...")
    from core.database import get_db, engine
    print("✓ Database module loaded successfully")
    
    print("5. Testing main app import...")
    from app.main import app
    print("✓ Main app imported successfully")
    
    print("\n✅ All backend imports successful!")
    print(f"FastAPI app: {app}")
    print(f"App title: {app.title}")
    print(f"App version: {app.version}")
    
except Exception as e:
    print(f"\n❌ Error: {type(e).__name__}: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)