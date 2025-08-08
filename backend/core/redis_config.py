# backend/core/redis_config.py

"""
Redis configuration and connection management.
Provides singleton Redis client for caching and background tasks.
"""

import os
from typing import Optional, Dict, Any
import redis
from redis import Redis
import logging

from core.config import settings

logger = logging.getLogger(__name__)


class RedisConfig:
    """Redis connection configuration"""
    
    def __init__(self):
        self.url = settings.redis_url or os.getenv("REDIS_URL", "redis://localhost:6379/0")
        self.max_connections = int(os.getenv("REDIS_MAX_CONNECTIONS", "10"))
        self.decode_responses = True
        self.socket_timeout = 5
        self.socket_connect_timeout = 5
        self.health_check_interval = 30
        

_redis_client: Optional[Redis] = None
_connection_pool: Optional[redis.ConnectionPool] = None


def get_redis_client() -> Optional[Redis]:
    """
    Get or create Redis client singleton.
    
    Returns None if Redis is not available.
    """
    global _redis_client, _connection_pool
    
    if _redis_client is not None:
        try:
            # Check if connection is still alive
            _redis_client.ping()
            return _redis_client
        except Exception:
            # Connection lost, recreate
            _redis_client = None
            _connection_pool = None
    
    try:
        config = RedisConfig()
        
        # Create connection pool
        _connection_pool = redis.ConnectionPool.from_url(
            config.url,
            max_connections=config.max_connections,
            decode_responses=config.decode_responses,
            socket_timeout=config.socket_timeout,
            socket_connect_timeout=config.socket_connect_timeout,
            health_check_interval=config.health_check_interval
        )
        
        # Create client
        _redis_client = Redis(connection_pool=_connection_pool)
        
        # Test connection
        _redis_client.ping()
        
        logger.info("Redis connection established")
        return _redis_client
        
    except Exception as e:
        logger.warning(f"Redis connection failed: {e}. Falling back to local cache.")
        return None


def close_redis_connection():
    """Close Redis connection and cleanup"""
    global _redis_client, _connection_pool
    
    if _redis_client:
        try:
            _redis_client.close()
        except Exception as e:
            logger.error(f"Error closing Redis client: {e}")
        finally:
            _redis_client = None
    
    if _connection_pool:
        try:
            _connection_pool.disconnect()
        except Exception as e:
            logger.error(f"Error disconnecting Redis pool: {e}")
        finally:
            _connection_pool = None


# Health check function
async def redis_health_check() -> Dict[str, Any]:
    """Check Redis connection health"""
    client = get_redis_client()
    
    if not client:
        return {
            "status": "unavailable",
            "message": "Redis connection not available"
        }
    
    try:
        # Ping Redis
        client.ping()
        
        # Get info
        info = client.info()
        
        return {
            "status": "healthy",
            "message": "Redis connection healthy",
            "details": {
                "version": info.get("redis_version"),
                "connected_clients": info.get("connected_clients"),
                "used_memory_human": info.get("used_memory_human"),
                "uptime_in_days": info.get("uptime_in_days")
            }
        }
    except Exception as e:
        return {
            "status": "unhealthy",
            "message": f"Redis health check failed: {str(e)}"
        }