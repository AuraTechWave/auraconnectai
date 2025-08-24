#!/bin/bash

# Fix corrupted virtual environment

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${YELLOW}=== Fixing Virtual Environment ===${NC}"
echo ""

cd backend

# Step 1: Remove corrupted virtual environment
if [ -d "venv" ]; then
    echo "Removing corrupted virtual environment..."
    rm -rf venv
fi

# Step 2: Create fresh virtual environment with Python 3.11
echo "Creating fresh virtual environment..."
if command -v python3.11 &> /dev/null; then
    echo "Using Python 3.11..."
    python3.11 -m venv venv
elif command -v python3 &> /dev/null; then
    PYTHON_VERSION=$(python3 --version 2>&1 | grep -oE '[0-9]+\.[0-9]+')
    echo "Using Python $PYTHON_VERSION..."
    if [ "$(printf '%s\n' "3.11" "$PYTHON_VERSION" | sort -V | head -n1)" != "3.11" ]; then 
        echo -e "${YELLOW}Warning: Python 3.11+ is recommended. Found: $PYTHON_VERSION${NC}"
    fi
    python3 -m venv venv
else
    echo -e "${RED}Error: Python 3 not found!${NC}"
    exit 1
fi

# Step 3: Activate virtual environment
echo "Activating virtual environment..."
source venv/bin/activate

# Step 4: Upgrade pip
echo "Upgrading pip..."
python -m pip install --upgrade pip

# Step 5: Install wheel and setuptools first
echo "Installing build tools..."
pip install wheel setuptools

# Step 6: Install requirements one by one to identify any issues
echo "Installing core dependencies..."

# Install critical dependencies first
pip install "pydantic>=2.0,<3.0"
pip install "fastapi>=0.100.0"
pip install "sqlalchemy>=2.0.0"
pip install "alembic>=1.12.0"
pip install "psycopg2-binary>=2.9.0"
pip install "python-jose[cryptography]>=3.3.0"
pip install "passlib[bcrypt]>=1.7.4"
pip install "python-multipart>=0.0.5"
pip install "redis>=4.5.0"
pip install "celery>=5.2.0"

# Step 7: Install remaining requirements
echo ""
echo "Installing remaining dependencies from requirements.txt..."
pip install -r requirements.txt

# Step 8: Install additional packages from fixes
echo ""
echo "Installing additional packages..."
pip install psutil==5.9.8
pip install twilio

# Step 9: Verify installation
echo ""
echo "Verifying installation..."
python -c "import pydantic; print(f'Pydantic version: {pydantic.__version__}')"
python -c "import fastapi; print(f'FastAPI version: {fastapi.__version__}')"
python -c "import sqlalchemy; print(f'SQLAlchemy version: {sqlalchemy.__version__}')"
python -c "import alembic; print(f'Alembic version: {alembic.__version__}')"

# Step 10: Test alembic
echo ""
echo "Testing Alembic..."
cd ..
source backend/venv/bin/activate
cd backend

# Set minimal environment variables for testing
export DATABASE_URL="postgresql://user:pass@localhost:5432/auraconnect"
export JWT_SECRET_KEY="test-key"
export REDIS_URL="redis://localhost:6379"

# Try to check current migration
if alembic current 2>/dev/null; then
    echo -e "${GREEN}✅ Alembic is working correctly!${NC}"
else
    echo -e "${RED}⚠️  Alembic test failed. Check your database connection.${NC}"
fi

echo ""
echo -e "${GREEN}=== Virtual Environment Fixed ===${NC}"
echo ""
echo "Next steps:"
echo "1. Ensure PostgreSQL is running"
echo "2. Update DATABASE_URL in backend/.env"
echo "3. Run: cd backend && source venv/bin/activate && alembic upgrade head"