#!/bin/bash

# AuraConnect - Start All Services Script
# This script starts all services needed for manual testing

set -e

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$SCRIPT_DIR"

echo "🚀 Starting AuraConnect Services..."
echo "=================================="

# Check if running on macOS or Linux
if [[ "$OSTYPE" == "darwin"* ]]; then
    # macOS - use osascript to open new terminal windows
    
    # Terminal 1: PostgreSQL (if not already running)
    if ! pg_isready -q; then
        echo "Starting PostgreSQL..."
        osascript -e 'tell app "Terminal" to do script "brew services start postgresql@14"'
    else
        echo "✅ PostgreSQL is already running"
    fi
    
    # Terminal 2: Redis (if not already running)
    if ! redis-cli ping > /dev/null 2>&1; then
        echo "Starting Redis..."
        osascript -e 'tell app "Terminal" to do script "brew services start redis"'
    else
        echo "✅ Redis is already running"
    fi
    
    # Wait for services to be ready
    sleep 3
    
    # Terminal 3: Backend API
    echo "Starting Backend API..."
    osascript -e "tell app \"Terminal\" to do script \"cd '$SCRIPT_DIR/backend' && source venv/bin/activate && uvicorn app.main:app --reload --host 0.0.0.0 --port 8000\""
    
    # Terminal 4: Frontend
    echo "Starting Frontend..."
    osascript -e "tell app \"Terminal\" to do script \"cd '$SCRIPT_DIR/frontend' && npm start\""
    
    # Terminal 5: Customer Web App
    echo "Starting Customer Web App..."
    osascript -e "tell app \"Terminal\" to do script \"cd '$SCRIPT_DIR/customer-web' && PORT=3001 npm start\""
    
    # Terminal 6: Mobile Metro Bundler
    echo "Starting Mobile Metro Bundler..."
    osascript -e "tell app \"Terminal\" to do script \"cd '$SCRIPT_DIR/mobile' && npx react-native start\""
    
else
    # Linux - use gnome-terminal or xterm
    
    # Check if PostgreSQL is running
    if ! systemctl is-active --quiet postgresql; then
        echo "Starting PostgreSQL..."
        sudo systemctl start postgresql
    else
        echo "✅ PostgreSQL is already running"
    fi
    
    # Check if Redis is running
    if ! systemctl is-active --quiet redis; then
        echo "Starting Redis..."
        sudo systemctl start redis
    else
        echo "✅ Redis is already running"
    fi
    
    # Start Backend API
    echo "Starting Backend API..."
    gnome-terminal --tab --title="Backend API" -- bash -c "cd '$SCRIPT_DIR/backend' && source venv/bin/activate && uvicorn app.main:app --reload --host 0.0.0.0 --port 8000; exec bash"
    
    # Start Frontend
    echo "Starting Frontend..."
    gnome-terminal --tab --title="Frontend" -- bash -c "cd '$SCRIPT_DIR/frontend' && npm start; exec bash"
    
    # Start Customer Web App
    echo "Starting Customer Web App..."
    gnome-terminal --tab --title="Customer Web" -- bash -c "cd '$SCRIPT_DIR/customer-web' && PORT=3001 npm start; exec bash"
    
    # Start Mobile Metro Bundler
    echo "Starting Mobile Metro Bundler..."
    gnome-terminal --tab --title="Mobile Metro" -- bash -c "cd '$SCRIPT_DIR/mobile' && npx react-native start; exec bash"
fi

# Wait for services to start
echo ""
echo "⏳ Waiting for services to start..."
sleep 5

# Display service URLs
echo ""
echo "✨ All services starting! Access them at:"
echo "========================================"
echo "📡 Backend API:      http://localhost:8000"
echo "📚 API Docs:         http://localhost:8000/docs"
echo "🏥 Health Check:     http://localhost:8000/api/v1/health/"
echo "💼 Admin Frontend:   http://localhost:3000"
echo "🛍️  Customer Web:     http://localhost:3001"
echo "📱 Mobile Metro:     http://localhost:8081"
echo ""
echo "📝 Test Accounts:"
echo "  Admin:    admin / secret"
echo "  Manager:  manager / secret"
echo "  Payroll:  payroll_clerk / secret"
echo ""
echo "Press Ctrl+C to stop all services"