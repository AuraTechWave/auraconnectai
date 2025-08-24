#!/bin/bash

# Frontend Startup Script

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${GREEN}=== AuraConnect Frontend Startup ===${NC}"

# Get script directory
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$SCRIPT_DIR"

# Check Node.js version
NODE_VERSION=$(node --version 2>&1 | grep -oE '[0-9]+' | head -1)
REQUIRED_VERSION="18"

if [ "$NODE_VERSION" -lt "$REQUIRED_VERSION" ]; then 
    echo -e "${RED}Error: Node.js $REQUIRED_VERSION or higher is required. Found: v$NODE_VERSION${NC}"
    exit 1
fi

# Check if node_modules exists
if [ ! -d "node_modules" ]; then
    echo -e "${YELLOW}Dependencies not found. Installing...${NC}"
    npm install
fi

# Check if .env exists
if [ ! -f ".env" ]; then
    echo -e "${YELLOW}Creating .env file...${NC}"
    cat > .env << EOF
REACT_APP_API_URL=http://localhost:8000
REACT_APP_WS_URL=ws://localhost:8000
REACT_APP_ENVIRONMENT=development
EOF
    echo ".env file created with default values"
fi

# Load environment variables
set -a
source .env
set +a

# Check if backend is running
echo "Checking backend connection..."
if ! curl -s -o /dev/null -w "%{http_code}" "$REACT_APP_API_URL" | grep -q "200\|404"; then
    echo -e "${YELLOW}Warning: Backend API is not accessible at $REACT_APP_API_URL${NC}"
    echo "Make sure the backend is running before starting the frontend."
    echo "Press Enter to continue anyway or Ctrl+C to exit..."
    read
fi

# Clear any previous build artifacts
if [ -d "build" ]; then
    echo "Clearing previous build..."
    rm -rf build
fi

# Start the development server
echo -e "${GREEN}Starting AuraConnect Frontend...${NC}"
echo "Frontend will be available at: http://localhost:3000"
echo ""

# Check if running in production or development
if [ "$REACT_APP_ENVIRONMENT" = "production" ]; then
    echo "Building for production..."
    npm run build
    echo -e "${GREEN}Production build complete!${NC}"
    echo "Serve the build directory with a static server:"
    echo "  npx serve -s build -l 3000"
else
    echo "Starting development server with hot reload..."
    exec npm start
fi