# backend/core/cache.py

"""
Simple in-memory cache service for analytics.

In production, this should be replaced with Redis or similar.
"""

from typing import Optional, Any
from datetime import datetime, timedelta
import json
import logging

logger = logging.getLogger(__name__)


class CacheService:
    """Simple in-memory cache implementation"""
    
    def __init__(self):
        self._cache = {}
        self._expiry = {}
    
    async def get(self, key: str) -> Optional[str]:
        """Get value from cache"""
        # Check if key exists and not expired
        if key in self._cache:
            if key in self._expiry:
                if datetime.utcnow() > self._expiry[key]:
                    # Expired, remove it
                    del self._cache[key]
                    del self._expiry[key]
                    return None
            return self._cache[key]
        return None
    
    async def set(self, key: str, value: str, ttl: int = 300) -> None:
        """Set value in cache with TTL in seconds"""
        self._cache[key] = value
        self._expiry[key] = datetime.utcnow() + timedelta(seconds=ttl)
        
        # Log cache operation
        logger.debug(f"Cached key: {key} with TTL: {ttl}s")
    
    async def delete(self, key: str) -> None:
        """Delete key from cache"""
        if key in self._cache:
            del self._cache[key]
        if key in self._expiry:
            del self._expiry[key]
    
    async def delete_pattern(self, pattern: str) -> None:
        """Delete all keys matching pattern"""
        # Simple pattern matching (just prefix for now)
        if pattern.endswith("*"):
            prefix = pattern[:-1]
            keys_to_delete = [k for k in self._cache.keys() if k.startswith(prefix)]
        else:
            keys_to_delete = [k for k in self._cache.keys() if pattern in k]
        
        for key in keys_to_delete:
            await self.delete(key)
        
        logger.debug(f"Deleted {len(keys_to_delete)} keys matching pattern: {pattern}")
    
    def clear(self) -> None:
        """Clear entire cache"""
        self._cache.clear()
        self._expiry.clear()


# Global cache instance
cache_service = CacheService()