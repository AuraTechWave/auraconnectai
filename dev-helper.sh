#!/bin/bash

# AuraConnect - Development Helper Script
# Common development tasks and shortcuts

set -e

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$SCRIPT_DIR"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Function to display menu
show_menu() {
    echo ""
    echo "🚀 AuraConnect Development Helper"
    echo "================================"
    echo "1)  Start all services"
    echo "2)  Stop all services"
    echo "3)  Backend only"
    echo "4)  Frontend only"
    echo "5)  Mobile only"
    echo "6)  Run backend tests"
    echo "7)  Run frontend tests"
    echo "8)  Seed test data"
    echo "9)  Reset database"
    echo "10) View logs"
    echo "11) Check health status"
    echo "12) Generate API docs"
    echo "13) Run linters"
    echo "14) Create database backup"
    echo "15) Restore database backup"
    echo "0)  Exit"
    echo ""
}

# Start all services
start_all() {
    echo -e "${GREEN}Starting all services...${NC}"
    ./start-all.sh
}

# Stop all services
stop_all() {
    echo -e "${YELLOW}Stopping all services...${NC}"
    
    # Kill backend
    lsof -ti:8000 | xargs kill -9 2>/dev/null || true
    
    # Kill frontend
    lsof -ti:3000 | xargs kill -9 2>/dev/null || true
    
    # Kill customer web
    lsof -ti:3001 | xargs kill -9 2>/dev/null || true
    
    # Kill metro bundler
    lsof -ti:8081 | xargs kill -9 2>/dev/null || true
    
    echo -e "${GREEN}All services stopped${NC}"
}

# Start backend only
start_backend() {
    echo -e "${GREEN}Starting backend...${NC}"
    cd backend
    source venv/bin/activate
    uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
}

# Start frontend only
start_frontend() {
    echo -e "${GREEN}Starting frontend...${NC}"
    cd frontend
    npm start
}

# Start mobile only
start_mobile() {
    echo -e "${GREEN}Starting mobile...${NC}"
    cd mobile
    npx react-native start
}

# Run backend tests
run_backend_tests() {
    echo -e "${GREEN}Running backend tests...${NC}"
    cd backend
    source venv/bin/activate
    pytest -v
}

# Run frontend tests
run_frontend_tests() {
    echo -e "${GREEN}Running frontend tests...${NC}"
    cd frontend
    npm test
}

# Seed test data
seed_data() {
    echo -e "${GREEN}Seeding test data...${NC}"
    cd backend
    source venv/bin/activate
    python scripts/seed_test_data.py
}

# Reset database
reset_database() {
    echo -e "${RED}WARNING: This will delete all data!${NC}"
    read -p "Are you sure? (y/N): " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        cd backend
        source venv/bin/activate
        
        # Drop and recreate database
        sudo -u postgres psql << EOF
DROP DATABASE IF EXISTS auraconnect_dev;
CREATE DATABASE auraconnect_dev OWNER auraconnect;
GRANT ALL PRIVILEGES ON DATABASE auraconnect_dev TO auraconnect;
EOF
        
        # Run migrations
        alembic upgrade head
        
        echo -e "${GREEN}Database reset complete${NC}"
        
        # Ask if user wants to seed data
        read -p "Seed test data? (y/N): " -n 1 -r
        echo
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            python scripts/seed_test_data.py
        fi
    fi
}

# View logs
view_logs() {
    echo "Select log to view:"
    echo "1) Backend logs"
    echo "2) Frontend console"
    echo "3) Mobile metro logs"
    echo "4) PostgreSQL logs"
    echo "5) Redis logs"
    
    read -p "Choice: " log_choice
    
    case $log_choice in
        1)
            tail -f backend/backend.log
            ;;
        2)
            echo "Frontend logs appear in the browser console (F12)"
            ;;
        3)
            echo "Metro logs appear in the terminal running metro"
            ;;
        4)
            if [[ "$OSTYPE" == "darwin"* ]]; then
                tail -f /usr/local/var/log/postgresql@14.log
            else
                sudo tail -f /var/log/postgresql/postgresql-14-main.log
            fi
            ;;
        5)
            if [[ "$OSTYPE" == "darwin"* ]]; then
                tail -f /usr/local/var/log/redis.log
            else
                sudo tail -f /var/log/redis/redis-server.log
            fi
            ;;
    esac
}

# Check health status
check_health() {
    echo -e "${GREEN}Checking health status...${NC}"
    curl -s http://localhost:8000/api/v1/health/ | python -m json.tool
}

# Generate API docs
generate_docs() {
    echo -e "${GREEN}API documentation available at:${NC}"
    echo "Swagger UI: http://localhost:8000/docs"
    echo "ReDoc: http://localhost:8000/redoc"
    open http://localhost:8000/docs
}

# Run linters
run_linters() {
    echo -e "${GREEN}Running linters...${NC}"
    
    # Backend linting
    echo "Backend linting..."
    cd backend
    source venv/bin/activate
    ruff check .
    black --check .
    mypy .
    
    # Frontend linting
    echo -e "\nFrontend linting..."
    cd ../frontend
    npm run lint
    
    # Mobile linting
    echo -e "\nMobile linting..."
    cd ../mobile
    npm run lint
    npm run typecheck
    
    cd ..
    echo -e "${GREEN}Linting complete${NC}"
}

# Create database backup
create_backup() {
    echo -e "${GREEN}Creating database backup...${NC}"
    
    # Create backups directory
    mkdir -p backups
    
    # Generate filename with timestamp
    BACKUP_FILE="backups/auraconnect_$(date +%Y%m%d_%H%M%S).sql"
    
    # Create backup
    pg_dump -U auraconnect -h localhost auraconnect_dev > "$BACKUP_FILE"
    
    echo -e "${GREEN}Backup created: $BACKUP_FILE${NC}"
}

# Restore database backup
restore_backup() {
    echo "Available backups:"
    ls -la backups/*.sql 2>/dev/null || echo "No backups found"
    
    echo ""
    read -p "Enter backup filename (or full path): " backup_file
    
    if [ -f "$backup_file" ]; then
        echo -e "${RED}WARNING: This will overwrite the current database!${NC}"
        read -p "Are you sure? (y/N): " -n 1 -r
        echo
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            psql -U auraconnect -h localhost auraconnect_dev < "$backup_file"
            echo -e "${GREEN}Database restored from $backup_file${NC}"
        fi
    else
        echo -e "${RED}Backup file not found: $backup_file${NC}"
    fi
}

# Main loop
while true; do
    show_menu
    read -p "Enter choice: " choice
    
    case $choice in
        1) start_all ;;
        2) stop_all ;;
        3) start_backend ;;
        4) start_frontend ;;
        5) start_mobile ;;
        6) run_backend_tests ;;
        7) run_frontend_tests ;;
        8) seed_data ;;
        9) reset_database ;;
        10) view_logs ;;
        11) check_health ;;
        12) generate_docs ;;
        13) run_linters ;;
        14) create_backup ;;
        15) restore_backup ;;
        0) echo "Goodbye!"; exit 0 ;;
        *) echo -e "${RED}Invalid choice${NC}" ;;
    esac
    
    echo ""
    read -p "Press Enter to continue..."
done