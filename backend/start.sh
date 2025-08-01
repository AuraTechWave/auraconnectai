#!/bin/bash

# Get the directory of this script
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"

# Move to the parent directory (project root)
cd "$SCRIPT_DIR/.."

# Activate the virtual environment
source backend/venv/bin/activate

# Set PYTHONPATH to include the project root
export PYTHONPATH="${PYTHONPATH}:$(pwd)"

# Start the backend server
echo "Starting backend server from $(pwd)..."
uvicorn backend.app.main:app --reload --host 0.0.0.0 --port 8000