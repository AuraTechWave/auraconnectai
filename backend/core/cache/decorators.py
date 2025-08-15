"""
Caching Decorators

Decorators for automatic caching of function results.
"""

import functools
import hashlib
import json
import logging
from typing import Optional, Callable, Any, Union, List, Dict
from inspect import signature

from .cache_manager import cache_manager, CacheTTL

logger = logging.getLogger(__name__)


def generate_cache_key(func: Callable, *args, **kwargs) -> str:
    """
    Generate cache key from function and arguments
    
    Args:
        func: Function being cached
        *args: Function arguments
        **kwargs: Function keyword arguments
        
    Returns:
        Generated cache key
    """
    # Get function signature
    func_name = f"{func.__module__}.{func.__name__}"
    
    # Create key components
    key_parts = [func_name]
    
    # Add positional arguments
    for arg in args:
        if hasattr(arg, 'id'):
            # For ORM objects, use their ID
            key_parts.append(f"id:{arg.id}")
        elif isinstance(arg, (str, int, float, bool)):
            key_parts.append(str(arg))
        elif arg is None:
            key_parts.append("None")
        else:
            # For complex objects, use hash
            key_parts.append(hashlib.md5(str(arg).encode()).hexdigest()[:8])
    
    # Add keyword arguments (sorted for consistency)
    for k, v in sorted(kwargs.items()):
        if v is not None:
            if hasattr(v, 'id'):
                key_parts.append(f"{k}:id:{v.id}")
            elif isinstance(v, (str, int, float, bool)):
                key_parts.append(f"{k}:{v}")
            else:
                key_parts.append(f"{k}:{hashlib.md5(str(v).encode()).hexdigest()[:8]}")
    
    return ":".join(key_parts)


def cache(
    cache_type: str = "api",
    ttl: Optional[Union[int, CacheTTL]] = None,
    key_func: Optional[Callable] = None,
    tenant_aware: bool = False,
    user_aware: bool = False,
    invalidate_on: Optional[List[str]] = None
):
    """
    Cache decorator for function results
    
    Args:
        cache_type: Type of cache to use
        ttl: Time to live (seconds or CacheTTL enum)
        key_func: Custom key generation function
        tenant_aware: Include tenant_id in cache key
        user_aware: Include user_id in cache key
        invalidate_on: List of events that invalidate this cache
        
    Example:
        @cache(cache_type="menu", ttl=CacheTTL.MENU_ITEMS)
        def get_menu_items(restaurant_id: int):
            return db.query(MenuItem).filter_by(restaurant_id=restaurant_id).all()
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            # Extract tenant_id and user_id if needed
            tenant_id = None
            user_id = None
            
            if tenant_aware:
                # Try to get tenant_id from various sources
                # Check kwargs first (explicitly check for None to allow 0 as valid ID)
                if 'tenant_id' in kwargs:
                    tenant_id = kwargs['tenant_id']
                elif 'restaurant_id' in kwargs:
                    tenant_id = kwargs['restaurant_id']
                elif tenant_id is None and args:
                    # Check if first arg has tenant_id
                    if hasattr(args[0], 'tenant_id'):
                        tenant_id = args[0].tenant_id
                    elif hasattr(args[0], 'restaurant_id'):
                        tenant_id = args[0].restaurant_id
            
            if user_aware:
                # Try to get user_id from various sources
                # Check kwargs first (explicitly check for None to allow 0 as valid ID)
                if 'user_id' in kwargs:
                    user_id = kwargs['user_id']
                elif user_id is None and args:
                    # Check if first arg has user_id
                    if hasattr(args[0], 'user_id'):
                        user_id = args[0].user_id
                    elif hasattr(args[0], 'id') and hasattr(args[0], '__tablename__'):
                        if args[0].__tablename__ == 'users':
                            user_id = args[0].id
            
            # Generate cache key
            if key_func:
                cache_key = key_func(*args, **kwargs)
            else:
                base_key = generate_cache_key(func, *args, **kwargs)
                cache_key = cache_manager.generate_key(
                    cache_type,
                    base_key,
                    tenant_id=tenant_id,
                    user_id=user_id
                )
            
            # Determine TTL
            cache_ttl = None
            if isinstance(ttl, CacheTTL):
                cache_ttl = ttl.value
            elif isinstance(ttl, int):
                cache_ttl = ttl
            
            # Try to get from cache with fetch function
            result = cache_manager.get(
                cache_type,
                cache_key,
                fetch_func=lambda: func(*args, **kwargs),
                ttl=cache_ttl
            )
            
            return result
        
        # Add cache control methods
        wrapper.invalidate = lambda *args, **kwargs: _invalidate_cache(
            func, cache_type, *args, **kwargs
        )
        wrapper.refresh = lambda *args, **kwargs: _refresh_cache(
            func, cache_type, ttl, *args, **kwargs
        )
        
        # Store invalidation events for potential use by cache invalidation system
        if invalidate_on:
            wrapper._invalidate_on = invalidate_on
            wrapper._cache_type = cache_type
            # Register with a global invalidation registry if needed
            _register_invalidation_events(func, cache_type, invalidate_on)
        
        return wrapper
    return decorator


def cache_menu(ttl: Optional[int] = None):
    """Cache decorator specifically for menu data"""
    return cache(
        cache_type="menu",
        ttl=ttl or CacheTTL.MENU_ITEMS,
        tenant_aware=True
    )


def cache_permissions(ttl: Optional[int] = None):
    """Cache decorator specifically for user permissions"""
    return cache(
        cache_type="permissions",
        ttl=ttl or CacheTTL.USER_PERMISSIONS,
        user_aware=True
    )


def cache_settings(ttl: Optional[int] = None):
    """Cache decorator specifically for restaurant settings"""
    return cache(
        cache_type="settings",
        ttl=ttl or CacheTTL.RESTAURANT_SETTINGS,
        tenant_aware=True
    )


def cache_analytics(ttl: Optional[int] = None):
    """Cache decorator specifically for analytics data"""
    return cache(
        cache_type="analytics",
        ttl=ttl or CacheTTL.ANALYTICS_AGGREGATIONS,
        tenant_aware=True
    )


def cache_api_response(ttl: int = 60):
    """Cache decorator for API responses"""
    return cache(
        cache_type="api",
        ttl=ttl,
        tenant_aware=True
    )


def cache_search_results(ttl: int = 180):
    """Cache decorator for search results"""
    return cache(
        cache_type="search",
        ttl=ttl,
        tenant_aware=True
    )


def cache_report(ttl: int = 900):
    """Cache decorator for report data"""
    return cache(
        cache_type="report",
        ttl=ttl,
        tenant_aware=True
    )


def cache_aside(*args, **kwargs):
    """
    Cache-aside pattern decorator
    
    This decorator implements read-through caching where:
    1. Check cache first
    2. If miss, fetch from source
    3. Update cache
    4. Return result
    """
    return cache(*args, **kwargs)


def cache_through(
    cache_type: str = "api",
    ttl: Optional[Union[int, CacheTTL]] = None
):
    """
    Cache-through pattern decorator
    
    This decorator implements write-through caching where:
    1. Write to cache
    2. Write to source
    3. Return result
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            # Execute function
            result = func(*args, **kwargs)
            
            # Generate cache key
            cache_key = generate_cache_key(func, *args, **kwargs)
            
            # Determine TTL
            cache_ttl = None
            if isinstance(ttl, CacheTTL):
                cache_ttl = ttl.value
            elif isinstance(ttl, int):
                cache_ttl = ttl
            
            # Write to cache
            cache_manager.set(cache_type, cache_key, result, cache_ttl)
            
            return result
        
        return wrapper
    return decorator


