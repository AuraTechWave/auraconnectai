# PostgreSQL Setup for AuraConnect

## Installation Complete ✅

PostgreSQL 14 is now installed and running on your system:
- **Version**: PostgreSQL 14.18
- **Port**: 5432 (default)
- **Database**: auraconnect
- **User**: sanv3 (your system user)
- **Status**: Running as a service

## PostgreSQL Management Commands

### Start/Stop PostgreSQL
```bash
# Start PostgreSQL (already running)
brew services start postgresql@14

# Stop PostgreSQL
brew services stop postgresql@14

# Restart PostgreSQL
brew services restart postgresql@14

# Check PostgreSQL status
brew services list | grep postgresql
```

### Connect to Database
```bash
# Connect to auraconnect database
psql -d auraconnect

# Check connection
psql -d auraconnect -c "SELECT version();"
```

## Database Configuration

The backend will use the following connection string:
```
DATABASE_URL=postgresql://sanv3@localhost/auraconnect
```

## Next Steps

To complete the database setup:

1. Run database migrations:
```bash
cd backend
source venv/bin/activate
alembic upgrade head
```

2. The migrations need to be fixed first as there are dependency issues with missing migration files.

## Current Status

- ✅ PostgreSQL installed and running
- ✅ Database created
- ✅ Connection verified
- ❌ Migrations need to be fixed (missing dependencies)

The payroll endpoints require the database tables to be created via migrations.