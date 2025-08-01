# Menu Versioning System - Setup Guide

## Prerequisites

### System Requirements

- **Python**: 3.9+ (3.11+ recommended)
- **Node.js**: 16+ (18+ recommended)
- **PostgreSQL**: 12+ (14+ recommended)
- **Redis**: 6+ (7+ recommended for persistence)

### Database Extensions

Ensure the following PostgreSQL extensions are enabled:

```sql
-- Required extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "btree_gin";

-- Optional but recommended for performance
CREATE EXTENSION IF NOT EXISTS "pg_stat_statements";
CREATE EXTENSION IF NOT EXISTS "pg_trgm";
```

## Installation Steps

### 1. Backend Setup

#### Environment Configuration

Create or update your `.env` file:

```bash
# Database Configuration
DATABASE_URL=postgresql://user:password@localhost:5432/auraconnect
DATABASE_POOL_SIZE=20
DATABASE_POOL_OVERFLOW=30

# Redis Configuration (for caching)
REDIS_URL=redis://localhost:6379/0
REDIS_CACHE_TTL=3600

# Menu Versioning Configuration
MENU_VERSIONING_ENABLED=true
AUTO_VERSIONING_THRESHOLD=10
MAX_AUDIT_LOG_RETENTION_DAYS=365
VERSION_COMPARISON_CACHE_TTL=1800

# Optional: Advanced Configuration
MENU_VERSION_COMPRESSION=true
ENABLE_VERSION_ENCRYPTION=false
BACKGROUND_VERSIONING=true
```

#### Database Migration

Run the database migration to create versioning tables:

```bash
# From the project root directory
cd backend

# Run the migration
alembic upgrade head

# Verify tables were created
psql $DATABASE_URL -c "\dt menu_*"
```

Expected tables:
- `menu_versions`
- `menu_category_versions`
- `menu_item_versions`
- `modifier_group_versions`
- `modifier_versions`
- `menu_item_modifier_versions`
- `menu_audit_logs`
- `menu_version_schedules`
- `menu_version_comparisons`

#### Install Dependencies

```bash
# Install Python dependencies
pip install -r requirements.txt

# Install additional dependencies for versioning (if not already included)
pip install redis python-dateutil pytz
```

#### Initialize Versioning System

Add the following to your application startup (already included in `main.py`):

```python
from backend.core.menu_versioning_triggers import init_versioning_triggers

# Initialize versioning triggers
init_versioning_triggers()
```

### 2. Frontend Setup

#### Install Dependencies

```bash
cd frontend

# Install Node.js dependencies
npm install

# Install additional dependencies for versioning
npm install react-window react-window-infinite-loader date-fns
```

#### Environment Configuration

Update your frontend `.env` file:

```bash
# API Configuration
REACT_APP_API_BASE_URL=http://localhost:8000
REACT_APP_ENABLE_VERSIONING=true

# Feature Flags
REACT_APP_ENABLE_VERSION_COMPARISON=true
REACT_APP_ENABLE_BULK_OPERATIONS=true
REACT_APP_MAX_VERSIONS_PER_PAGE=20

# UI Configuration
REACT_APP_VIRTUALIZATION_THRESHOLD=100
REACT_APP_AUTO_REFRESH_INTERVAL=30000
```

#### Component Integration

The versioning components are already integrated into the MenuDashboard. To verify:

1. Start the development server:
   ```bash
   npm start
   ```

2. Navigate to the Menu Management section
3. Look for the "Versioning" tab

### 3. Verification Steps

#### Backend Verification

1. **API Health Check**:
   ```bash
   curl http://localhost:8000/menu/versions/stats
   ```

2. **Create Test Version**:
   ```bash
   curl -X POST http://localhost:8000/menu/versions \
     -H "Content-Type: application/json" \
     -H "Authorization: Bearer YOUR_JWT_TOKEN" \
     -d '{
       "version_name": "Test Version",
       "description": "Initial test version",
       "version_type": "manual"
     }'
   ```

3. **Check Audit Logs**:
   ```bash
   curl http://localhost:8000/menu/versions/audit/logs \
     -H "Authorization: Bearer YOUR_JWT_TOKEN"
   ```

#### Frontend Verification

1. **Access Versioning Interface**:
   - Go to `/menu` in your browser
   - Click on the "Versioning" tab
   - Verify you can see the versioning interface

2. **Test Version Creation**:
   - Click "Create Version"
   - Fill out the form
   - Submit and verify version appears in the list

3. **Test Audit Trail**:
   - Click on "Audit Trail" tab
   - Verify audit entries are displayed

#### Database Verification

```sql
-- Check version tables have data
SELECT COUNT(*) FROM menu_versions;
SELECT COUNT(*) FROM menu_audit_logs;

-- Check triggers are working
SELECT 
  schemaname, 
  tablename, 
  schemaname||'.'||tablename as "relation",
  n_tup_ins as "inserts",
  n_tup_upd as "updates",
  n_tup_del as "deletes"
FROM pg_stat_user_tables 
WHERE tablename LIKE 'menu_%'
ORDER BY tablename;
```

