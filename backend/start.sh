#!/bin/bash

# Activate the virtual environment
source venv/bin/activate

# Start the backend server
echo "Starting backend server..."
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000