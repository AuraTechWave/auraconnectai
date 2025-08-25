#!/bin/bash

# AuraConnect - Quick Setup Fix
# Fixes the current environment issues

set -e

echo "🚀 AuraConnect Quick Setup Fix"
echo "============================="
echo ""

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

# Step 1: Fix database if needed
echo "Step 1: Checking database..."
if ! psql -U $(whoami) -lqt 2>/dev/null | cut -d \| -f 1 | grep -qw auraconnect_dev; then
    echo "Creating database..."
    ./fix-database.sh
else
    echo -e "${GREEN}✅ Database already exists${NC}"
fi

# Step 2: Set up backend with proper environment
echo ""
echo "Step 2: Setting up backend..."
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

# File Upload
MAX_UPLOAD_SIZE_MB=10
ALLOWED_FILE_TYPES=csv,xlsx,pdf,jpg,jpeg,png

# Feature Flags
FEATURE_EMAIL_NOTIFICATIONS=true
FEATURE_SMS_NOTIFICATIONS=false
FEATURE_PUSH_NOTIFICATIONS=true
EOF
fi

# Recreate virtual environment with Python 3.11 if available
if [ -d "venv" ] && [ "$(./venv/bin/python --version | grep -o '3\.13')" ]; then
    echo -e "${YELLOW}⚠ Python 3.13 detected in venv. Recreating with Python 3.11...${NC}"
    rm -rf venv
fi

if [ ! -d "venv" ]; then
    if command -v python3.11 >/dev/null 2>&1; then
        echo "Creating virtual environment with Python 3.11..."
        python3.11 -m venv venv
    else
        echo -e "${YELLOW}⚠ Python 3.11 not found. Using default Python 3...${NC}"
        python3 -m venv venv
    fi
fi

# Install dependencies
echo "Installing dependencies..."
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
pip install -r requirements-dev.txt

# Run migrations with environment variables
echo ""
echo "Running migrations..."
export DATABASE_URL="postgresql://auraconnect:auraconnect123@localhost:5432/auraconnect_dev"
export REDIS_URL="redis://localhost:6379/0"
export JWT_SECRET_KEY="your-super-secret-key-change-this-in-production"
export ENVIRONMENT="development"

alembic upgrade head

# Seed test data
echo ""
read -p "Do you want to seed test data? (y/N): " -n 1 -r
echo ""
if [[ $REPLY =~ ^[Yy]$ ]]; then
    python scripts/seed_test_data.py
fi

deactivate
cd ..

# Step 3: Quick check
echo ""
echo "Step 3: Running quick checks..."
./check-dependencies.sh

echo ""
echo -e "${GREEN}✅ Quick setup complete!${NC}"
echo ""
echo "To start all services, run:"
echo "  ./start-all.sh"
echo ""
echo "Or start services individually:"
echo "  Backend:  cd backend && source venv/bin/activate && uvicorn app.main:app --reload"
echo "  Frontend: cd frontend && npm start"