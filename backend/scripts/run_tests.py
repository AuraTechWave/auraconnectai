#!/usr/bin/env python3
"""
Test runner script for AUR-279 Phase 5 Testing.

Provides organized test execution with coverage reporting and categorized test runs.
"""

import sys
import subprocess
import argparse
from pathlib import Path
from typing import List, Optional


def run_command(cmd: List[str], description: str) -> int:
    """Run a command and return the exit code."""
    print(f"\n🔄 {description}")
    print(f"Running: {' '.join(cmd)}")
    print("-" * 50)
    
    result = subprocess.run(cmd, capture_output=False)
    
    if result.returncode == 0:
        print(f"✅ {description} completed successfully")
    else:
        print(f"❌ {description} failed with exit code {result.returncode}")
    
    return result.returncode


def run_unit_tests(coverage: bool = True) -> int:
    """Run unit tests for all modules."""
    cmd = ["python", "-m", "pytest"]
    
    if coverage:
        cmd.extend([
            "--cov=modules",
            "--cov-report=html:htmlcov",
            "--cov-report=term-missing",
            "--cov-report=xml"
        ])
    
    cmd.extend([
        "-m", "unit",
        "-v",
        "tests/test_tax_services.py",
        "tests/test_payroll_engine.py"
    ])
    
    return run_command(cmd, "Unit Tests")


def run_api_tests() -> int:
    """Run API endpoint tests."""
    cmd = [
        "python", "-m", "pytest",
        "-m", "api",
        "-v",
        "tests/test_payroll_api.py"
    ]
    
    return run_command(cmd, "API Tests")


def run_integration_tests() -> int:
    """Run integration tests."""
    cmd = [
        "python", "-m", "pytest",
        "-m", "integration or e2e",
        "-v",
        "tests/test_enhanced_payroll_e2e.py"
    ]
    
    return run_command(cmd, "Integration Tests")


def run_performance_tests() -> int:
    """Run performance and load tests."""
    cmd = [
        "python", "-m", "pytest",
        "-m", "performance",
        "-v",
        "tests/test_performance.py"
    ]
    
    return run_command(cmd, "Performance Tests")


def run_all_tests(coverage: bool = True) -> int:
    """Run all tests with comprehensive coverage."""
    cmd = ["python", "-m", "pytest"]
    
    if coverage:
        cmd.extend([
            "--cov=modules",
            "--cov-report=html:htmlcov",
            "--cov-report=term-missing",
            "--cov-report=xml",
            "--cov-fail-under=90"
        ])
    
    cmd.extend([
        "-v",
        "--tb=short",
        "tests/"
    ])
    
    return run_command(cmd, "All Tests")


def run_specific_module_tests(module: str) -> int:
    """Run tests for a specific module."""
    module_tests = {
        "tax": "tests/test_tax_services.py",
        "payroll": "tests/test_payroll_engine.py", 
        "api": "tests/test_payroll_api.py",
        "e2e": "tests/test_enhanced_payroll_e2e.py",
        "performance": "tests/test_performance.py"
    }
    
    if module not in module_tests:
        print(f"❌ Unknown module: {module}")
        print(f"Available modules: {', '.join(module_tests.keys())}")
        return 1
    
    cmd = [
        "python", "-m", "pytest",
        "-v",
        module_tests[module]
    ]
    
    return run_command(cmd, f"{module.title()} Module Tests")


def check_coverage_threshold() -> int:
    """Check if coverage meets the 90% threshold."""
    cmd = [
        "python", "-m", "pytest",
        "--cov=modules",
        "--cov-fail-under=90",
        "--cov-report=term-missing",
        "--tb=no",
        "-q"
    ]
    
    return run_command(cmd, "Coverage Threshold Check (90%)")


def generate_coverage_report() -> int:
    """Generate detailed coverage report."""
    cmd = [
        "python", "-m", "pytest",
        "--cov=modules",
        "--cov-report=html:htmlcov",
        "--cov-report=xml",
        "--cov-report=term",
        "--tb=no",
        "-q"
    ]
    
    result = run_command(cmd, "Coverage Report Generation")
    
    if result == 0:
        print("\n📊 Coverage reports generated:")
        print("  - HTML: htmlcov/index.html")
        print("  - XML: coverage.xml")
    
    return result


