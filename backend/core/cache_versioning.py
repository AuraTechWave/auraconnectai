"""
Cache key versioning for backward compatibility.

Provides versioned cache keys to handle schema changes
and data format evolution without cache invalidation storms.
"""

import json
import logging
import asyncio
from typing import Any, Optional, Dict, Callable, Type, List, Tuple
from datetime import datetime
from functools import wraps
from abc import ABC, abstractmethod
from enum import Enum

logger = logging.getLogger(__name__)


class CacheVersion(Enum):
    """Cache schema versions."""
    V1 = "v1"  # Initial version
    V2 = "v2"  # Added compression
    V3 = "v3"  # Changed data structure
    # Add new versions as needed


class CacheDataMigrator(ABC):
    """Base class for cache data migration."""
    
    @abstractmethod
    def migrate_up(self, data: Any) -> Any:
        """Migrate data from previous version to current version."""
        pass
    
    @abstractmethod
    def migrate_down(self, data: Any) -> Any:
        """Migrate data from current version to previous version."""
        pass


class V1ToV2Migrator(CacheDataMigrator):
    """Example migrator from V1 to V2."""
    
    def migrate_up(self, data: Any) -> Any:
        """V1 to V2 migration."""
        if isinstance(data, dict):
            # Example: Add new field with default value
            data["_format_version"] = 2
            return data
        return data
    
    def migrate_down(self, data: Any) -> Any:
        """V2 to V1 migration."""
        if isinstance(data, dict):
            # Remove V2-specific fields
            data.pop("_format_version", None)
            return data
        return data


class VersionedCacheKey:
    """Manages versioned cache keys."""
    
    def __init__(
        self,
        base_key: str,
        version: CacheVersion = CacheVersion.V2,
        namespace: Optional[str] = None
    ):
        self.base_key = base_key
        self.version = version
        self.namespace = namespace
    
    def get_versioned_key(self, version: Optional[CacheVersion] = None) -> str:
        """Get cache key for specific version."""
        ver = version or self.version
        parts = []
        
        if self.namespace:
            parts.append(self.namespace)
        
        parts.extend([ver.value, self.base_key])
        
        return ":".join(parts)
    
    def get_all_version_keys(self) -> Dict[CacheVersion, str]:
        """Get keys for all versions."""
        return {
            version: self.get_versioned_key(version)
            for version in CacheVersion
        }


class CacheVersionManager:
    """Manages cache versions and migrations."""
    
    def __init__(self, current_version: CacheVersion = CacheVersion.V2):
        self.current_version = current_version
        self.migrators: Dict[tuple[CacheVersion, CacheVersion], CacheDataMigrator] = {
            (CacheVersion.V1, CacheVersion.V2): V1ToV2Migrator(),
            # Add more migrators as needed
        }
    
    def migrate_data(
        self,
        data: Any,
        from_version: CacheVersion,
        to_version: CacheVersion
    ) -> Any:
        """Migrate data between versions."""
        if from_version == to_version:
            return data
        
        # Find migration path
        migrator_key = (from_version, to_version)
        reverse_key = (to_version, from_version)
        
        if migrator_key in self.migrators:
            return self.migrators[migrator_key].migrate_up(data)
        elif reverse_key in self.migrators:
            return self.migrators[reverse_key].migrate_down(data)
        else:
            logger.warning(
                f"No migrator found for {from_version.value} -> {to_version.value}"
            )
            return data
    
    def wrap_with_version(self, data: Any, version: Optional[CacheVersion] = None) -> Dict[str, Any]:
        """Wrap data with version metadata."""
        return {
            "_cache_version": (version or self.current_version).value,
            "_cached_at": datetime.utcnow().isoformat(),
            "data": data
        }
    
    def unwrap_versioned_data(self, wrapped_data: Dict[str, Any]) -> tuple[Any, CacheVersion]:
        """Unwrap versioned data and return data with its version."""
        if not isinstance(wrapped_data, dict) or "_cache_version" not in wrapped_data:
            # Assume it's V1 (unversioned) data
            return wrapped_data, CacheVersion.V1
        
        version_str = wrapped_data.get("_cache_version", CacheVersion.V1.value)
        try:
            version = CacheVersion(version_str)
        except ValueError:
            logger.warning(f"Unknown cache version: {version_str}")
            version = CacheVersion.V1
        
        return wrapped_data.get("data"), version


