#!/bin/bash

# AuraConnect - Environment Setup Script
# This script sets up the complete development environment

set -e

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$SCRIPT_DIR"

echo "🎯 AuraConnect Development Environment Setup"
echo "==========================================="

# Detect OS
if [[ "$OSTYPE" == "darwin"* ]]; then
    OS="macos"
    echo "Detected macOS"
elif [[ "$OSTYPE" == "linux-gnu"* ]]; then
    OS="linux"
    echo "Detected Linux"
else
    echo "❌ Unsupported OS: $OSTYPE"
    exit 1
fi

# Function to check if command exists
command_exists() {
    command -v "$1" >/dev/null 2>&1
}

# Function to create .env file
create_env_file() {
    local dir=$1
    local env_file=$2
    
    if [ ! -f "$dir/.env" ]; then
        echo "Creating $dir/.env..."
        cp "$env_file" "$dir/.env"
    else
        echo "✅ $dir/.env already exists"
    fi
}

echo ""
echo "📦 Step 1: Installing System Dependencies"
echo "----------------------------------------"

if [ "$OS" == "macos" ]; then
    # Install Homebrew if not present
    if ! command_exists brew; then
        echo "Installing Homebrew..."
        /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
    fi
    
    # Install dependencies
    echo "Installing system dependencies..."
    brew install python@3.11 node@20 postgresql@14 redis
    
    # Add node@20 to PATH if not already there
    if ! echo $PATH | grep -q "/opt/homebrew/opt/node@20/bin" && [ -d "/opt/homebrew/opt/node@20/bin" ]; then
        echo ""
        echo "Adding node@20 to PATH..."
        echo 'export PATH="/opt/homebrew/opt/node@20/bin:$PATH"' >> ~/.zshrc
        export PATH="/opt/homebrew/opt/node@20/bin:$PATH"
    elif ! echo $PATH | grep -q "/usr/local/opt/node@20/bin" && [ -d "/usr/local/opt/node@20/bin" ]; then
        # Intel Mac path
        echo ""
        echo "Adding node@20 to PATH..."
        echo 'export PATH="/usr/local/opt/node@20/bin:$PATH"' >> ~/.zshrc
        export PATH="/usr/local/opt/node@20/bin:$PATH"
    fi
    
    # Start services
    brew services start postgresql@14
    brew services start redis
    
elif [ "$OS" == "linux" ]; then
    # Update package list
    sudo apt update
    
    # Install Python 3.11
    if ! command_exists python3.11; then
        echo "Installing Python 3.11..."
        sudo apt install -y python3.11 python3.11-venv python3-pip
    fi
    
    # Install Node.js 20
    if ! command_exists node || [ $(node -v | cut -d'v' -f2 | cut -d'.' -f1) -lt 20 ]; then
        echo "Installing Node.js 20..."
        curl -fsSL https://deb.nodesource.com/setup_20.x | sudo -E bash -
        sudo apt-get install -y nodejs
    fi
    
    # Install PostgreSQL 14
    if ! command_exists psql; then
        echo "Installing PostgreSQL 14..."
        sudo sh -c 'echo "deb http://apt.postgresql.org/pub/repos/apt $(lsb_release -cs)-pgdg main" > /etc/apt/sources.list.d/pgdg.list'
        wget --quiet -O - https://www.postgresql.org/media/keys/ACCC4CF8.asc | sudo apt-key add -
        sudo apt-get update
        sudo apt-get -y install postgresql-14
    fi
    
    # Install Redis
    if ! command_exists redis-server; then
        echo "Installing Redis..."
        sudo apt install -y redis-server
    fi
    
    # Start services
    sudo systemctl start postgresql
    sudo systemctl start redis-server
fi

echo ""
echo "🗄️  Step 2: Setting up Database"
echo "-------------------------------"

# Check if database exists
# On macOS with Homebrew, use the current user instead of postgres
if [ "$OS" == "macos" ]; then
    DB_USER=$(whoami)
    if ! psql -U $DB_USER -lqt 2>/dev/null | cut -d \| -f 1 | grep -qw auraconnect_dev; then
        echo "Creating database and user..."
        psql -U $DB_USER << EOF
CREATE USER auraconnect WITH PASSWORD 'auraconnect123';
CREATE DATABASE auraconnect_dev OWNER auraconnect;
CREATE DATABASE auraconnect_test OWNER auraconnect;
GRANT ALL PRIVILEGES ON DATABASE auraconnect_dev TO auraconnect;
GRANT ALL PRIVILEGES ON DATABASE auraconnect_test TO auraconnect;
EOF
    else
        echo "✅ Database already exists"
    fi
