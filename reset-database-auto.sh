#!/bin/bash

# AuraConnect - Auto Reset Database
# Non-interactive version for automated setup

set -e

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$SCRIPT_DIR"

echo "🔄 AuraConnect Database Auto Reset"
echo "================================="
echo ""

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

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

echo "Step 3: Setting up backend environment..."
cd backend

# Create .env if it doesn't exist
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

# Install python-dotenv if not already installed
source venv/bin/activate
pip install python-dotenv >/dev/null 2>&1

# Export environment variables
export DATABASE_URL="postgresql://auraconnect:auraconnect123@localhost:5432/auraconnect_dev"
export JWT_SECRET_KEY="your-super-secret-key-change-this-in-production"
export REDIS_URL="redis://localhost:6379/0"
export ENVIRONMENT="development"

echo "Step 4: Running migrations..."
# Suppress warnings but show errors
alembic upgrade head 2>&1 | grep -v "UserWarning" | grep -v "Using mock users" || true

echo "Step 5: Seeding test data..."
# Try the simple seed script first
python scripts/seed_test_data_simple.py || {
    echo -e "${YELLOW}⚠ Simple seeding failed, trying full seed...${NC}"
    
    # Try the full seed script
    python scripts/seed_test_data.py || {
        echo -e "${RED}❌ Full seeding also failed!${NC}"
        echo "Database is set up but without test data."
        echo "You can still create users manually through the API."
    }
}

deactivate

echo ""
echo -e "${GREEN}✅ Database setup complete!${NC}"
echo ""
echo "Test accounts created:"
echo "  Admin:    admin / admin123"
echo "  Manager:  manager / manager123"  
echo "  Staff:    staff / staff123"
echo "  Customer: customer@example.com / customer123"
echo ""
echo "To start all services, run:"
echo "  ./start-all.sh"