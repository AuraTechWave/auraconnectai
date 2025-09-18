#!/bin/bash

# Script to stop E2E backend services
set -e

echo "🛑 Stopping E2E Backend Services..."

# Stop Docker services
echo "📦 Stopping PostgreSQL and Redis..."
docker-compose -f docker-compose.e2e.yml down

# Kill any running uvicorn processes on port 8000
echo "🔌 Stopping backend server..."
pkill -f "uvicorn main:app.*--port 8000" 2>/dev/null || true

# Clean up any remaining processes
lsof -ti:8000 | xargs kill -9 2>/dev/null || true

echo "✅ All E2E services stopped"