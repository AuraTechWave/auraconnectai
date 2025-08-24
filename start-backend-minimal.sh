#!/bin/bash

# Minimal backend startup script
# Starts backend with basic configuration

cd backend

# Kill any existing uvicorn processes
pkill -f uvicorn || true

# Create minimal .env if not exists
if [ ! -f ".env" ]; then
    cat > .env << 'EOF'
DATABASE_URL=postgresql://auraconnect:auraconnect123@localhost:5432/auraconnect_dev
REDIS_URL=redis://localhost:6379/0
JWT_SECRET_KEY=your-super-secret-key-change-this-in-production
ENVIRONMENT=development
EOF
fi

# Activate virtual environment
source venv/bin/activate

# Export environment variables
export DATABASE_URL="postgresql://auraconnect:auraconnect123@localhost:5432/auraconnect_dev"
export JWT_SECRET_KEY="your-super-secret-key-change-this-in-production"
export REDIS_URL="redis://localhost:6379/0"
export ENVIRONMENT="development"
export DEBUG="True"
export LOG_LEVEL="INFO"

# Start backend
echo "Starting backend on http://localhost:8000"
echo "API docs: http://localhost:8000/docs"
echo "Health check: http://localhost:8000/api/v1/health/"
echo ""
echo "Press Ctrl+C to stop"

uvicorn app.main:app --reload --host 0.0.0.0 --port 8000