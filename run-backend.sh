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
    cp backend/.env.example backend/.env
fi

# Set PYTHONPATH
export PYTHONPATH="${PYTHONPATH}:$(pwd)"

# Run the backend
echo -e "${GREEN}Starting server on http://localhost:8000${NC}"
echo -e "${GREEN}API Documentation: http://localhost:8000/docs${NC}"
echo -e "${YELLOW}Press Ctrl+C to stop${NC}"

uvicorn backend.app.main:app --reload --host 0.0.0.0 --port 8000