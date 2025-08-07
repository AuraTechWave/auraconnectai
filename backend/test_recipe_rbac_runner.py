#!/usr/bin/env python3

"""
Test runner for Recipe RBAC tests with coverage reporting.
This script runs the RBAC tests and provides a summary of permission enforcement.
"""

import subprocess
import sys
import os
import argparse

# Add backend to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def run_rbac_tests(coverage=False, coverage_format="term"):
    """Run all RBAC tests and display results
    
    Args:
        coverage: Whether to run with coverage reporting
        coverage_format: Format for coverage report (term, html, xml)
    """
    print("=" * 80)
    print("RECIPE MANAGEMENT RBAC TEST SUITE")
    print("=" * 80)
    print()
    
    test_files = [
        "modules/menu/tests/test_recipe_rbac_basic_crud.py",
        "modules/menu/tests/test_recipe_rbac_admin_endpoints.py",
        "modules/menu/tests/test_recipe_rbac_manager_endpoints.py",
        "modules/menu/tests/test_recipe_rbac_public_access.py",
        "modules/menu/tests/test_recipe_rbac_edge_cases.py",
        "modules/menu/tests/test_recipe_rbac_integration.py"
    ]
    
    total_passed = 0
    total_failed = 0
    
    # Build pytest command
    cmd = [sys.executable, "-m", "pytest", "-v", "--tb=short"]
    
    if coverage:
        # Add coverage options
        cmd.extend([
            "--cov=modules.menu.routes.recipe_routes",
            "--cov=modules.menu.services.recipe_service",
            f"--cov-report={coverage_format}"
        ])
        
        if coverage_format == "html":
            cmd.append("--cov-report=html:htmlcov")
        elif coverage_format == "xml":
            cmd.append("--cov-report=xml:coverage.xml")
        elif coverage_format == "term-missing":
            cmd.append("--cov-report=term-missing")
    
    # Add all test files
    cmd.extend(test_files)
    
    try:
        # Run all tests together for better coverage reporting
        print(f"Running RBAC tests{' with coverage' if coverage else ''}...")
        print("-" * 60)
        
        result = subprocess.run(cmd, capture_output=True, text=True)
        
        # Parse output for results
        output = result.stdout + result.stderr
        print(output)  # Show full pytest output
        
        if "passed" in output:
            # Extract test counts
            import re
            match = re.search(r'(\d+) passed', output)
            if match:
                total_passed = int(match.group(1))
                print(f"\n✅ {total_passed} tests passed")
        
        if "failed" in output:
            match = re.search(r'(\d+) failed', output)
            if match:
                total_failed = int(match.group(1))
                print(f"❌ {total_failed} tests failed")
        
        if result.returncode != 0 and "failed" not in output:
            print("❌ Test execution failed")
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
    parser = argparse.ArgumentParser(description="Run Recipe RBAC tests with optional coverage")
    parser.add_argument("--coverage", "-c", action="store_true", help="Run with coverage reporting")
    parser.add_argument("--cov-format", choices=["term", "term-missing", "html", "xml"], 
                       default="term-missing", help="Coverage report format")
    
    args = parser.parse_args()
    
    success = run_rbac_tests(coverage=args.coverage, coverage_format=args.cov_format)
    sys.exit(0 if success else 1)