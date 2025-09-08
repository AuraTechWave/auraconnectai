#!/bin/bash

# Script to start backend services for E2E testing
set -e

echo "🚀 Starting E2E Backend Services..."

# Check if Docker is running
if ! docker info >/dev/null 2>&1; then
    echo "❌ Docker is not running. Please start Docker first."
    exit 1
fi

# Start PostgreSQL and Redis services
echo "📦 Starting PostgreSQL and Redis..."
docker-compose -f docker-compose.e2e.yml up -d

# Wait for services to be healthy
echo "⏳ Waiting for services to be ready..."
until docker-compose -f docker-compose.e2e.yml ps | grep -q "healthy"; do
    echo "Waiting for databases to be healthy..."
    sleep 2
done

echo "✅ Database services are running"

# Set environment variables for backend
export DATABASE_URL="postgresql://testuser:testpass@localhost:5432/auraconnect_test"
export REDIS_URL="redis://localhost:6379"
export JWT_SECRET_KEY="test-jwt-secret-key-for-e2e"
export ENVIRONMENT="test"
export CORS_ORIGINS="http://localhost:3000,http://test.localhost:3000"

# Check if we're in the right directory
if [ ! -d "backend" ]; then
    echo "❌ Please run this script from the project root directory"
    exit 1
fi

# Navigate to backend directory
cd backend

# Install dependencies if needed
if [ ! -d "venv" ] && [ ! -f ".venv/bin/activate" ]; then
    echo "🔧 Installing backend dependencies..."
    if command -v python3 >/dev/null 2>&1; then
        python3 -m venv venv
        source venv/bin/activate
        pip install -r requirements.txt
    else
        echo "❌ Python 3 is required but not installed"
        exit 1
    fi
else
    # Activate existing virtual environment
    if [ -f "venv/bin/activate" ]; then
        source venv/bin/activate
    elif [ -f ".venv/bin/activate" ]; then
        source .venv/bin/activate
    fi
fi

# Run database migrations
echo "🗄️ Running database migrations..."
alembic upgrade head

# Start backend server
echo "🚀 Starting backend server on port 8000..."
uvicorn main:app --host 0.0.0.0 --port 8000 --reload &
BACKEND_PID=$!

# Wait for backend to be ready
echo "⏳ Waiting for backend to be ready..."
sleep 5

# Test backend health
max_attempts=10
attempt=1
while [ $attempt -le $max_attempts ]; do
    if curl -f http://localhost:8000/health >/dev/null 2>&1; then
        echo "✅ Backend is running and healthy!"
        echo "🌐 Backend URL: http://localhost:8000"
        echo "📋 API Docs: http://localhost:8000/docs"
        echo "🔄 Process ID: $BACKEND_PID"
        echo ""
        echo "To stop the backend:"
        echo "  kill $BACKEND_PID"
        echo "To stop all services:"
        echo "  docker-compose -f docker-compose.e2e.yml down"
        echo ""
        echo "You can now run E2E tests with: cd frontend && npm run test:e2e"
        
        # Keep the backend running
        wait $BACKEND_PID
        exit 0
    else
        echo "Attempt $attempt/$max_attempts: Backend not ready yet..."
        sleep 3
        attempt=$((attempt + 1))
    fi
done

echo "❌ Backend failed to start properly"
kill $BACKEND_PID 2>/dev/null || true
docker-compose -f docker-compose.e2e.yml down
exit 1