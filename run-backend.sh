#!/bin/bash

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}Starting AuraConnect Backend...${NC}"

# Kill any existing process on port 8000
if lsof -ti:8000 > /dev/null 2>&1; then
    echo -e "${YELLOW}Killing existing process on port 8000...${NC}"
    lsof -ti:8000 | xargs kill -9 2>/dev/null
    sleep 1
fi

# Check if virtual environment exists
if [ ! -d "backend/venv" ]; then
    echo -e "${YELLOW}Creating virtual environment...${NC}"
    cd backend && python3 -m venv venv && cd ..
fi

# Activate virtual environment
echo -e "${GREEN}Activating virtual environment...${NC}"
source backend/venv/bin/activate

# Install dependencies if needed
if ! python -c "import fastapi" 2>/dev/null; then
    echo -e "${YELLOW}Installing dependencies...${NC}"
    pip install -r backend/requirements.txt
fi

# Check if .env file exists
if [ ! -f "backend/.env" ]; then
    echo -e "${YELLOW}Creating .env file from example...${NC}"
    if [ -f "backend/.env.example" ]; then
        cp backend/.env.example backend/.env
    else
        echo -e "${YELLOW}Creating default .env file...${NC}"
        cat > backend/.env << 'EOF'
DATABASE_URL=postgresql://auraconnect:auraconnect123@localhost:5432/auraconnect_dev
REDIS_URL=redis://localhost:6379/0
JWT_SECRET_KEY=your-super-secret-key-change-this-in-production
ENVIRONMENT=development
DEBUG=True
LOG_LEVEL=INFO
EOF
    fi
fi

# Set PYTHONPATH to include backend directory
export PYTHONPATH="${PYTHONPATH}:$(pwd)/backend"

# Export environment variables
export DATABASE_URL="postgresql://auraconnect:auraconnect123@localhost:5432/auraconnect_dev"
export JWT_SECRET_KEY="your-super-secret-key-change-this-in-production"
export REDIS_URL="redis://localhost:6379/0"
export ENVIRONMENT="development"
export DEBUG="True"
export LOG_LEVEL="INFO"
export SESSION_SECRET="development-session-secret-change-in-production"
export SECRET_KEY="development-secret-key-change-in-production"

# Change to backend directory
cd backend

# Run the backend
echo -e "${GREEN}Starting server on http://localhost:8000${NC}"
echo -e "${GREEN}API Documentation: http://localhost:8000/docs${NC}"
echo -e "${YELLOW}Press Ctrl+C to stop${NC}"

uvicorn app.main:app --reload --host 0.0.0.0 --port 8000