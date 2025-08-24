#!/bin/bash

# AuraConnect - Fix Migration Issues
# Repairs migration revision conflicts

set -e

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$SCRIPT_DIR/backend"

echo "🔧 Fixing AuraConnect Migration Issues"
echo "====================================="
echo ""

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

# Activate virtual environment
source venv/bin/activate

# Export required environment variables
export DATABASE_URL="postgresql://auraconnect:auraconnect123@localhost:5432/auraconnect_dev"
export JWT_SECRET_KEY="your-super-secret-key-change-this-in-production"
export REDIS_URL="redis://localhost:6379/0"
export ENVIRONMENT="development"

# Check current migration status
echo "Checking current migration status..."
alembic current 2>/dev/null || echo "No current revision"

# Get migration history
echo ""
echo "Migration files found:"
ls -1 alembic/versions/*.py | grep -v __pycache__ | sort

# Fix the duplicate revision issue
echo ""
echo "Fixing duplicate revision 0016..."

# Check if the problematic file exists
PROBLEM_FILE="alembic/versions/20250728_0130_0016_create_menu_versioning_tables.py"
if [ -f "$PROBLEM_FILE" ]; then
    echo "Found duplicate revision file. Renaming..."
    # Generate new revision number
    NEW_REV="0017"
    NEW_FILE="alembic/versions/20250728_0130_${NEW_REV}_create_menu_versioning_tables.py"
    
    # Update the revision number in the file
    sed -i.bak "s/revision = '0016'/revision = '${NEW_REV}'/" "$PROBLEM_FILE"
    sed -i.bak "s/Revision ID: 0016/Revision ID: ${NEW_REV}/" "$PROBLEM_FILE"
    
    # Rename the file
    mv "$PROBLEM_FILE" "$NEW_FILE"
    echo "Renamed to: $NEW_FILE"
fi

# Fix the missing down_revision reference
echo ""
echo "Fixing missing down_revision reference..."
BIOMETRIC_FILE="alembic/versions/20240208_1000_add_biometric_authentication.py"
if [ -f "$BIOMETRIC_FILE" ]; then
    # Update the down_revision to point to an existing revision
    sed -i.bak "s/down_revision = '20250130_1500_0016_add_payroll_audit_indexes'/down_revision = '0016'/" "$BIOMETRIC_FILE"
    echo "Fixed down_revision in biometric authentication migration"
fi

# Try to run migrations again
echo ""
echo "Attempting to run migrations..."

# First, try to stamp to the base if database is empty
echo "Checking if we need to initialize migration history..."
if ! alembic current 2>/dev/null | grep -q "head"; then
    echo "Initializing migration history..."
    alembic stamp base 2>/dev/null || true
fi

# Now run the migrations
echo "Running migrations..."
alembic upgrade head

if [ $? -eq 0 ]; then
    echo ""
    echo -e "${GREEN}✅ Migrations fixed and applied successfully!${NC}"
    
    # Show current status
    echo ""
    echo "Current migration status:"
    alembic current
else
    echo ""
    echo -e "${RED}❌ Migration failed. Manual intervention may be required.${NC}"
    echo ""
    echo "Common fixes:"
    echo "1. Drop and recreate the database:"
    echo "   psql -U $(whoami) -c 'DROP DATABASE auraconnect_dev;'"
    echo "   psql -U $(whoami) -c 'CREATE DATABASE auraconnect_dev OWNER auraconnect;'"
    echo ""
    echo "2. Clear alembic version table:"
    echo "   psql -U auraconnect -d auraconnect_dev -c 'DROP TABLE IF EXISTS alembic_version;'"
    echo ""
    echo "3. Then run: alembic upgrade head"
fi

deactivate