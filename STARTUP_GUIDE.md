# AuraConnect AI - Startup Guide

This guide will help you start all components of the AuraConnect AI platform after the recent fixes.

## Prerequisites

### 1. System Requirements
- Python 3.11+ 
- Node.js 18+ and npm
- PostgreSQL 14+
- Redis 6+
- Git

### 2. Database Setup
```bash
# Create PostgreSQL database
createdb auraconnect
createdb auraconnect_test  # For testing

# Or using psql
psql -U postgres
CREATE DATABASE auraconnect;
CREATE DATABASE auraconnect_test;
```

### 3. Redis Setup
```bash
# macOS
brew install redis
brew services start redis

# Ubuntu/Debian
sudo apt-get install redis-server
sudo systemctl start redis

# Verify Redis is running
redis-cli ping  # Should return PONG
```

## Backend Setup

### 1. Navigate to Backend Directory
```bash
cd /path/to/auraconnectai/backend
```

### 2. Create Python Virtual Environment
```bash
# Create virtual environment
python3 -m venv venv

# Activate virtual environment
# macOS/Linux:
source venv/bin/activate

# Windows:
venv\Scripts\activate
```

### 3. Install Dependencies
```bash
# Upgrade pip
pip install --upgrade pip

# Install main requirements
pip install -r requirements.txt

# Install development requirements (optional)
pip install -r requirements-dev.txt

# Install performance monitoring tools
pip install -r requirements_performance.txt

# Additional packages needed after fixes
pip install psutil==5.9.8
pip install twilio
```

### 4. Environment Configuration
```bash
# Copy example environment file
cp .env.example .env

# Edit .env with your configuration
# IMPORTANT: Change all secret keys!
nano .env  # or use your preferred editor
```

**Key environment variables to set:**
```bash
# Required - Generate secure keys!
JWT_SECRET_KEY=$(openssl rand -hex 32)
JWT_REFRESH_SECRET_KEY=$(openssl rand -hex 32)
SECRET_KEY=$(openssl rand -hex 32)
SESSION_SECRET=$(openssl rand -hex 32)

# Database
DATABASE_URL=postgresql://username:password@localhost:5432/auraconnect

# Redis
REDIS_URL=redis://localhost:6379/0

# Restaurant Config
RESTAURANT_NAME="Your Restaurant Name"
RESTAURANT_ID=1

# Environment
ENVIRONMENT=development
```

### 5. Database Migrations
```bash
# Initialize Alembic (if needed)
alembic init alembic

# Run all migrations
alembic upgrade head

# Verify migrations
alembic current
```

### 6. Start Backend Server

#### Option A: Development Mode (with auto-reload)
```bash
# From backend directory
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

#### Option B: Using Start Script
```bash
# Make script executable
chmod +x start.sh

# Run the script
./start.sh
```

#### Option C: Production Mode
```bash
# With multiple workers
uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 4
```

### 7. Verify Backend is Running
- Open http://localhost:8000 - Should show {"message": "AuraConnect backend is running"}
- API Documentation: http://localhost:8000/docs
- ReDoc Documentation: http://localhost:8000/redoc

## Frontend Setup

### 1. Navigate to Frontend Directory
```bash
cd /path/to/auraconnectai/frontend
```

### 2. Install Dependencies
```bash
# Install node modules
npm install

# Or using yarn
yarn install
```

### 3. Environment Configuration
```bash
# Create .env file for frontend
cat > .env << EOF
REACT_APP_API_URL=http://localhost:8000
REACT_APP_WS_URL=ws://localhost:8000
REACT_APP_ENVIRONMENT=development
EOF
```

### 4. Start Frontend Development Server
```bash
# Start the development server
npm start

# Or using yarn
yarn start
```

The frontend will be available at http://localhost:3000

## Mobile App Setup

### 1. Navigate to Mobile Directory
```bash
cd /path/to/auraconnectai/mobile
```

### 2. Install Dependencies
```bash
# Install node modules
npm install

# Install iOS dependencies (macOS only)
cd ios && pod install && cd ..
```

### 3. Environment Configuration
```bash
# Create .env file
cat > .env << EOF
API_URL=http://localhost:8000
WS_URL=ws://localhost:8000
ENVIRONMENT=development
EOF
```

### 4. Start Mobile App

#### iOS (macOS only)
```bash
npm run ios
# Or
npx react-native run-ios
```

#### Android
```bash
# Start Android emulator first
npm run android
# Or
npx react-native run-android
```

## Starting All Services Together

### Create a Master Startup Script
```bash
# Create start-all.sh in project root
cat > start-all.sh << 'EOF'
#!/bin/bash

