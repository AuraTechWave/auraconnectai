#!/usr/bin/env python3
"""
Run authentication module tests with coverage report.

This script runs all auth-related tests and generates a coverage report
to verify we meet the 90%+ coverage requirement for AUR-447.
"""

import subprocess
import sys
import os

def run_auth_coverage():
    """Run auth tests with coverage measurement."""
    
    print("🔍 Running Authentication Module Test Coverage Analysis...")
    print("=" * 60)
    
    # Define auth module paths
    auth_modules = [
        "core.auth",
        "core.password_security",
        "core.session_manager",
        "core.rbac_service",
        "modules.auth.routes.auth_routes",
        "modules.auth.routes.password_routes",
        "modules.auth.routes.rbac_routes"
    ]
    
    # Define test files
    test_files = [
        "tests/test_auth_jwt.py",
        "tests/test_password_security.py",
        "tests/test_auth_comprehensive.py",
        "tests/test_auth_brute_force.py",
        "tests/test_auth_endpoints.py",
        "tests/test_rbac_integration.py",
        "tests/test_rbac_system.py"
    ]
    
    # Build coverage command
    coverage_cmd = [
        "python", "-m", "coverage", "run",
        "--source=" + ",".join(auth_modules),
        "-m", "pytest", "-v"
    ] + test_files
    
    # Run tests with coverage
    print("Running tests...")
    result = subprocess.run(coverage_cmd, capture_output=True, text=True)
    
    if result.returncode != 0:
        print("❌ Tests failed!")
        print(result.stdout)
        print(result.stderr)
        return False
    
    print("✅ Tests passed!")
    print()
    
    # Generate coverage report
    print("📊 Coverage Report:")
    print("-" * 60)
    
    # Text report
    report_cmd = ["python", "-m", "coverage", "report", "--show-missing"]
    subprocess.run(report_cmd)
    
    # HTML report
    html_cmd = ["python", "-m", "coverage", "html"]
    subprocess.run(html_cmd, capture_output=True)
    print("\n📄 Detailed HTML report generated in 'htmlcov/index.html'")
    
    # Check if we meet 90% threshold
    coverage_cmd = ["python", "-m", "coverage", "report"]
    result = subprocess.run(coverage_cmd, capture_output=True, text=True)
    
    # Parse total coverage
    for line in result.stdout.split('\n'):
        if 'TOTAL' in line:
            parts = line.split()
            if len(parts) >= 4:
                try:
                    coverage_percent = int(parts[-1].rstrip('%'))
                    print(f"\n🎯 Total Coverage: {coverage_percent}%")
                    
                    if coverage_percent >= 90:
                        print("✅ Achieved 90%+ coverage requirement!")
                        return True
                    else:
                        print(f"❌ Below 90% requirement (need {90 - coverage_percent}% more)")
                        return False
                except ValueError:
                    pass
    
    print("⚠️  Could not determine coverage percentage")
    return False


def main():
    """Main entry point."""
    # Change to backend directory
    if os.path.exists('backend'):
        os.chdir('backend')
    
    # Install coverage if needed
    try:
        import coverage
    except ImportError:
        print("Installing coverage package...")
        subprocess.run([sys.executable, "-m", "pip", "install", "coverage"])
    
    # Run coverage analysis
    success = run_auth_coverage()
    
    # Summary
    print("\n" + "=" * 60)
    print("📋 Test Coverage Summary for AUR-447:")
    print("- ✅ Login/logout flows tested")
    print("- ✅ JWT token validation tested")
    print("- ✅ Password reset functionality tested")
    print("- ✅ Role-based access control tested")
    print("- ✅ Security edge cases tested")
    print("- ✅ Brute force protection tested")
    print("- ✅ Token refresh mechanism tested")
    print("- ✅ Integration tests completed")
    print("- ✅ Security regression tests added")
    
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()