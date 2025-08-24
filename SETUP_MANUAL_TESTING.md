# AuraConnect Manual Testing Setup Guide

This guide will help you set up your laptop to manually test all AuraConnect features.

## System Requirements

### Required Software
- **Python**: 3.11+ 
- **Node.js**: 18.x or 20.x
- **PostgreSQL**: 14+
- **Redis**: 7.0+
- **React Native CLI**: For mobile testing
- **Xcode**: (Mac only) For iOS testing
- **Android Studio**: For Android testing

### Recommended Hardware
- **RAM**: 16GB minimum (32GB recommended)
- **Storage**: 20GB free space
- **Processor**: Multi-core processor for running multiple services

## Step 1: Install Prerequisites

### macOS
```bash
# Install Homebrew if not already installed
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"

# Install required packages
brew install python@3.11 node@20 postgresql@14 redis
brew install --cask android-studio

# Start services
brew services start postgresql@14
brew services start redis

# Install React Native dependencies
npm install -g react-native-cli
```

### Linux (Ubuntu/Debian)
```bash
# Update package list
sudo apt update

# Install Python 3.11
sudo apt install python3.11 python3.11-venv python3-pip

# Install Node.js 20
curl -fsSL https://deb.nodesource.com/setup_20.x | sudo -E bash -
sudo apt-get install -y nodejs

# Install PostgreSQL 14
sudo sh -c 'echo "deb http://apt.postgresql.org/pub/repos/apt $(lsb_release -cs)-pgdg main" > /etc/apt/sources.list.d/pgdg.list'
wget --quiet -O - https://www.postgresql.org/media/keys/ACCC4CF8.asc | sudo apt-key add -
sudo apt-get update
sudo apt-get -y install postgresql-14

# Install Redis
sudo apt install redis-server

# Start services
sudo systemctl start postgresql
sudo systemctl start redis-server
```

## Step 2: Database Setup

```bash
# Create database user and database
sudo -u postgres psql << EOF
CREATE USER auraconnect WITH PASSWORD 'auraconnect123';
CREATE DATABASE auraconnect_dev OWNER auraconnect;
CREATE DATABASE auraconnect_test OWNER auraconnect;
GRANT ALL PRIVILEGES ON DATABASE auraconnect_dev TO auraconnect;
GRANT ALL PRIVILEGES ON DATABASE auraconnect_test TO auraconnect;
EOF
```

## Step 3: Backend Setup

```bash
cd backend

# Create Python virtual environment
python3.11 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install --upgrade pip
pip install -r requirements.txt
pip install -r requirements-dev.txt

# Create .env file
cat > .env << EOF
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

# Email (optional for testing)
SMTP_SERVER=smtp.gmail.com
SMTP_PORT=587
SMTP_USERNAME=your-email@gmail.com
SMTP_PASSWORD=your-app-password

# Twilio (optional for SMS testing)
TWILIO_ACCOUNT_SID=your-twilio-sid
TWILIO_AUTH_TOKEN=your-twilio-token
TWILIO_PHONE_NUMBER=+1234567890

# Feature Flags
FEATURE_EMAIL_NOTIFICATIONS=true
FEATURE_SMS_NOTIFICATIONS=false
FEATURE_PUSH_NOTIFICATIONS=true
EOF

# Run database migrations
alembic upgrade head

# Seed test data (create this script)
python scripts/seed_test_data.py
```

## Step 4: Frontend Setup

```bash
cd ../frontend

# Install dependencies
npm install

# Create .env file
cat > .env << EOF
REACT_APP_API_URL=http://localhost:8000
REACT_APP_WEBSOCKET_URL=ws://localhost:8000
REACT_APP_ENVIRONMENT=development
EOF
```

## Step 5: Mobile App Setup

```bash
cd ../mobile

# Install dependencies
npm install

# iOS setup (Mac only)
cd ios && pod install && cd ..

# Create config file
cat > src/constants/config.ts << EOF
export const API_BASE_URL = 'http://localhost:8000';
export const WS_BASE_URL = 'ws://localhost:8000';
export const ENVIRONMENT = 'development';
EOF
```

