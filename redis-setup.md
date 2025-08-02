# Redis Setup for AuraConnect

## Installation Complete ✅

Redis is now installed and running on your system:
- **Version**: 8.0.3
- **Port**: 6379 (default)
- **Status**: Running as a service

## Redis Management Commands

### Start/Stop Redis
```bash
# Start Redis (already running)
brew services start redis

# Stop Redis
brew services stop redis

# Restart Redis
brew services restart redis

# Check Redis status
brew services list | grep redis
```

### Connect to Redis
```bash
# Open Redis CLI
redis-cli

# Test connection
redis-cli ping

# Monitor Redis in real-time
redis-cli monitor

# Check all keys
redis-cli keys "*"

# Check session keys
redis-cli keys "session:*"
redis-cli keys "blacklist:*"
```

## Backend Configuration

The backend will automatically detect and use Redis for:
- Session management
- Token blacklisting
- Caching

Default connection: `redis://localhost:6379`

## Benefits with Redis

1. **Persistent Sessions**: Sessions survive backend restarts
2. **Token Blacklisting**: Proper logout functionality
3. **Multi-instance Support**: Can run multiple backend instances
4. **Performance**: Faster session lookups
5. **Session Expiry**: Automatic cleanup of expired sessions

## Testing Redis Integration

After restarting the backend, you'll see:
- No more "Failed to connect to Redis" warnings
- Session count will be accurate
- Logout functionality will work properly
- Sessions persist across backend restarts