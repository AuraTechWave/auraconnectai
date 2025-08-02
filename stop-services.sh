#!/bin/bash

# Stop Frontend and Backend Services for AuraConnect

echo "Stopping AuraConnect Services..."

# Kill processes on port 3000 (frontend)
if lsof -ti:3000 > /dev/null 2>&1; then
    echo "Stopping frontend on port 3000..."
    kill -9 $(lsof -ti:3000)
fi

# Kill processes on port 8000 (backend)
if lsof -ti:8000 > /dev/null 2>&1; then
    echo "Stopping backend on port 8000..."
    kill -9 $(lsof -ti:8000)
fi

echo "Services stopped."