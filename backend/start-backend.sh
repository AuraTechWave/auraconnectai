#!/bin/bash

# Backend Startup Script with Health Checks

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${GREEN}=== AuraConnect Backend Startup ===${NC}"

# Get script directory
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$SCRIPT_DIR"

# Check Python version
PYTHON_VERSION=$(python3 --version 2>&1 | grep -oE '[0-9]+\.[0-9]+')
REQUIRED_VERSION="3.11"

if [ "$(printf '%s\n' "$REQUIRED_VERSION" "$PYTHON_VERSION" | sort -V | head -n1)" != "$REQUIRED_VERSION" ]; then 
    echo -e "${RED}Error: Python $REQUIRED_VERSION or higher is required. Found: $PYTHON_VERSION${NC}"
    exit 1
fi

# Check if virtual environment exists
if [ ! -d "venv" ]; then
    echo -e "${YELLOW}Virtual environment not found. Creating...${NC}"
    python3 -m venv venv
fi

# Activate virtual environment
echo "Activating virtual environment..."
source venv/bin/activate

# Check if .env exists
if [ ! -f ".env" ]; then
    echo -e "${YELLOW}Warning: .env file not found!${NC}"
    echo "Creating .env from .env.example..."
    cp .env.example .env
    echo -e "${RED}IMPORTANT: Please edit .env and set your configuration values!${NC}"
    echo "Press Enter to continue or Ctrl+C to exit..."
    read
fi

# Load environment variables
set -a
source .env
set +a

# Check required environment variables
REQUIRED_VARS=("JWT_SECRET_KEY" "DATABASE_URL" "REDIS_URL")
for var in "${REQUIRED_VARS[@]}"; do
    if [ -z "${!var}" ]; then
        echo -e "${RED}Error: Required environment variable $var is not set!${NC}"
        exit 1
    fi
done

# Check if dependencies are installed
echo "Checking dependencies..."
if ! python -c "import fastapi" 2>/dev/null; then
    echo -e "${YELLOW}Dependencies not installed. Installing...${NC}"
    pip install -r requirements.txt
    pip install psutil==5.9.8 twilio  # Additional packages from fixes
fi

# Check PostgreSQL connection
echo "Checking PostgreSQL connection..."
if ! python -c "
import os
from sqlalchemy import create_engine
try:
    engine = create_engine(os.environ['DATABASE_URL'])
    conn = engine.connect()
    conn.close()
    print('PostgreSQL connection: OK')
except Exception as e:
    print(f'PostgreSQL connection failed: {e}')
    exit(1)
" ; then
    echo -e "${RED}Cannot connect to PostgreSQL. Please check DATABASE_URL and ensure PostgreSQL is running.${NC}"
    exit 1
fi

# Check Redis connection
echo "Checking Redis connection..."
if ! python -c "
import os
import redis
try:
    r = redis.from_url(os.environ.get('REDIS_URL', 'redis://localhost:6379'))
    r.ping()
    print('Redis connection: OK')
except Exception as e:
    print(f'Redis connection failed: {e}')
    exit(1)
" ; then
    echo -e "${RED}Cannot connect to Redis. Please check REDIS_URL and ensure Redis is running.${NC}"
    exit 1
fi

# Run migrations
echo "Checking database migrations..."
alembic current
echo "Running migrations..."
alembic upgrade head

# Set PYTHONPATH
export PYTHONPATH="${PYTHONPATH}:$(pwd)"

# Start the server
echo -e "${GREEN}Starting AuraConnect Backend Server...${NC}"
echo "Server will be available at:"
echo "  - API: http://localhost:8000"
echo "  - Docs: http://localhost:8000/docs"
echo "  - ReDoc: http://localhost:8000/redoc"
echo ""

# Check if running in production or development
if [ "$ENVIRONMENT" = "production" ]; then
    echo "Starting in PRODUCTION mode with 4 workers..."
    exec uvicorn app.main:app \
        --host 0.0.0.0 \
        --port ${PORT:-8000} \
        --workers 4 \
        --log-level ${LOG_LEVEL:-info}
else
    echo "Starting in DEVELOPMENT mode with auto-reload..."
    exec uvicorn app.main:app \
        --reload \
        --host 0.0.0.0 \
        --port ${PORT:-8000} \
        --log-level ${LOG_LEVEL:-info}
fi