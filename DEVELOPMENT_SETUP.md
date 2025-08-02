# Development Setup Guide

## Current Status

The application is running with the following warnings that are **normal for development**:

### 1. **Redis Connection** (Optional)
- **Warning**: "Failed to connect to Redis: Connection refused"
- **Impact**: Using in-memory session storage instead
- **Solution**: Install and run Redis if needed:
  ```bash
  # macOS
  brew install redis
  brew services start redis
  
  # Linux
  sudo apt-get install redis-server
  sudo systemctl start redis
  ```

### 2. **PostgreSQL Connection** (Optional for testing)
- **Warning**: "Database connection failed: Connection refused"
- **Impact**: API will work but data won't persist
- **Solution**: Install and setup PostgreSQL:
  ```bash
  # macOS
  brew install postgresql
  brew services start postgresql
  createdb auraconnect
  
  # Linux
  sudo apt-get install postgresql
  sudo systemctl start postgresql
  sudo -u postgres createdb auraconnect
  ```

### 3. **Pydantic Warnings** (Informational)
- **Warning**: "Valid config keys have changed in V2"
- **Impact**: None - backward compatibility warnings
- **Note**: These will be addressed in a future update

### 4. **Session Secret Warning** (Development Only)
- **Warning**: "Using default SESSION_SECRET"
- **Impact**: Fine for development
- **Production**: Set `SESSION_SECRET` environment variable

## Quick Development Setup

For basic frontend-backend integration testing, the current setup is sufficient:

1. **Backend is running** on http://localhost:8000
   - API docs: http://localhost:8000/docs
   - Uses in-memory storage (no database needed)

2. **Frontend is running** on http://localhost:3000
   - Login with: admin/secret
   - Connected to backend API

## Optional: Full Development Environment

If you want persistent data and all features:

1. **Create .env file in backend directory**:
   ```bash
   cd backend
   cp .env.example .env
   # Edit .env with your values
   ```

2. **Install PostgreSQL and Redis**:
   ```bash
   # macOS
   brew install postgresql redis
   brew services start postgresql
   brew services start redis
   
   # Create database
   createdb auraconnect
   ```

3. **Run database migrations**:
   ```bash
   cd backend
   alembic upgrade head
   ```

4. **Restart the backend**:
   ```bash
   ./stop-services.sh
   ./start-services.sh
   ```

## Testing the Integration

1. Open http://localhost:3000
2. Login with test credentials:
   - Admin: `admin` / `secret`
   - Manager: `manager` / `secret`
   - Payroll Clerk: `payroll_clerk` / `secret`
3. The API should work even without PostgreSQL/Redis

## Note on SQLAlchemy Errors

All SQLAlchemy relationship errors have been fixed:
- ✅ TaxRule duplicate class
- ✅ StaffMember.pay_policies relationship
- ✅ RBACUser.roles relationship
- ✅ RBACUser.direct_permissions relationship

The backend should now run without SQLAlchemy errors.