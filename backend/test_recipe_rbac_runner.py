#!/usr/bin/env python3

"""
Test runner for Recipe RBAC tests.
This script runs the RBAC tests and provides a summary of permission enforcement.
"""

import subprocess
import sys
import os

# Add backend to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def run_rbac_tests():
    """Run all RBAC tests and display results"""
    print("=" * 80)
    print("RECIPE MANAGEMENT RBAC TEST SUITE")
    print("=" * 80)
    print()
    
    test_files = [
        "modules/menu/tests/test_recipe_rbac.py",
        "modules/menu/tests/test_recipe_rbac_integration.py"
    ]
    
    total_passed = 0
    total_failed = 0
    
    for test_file in test_files:
        print(f"\n Running {test_file}...")
        print("-" * 60)
        
        try:
            # Run pytest with verbose output
            result = subprocess.run(
                [sys.executable, "-m", "pytest", test_file, "-v", "--tb=short"],
                capture_output=True,
                text=True
            )
            
            # Parse output for results
            output = result.stdout + result.stderr
            
            if "passed" in output:
                # Extract test counts
                import re
                match = re.search(r'(\d+) passed', output)
                if match:
                    passed = int(match.group(1))
                    total_passed += passed
                    print(f"✅ {passed} tests passed")
            
            if "failed" in output:
                match = re.search(r'(\d+) failed', output)
                if match:
                    failed = int(match.group(1))
                    total_failed += failed
                    print(f"❌ {failed} tests failed")
            
            if result.returncode != 0 and "failed" not in output:
                print("❌ Test execution failed")
                print(output)
                total_failed += 1
                
        except Exception as e:
            print(f"❌ Error running tests: {e}")
            total_failed += 1
    
    print("\n" + "=" * 80)
    print("RBAC TEST SUMMARY")
    print("=" * 80)
    print(f"Total Tests Passed: {total_passed}")
    print(f"Total Tests Failed: {total_failed}")
    
    if total_failed == 0:
        print("\n✅ All RBAC tests passed! Permission enforcement is working correctly.")
    else:
        print("\n❌ Some RBAC tests failed. Please review the permission enforcement.")
    
    # Display permission matrix
    print("\n" + "=" * 80)
    print("PERMISSION MATRIX")
    print("=" * 80)
    print()
    print("Endpoint                           | Admin | Manager | Chef | Waiter | Unauthorized")
    print("-" * 85)
    
    permissions = [
        ("GET    /recipes/{id}",           "✅",   "✅",     "✅",  "✅",    "❌"),
        ("POST   /recipes/",               "✅",   "✅",     "✅",  "❌",    "❌"),
        ("PUT    /recipes/{id}",           "✅",   "✅",     "✅",  "❌",    "❌"),
        ("DELETE /recipes/{id}",           "✅",   "✅",     "❌",  "❌",    "❌"),
        ("POST   /recipes/recalculate-costs", "✅", "❌",     "❌",  "❌",    "❌"),
        ("PUT    /recipes/bulk/update",    "✅",   "✅",     "❌",  "❌",    "❌"),
        ("PUT    /recipes/bulk/activate",  "✅",   "✅",     "❌",  "❌",    "❌"),
        ("POST   /recipes/{id}/approve",   "✅",   "✅",     "❌",  "❌",    "❌"),
        ("GET    /recipes/public/nutrition", "✅",  "✅",     "✅",  "✅",    "✅"),
    ]
    
    for endpoint, admin, manager, chef, waiter, unauth in permissions:
        print(f"{endpoint:<35} | {admin:<5} | {manager:<7} | {chef:<4} | {waiter:<6} | {unauth}")
    
    print("\n✅ = Allowed | ❌ = Denied")
    
    return total_failed == 0


if __name__ == "__main__":
    success = run_rbac_tests()
    sys.exit(0 if success else 1)