# Colors for output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${BLUE}Starting AuraConnect AI Services...${NC}"

# Check if Redis is running
if ! redis-cli ping > /dev/null 2>&1; then
    echo -e "${RED}Redis is not running. Please start Redis first.${NC}"
    exit 1
fi

# Check if PostgreSQL is running
if ! pg_isready > /dev/null 2>&1; then
    echo -e "${RED}PostgreSQL is not running. Please start PostgreSQL first.${NC}"
    exit 1
fi

# Start Backend
echo -e "${GREEN}Starting Backend...${NC}"
cd backend
source venv/bin/activate
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000 &
BACKEND_PID=$!
cd ..

# Wait for backend to start
sleep 5

# Start Frontend
echo -e "${GREEN}Starting Frontend...${NC}"
cd frontend
npm start &
FRONTEND_PID=$!
cd ..

echo -e "${GREEN}All services started!${NC}"
echo "Backend PID: $BACKEND_PID"
echo "Frontend PID: $FRONTEND_PID"
echo ""
echo "Services available at:"
echo "- Frontend: http://localhost:3000"
echo "- Backend API: http://localhost:8000"
echo "- API Docs: http://localhost:8000/docs"
echo ""
echo "Press Ctrl+C to stop all services"

# Wait for Ctrl+C
trap "kill $BACKEND_PID $FRONTEND_PID; exit" INT
wait
EOF

chmod +x start-all.sh
```

### Using Docker Compose (Alternative)
```bash
# Create docker-compose.yml in project root
cat > docker-compose.yml << 'EOF'
version: '3.8'

services:
  postgres:
    image: postgres:14
    environment:
      POSTGRES_DB: auraconnect
      POSTGRES_USER: postgres
      POSTGRES_PASSWORD: postgres
    ports:
      - "5432:5432"
    volumes:
      - postgres_data:/var/lib/postgresql/data

  redis:
    image: redis:7
    ports:
      - "6379:6379"

  backend:
    build: ./backend
    ports:
      - "8000:8000"
    environment:
      DATABASE_URL: postgresql://postgres:postgres@postgres:5432/auraconnect
      REDIS_URL: redis://redis:6379/0
    depends_on:
      - postgres
      - redis
    volumes:
      - ./backend:/app

  frontend:
    build: ./frontend
    ports:
      - "3000:3000"
    environment:
      REACT_APP_API_URL: http://localhost:8000
    depends_on:
      - backend

volumes:
  postgres_data:
EOF

# Start all services
docker-compose up
```

## Troubleshooting

### Backend Issues

1. **Import Errors**
   - Ensure virtual environment is activated
   - Verify all dependencies are installed
   - Check PYTHONPATH includes project root

2. **Database Connection Errors**
   - Verify PostgreSQL is running
   - Check DATABASE_URL in .env
   - Ensure database exists

3. **Redis Connection Errors**
   - Verify Redis is running: `redis-cli ping`
   - Check REDIS_URL in .env

4. **JWT/Authentication Errors**
   - Ensure JWT_SECRET_KEY is set in .env
   - Regenerate tokens if needed

### Frontend Issues

1. **API Connection Errors**
   - Verify backend is running on port 8000
   - Check REACT_APP_API_URL in frontend .env
   - Check CORS settings in backend

2. **Build Errors**
   - Clear node_modules and reinstall: `rm -rf node_modules && npm install`
   - Clear npm cache: `npm cache clean --force`

## Default Test Credentials

For development/testing:
- **Admin**: username=`admin`, password=`secret`
- **Manager**: username=`manager`, password=`secret`
- **Payroll Manager**: username=`payroll_clerk`, password=`secret`

## Health Checks

### Backend Health Check
```bash
curl http://localhost:8000/health
```

### Database Connection Test
```bash
curl http://localhost:8000/health/db
```

### Redis Connection Test
```bash
curl http://localhost:8000/health/redis
```

## Next Steps

1. **Create initial admin user**
```bash
# Run from backend directory with venv activated
python scripts/create_admin.py
```

2. **Load sample data (optional)**
```bash
python scripts/seed_test_data.py
```

3. **Configure POS integrations** (if needed)
   - Add Square/Toast/Clover API keys to .env
   - Set up webhook endpoints

4. **Set up monitoring** (production)
   - Configure Sentry DSN
   - Enable Prometheus metrics
   - Set up log aggregation

## Support

For issues or questions:
- Check logs in `backend/logs/`
- Review API documentation at `/docs`
- Check database migrations status
- Verify all environment variables are set correctly