## Configuration Options

### Auto-Versioning Configuration

Customize auto-versioning behavior in your application:

```python
# In your application initialization
from backend.core.menu_versioning_triggers import menu_versioning_triggers

# Adjust threshold for auto-versioning
menu_versioning_triggers.auto_version_threshold = 15

# Enable/disable auto-versioning
menu_versioning_triggers.enabled = True
```

### Performance Tuning

#### Database Optimization

```sql
-- Create additional indexes for better performance
CREATE INDEX CONCURRENTLY idx_menu_versions_created_by 
ON menu_versions(created_by) WHERE deleted_at IS NULL;

CREATE INDEX CONCURRENTLY idx_menu_audit_logs_batch 
ON menu_audit_logs(batch_id) WHERE batch_id IS NOT NULL;

-- Optimize for time-based queries
CREATE INDEX CONCURRENTLY idx_menu_audit_logs_created_at_desc 
ON menu_audit_logs(created_at DESC);
```

#### Redis Caching

Configure Redis for optimal caching:

```bash
# Redis configuration (redis.conf)
maxmemory 2gb
maxmemory-policy allkeys-lru
save 900 1
save 300 10
save 60 10000
```

### Security Configuration

#### RBAC Permissions Setup

Ensure proper permissions are configured:

```python
# Required permissions for versioning
VERSIONING_PERMISSIONS = [
    "menu:read",           # View versions and audit logs
    "menu:create",         # Create new versions
    "menu:update",         # Publish and rollback versions
    "menu:delete",         # Delete draft versions
    "menu:manage_versions" # Advanced version management
]
```

#### Audit Log Security

```python
# Configure audit log retention
AUDIT_LOG_CONFIG = {
    "retention_days": 365,
    "archive_after_days": 90,
    "encryption_enabled": False,  # Set to True for sensitive data
    "checksum_validation": True
}
```

## Troubleshooting

### Common Issues

#### 1. Migration Fails

**Problem**: Database migration fails with permission errors.

**Solution**:
```bash
# Ensure database user has proper permissions
GRANT CREATE ON DATABASE auraconnect TO your_user;
GRANT USAGE ON SCHEMA public TO your_user;
GRANT CREATE ON SCHEMA public TO your_user;

# Run migration with verbose output
alembic upgrade head --sql
```

#### 2. Auto-Versioning Not Working

**Problem**: Changes to menu items don't trigger automatic versioning.

**Solutions**:

1. Verify triggers are initialized:
   ```python
   from backend.core.menu_versioning_triggers import get_change_buffer_status
   print(get_change_buffer_status())
   ```

2. Check if auto-versioning is enabled:
   ```python
   from backend.core.menu_versioning_triggers import menu_versioning_triggers
   print(f"Auto-versioning enabled: {menu_versioning_triggers.enabled}")
   ```

3. Monitor change buffer:
   ```bash
   # Check application logs for versioning events
   grep "versioning" logs/application.log
   ```

#### 3. Frontend Components Not Loading

**Problem**: Versioning tab shows empty or error state.

**Solutions**:

1. Check API connectivity:
   ```bash
   curl http://localhost:8000/menu/versions/stats \
     -H "Authorization: Bearer YOUR_TOKEN"
   ```

2. Verify permissions:
   ```javascript
   // In browser console
   console.log(window.localStorage.getItem('userPermissions'));
   ```

3. Check browser console for errors:
   ```javascript
   // Look for CORS, authentication, or API errors
   ```

#### 4. Performance Issues

**Problem**: Version operations are slow.

**Solutions**:

1. **Database Performance**:
   ```sql
   -- Analyze query performance
   EXPLAIN ANALYZE SELECT * FROM menu_versions 
   WHERE deleted_at IS NULL ORDER BY created_at DESC LIMIT 20;
   
   -- Update table statistics
   ANALYZE menu_versions;
   ANALYZE menu_audit_logs;
   ```

2. **Cache Performance**:
   ```bash
   # Check Redis connectivity
   redis-cli ping
   
   # Monitor cache hit rates
   redis-cli info stats | grep hit_rate
   ```

3. **Application Performance**:
   ```python
   # Enable SQL query logging
   import logging
   logging.getLogger('sqlalchemy.engine').setLevel(logging.INFO)
   ```

### Health Checks

Create health check endpoints to monitor system status:

