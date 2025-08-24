#!/bin/bash

# AuraConnect - Run Database Migrations
# Ensures environment is properly set up before running migrations

set -e

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$SCRIPT_DIR/backend"

echo "🔄 Running AuraConnect Database Migrations"
echo "========================================"
echo ""

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

# Check if .env file exists
if [ ! -f ".env" ]; then
    echo -e "${RED}❌ .env file not found!${NC}"
    echo "Creating .env file..."
    
    cat > .env << 'EOF'
# Database
DATABASE_URL=postgresql://auraconnect:auraconnect123@localhost:5432/auraconnect_dev

# Redis
REDIS_URL=redis://localhost:6379/0

# JWT
JWT_SECRET_KEY=your-super-secret-key-change-this-in-production
JWT_ACCESS_TOKEN_EXPIRE_MINUTES=30
JWT_REFRESH_TOKEN_EXPIRE_DAYS=7

# Environment
ENVIRONMENT=development
DEBUG=True
LOG_LEVEL=INFO

# CORS
CORS_ORIGINS=http://localhost:3000,http://localhost:3001,http://localhost:19006

# File Upload
MAX_UPLOAD_SIZE_MB=10
ALLOWED_FILE_TYPES=csv,xlsx,pdf,jpg,jpeg,png

# Email (optional)
SMTP_SERVER=smtp.gmail.com
SMTP_PORT=587
SMTP_USERNAME=
SMTP_PASSWORD=

# Twilio (optional)
TWILIO_ACCOUNT_SID=
TWILIO_AUTH_TOKEN=
TWILIO_PHONE_NUMBER=

# Feature Flags
FEATURE_EMAIL_NOTIFICATIONS=true
FEATURE_SMS_NOTIFICATIONS=false
FEATURE_PUSH_NOTIFICATIONS=true
EOF
fi

# Load environment variables
echo "Loading environment variables..."
set -a
source .env
set +a

# Check if virtual environment exists
if [ ! -d "venv" ]; then
    echo -e "${YELLOW}⚠ Virtual environment not found. Creating...${NC}"
    python3.11 -m venv venv || python3 -m venv venv
fi

# Activate virtual environment
echo "Activating virtual environment..."
source venv/bin/activate

# Check if alembic is installed
if ! command -v alembic &> /dev/null; then
    echo -e "${YELLOW}⚠ Alembic not installed. Installing dependencies...${NC}"
    pip install --upgrade pip
    pip install -r requirements.txt
fi

# Check database connection
echo "Checking database connection..."
python3 << EOF
import sys
import psycopg2
from urllib.parse import urlparse

try:
    url = urlparse("$DATABASE_URL")
    conn = psycopg2.connect(
        host=url.hostname,
        port=url.port,
        database=url.path[1:],
        user=url.username,
        password=url.password
    )
    conn.close()
    print("✅ Database connection successful")
except Exception as e:
    print(f"❌ Database connection failed: {e}")
    print("")
    print("Please ensure:")
    print("1. PostgreSQL is running")
    print("2. Database 'auraconnect_dev' exists")
    print("3. User 'auraconnect' has proper permissions")
    print("")
    print("Run ./fix-database.sh to fix database issues")
    sys.exit(1)
EOF

if [ $? -ne 0 ]; then
    exit 1
fi

# Run migrations
echo ""
echo "Running database migrations..."
alembic upgrade head

if [ $? -eq 0 ]; then
    echo ""
    echo -e "${GREEN}✅ Migrations completed successfully!${NC}"
    
    # Show migration history
    echo ""
    echo "Current migration status:"
    alembic current
else
    echo ""
    echo -e "${RED}❌ Migration failed!${NC}"
    echo "Check the error messages above for details."
    exit 1
fi

# Deactivate virtual environment
deactivate

echo ""
echo "Next steps:"
echo "1. Start the backend: cd backend && source venv/bin/activate && uvicorn app.main:app --reload"
echo "2. Or use: ./start-all.sh to start all services"