def invalidate_cache(cache_types: Union[str, List[str]], pattern: Optional[str] = None):
    """
    Decorator to invalidate cache after function execution
    
    Args:
        cache_types: Cache type(s) to invalidate
        pattern: Optional pattern for invalidation
        
    Example:
        @invalidate_cache("menu")
        def update_menu_item(item_id: int, data: dict):
            # Update menu item
            return updated_item
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            # Execute function
            result = func(*args, **kwargs)
            
            # Invalidate cache(s)
            types_to_invalidate = cache_types if isinstance(cache_types, list) else [cache_types]
            
            for cache_type in types_to_invalidate:
                if pattern:
                    cache_manager.invalidate_pattern(cache_type, pattern)
                else:
                    # Try to extract tenant_id for pattern
                    # Check explicitly for keys to allow 0 as valid ID
                    tenant_id = None
                    if 'tenant_id' in kwargs:
                        tenant_id = kwargs['tenant_id']
                    elif 'restaurant_id' in kwargs:
                        tenant_id = kwargs['restaurant_id']
                    
                    if tenant_id is not None:
                        cache_manager.invalidate_pattern(cache_type, f"*t{tenant_id}*")
                    else:
                        logger.warning(f"No pattern specified for cache invalidation of {cache_type}")
            
            return result
        
        return wrapper
    return decorator


def _invalidate_cache(func: Callable, cache_type: str, *args, **kwargs):
    """Helper to invalidate cache for a specific function call"""
    cache_key = generate_cache_key(func, *args, **kwargs)
    return cache_manager.delete(cache_type, cache_key)


def _refresh_cache(func: Callable, cache_type: str, ttl: Optional[Union[int, CacheTTL]], *args, **kwargs):
    """Helper to refresh cache for a specific function call"""
    # Generate cache key
    cache_key = generate_cache_key(func, *args, **kwargs)
    
    # Determine TTL
    cache_ttl = None
    if isinstance(ttl, CacheTTL):
        cache_ttl = ttl.value
    elif isinstance(ttl, int):
        cache_ttl = ttl
    
    # Force refresh
    return cache_manager.get(
        cache_type,
        cache_key,
        fetch_func=lambda: func(*args, **kwargs),
        ttl=cache_ttl,
        force_refresh=True
    )


# Global registry for invalidation events
_invalidation_registry: Dict[str, List[Callable]] = {}


def _register_invalidation_events(func: Callable, cache_type: str, events: List[str]):
    """
    Register function for cache invalidation on specific events
    
    Args:
        func: Function to register
        cache_type: Cache type
        events: List of event names that should trigger invalidation
    """
    for event in events:
        if event not in _invalidation_registry:
            _invalidation_registry[event] = []
        _invalidation_registry[event].append((func, cache_type))
    
    logger.debug(f"Registered {func.__name__} for invalidation on events: {events}")


def trigger_cache_invalidation(event: str, *args, **kwargs):
    """
    Trigger cache invalidation for all functions registered to an event
    
    Args:
        event: Event name
        *args, **kwargs: Arguments to pass to invalidation
    """
    if event in _invalidation_registry:
        for func, cache_type in _invalidation_registry[event]:
            try:
                cache_key = generate_cache_key(func, *args, **kwargs)
                cache_manager.delete(cache_type, cache_key)
                logger.info(f"Invalidated cache for {func.__name__} on event {event}")
            except Exception as e:
                logger.error(f"Failed to invalidate cache for {func.__name__}: {e}")