```python
@router.get("/health/versioning")
async def versioning_health_check(db: Session = Depends(get_db)):
    """Health check for versioning system"""
    
    health_status = {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "checks": {}
    }
    
    try:
        # Check database connectivity
        version_count = db.query(MenuVersion).count()
        health_status["checks"]["database"] = {
            "status": "ok",
            "version_count": version_count
        }
        
        # Check auto-versioning system
        buffer_status = get_change_buffer_status()
        health_status["checks"]["auto_versioning"] = {
            "status": "ok" if buffer_status["enabled"] else "disabled",
            "buffer_size": buffer_status["buffer_size"]
        }
        
        # Check Redis connectivity (if configured)
        try:
            # Redis health check logic here
            health_status["checks"]["cache"] = {"status": "ok"}
        except:
            health_status["checks"]["cache"] = {"status": "unavailable"}
            
    except Exception as e:
        health_status["status"] = "unhealthy"
        health_status["error"] = str(e)
    
    return health_status
```

## Maintenance

### Regular Maintenance Tasks

#### 1. Audit Log Cleanup

Create a scheduled task to manage audit log retention:

```python
# scripts/cleanup_audit_logs.py
from datetime import datetime, timedelta
from backend.core.database import get_db
from backend.core.menu_versioning_models import MenuAuditLog

def cleanup_old_audit_logs(retention_days: int = 365):
    """Clean up audit logs older than retention period"""
    
    cutoff_date = datetime.utcnow() - timedelta(days=retention_days)
    
    with get_db() as db:
        deleted_count = db.query(MenuAuditLog).filter(
            MenuAuditLog.created_at < cutoff_date
        ).delete()
        
        db.commit()
        print(f"Cleaned up {deleted_count} old audit log entries")

if __name__ == "__main__":
    cleanup_old_audit_logs()
```

#### 2. Version Cleanup

```python
# scripts/cleanup_old_versions.py
def cleanup_old_versions(keep_count: int = 100):
    """Keep only the most recent versions"""
    
    with get_db() as db:
        # Keep active version and most recent drafts
        versions_to_delete = db.query(MenuVersion).filter(
            MenuVersion.is_active == False,
            MenuVersion.deleted_at == None
        ).order_by(
            MenuVersion.created_at.desc()
        ).offset(keep_count).all()
        
        for version in versions_to_delete:
            version.deleted_at = datetime.utcnow()
        
        db.commit()
        print(f"Marked {len(versions_to_delete)} old versions for deletion")
```

#### 3. Performance Monitoring

Set up monitoring for key metrics:

```bash
# Create monitoring script
#!/bin/bash
# scripts/monitor_versioning.sh

echo "=== Menu Versioning System Status ==="
echo "Date: $(date)"
echo

# Database metrics
echo "Database Metrics:"
psql $DATABASE_URL -c "
SELECT 
    'Total Versions' as metric,
    COUNT(*) as value 
FROM menu_versions WHERE deleted_at IS NULL
UNION ALL
SELECT 
    'Active Versions' as metric,
    COUNT(*) as value 
FROM menu_versions WHERE is_active = true
UNION ALL
SELECT 
    'Audit Log Entries (Last 24h)' as metric,
    COUNT(*) as value 
FROM menu_audit_logs 
WHERE created_at > NOW() - INTERVAL '24 hours';
"

# Application metrics
echo
echo "Application Metrics:"
curl -s http://localhost:8000/health/versioning | python -m json.tool
```

### Backup Strategy

#### Database Backup

```bash
#!/bin/bash
# scripts/backup_versioning_data.sh

BACKUP_DIR="/backups/versioning"
DATE=$(date +%Y%m%d_%H%M%S)

# Create backup directory
mkdir -p $BACKUP_DIR

# Backup versioning tables
pg_dump $DATABASE_URL \
  --table=menu_versions \
  --table=menu_category_versions \
  --table=menu_item_versions \
  --table=modifier_group_versions \
  --table=modifier_versions \
  --table=menu_audit_logs \
  --data-only \
  --compress=9 \
  > $BACKUP_DIR/versioning_data_$DATE.sql.gz

echo "Backup completed: $BACKUP_DIR/versioning_data_$DATE.sql.gz"
```

## Support and Documentation

### Additional Resources

- **API Documentation**: Visit `/docs` endpoint when server is running
- **Database Schema**: Check `backend/alembic/versions/` for migration files
- **Component Documentation**: See JSDoc comments in React components
- **Error Codes**: Reference `backend/core/menu_versioning_service.py` for error handling

### Getting Help

If you encounter issues:

1. Check the troubleshooting section above
2. Review application logs for error messages
3. Verify database and Redis connectivity
4. Ensure all dependencies are properly installed
5. Check that RBAC permissions are correctly configured

### Contributing

When contributing to the versioning system:

1. Run the test suite: `pytest backend/tests/test_menu_versioning_*.py`
2. Update documentation for any API changes
3. Follow the existing code style and patterns
4. Add appropriate error handling and logging
5. Test with different user permission levels

This setup guide should help you get the menu versioning system up and running in your environment. The system is designed to be robust and scalable, but proper configuration and maintenance are essential for optimal performance.