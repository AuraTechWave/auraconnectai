#!/bin/bash

# Start the backend server
echo "Starting backend server..."
source backend/venv/bin/activate
export PYTHONPATH="${PYTHONPATH}:$(pwd)"
uvicorn backend.app.main:app --reload --host 0.0.0.0 --port 8000 &
BACKEND_PID=$!

# Wait for backend to start
echo "Waiting for backend to start..."
sleep 5

# Start the frontend
echo "Starting frontend..."
cd customer-web
npm start &
FRONTEND_PID=$!

echo "Backend PID: $BACKEND_PID"
echo "Frontend PID: $FRONTEND_PID"

# Function to kill both processes
cleanup() {
    echo "Stopping servers..."
    kill $BACKEND_PID $FRONTEND_PID
    exit
}

# Set up trap to catch Ctrl+C
trap cleanup INT

# Wait for both processes
wait $BACKEND_PID $FRONTEND_PID