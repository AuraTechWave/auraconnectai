#!/bin/bash

# Cleanup temporary files created during debugging
# This script removes temporary test and fix scripts while keeping essential setup scripts

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${YELLOW}=== Cleaning Up Temporary Files ===${NC}"
echo ""

# Get script directory
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$SCRIPT_DIR"

# List of temporary files to remove
TEMP_FILES=(
    # Backend temporary test scripts
    "backend/test-backend-startup.py"
    "backend/test-backend-with-env.py"
    "backend/fix-get-current-active-user.sh"
    "backend/fix-metadata-columns.sh"
    "backend/fix-cache-service-imports.sh"
    
    # Root directory temporary scripts
    "test-backend-startup.py"
    "test-backend.py"
    "test-api.sh"
    "fix-auth-imports.sh"
    "fix-backend-imports.sh"
    "fix-cache-service-imports.sh"
    "fix-field-validators.sh"
    "fix-menuitem-imports.sh"
    "fix-migrations.sh"
    "fix-pydantic-v2.sh"
    "fix-root-validators.sh"
    "check-dependencies.sh"
    "fix-database.sh"
    
    # Backup files
    "backend/.env.backup"
    "backend/.env.bak"
)

# Files to KEEP (essential setup and startup scripts)
echo "Files that will be KEPT:"
echo "  ✓ start-all.sh"
echo "  ✓ quick-setup.sh"
echo "  ✓ setup-env.sh"
echo "  ✓ fix-venv.sh (useful for environment issues)"
echo "  ✓ backend/start-backend.sh"
echo "  ✓ backend/run-migrations.sh"
echo "  ✓ frontend/start-frontend.sh"
echo "  ✓ STARTUP_GUIDE.md"
echo ""

# Confirm before deletion
echo -e "${YELLOW}The following temporary files will be removed:${NC}"
for file in "${TEMP_FILES[@]}"; do
    if [ -f "$file" ]; then
        echo "  - $file"
    fi
done

echo ""
read -p "Do you want to proceed with cleanup? (y/N): " -n 1 -r
echo ""

if [[ $REPLY =~ ^[Yy]$ ]]; then
    echo ""
    echo "Removing temporary files..."
    
    for file in "${TEMP_FILES[@]}"; do
        if [ -f "$file" ]; then
            rm -f "$file"
            echo -e "${GREEN}✓${NC} Removed: $file"
        fi
    done
    
    # Also remove any .bak files created by sed
    echo ""
    echo "Removing .bak files..."
    find . -name "*.bak" -type f -delete
    echo -e "${GREEN}✓${NC} Removed all .bak files"
    
    # Remove __pycache__ directories
    echo ""
    echo "Removing __pycache__ directories..."
    find . -name "__pycache__" -type d -exec rm -rf {} + 2>/dev/null || true
    echo -e "${GREEN}✓${NC} Removed __pycache__ directories"
    
    # Remove .pyc files
    echo "Removing .pyc files..."
    find . -name "*.pyc" -type f -delete
    echo -e "${GREEN}✓${NC} Removed .pyc files"
    
    echo ""
    echo -e "${GREEN}=== Cleanup Complete ===${NC}"
    echo ""
    echo "Essential setup scripts have been preserved:"
    echo "  • start-all.sh - Start all services"
    echo "  • quick-setup.sh - Initial setup helper"
    echo "  • setup-env.sh - Environment configuration"
    echo "  • fix-venv.sh - Virtual environment repair"
    echo "  • backend/start-backend.sh - Backend startup"
    echo "  • backend/run-migrations.sh - Database migrations"
    echo "  • frontend/start-frontend.sh - Frontend startup"
else
    echo ""
    echo "Cleanup cancelled."
fi

# Self-destruct option
echo ""
echo "This cleanup script itself is temporary."
read -p "Do you want to remove this cleanup script too? (y/N): " -n 1 -r
echo ""

if [[ $REPLY =~ ^[Yy]$ ]]; then
    echo -e "${GREEN}✓${NC} Removing cleanup script..."
    rm -f "$0"
fi