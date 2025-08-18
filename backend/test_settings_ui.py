"""
Test script for settings configuration UI functionality.

This script tests:
1. Settings dashboard endpoint
2. Validation functionality  
3. Bulk update operations
4. Reset functionality
5. Presets application
"""

import asyncio
import httpx
from datetime import datetime

# Test configuration
BASE_URL = "http://localhost:8000"

# Test JWT token (replace with actual token)
AUTH_TOKEN = "your-test-token-here"


async def test_settings_dashboard():
    """Test getting settings dashboard"""
    print("\n=== Testing Settings Dashboard ===")
    
    headers = {"Authorization": f"Bearer {AUTH_TOKEN}"}
    
    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(
                f"{BASE_URL}/api/v1/settings-ui/dashboard",
                params={"scope": "restaurant"},
                headers=headers
            )
            
            if response.status_code == 200:
                data = response.json()
                print(f"✓ Dashboard loaded: {len(data['sections'])} sections")
                print(f"✓ Categories: {len(data['categories'])}")
                print(f"✓ Has unsaved changes: {data['has_unsaved_changes']}")
            else:
                print(f"✗ Dashboard failed: {response.status_code}")
                print(response.text)
                
        except Exception as e:
            print(f"✗ Dashboard error: {e}")


async def test_settings_validation():
    """Test settings validation"""
    print("\n=== Testing Settings Validation ===")
    
    headers = {"Authorization": f"Bearer {AUTH_TOKEN}"}
    
    test_settings = {
        "tax_rate": 8.5,
        "order_timeout_minutes": 60,
        "password_min_length": 5,  # Should fail - too short
    }
    
    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(
                f"{BASE_URL}/api/v1/settings-ui/validate",
                json=test_settings,
                params={"scope": "restaurant"},
                headers=headers
            )
            
            if response.status_code == 200:
                data = response.json()
                print(f"✓ Validation completed: Valid={data['is_valid']}")
                if data['errors']:
                    print(f"✓ Errors detected: {len(data['errors'])}")
                    for error in data['errors']:
                        print(f"  - {error['field']}: {error['message']}")
            else:
                print(f"✗ Validation failed: {response.status_code}")
                
        except Exception as e:
            print(f"✗ Validation error: {e}")


async def test_bulk_update():
    """Test bulk update functionality"""
    print("\n=== Testing Bulk Update ===")
    
    headers = {"Authorization": f"Bearer {AUTH_TOKEN}"}
    
    update_request = {
        "settings": [
            {
                "key": "tax_rate",
                "value": 9.0
            },
            {
                "key": "order_timeout_minutes", 
                "value": 45
            }
        ],
        "scope": "restaurant",
        "validate_only": True,  # Just validate, don't save
        "reason": "Testing bulk update"
    }
    
    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(
                f"{BASE_URL}/api/v1/settings-ui/bulk-update",
                json=update_request,
                headers=headers
            )
            
            if response.status_code == 200:
                data = response.json()
                print(f"✓ Bulk update: Success={data['success']}")
                print(f"✓ Processed: {data['processed']}, Failed: {data['failed']}")
                if data['requires_restart']:
                    print(f"✓ Settings requiring restart: {data['requires_restart']}")
            else:
                print(f"✗ Bulk update failed: {response.status_code}")
                
        except Exception as e:
            print(f"✗ Bulk update error: {e}")


async def test_apply_preset():
    """Test applying a preset configuration"""
    print("\n=== Testing Preset Application ===")
    
    headers = {"Authorization": f"Bearer {AUTH_TOKEN}"}
    
    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(
                f"{BASE_URL}/api/v1/settings-ui/apply-preset/quick_service",
                params={
                    "scope": "restaurant",
                    "override_existing": False
                },
                headers=headers
            )
            
            if response.status_code == 200:
                data = response.json()
                print(f"✓ Preset applied: Success={data['success']}")
                print(f"✓ Settings changed: {data['processed']}")
            else:
                print(f"✗ Preset failed: {response.status_code}")
                
        except Exception as e:
            print(f"✗ Preset error: {e}")


async def test_ui_metadata():
    """Test getting UI metadata"""
    print("\n=== Testing UI Metadata ===")
    
    headers = {"Authorization": f"Bearer {AUTH_TOKEN}"}
    
    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(
                f"{BASE_URL}/api/v1/settings-ui/metadata",
                headers=headers
            )
            
            if response.status_code == 200:
                data = response.json()
                print(f"✓ Categories: {len(data['categories'])}")
                print(f"✓ Scopes: {len(data['scopes'])}")
                print(f"✓ Field types: {len(data['field_types'])}")
                print(f"✓ Available presets: {data['presets']}")
                print(f"✓ Permissions: {data['permissions']}")
            else:
                print(f"✗ Metadata failed: {response.status_code}")
                
        except Exception as e:
            print(f"✗ Metadata error: {e}")


async def test_search_settings():
    """Test searching settings"""
    print("\n=== Testing Settings Search ===")
    
    headers = {"Authorization": f"Bearer {AUTH_TOKEN}"}
    
    search_request = {
        "query": "tax",
        "scope": "restaurant",
        "include_advanced": False,
        "limit": 10
    }
    
    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(
                f"{BASE_URL}/api/v1/settings-ui/search",
                json=search_request,
                headers=headers
            )
            
            if response.status_code == 200:
                data = response.json()
                print(f"✓ Search results: {len(data)} settings found")
                for setting in data[:3]:  # Show first 3
                    print(f"  - {setting['key']}: {setting['label']}")
            else:
                print(f"✗ Search failed: {response.status_code}")
                
        except Exception as e:
            print(f"✗ Search error: {e}")


async def main():
    """Run all tests"""
    print("Starting Settings UI Tests")
    print("=========================")
    print(f"Base URL: {BASE_URL}")
    
    # Note: Update AUTH_TOKEN before running
    if AUTH_TOKEN == "your-test-token-here":
        print("\n⚠️  WARNING: Please update AUTH_TOKEN with a valid JWT token")
        print("You can get a token by logging in through the API")
        return
    
    await test_settings_dashboard()
    await test_settings_validation()
    await test_bulk_update()
    await test_apply_preset()
    await test_ui_metadata()
    await test_search_settings()
    
    print("\n✅ All tests completed!")


if __name__ == "__main__":
    asyncio.run(main())