def lint_and_format_check() -> int:
    """Run linting and format checks."""
    print("\n🔍 Running code quality checks...")
    
    # Check if tools are available
    tools_available = True
    
    # Try flake8
    try:
        subprocess.run(["flake8", "--version"], capture_output=True, check=True)
        flake8_cmd = [
            "flake8",
            "modules/",
            "--max-line-length=100",
            "--ignore=E203,W503",
            "--exclude=__pycache__,*.pyc,.git,alembic/versions"
        ]
        flake8_result = run_command(flake8_cmd, "Flake8 Linting")
    except (subprocess.CalledProcessError, FileNotFoundError):
        print("⚠️  flake8 not available, skipping linting check")
        flake8_result = 0
        tools_available = False
    
    # Try black format check
    try:
        subprocess.run(["black", "--version"], capture_output=True, check=True)
        black_cmd = [
            "black",
            "--check",
            "--line-length=100",
            "modules/"
        ]
        black_result = run_command(black_cmd, "Black Format Check")
    except (subprocess.CalledProcessError, FileNotFoundError):
        print("⚠️  black not available, skipping format check")
        black_result = 0
        tools_available = False
    
    if not tools_available:
        print("💡 Install linting tools: pip install flake8 black")
        return 0
    
    return max(flake8_result, black_result)


def main():
    """Main test runner function."""
    parser = argparse.ArgumentParser(description="AUR-279 Phase 5 Testing - Comprehensive Test Runner")
    parser.add_argument("--unit", action="store_true", help="Run unit tests only")
    parser.add_argument("--api", action="store_true", help="Run API tests only")
    parser.add_argument("--integration", action="store_true", help="Run integration tests only")
    parser.add_argument("--performance", action="store_true", help="Run performance tests only")
    parser.add_argument("--module", choices=["tax", "payroll", "api", "e2e", "performance"], 
                       help="Run tests for specific module")
    parser.add_argument("--coverage", action="store_true", help="Generate coverage report")
    parser.add_argument("--check-coverage", action="store_true", help="Check 90% coverage threshold")
    parser.add_argument("--lint", action="store_true", help="Run linting and format checks")
    parser.add_argument("--all", action="store_true", help="Run all tests with coverage")
    parser.add_argument("--no-coverage", action="store_true", help="Skip coverage reporting")
    
    args = parser.parse_args()
    
    # If no specific arguments, run all tests
    if not any([args.unit, args.api, args.integration, args.performance, 
                args.module, args.coverage, args.check_coverage, args.lint, args.all]):
        args.all = True
    
    print("🧪 AUR-279 Phase 5 Testing - Comprehensive Test Suite")
    print("=" * 60)
    
    exit_codes = []
    
    # Run linting first if requested
    if args.lint:
        exit_codes.append(lint_and_format_check())
    
    # Run specific test categories
    coverage = not args.no_coverage
    
    if args.unit:
        exit_codes.append(run_unit_tests(coverage=coverage))
    
    if args.api:
        exit_codes.append(run_api_tests())
    
    if args.integration:
        exit_codes.append(run_integration_tests())
    
    if args.performance:
        exit_codes.append(run_performance_tests())
    
    if args.module:
        exit_codes.append(run_specific_module_tests(args.module))
    
    if args.coverage:
        exit_codes.append(generate_coverage_report())
    
    if args.check_coverage:
        exit_codes.append(check_coverage_threshold())
    
    if args.all:
        exit_codes.append(run_all_tests(coverage=coverage))
    
    # Summary
    print("\n" + "=" * 60)
    print("📋 Test Execution Summary")
    
    total_commands = len(exit_codes)
    successful_commands = sum(1 for code in exit_codes if code == 0)
    failed_commands = total_commands - successful_commands
    
    print(f"Total commands: {total_commands}")
    print(f"✅ Successful: {successful_commands}")
    print(f"❌ Failed: {failed_commands}")
    
    if failed_commands == 0:
        print("\n🎉 All tests passed successfully!")
        if coverage:
            print("📊 Open htmlcov/index.html to view detailed coverage report")
        return 0
    else:
        print(f"\n💥 {failed_commands} test commands failed")
        return 1


if __name__ == "__main__":
    sys.exit(main())