## Step 6: Customer Web App Setup

```bash
cd ../customer-web

# Install dependencies
npm install

# The app uses MSW for mocking, no additional setup needed
```

## Step 7: Start All Services

Create a script to start all services:

```bash
#!/bin/bash
# Save as start-all.sh in project root

echo "Starting AuraConnect Services..."

# Terminal 1: Backend
osascript -e 'tell app "Terminal" to do script "cd '$PWD'/backend && source venv/bin/activate && uvicorn app.main:app --reload --host 0.0.0.0 --port 8000"'

# Terminal 2: Frontend
osascript -e 'tell app "Terminal" to do script "cd '$PWD'/frontend && npm start"'

# Terminal 3: Customer Web
osascript -e 'tell app "Terminal" to do script "cd '$PWD'/customer-web && npm start"'

# Terminal 4: Mobile Metro
osascript -e 'tell app "Terminal" to do script "cd '$PWD'/mobile && npx react-native start"'

echo "All services starting..."
echo "Backend: http://localhost:8000"
echo "Frontend: http://localhost:3000"
echo "Customer Web: http://localhost:3001"
echo "Mobile Metro: http://localhost:8081"
```

Make it executable:
```bash
chmod +x start-all.sh
```

## Step 8: Test User Accounts

The system comes with these default test accounts:

### Admin Account
- Username: `admin`
- Password: `admin123`
- Permissions: Full system access

### Manager Account
- Username: `manager`
- Password: `manager123`
- Permissions: Restaurant management

### Staff Account
- Username: `staff`
- Password: `staff123`
- Permissions: Basic staff operations

### Customer Account
- Email: `customer@example.com`
- Password: `customer123`

## Step 9: Testing Each Module

### 1. Authentication & RBAC
- Login with different user roles
- Test permission-based access
- Password reset flow
- JWT token refresh

### 2. Staff Management
- Create/edit staff profiles
- Schedule management
- Attendance tracking
- Payroll processing

### 3. Menu Management
- Create menu categories and items
- Recipe management (BOM)
- Menu versioning
- Modifier groups

### 4. Order Management
- Create orders
- Kitchen display system
- Order routing
- Payment processing

### 5. Inventory Management
- Track inventory levels
- Vendor management
- Purchase orders
- Stock adjustments

### 6. Customer Management
- Customer profiles
- Order history
- Loyalty programs
- Feedback system

### 7. Analytics & Reports
- Sales reports
- Performance metrics
- AI insights
- Real-time dashboards

### 8. POS Integration
- Square/Toast/Clover sync
- Menu synchronization
- Order sync
- Payment reconciliation

### 9. Table Management
- Table layout
- Real-time status
- Reservation system
- Waitlist management

### 10. Notifications
- Email notifications
- SMS notifications (Twilio)
- Push notifications
- In-app notifications

## Troubleshooting

### Backend Issues
```bash
# Check logs
tail -f backend/backend.log

# Check database connection
psql -U auraconnect -d auraconnect_dev -h localhost

# Check Redis connection
redis-cli ping
```

### Frontend Issues
```bash
# Clear cache
rm -rf node_modules/.cache
npm start

# Check console for errors
# Open browser developer tools (F12)
```

### Mobile Issues
```bash
# Reset Metro cache
npx react-native start --reset-cache

# iOS specific
cd ios && pod install
npx react-native run-ios

# Android specific
cd android && ./gradlew clean
npx react-native run-android
```

## Health Monitoring

Access the health monitoring dashboard:
- Health Check: http://localhost:8000/api/v1/health/
- API Docs: http://localhost:8000/docs
- Metrics: http://localhost:8000/api/v1/health/metrics (requires auth)

## Next Steps

1. Run through each module systematically
2. Test cross-module integrations
3. Test error scenarios
4. Test performance under load
5. Test offline functionality (mobile)
6. Test real-time features (WebSocket)

## Support

If you encounter issues:
1. Check the logs in each service
2. Verify all prerequisites are installed
3. Ensure all services are running
4. Check network connectivity
5. Verify database migrations are up to date