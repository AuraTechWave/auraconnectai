#!/bin/bash

# AuraConnect - Reset Database
# Drops and recreates the database with fresh migrations

set -e

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$SCRIPT_DIR"

echo "🔄 AuraConnect Database Reset"
echo "============================"
echo ""

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo -e "${RED}WARNING: This will delete all data in the database!${NC}"
read -p "Are you sure you want to continue? (y/N): " -n 1 -r
echo ""

if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "Cancelled."
    exit 0
fi

# Get current user for macOS
DB_USER=$(whoami)

echo "Step 1: Dropping existing databases..."
psql -U $DB_USER -d postgres << EOF 2>/dev/null || true
DROP DATABASE IF EXISTS auraconnect_dev;
DROP DATABASE IF EXISTS auraconnect_test;
EOF

echo "Step 2: Creating fresh databases..."
psql -U $DB_USER -d postgres << EOF
CREATE USER auraconnect WITH PASSWORD 'auraconnect123';
CREATE DATABASE auraconnect_dev OWNER auraconnect;
CREATE DATABASE auraconnect_test OWNER auraconnect;
GRANT ALL PRIVILEGES ON DATABASE auraconnect_dev TO auraconnect;
GRANT ALL PRIVILEGES ON DATABASE auraconnect_test TO auraconnect;
EOF

echo "Step 3: Running migrations..."
cd backend

# Ensure .env file exists
if [ ! -f ".env" ]; then
    echo "Creating .env file..."
    cat > .env << 'EOF'
# Database
DATABASE_URL=postgresql://auraconnect:auraconnect123@localhost:5432/auraconnect_dev

# Redis
REDIS_URL=redis://localhost:6379/0

# JWT
JWT_SECRET_KEY=your-super-secret-key-change-this-in-production
JWT_ACCESS_TOKEN_EXPIRE_MINUTES=30
JWT_REFRESH_TOKEN_EXPIRE_DAYS=7

# Environment
ENVIRONMENT=development
DEBUG=True
LOG_LEVEL=INFO

# CORS
CORS_ORIGINS=http://localhost:3000,http://localhost:3001,http://localhost:19006

# Feature Flags
FEATURE_EMAIL_NOTIFICATIONS=true
FEATURE_SMS_NOTIFICATIONS=false
FEATURE_PUSH_NOTIFICATIONS=true
EOF
fi

# Activate virtual environment
source venv/bin/activate

# Export environment variables
export DATABASE_URL="postgresql://auraconnect:auraconnect123@localhost:5432/auraconnect_dev"
export JWT_SECRET_KEY="your-super-secret-key-change-this-in-production"
export REDIS_URL="redis://localhost:6379/0"
export ENVIRONMENT="development"

# Run migrations
echo "Running alembic migrations..."
alembic upgrade head 2>&1 | grep -v "UserWarning" || {
    echo -e "${RED}Migration failed!${NC}"
    echo ""
    echo "Trying alternative approach..."
    
    # If migrations fail, try to fix common issues
    echo "Attempting to fix migration issues..."
    
    # Remove duplicate revision
    if [ -f "alembic/versions/20250728_0130_0016_create_menu_versioning_tables.py" ]; then
        echo "Removing duplicate revision file..."
        rm -f "alembic/versions/20250728_0130_0016_create_menu_versioning_tables.py"
    fi
    
    # Fix biometric auth migration
    if [ -f "alembic/versions/20240208_1000_add_biometric_authentication.py" ]; then
        echo "Fixing biometric auth migration..."
        sed -i.bak "s/down_revision = '20250130_1500_0016_add_payroll_audit_indexes'/down_revision = None/" "alembic/versions/20240208_1000_add_biometric_authentication.py"
    fi
    
    # Try again
    echo "Retrying migrations..."
    alembic upgrade head
}

if [ $? -eq 0 ]; then
    echo ""
    echo -e "${GREEN}✅ Database reset complete!${NC}"
    
    # Ask about seeding data
    echo ""
    read -p "Do you want to seed test data? (y/N): " -n 1 -r
    echo ""
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        python scripts/seed_test_data.py
    fi
else
    echo ""
    echo -e "${RED}❌ Database setup failed!${NC}"
    echo "Please check the error messages above."
    exit 1
fi

deactivate

echo ""
echo "Next steps:"
echo "1. Start all services: ./start-all.sh"
echo "2. Or start backend only: cd backend && source venv/bin/activate && uvicorn app.main:app --reload"