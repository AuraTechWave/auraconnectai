#!/bin/bash

# Run Alembic Migrations with Proper Environment

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo "Running AuraConnect Database Migrations"
echo "======================================"
echo ""

# Get script directory
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$SCRIPT_DIR"

# Check if virtual environment exists
if [ ! -d "venv" ]; then
    echo -e "${RED}Error: Virtual environment not found!${NC}"
    echo "Please run: python3 -m venv venv && source venv/bin/activate && pip install -r requirements.txt"
    exit 1
fi

# Activate virtual environment
source venv/bin/activate

# Load environment variables from .env if it exists
if [ -f ".env" ]; then
    echo "Loading environment from .env..."
    set -a
    source .env
    set +a
else
    echo -e "${YELLOW}Warning: .env file not found!${NC}"
    echo "Using default values..."
    
    # Set minimal required environment variables
    export DATABASE_URL="postgresql://postgres:postgres@localhost:5432/auraconnect"
    export JWT_SECRET_KEY="temporary-key-for-migrations"
    export REDIS_URL="redis://localhost:6379/0"
    export RESTAURANT_NAME="AuraConnect"
    export RESTAURANT_ID="1"
    export ENVIRONMENT="development"
fi

# Display connection info
echo ""
echo "Database URL: ${DATABASE_URL}"
echo ""

# Check PostgreSQL connection
echo -n "Testing database connection... "
python -c "
import os
from sqlalchemy import create_engine
try:
    engine = create_engine(os.environ['DATABASE_URL'])
    conn = engine.connect()
    conn.close()
    print('✓')
except Exception as e:
    print('✗')
    print(f'Error: {e}')
    exit(1)
" || exit 1

# Run migrations
echo ""
echo "Running migrations..."
echo "--------------------"

# First, show current state
echo "Current migration state:"
alembic current

echo ""
echo "Applying pending migrations..."
alembic upgrade head

echo ""
echo "Final migration state:"
alembic current

echo ""
echo -e "${GREEN}✅ Migrations completed successfully!${NC}"