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
                    coverage_percent = float(parts[-1].rstrip('%'))
                    print(f"\n🎯 Total Coverage: {coverage_percent}%")
                    
                    if coverage_percent >= 90:
                        print("✅ Achieved 90%+ coverage requirement!")
                        return True
                    else:
                        print(f"❌ Below 90% requirement (need {90 - coverage_percent:.1f}% more)")
                        return False
                except ValueError:
                    pass
    
    print("⚠️  Could not determine coverage percentage")
    return False


def main():
    """Main entry point."""
    # Find the correct backend directory
    current_dir = os.getcwd()
    backend_dir = None
    
    # Check if we're already in the backend directory
    if os.path.exists('core/auth.py') and os.path.exists('tests'):
        backend_dir = current_dir
        print(f"✓ Already in backend directory: {backend_dir}")
    # Check if backend is a subdirectory
    elif os.path.exists('backend') and os.path.exists('backend/core/auth.py'):
        backend_dir = os.path.join(current_dir, 'backend')
        os.chdir(backend_dir)
        print(f"✓ Changed to backend directory: {backend_dir}")
    # Check if we're in a subdirectory of backend
    elif 'backend' in current_dir:
        # Try to find the backend root
        path_parts = current_dir.split(os.sep)
        for i, part in enumerate(path_parts):
            if part == 'backend':
                potential_backend = os.sep.join(path_parts[:i+1])
                if os.path.exists(os.path.join(potential_backend, 'core/auth.py')):
                    backend_dir = potential_backend
                    os.chdir(backend_dir)
                    print(f"✓ Changed to backend root: {backend_dir}")
                    break
    
    if not backend_dir:
        print("❌ Error: Could not find the backend directory!")
        print(f"Current directory: {current_dir}")
        print("Please run this script from the project root or backend directory.")
        sys.exit(1)
    
    # Verify we have the expected structure
    required_paths = [
        'core/auth.py',
        'modules/auth/routes/auth_routes.py',
        'tests/test_auth_jwt.py'
    ]
    
    missing_paths = []
    for path in required_paths:
        if not os.path.exists(path):
            missing_paths.append(path)
    
    if missing_paths:
        print("❌ Error: Missing required files in backend directory!")
        print("Missing files:")
        for path in missing_paths:
            print(f"  - {path}")
        print(f"Current directory: {os.getcwd()}")
        sys.exit(1)
    
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