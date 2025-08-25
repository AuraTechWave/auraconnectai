#!/bin/bash

# AuraConnect - Database Fix Script
# Fixes database setup issues on macOS

set -e

echo "🔧 AuraConnect Database Fix"
echo "=========================="
echo ""

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

# Get current user
DB_USER=$(whoami)

echo "Using database user: $DB_USER"
echo ""

# Check if PostgreSQL is running
if ! brew services list | grep "postgresql@14" | grep -q "started"; then
    echo "Starting PostgreSQL..."
    brew services start postgresql@14
    sleep 3
fi

# Create database and user
echo "Creating AuraConnect database and user..."

# First, try to create the user (it may already exist)
psql -U $DB_USER -d postgres << EOF 2>/dev/null || true
CREATE USER auraconnect WITH PASSWORD 'auraconnect123';
EOF

# Create databases
psql -U $DB_USER -d postgres << EOF
-- Create development database
CREATE DATABASE auraconnect_dev OWNER auraconnect;

-- Create test database
CREATE DATABASE auraconnect_test OWNER auraconnect;

-- Grant all privileges
GRANT ALL PRIVILEGES ON DATABASE auraconnect_dev TO auraconnect;
GRANT ALL PRIVILEGES ON DATABASE auraconnect_test TO auraconnect;
EOF

echo ""
echo -e "${GREEN}✅ Database setup complete!${NC}"
echo ""
echo "Databases created:"
echo "  - auraconnect_dev (development)"
echo "  - auraconnect_test (testing)"
echo ""
echo "Database user:"
echo "  - Username: auraconnect"
echo "  - Password: auraconnect123"
echo ""
echo "Connection string:"
echo "  postgresql://auraconnect:auraconnect123@localhost:5432/auraconnect_dev"