class VersionedCache:
    """Cache service with version support."""
    
    def __init__(
        self,
        cache_service,
        version_manager: CacheVersionManager,
        fallback_versions: Optional[List[CacheVersion]] = None
    ):
        self.cache = cache_service
        self.version_manager = version_manager
        self.fallback_versions = fallback_versions or [CacheVersion.V1]
    
    async def get(
        self,
        key: str,
        namespace: Optional[str] = None,
        version: Optional[CacheVersion] = None
    ) -> Any:
        """Get value with version support and fallback."""
        versioned_key = VersionedCacheKey(key, version or self.version_manager.current_version, namespace)
        
        # Try current version first
        wrapped_data = await self.cache.get(versioned_key.get_versioned_key())
        
        if wrapped_data is not None:
            data, data_version = self.version_manager.unwrap_versioned_data(wrapped_data)
            
            # Migrate if needed
            if data_version != self.version_manager.current_version:
                data = self.version_manager.migrate_data(
                    data,
                    data_version,
                    self.version_manager.current_version
                )
            
            return data
        
        # Try fallback versions
        for fallback_version in self.fallback_versions:
            fallback_key = versioned_key.get_versioned_key(fallback_version)
            wrapped_data = await self.cache.get(fallback_key)
            
            if wrapped_data is not None:
                data, data_version = self.version_manager.unwrap_versioned_data(wrapped_data)
                
                # Migrate to current version
                migrated_data = self.version_manager.migrate_data(
                    data,
                    data_version,
                    self.version_manager.current_version
                )
                
                # Cache in current version for next time
                await self.set(key, migrated_data, namespace=namespace)
                
                return migrated_data
        
        return None
    
    async def set(
        self,
        key: str,
        value: Any,
        ttl: Optional[int] = None,
        namespace: Optional[str] = None,
        version: Optional[CacheVersion] = None
    ) -> bool:
        """Set value with version metadata."""
        version = version or self.version_manager.current_version
        versioned_key = VersionedCacheKey(key, version, namespace)
        
        # Wrap data with version
        wrapped_data = self.version_manager.wrap_with_version(value, version)
        
        return await self.cache.set(
            versioned_key.get_versioned_key(),
            wrapped_data,
            ttl=ttl
        )
    
    async def invalidate_all_versions(
        self,
        key: str,
        namespace: Optional[str] = None
    ) -> int:
        """Invalidate all versions of a key."""
        versioned_key = VersionedCacheKey(key, self.version_manager.current_version, namespace)
        all_keys = versioned_key.get_all_version_keys()
        
        deleted = 0
        for version, key in all_keys.items():
            if await self.cache.delete(key):
                deleted += 1
        
        return deleted


def versioned_cache(
    version: Optional[CacheVersion] = None,
    namespace: Optional[str] = None,
    ttl: Optional[int] = None,
    fallback_versions: Optional[List[CacheVersion]] = None
):
    """
    Decorator for versioned caching.
    
    Example:
        @versioned_cache(version=CacheVersion.V2, fallback_versions=[CacheVersion.V1])
        async def get_user_profile(user_id: int):
            # Fetch from database
            return profile
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            # Use enhanced cache with versioning
            from .enhanced_redis_cache import enhanced_cache
            
            version_manager = CacheVersionManager(version or CacheVersion.V2)
            v_cache = VersionedCache(
                enhanced_cache,
                version_manager,
                fallback_versions
            )
            
            # Generate cache key
            key_parts = [func.__name__]
            key_parts.extend(str(arg) for arg in args)
            key_parts.extend(f"{k}={v}" for k, v in sorted(kwargs.items()))
            cache_key = ":".join(key_parts)
            
            # Check cache
            cached_value = await v_cache.get(cache_key, namespace)
            if cached_value is not None:
                return cached_value
            
            # Compute value
            result = await func(*args, **kwargs)
            
            # Cache with version
            await v_cache.set(cache_key, result, ttl=ttl, namespace=namespace)
            
            return result
        
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        else:
            return func
    
    return decorator


# Global version manager
cache_version_manager = CacheVersionManager(CacheVersion.V2)


# Export public interface
__all__ = [
    "CacheVersion",
    "VersionedCacheKey",
    "CacheVersionManager",
    "VersionedCache",
    "versioned_cache",
    "cache_version_manager",
    "CacheDataMigrator"
]