#!/bin/bash

# Minimal backend startup script

echo "🚀 Starting AuraConnect Backend (Minimal)"
echo "========================================"

# Export required environment variables
export DATABASE_URL="postgresql://auraconnect:auraconnect123@localhost:5432/auraconnect_dev"
export JWT_SECRET_KEY="your-super-secret-key-change-this-in-production"
export REDIS_URL="redis://localhost:6379/0"
export ENVIRONMENT="development"
export SESSION_SECRET="development-session-secret-change-in-production"
export SECRET_KEY="development-secret-key-change-in-production"
export DEBUG="True"
export LOG_LEVEL="INFO"
export PYTHONPATH="${PYTHONPATH}:$(pwd)/backend"

# Change to backend directory
cd backend

# Run with minimal output
echo ""
echo "Starting server on http://localhost:8000"
echo "API docs: http://localhost:8000/docs"
echo "Press Ctrl+C to stop"
echo ""

# Run uvicorn
python3 -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000