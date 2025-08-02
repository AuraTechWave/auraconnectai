#!/bin/bash

# Start Backend and Frontend Services for AuraConnect

echo "Starting AuraConnect Services..."

# Function to handle cleanup on script exit
cleanup() {
    echo "Stopping services..."
    kill $BACKEND_PID $FRONTEND_PID 2>/dev/null
    exit
}

# Set trap to cleanup on exit
trap cleanup EXIT INT TERM

# Start Backend
echo "Starting Backend..."
cd backend
if [ ! -d "venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv venv
fi

source venv/bin/activate
pip install -r requirements.txt

# Set development environment variables
export JWT_SECRET_KEY="dev-secret-change-in-production"
export DATABASE_URL="postgresql://user:password@localhost:5432/auraconnect"

# Start backend server
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000 &
BACKEND_PID=$!

echo "Backend started on http://localhost:8000"
echo "API Docs available at http://localhost:8000/docs"

# Wait a bit for backend to start
sleep 5

# Start Frontend
echo "Starting Frontend..."
cd ../frontend

# Install dependencies if needed
if [ ! -d "node_modules" ]; then
    echo "Installing frontend dependencies..."
    npm install
fi

# Start frontend server
npm start &
FRONTEND_PID=$!

echo "Frontend started on http://localhost:3000"

# Keep script running
echo "Services are running. Press Ctrl+C to stop."
wait