else
    # Linux uses postgres user
    if ! sudo -u postgres psql -lqt 2>/dev/null | cut -d \| -f 1 | grep -qw auraconnect_dev; then
        echo "Creating database and user..."
        sudo -u postgres psql << EOF
CREATE USER auraconnect WITH PASSWORD 'auraconnect123';
CREATE DATABASE auraconnect_dev OWNER auraconnect;
CREATE DATABASE auraconnect_test OWNER auraconnect;
GRANT ALL PRIVILEGES ON DATABASE auraconnect_dev TO auraconnect;
GRANT ALL PRIVILEGES ON DATABASE auraconnect_test TO auraconnect;
EOF
    else
        echo "✅ Database already exists"
    fi
fi

echo ""
echo "🐍 Step 3: Setting up Backend"
echo "-----------------------------"

cd "$SCRIPT_DIR/backend"

# Create virtual environment
if [ ! -d "venv" ]; then
    echo "Creating Python virtual environment..."
    # Try python3.11 first, then python3
    if command -v python3.11 >/dev/null 2>&1; then
        python3.11 -m venv venv
    elif command -v python3 >/dev/null 2>&1; then
        echo "Warning: python3.11 not found, using python3"
        python3 -m venv venv
    else
        echo "Error: Python 3 not found!"
        exit 1
    fi
else
    echo "✅ Virtual environment already exists"
    # Check Python version in venv
    VENV_PYTHON_VERSION=$(./venv/bin/python --version | cut -d' ' -f2)
    echo "  Python version in venv: $VENV_PYTHON_VERSION"
fi

# Activate venv and install dependencies
echo "Installing backend dependencies..."
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
pip install -r requirements-dev.txt

# Create .env file
if [ ! -f ".env" ]; then
    echo "Creating backend .env file..."
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
else
    echo "✅ Backend .env already exists"
fi

# Run migrations
echo "Running database migrations..."
# Export the DATABASE_URL for alembic
export DATABASE_URL="postgresql://auraconnect:auraconnect123@localhost:5432/auraconnect_dev"
alembic upgrade head

# Seed test data
echo ""
read -p "Do you want to seed test data? (y/N): " -n 1 -r
echo ""
if [[ $REPLY =~ ^[Yy]$ ]]; then
    python scripts/seed_test_data.py
fi

deactivate

echo ""
echo "⚛️  Step 4: Setting up Frontend"
echo "-------------------------------"

cd "$SCRIPT_DIR/frontend"

# Install dependencies
echo "Installing frontend dependencies..."
npm install

# Create .env file
if [ ! -f ".env" ]; then
    echo "Creating frontend .env file..."
    cat > .env << 'EOF'
REACT_APP_API_URL=http://localhost:8000
REACT_APP_WEBSOCKET_URL=ws://localhost:8000
REACT_APP_ENVIRONMENT=development
EOF
else
    echo "✅ Frontend .env already exists"
fi

echo ""
echo "🛍️  Step 5: Setting up Customer Web App"
echo "---------------------------------------"

cd "$SCRIPT_DIR/customer-web"

# Install dependencies
echo "Installing customer web dependencies..."
npm install

echo ""
echo "📱 Step 6: Setting up Mobile App"
echo "--------------------------------"

cd "$SCRIPT_DIR/mobile"

# Install dependencies
echo "Installing mobile dependencies..."
npm install

# Create config file
if [ ! -f "src/constants/config.ts" ]; then
    echo "Creating mobile config file..."
    mkdir -p src/constants
    cat > src/constants/config.ts << 'EOF'
export const API_BASE_URL = 'http://localhost:8000';
export const WS_BASE_URL = 'ws://localhost:8000';
export const ENVIRONMENT = 'development';
EOF
else
    echo "✅ Mobile config already exists"
fi

# iOS setup (macOS only)
if [ "$OS" == "macos" ] && [ -d "ios" ]; then
    echo "Setting up iOS dependencies..."
    cd ios && pod install && cd ..
fi

cd "$SCRIPT_DIR"

echo ""
echo "✅ Setup Complete!"
echo "=================="
echo ""
echo "To start all services, run:"
echo "  ./start-all.sh"
echo ""
echo "Or start services individually:"
echo "  Backend:  cd backend && source venv/bin/activate && uvicorn app.main:app --reload"
echo "  Frontend: cd frontend && npm start"
echo "  Customer: cd customer-web && PORT=3001 npm start"
echo "  Mobile:   cd mobile && npx react-native start"
echo ""
echo "📚 For detailed testing instructions, see SETUP_MANUAL_TESTING.md"