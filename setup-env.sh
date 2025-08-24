#!/bin/bash

# Setup Environment Variables for AuraConnect

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}=== AuraConnect Environment Setup ===${NC}"
echo ""

# Get script directory
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$SCRIPT_DIR/backend"

# Check if .env exists
if [ -f ".env" ]; then
    echo -e "${YELLOW}.env file already exists. Backing up to .env.backup${NC}"
    cp .env .env.backup
fi

# Function to generate secret key
generate_secret() {
    if command -v openssl &> /dev/null; then
        openssl rand -hex 32
    else
        # Fallback to /dev/urandom
        cat /dev/urandom | tr -dc 'a-zA-Z0-9' | fold -w 64 | head -n 1
    fi
}

# Generate secure keys
JWT_SECRET=$(generate_secret)
JWT_REFRESH_SECRET=$(generate_secret)
SECRET_KEY=$(generate_secret)
SESSION_SECRET=$(generate_secret)

# Create comprehensive .env file
cat > .env << EOF
# AuraConnect Backend Configuration
# Generated on $(date)

# ===================
# Security Keys (REQUIRED)
# ===================
JWT_SECRET_KEY=$JWT_SECRET
JWT_REFRESH_SECRET_KEY=$JWT_REFRESH_SECRET
SECRET_KEY=$SECRET_KEY
SESSION_SECRET=$SESSION_SECRET

# ===================
# Database Configuration
# ===================
# Default PostgreSQL connection
DATABASE_URL=postgresql://postgres:postgres@localhost:5432/auraconnect
DATABASE_TEST_URL=postgresql://postgres:postgres@localhost:5432/auraconnect_test

# Connection pool settings
DATABASE_POOL_SIZE=20
DATABASE_MAX_OVERFLOW=40

# ===================
# Redis Configuration
# ===================
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_DB=0
REDIS_PASSWORD=
REDIS_URL=redis://localhost:6379/0

# ===================
# Restaurant Configuration
# ===================
RESTAURANT_NAME=AuraConnect Demo Restaurant
RESTAURANT_ID=1
RESTAURANT_PHONE=+1-555-123-4567
RESTAURANT_ADDRESS=123 Main St, City, State 12345

# ===================
# Environment Settings
# ===================
ENVIRONMENT=development
DEBUG=true
LOG_LEVEL=INFO

# ===================
# API Configuration
# ===================
API_V1_STR=/api/v1
BACKEND_CORS_ORIGINS=["http://localhost:3000","http://localhost:3001","http://localhost:8080"]

# ===================
# Email Configuration (Optional)
# ===================
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=
SMTP_PASSWORD=
EMAILS_FROM_EMAIL=noreply@auraconnect.ai
EMAILS_FROM_NAME=AuraConnect AI

# ===================
# SMS Configuration (Optional)
# ===================
TWILIO_ACCOUNT_SID=
TWILIO_AUTH_TOKEN=
TWILIO_PHONE_NUMBER=

# ===================
# Worker Configuration
# ===================
CELERY_BROKER_URL=redis://localhost:6379/1
CELERY_RESULT_BACKEND=redis://localhost:6379/2

# ===================
# Feature Flags
# ===================
ENABLE_WEBSOCKETS=true
ENABLE_CACHE_WARMING=true
ENABLE_BACKGROUND_TASKS=true

# ===================
# Performance Settings
# ===================
QUERY_TIMEOUT_SECONDS=30
CACHE_TTL_SECONDS=3600
MAX_REQUEST_SIZE_MB=10

# ===================
# File Upload Settings
# ===================
MAX_UPLOAD_SIZE_MB=10
ALLOWED_FILE_TYPES=["csv", "xlsx", "pdf", "jpg", "jpeg", "png"]

# ===================
# Multi-tenant Configuration
# ===================
DEFAULT_TENANT_ID=1
ENABLE_MULTI_TENANT=true

# ===================
# Inventory Configuration
# ===================
INVENTORY_DEDUCTION_DEDUCTION_TRIGGER=order_completed
INVENTORY_DEDUCTION_ALLOW_NEGATIVE_INVENTORY=false
INVENTORY_DEDUCTION_AUTO_REVERSE_ON_CANCEL=true
EOF

echo -e "${GREEN}✅ Created .env file with secure keys${NC}"
echo ""

# Export for current session
export DATABASE_URL="postgresql://postgres:postgres@localhost:5432/auraconnect"
export JWT_SECRET_KEY="$JWT_SECRET"
export REDIS_URL="redis://localhost:6379/0"
export RESTAURANT_NAME="AuraConnect Demo Restaurant"
export RESTAURANT_ID="1"
export ENVIRONMENT="development"

echo "Environment variables set for current session."
echo ""

# Check PostgreSQL connection
echo -n "Checking PostgreSQL connection... "
if PGPASSWORD=postgres psql -h localhost -U postgres -d postgres -c '\q' 2>/dev/null; then
    echo -e "${GREEN}✓${NC}"
    
    # Create database if it doesn't exist
    echo -n "Checking if database 'auraconnect' exists... "
    if PGPASSWORD=postgres psql -h localhost -U postgres -lqt | cut -d \| -f 1 | grep -qw auraconnect; then
        echo -e "${GREEN}✓${NC}"
    else
        echo -e "${YELLOW}Creating...${NC}"
        PGPASSWORD=postgres createdb -h localhost -U postgres auraconnect
        echo -e "${GREEN}✅ Database created${NC}"
    fi
else
    echo -e "${RED}✗${NC}"
    echo ""
    echo -e "${RED}ERROR: Cannot connect to PostgreSQL!${NC}"
    echo ""
    echo "Please ensure PostgreSQL is running and accessible."
    echo "Default connection assumes:"
    echo "  - Host: localhost"
    echo "  - User: postgres"
    echo "  - Password: postgres"
    echo ""
    echo "To use different credentials, edit the DATABASE_URL in .env"
    echo ""
    echo "Start PostgreSQL:"
    echo "  macOS:  brew services start postgresql@14"
    echo "  Ubuntu: sudo systemctl start postgresql"
fi

echo ""
echo -e "${GREEN}=== Environment Setup Complete ===${NC}"
echo ""
echo "Next steps:"
echo "1. Review and adjust settings in backend/.env if needed"
echo "2. Run database migrations:"
echo "   cd backend && source venv/bin/activate && alembic upgrade head"
echo "3. Start the application:"
echo "   ./start-all.sh"