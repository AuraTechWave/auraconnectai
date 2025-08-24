# AuraConnect Scripts Guide

This guide explains the purpose of each script in the repository after cleanup.

## Essential Scripts to Keep

### Root Directory Scripts

1. **`start-all.sh`**
   - Purpose: Master script to start all services (backend, frontend, mobile)
   - Usage: `./start-all.sh`
   - Opens separate terminal windows for each service

2. **`quick-setup.sh`**
   - Purpose: Initial setup helper that checks dependencies and creates databases
   - Usage: `./quick-setup.sh`
   - Run once after cloning the repository

3. **`setup-env.sh`**
   - Purpose: Creates proper .env files with secure keys
   - Usage: `./setup-env.sh`
   - Generates secure JWT keys and sets up environment variables

4. **`fix-venv.sh`**
   - Purpose: Repairs corrupted Python virtual environment
   - Usage: `./fix-venv.sh`
   - Use when you encounter pip or import errors

### Backend Scripts

5. **`backend/start-backend.sh`**
   - Purpose: Starts the backend with proper checks
   - Usage: `cd backend && ./start-backend.sh`
   - Includes health checks for PostgreSQL and Redis

6. **`backend/run-migrations.sh`**
   - Purpose: Runs database migrations with proper environment setup
   - Usage: `cd backend && ./run-migrations.sh`
   - Loads .env automatically and shows migration status

### Frontend Scripts

7. **`frontend/start-frontend.sh`**
   - Purpose: Starts the React frontend
   - Usage: `cd frontend && ./start-frontend.sh`
   - Checks Node.js version and installs dependencies if needed

## Documentation Files

- **`STARTUP_GUIDE.md`** - Comprehensive startup instructions
- **`SCRIPTS_GUIDE.md`** - This file, explaining all scripts

## Temporary Scripts to Remove

Run `./cleanup-temp-files.sh` to remove these temporary debugging scripts:

- All `fix-*.sh` scripts (used for one-time fixes)
- All `test-*.py` scripts (used for debugging)
- All `.bak` files
- All `__pycache__` directories

## Quick Start After Cleanup

```bash
# 1. First time setup
./quick-setup.sh
./setup-env.sh

# 2. Start all services
./start-all.sh

# Or start individually:
cd backend && ./start-backend.sh
cd frontend && ./start-frontend.sh
```

## Troubleshooting

- **Virtual environment issues**: `./fix-venv.sh`
- **Database connection issues**: Check `backend/.env` and PostgreSQL status
- **Port conflicts**: Kill existing processes on ports 3000 and 8000

## Environment Variables

The `.env` files created by `setup-env.sh` contain:
- Database connection strings
- Security keys (JWT, session)
- Redis configuration
- Feature flags
- Service URLs

Always review and update these files for your environment!