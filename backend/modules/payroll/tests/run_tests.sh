#!/bin/bash
# backend/modules/payroll/tests/run_tests.sh

# Payroll Module Test Runner
# 
# This script runs the payroll module test suite with various options

set -e

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Default values
TEST_TYPE="all"
COVERAGE=true
VERBOSE=false
MARKERS=""

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --unit)
            TEST_TYPE="unit"
            MARKERS="-m unit"
            shift
            ;;
        --integration)
            TEST_TYPE="integration"
            MARKERS="-m integration"
            shift
            ;;
        --e2e)
            TEST_TYPE="e2e"
            MARKERS="-m e2e"
            shift
            ;;
        --performance)
            TEST_TYPE="performance"
            MARKERS="-m performance"
            shift
            ;;
        --smoke)
            TEST_TYPE="smoke"
            MARKERS="-m smoke"
            shift
            ;;
        --no-coverage)
            COVERAGE=false
            shift
            ;;
        --verbose|-v)
            VERBOSE=true
            shift
            ;;
        --help|-h)
            echo "Usage: $0 [options]"
            echo ""
            echo "Options:"
            echo "  --unit          Run only unit tests"
            echo "  --integration   Run only integration tests"
            echo "  --e2e           Run only end-to-end tests"
            echo "  --performance   Run only performance tests"
            echo "  --smoke         Run only smoke tests"
            echo "  --no-coverage   Skip coverage report"
            echo "  --verbose, -v   Verbose output"
            echo "  --help, -h      Show this help message"
            echo ""
            echo "Examples:"
            echo "  $0                    # Run all tests with coverage"
            echo "  $0 --unit             # Run only unit tests"
            echo "  $0 --no-coverage      # Run all tests without coverage"
            echo "  $0 --unit --verbose   # Run unit tests with verbose output"
            exit 0
            ;;
        *)
            echo -e "${RED}Unknown option: $1${NC}"
            echo "Use --help for usage information"
            exit 1
            ;;
    esac
done

# Change to the payroll module directory
cd "$(dirname "$0")/.."

echo -e "${GREEN}Payroll Module Test Suite${NC}"
echo "=========================="
echo ""

# Check if pytest is installed
if ! command -v pytest &> /dev/null; then
    echo -e "${RED}Error: pytest is not installed${NC}"
    echo "Please install pytest: pip install pytest pytest-cov pytest-asyncio"
    exit 1
fi

# Build pytest command
PYTEST_CMD="pytest tests/"

# Add markers if specified
if [[ -n "$MARKERS" ]]; then
    PYTEST_CMD="$PYTEST_CMD $MARKERS"
fi

# Add coverage options
if [[ "$COVERAGE" == true ]]; then
    PYTEST_CMD="$PYTEST_CMD --cov=. --cov-report=html:tests/htmlcov --cov-report=term-missing --cov-config=tests/.coveragerc"
fi

# Add verbose flag
if [[ "$VERBOSE" == true ]]; then
    PYTEST_CMD="$PYTEST_CMD -vv"
fi

# Run the tests
echo -e "${YELLOW}Running $TEST_TYPE tests...${NC}"
echo "Command: $PYTEST_CMD"
echo ""

if $PYTEST_CMD; then
    echo ""
    echo -e "${GREEN}✓ All tests passed!${NC}"
    
    if [[ "$COVERAGE" == true ]]; then
        echo ""
        echo -e "${GREEN}Coverage report generated:${NC}"
        echo "  - HTML report: tests/htmlcov/index.html"
        echo "  - XML report: coverage.xml"
        
        # Display coverage summary
        echo ""
        echo "Coverage Summary:"
        python -m coverage report --rcfile=tests/.coveragerc | tail -n 20
    fi
else
    echo ""
    echo -e "${RED}✗ Some tests failed${NC}"
    exit 1
fi

# Performance test results
if [[ "$TEST_TYPE" == "performance" ]]; then
    echo ""
    echo -e "${GREEN}Performance Test Results${NC}"
    echo "========================"
    echo "Check the test output above for performance metrics"
fi

echo ""
echo -e "${GREEN}Test run completed successfully!${NC}"