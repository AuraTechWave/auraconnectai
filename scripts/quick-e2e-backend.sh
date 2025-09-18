#!/bin/bash

# Quick script to start a minimal backend for E2E testing (SQLite + no Redis)
set -e

echo "⚡ Starting Quick E2E Backend (SQLite)..."

# Check if we're in the right directory
if [ ! -d "backend" ]; then
    echo "❌ Please run this script from the project root directory"
    exit 1
fi

# Navigate to backend directory
cd backend

# Set environment variables for minimal backend
export DATABASE_URL="sqlite:///./test_e2e.db"
export JWT_SECRET_KEY="test-jwt-secret-key-for-e2e"
export SECRET_KEY="test-secret-key-for-e2e" 
export SESSION_SECRET="test-session-secret-for-e2e"
export ENVIRONMENT="development"
# Skip CORS_ORIGINS - use default value

echo "🗄️ Using SQLite database: $DATABASE_URL"

# Test if backend can start (run startup test)
echo "🧪 Testing backend startup..."
if python3 -c "
import sys
sys.path.append('.')
try:
    from app.main import app
    print('✅ Backend can be imported successfully')
except Exception as e:
    print(f'❌ Backend import failed: {e}')
    exit(1)
" 2>/dev/null; then
    echo "✅ Backend startup test passed"
else 
    echo "❌ Backend startup test failed"
    echo "💡 This might be due to missing dependencies or configuration issues"
    echo "💡 The E2E tests will use mocked APIs instead"
    echo ""
    echo "To run E2E tests with mocks: cd frontend && npm run test:e2e"
    exit 0
fi

# Start backend server
echo "🚀 Starting minimal backend server on port 8000..."
python3 -m uvicorn main:app --host 0.0.0.0 --port 8000 --reload &
BACKEND_PID=$!

# Wait for backend to be ready
echo "⏳ Waiting for backend to be ready..."
sleep 3

# Test backend health
max_attempts=5
attempt=1
while [ $attempt -le $max_attempts ]; do
    if curl -f http://localhost:8000/health >/dev/null 2>&1; then
        echo "✅ Quick backend is running!"
        echo "🌐 Backend URL: http://localhost:8000"
        echo "📋 API Docs: http://localhost:8000/docs"
        echo "🔄 Process ID: $BACKEND_PID"
        echo ""
        echo "To stop the backend: kill $BACKEND_PID"
        echo "You can now run E2E tests with: cd frontend && npm run test:e2e"
        
        # Keep the backend running
        wait $BACKEND_PID
        exit 0
    else
        echo "Attempt $attempt/$max_attempts: Backend not ready yet..."
        sleep 2
        attempt=$((attempt + 1))
    fi
done

echo "❌ Quick backend failed to start"
echo "💡 The E2E tests will use mocked APIs instead"
kill $BACKEND_PID 2>/dev/null || true
exit 1