# Customer Web App Setup Instructions

## Prerequisites

1. Make sure you have Node.js 16+ installed
2. Ensure PostgreSQL is running
3. Backend dependencies are installed

## Quick Start

### Option 1: Easiest Method - Use the startup scripts

```bash
# From the project root directory

# Terminal 1 - Backend
./run-backend.sh

# Terminal 2 - Frontend
cd customer-web && npm start
```

### Option 2: Run Both Together

```bash
# From the project root directory
./start-dev.sh
```

This will start both the backend (port 8000) and frontend (port 3000).

### Option 3: Run Manually

#### Terminal 1 - Start Backend:
```bash
cd backend
# Create Python virtual environment (if not already created)
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Copy environment file (first time only)
cp .env.example .env

# Run database migrations
alembic upgrade head

# Start the backend server
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# OR use the convenience script:
./start.sh
```

#### Terminal 2 - Start Frontend:
```bash
cd customer-web
npm install  # Only needed first time
npm start
```

## Accessing the Application

- Frontend: http://localhost:3000
- Backend API: http://localhost:8000/docs
- Backend Health Check: http://localhost:8000/health

## Troubleshooting

### Backend Connection Issues
1. Make sure the backend is running on port 8000
2. Check that PostgreSQL is running
3. Verify the DATABASE_URL in backend/.env

### Frontend Compilation Errors
1. Ensure all dependencies are installed: `npm install`
2. Clear npm cache if needed: `npm cache clean --force`
3. Delete node_modules and reinstall: `rm -rf node_modules && npm install`

### Port Already in Use
- Backend: `lsof -ti:8000 | xargs kill -9`
- Frontend: `lsof -ti:3000 | xargs kill -9`

## Features Available

1. **Browse Menu**: View all menu items with categories
2. **Shopping Cart**: Add items to cart and manage quantities
3. **User Registration**: Create a new customer account
4. **Login**: Access your account
5. **Make Reservations**: Book a table (requires login)

## Test Credentials

For testing, you can create a new account through the registration page.

## Environment Variables

Make sure the following files exist:

### backend/.env
```
DATABASE_URL=postgresql://user:password@localhost:5432/auraconnect
JWT_SECRET_KEY=your-secret-key
ENVIRONMENT=development
```

### customer-web/.env
```
REACT_APP_API_URL=http://localhost:8000/api/v1
```