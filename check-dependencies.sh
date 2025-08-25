#!/bin/bash

# AuraConnect - Dependency Checker
# Verifies all required dependencies are installed

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo "🔍 AuraConnect Dependency Checker"
echo "=================================="
echo ""

# Track missing dependencies
MISSING_DEPS=()

# Function to check command exists
check_command() {
    local cmd=$1
    local name=$2
    local version_cmd=$3
    local min_version=$4
    
    if command -v "$cmd" >/dev/null 2>&1; then
        if [ -n "$version_cmd" ]; then
            version=$(eval "$version_cmd" 2>/dev/null || echo "unknown")
            echo -e "${GREEN}✓${NC} $name: $version"
        else
            echo -e "${GREEN}✓${NC} $name: installed"
        fi
    else
        echo -e "${RED}✗${NC} $name: NOT INSTALLED"
        MISSING_DEPS+=("$name")
    fi
}

# Function to check Python version
check_python() {
    if command -v python3 >/dev/null 2>&1; then
        version=$(python3 --version 2>&1 | awk '{print $2}')
        major=$(echo $version | cut -d. -f1)
        minor=$(echo $version | cut -d. -f2)
        
        if [ "$major" -eq 3 ] && [ "$minor" -ge 11 ]; then
            echo -e "${GREEN}✓${NC} Python: $version"
        else
            echo -e "${YELLOW}⚠${NC} Python: $version (3.11+ required)"
            MISSING_DEPS+=("Python 3.11+")
        fi
    else
        echo -e "${RED}✗${NC} Python: NOT INSTALLED"
        MISSING_DEPS+=("Python")
    fi
}

# Function to check Node version
check_node() {
    # Check standard node command
    if command -v node >/dev/null 2>&1; then
        version=$(node --version | cut -d'v' -f2)
        major=$(echo $version | cut -d. -f1)
        
        if [ "$major" -ge 18 ]; then
            echo -e "${GREEN}✓${NC} Node.js: v$version"
        else
            echo -e "${YELLOW}⚠${NC} Node.js: v$version (18+ required)"
            MISSING_DEPS+=("Node.js 18+")
        fi
    else
        # Check Homebrew node@20 paths
        NODE_PATH=""
        if [ -d "/opt/homebrew/opt/node@20/bin" ]; then
            NODE_PATH="/opt/homebrew/opt/node@20/bin/node"
        elif [ -d "/usr/local/opt/node@20/bin" ]; then
            NODE_PATH="/usr/local/opt/node@20/bin/node"
        fi
        
        if [ -n "$NODE_PATH" ] && [ -x "$NODE_PATH" ]; then
            version=$($NODE_PATH --version | cut -d'v' -f2)
            echo -e "${YELLOW}⚠${NC} Node.js: v$version (installed but not in PATH)"
            echo "    Run: export PATH=\"$(dirname $NODE_PATH):\$PATH\""
            MISSING_DEPS+=("Node.js in PATH")
        else
            echo -e "${RED}✗${NC} Node.js: NOT INSTALLED"
            MISSING_DEPS+=("Node.js")
        fi
    fi
}

# Function to check PostgreSQL
check_postgresql() {
    if command -v psql >/dev/null 2>&1; then
        version=$(psql --version | awk '{print $3}' | cut -d. -f1)
        
        if [ "$version" -ge 14 ]; then
            echo -e "${GREEN}✓${NC} PostgreSQL: $(psql --version | awk '{print $3}')"
        else
            echo -e "${YELLOW}⚠${NC} PostgreSQL: $(psql --version | awk '{print $3}') (14+ required)"
            MISSING_DEPS+=("PostgreSQL 14+")
        fi
    else
        echo -e "${RED}✗${NC} PostgreSQL: NOT INSTALLED"
        MISSING_DEPS+=("PostgreSQL")
    fi
}

# Check Python virtual environment
check_venv() {
    if [ -d "backend/venv" ]; then
        echo -e "${GREEN}✓${NC} Python venv: exists"
    else
        echo -e "${YELLOW}⚠${NC} Python venv: not created (run setup-environment.sh)"
    fi
}

# Check npm packages
check_npm_packages() {
    local dir=$1
    local name=$2
    
    if [ -d "$dir/node_modules" ]; then
        echo -e "${GREEN}✓${NC} $name npm packages: installed"
    else
        echo -e "${YELLOW}⚠${NC} $name npm packages: not installed (run setup-environment.sh)"
    fi
}

# Check environment files
check_env_file() {
    local file=$1
    local name=$2
    
    if [ -f "$file" ]; then
        echo -e "${GREEN}✓${NC} $name .env: exists"
    else
        echo -e "${YELLOW}⚠${NC} $name .env: missing (run setup-environment.sh)"
    fi
}

# Check database
check_database() {
    # On macOS, use current user; on Linux use postgres
    DB_USER="postgres"
    if [[ "$OSTYPE" == "darwin"* ]]; then
        DB_USER=$(whoami)
    fi
    
    if psql -U $DB_USER -lqt 2>/dev/null | cut -d \| -f 1 | grep -qw auraconnect_dev; then
        echo -e "${GREEN}✓${NC} Database: auraconnect_dev exists"
    else
        echo -e "${YELLOW}⚠${NC} Database: auraconnect_dev not created (run ./fix-database.sh or ./setup-environment.sh)"
    fi
}

# Check Redis
check_redis() {
    if redis-cli ping >/dev/null 2>&1; then
        echo -e "${GREEN}✓${NC} Redis: running"
    else
        echo -e "${YELLOW}⚠${NC} Redis: not running (start with brew services start redis or sudo systemctl start redis)"
    fi
}

echo "System Dependencies:"
echo "-------------------"
check_python
check_node
check_postgresql
check_command "redis-server" "Redis" "redis-server --version" ""
check_command "git" "Git" "git --version" ""

echo ""
echo "Mobile Development (Optional):"
echo "-----------------------------"
check_command "react-native" "React Native CLI" "react-native --version" ""

if [[ "$OSTYPE" == "darwin"* ]]; then
    check_command "xcodebuild" "Xcode" "xcodebuild -version | head -1" ""
    check_command "pod" "CocoaPods" "pod --version" ""
fi

check_command "adb" "Android SDK" "adb version | head -1" ""

echo ""
echo "Project Setup:"
echo "--------------"
check_venv
check_npm_packages "frontend" "Frontend"
check_npm_packages "mobile" "Mobile"
check_npm_packages "customer-web" "Customer Web"

echo ""
echo "Environment Files:"
echo "-----------------"
check_env_file "backend/.env" "Backend"
check_env_file "frontend/.env" "Frontend"
check_env_file "mobile/src/constants/config.ts" "Mobile"

echo ""
echo "Services:"
echo "---------"
check_database
check_redis

echo ""
echo "=================================="

if [ ${#MISSING_DEPS[@]} -eq 0 ]; then
    echo -e "${GREEN}✅ All required dependencies are installed!${NC}"
else
    echo -e "${RED}❌ Missing dependencies:${NC}"
    for dep in "${MISSING_DEPS[@]}"; do
        echo "   - $dep"
    done
    echo ""
    echo "Run ./setup-environment.sh to install missing dependencies"
fi

echo ""