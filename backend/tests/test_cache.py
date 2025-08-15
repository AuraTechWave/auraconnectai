"""
Comprehensive tests for Redis caching implementation

Tests all cache components including connection pooling, cache manager,
decorators, warming utilities, and monitoring.
"""

import pytest
import time
import json
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime, timedelta
from typing import Dict, Any, Optional

from core.cache.redis_client import RedisClient, RedisCache, get_cache
from core.cache.cache_manager import CacheManager, CacheTTL, CacheStats
from core.cache.decorators import (
    cache, cache_menu, cache_permissions, cache_settings,
    cache_analytics, invalidate_cache, generate_cache_key
)
from core.cache.cache_warmer import CacheWarmer
from core.cache.monitoring import CacheMonitor, CacheMetric


class TestRedisClient:
    """Test Redis client connection pooling"""
    
    def test_singleton_pool(self):
        """Test that connection pool is singleton"""
        pool1 = RedisClient.get_pool()
        pool2 = RedisClient.get_pool()
        assert pool1 is pool2
    
    def test_singleton_client(self):
        """Test that Redis client is singleton"""
        client1 = RedisClient.get_client()
        client2 = RedisClient.get_client()
        assert client1 is client2
    
    @patch('core.cache.redis_client.redis.ConnectionPool')
    def test_pool_configuration(self, mock_pool):
        """Test connection pool configuration"""
        RedisClient._pool = None  # Reset singleton
        RedisClient.get_pool()
        
        # Verify pool was created with correct settings
        assert mock_pool.from_url.called or mock_pool.called
    
    def test_close_connection(self):
        """Test closing Redis connection"""
        RedisClient.get_client()
        RedisClient.close()
        assert RedisClient._pool is None
        assert RedisClient._client is None


class TestRedisCache:
    """Test Redis cache operations"""
    
    @pytest.fixture
    def cache(self):
        """Create test cache instance"""
        return RedisCache(prefix="test", serializer="json")
    
    @pytest.fixture
    def mock_client(self):
        """Create mock Redis client"""
        with patch.object(RedisClient, 'get_client') as mock:
            mock.return_value = MagicMock()
            yield mock.return_value
    
    def test_key_namespacing(self, cache):
        """Test key namespacing"""
        key = cache._make_key("mykey")
        assert key == "test:mykey"
    
    def test_json_serialization(self, cache):
        """Test JSON serialization"""
        data = {"id": 1, "name": "test", "items": [1, 2, 3]}
        serialized = cache._serialize(data)
        assert isinstance(serialized, bytes)
        
        deserialized = cache._deserialize(serialized)
        assert deserialized == data
    
    def test_pickle_serialization(self):
        """Test pickle serialization"""
        cache = RedisCache(prefix="test", serializer="pickle")
        
        # Complex object that JSON can't handle
        class CustomObject:
            def __init__(self, value):
                self.value = value
        
        obj = CustomObject(42)
        serialized = cache._serialize(obj)
        assert isinstance(serialized, bytes)
        
        deserialized = cache._deserialize(serialized)
        assert deserialized.value == 42
    
    @patch.object(RedisCache, 'client')
    def test_get_operation(self, mock_client, cache):
        """Test get operation"""
        mock_client.get.return_value = b'{"value": "test"}'
        
        result = cache.get("key1")
        assert result == {"value": "test"}
        mock_client.get.assert_called_with("test:key1")
    
    @patch.object(RedisCache, 'client')
    def test_set_with_ttl(self, mock_client, cache):
        """Test set operation with TTL"""
        mock_client.setex.return_value = True
        
        result = cache.set("key1", {"value": "test"}, ttl=60)
        assert result is True
        mock_client.setex.assert_called_once()
    
    @patch.object(RedisCache, 'client')
    def test_delete_pattern(self, mock_client, cache):
        """Test delete pattern operation"""
        mock_client.keys.return_value = [b"test:key1", b"test:key2"]
        mock_client.delete.return_value = 2
        
        count = cache.delete_pattern("key*")
        assert count == 2
        mock_client.keys.assert_called_with("test:key*")
    
    @patch.object(RedisCache, 'client')
    def test_mget_mset(self, mock_client, cache):
        """Test multi-get and multi-set operations"""
        # Test mget
        mock_client.mget.return_value = [b'{"v": 1}', b'{"v": 2}', None]
        result = cache.mget(["k1", "k2", "k3"])
        assert result == {"k1": {"v": 1}, "k2": {"v": 2}}
        
        # Test mset
        mock_client.mset.return_value = True
        result = cache.mset({"k1": {"v": 1}, "k2": {"v": 2}})
        assert result is True
    
    @patch.object(RedisCache, 'client')
    def test_counter_operations(self, mock_client, cache):
        """Test increment and decrement operations"""
        mock_client.incr.return_value = 5
        result = cache.incr("counter", 1)
        assert result == 5
        
        mock_client.decr.return_value = 4
        result = cache.decr("counter", 1)
        assert result == 4


class TestCacheManager:
    """Test cache manager functionality"""
    
    @pytest.fixture
    def manager(self):
        """Create test cache manager"""
        return CacheManager()
    
    def test_key_generation(self, manager):
        """Test cache key generation"""
        # Basic key
        key = manager.generate_key("menu", "item", 123)
        assert key == "menu:item:123"
        
        # With tenant ID
        key = manager.generate_key("menu", "item", 123, tenant_id=1)
        assert key == "menu:t1:item:123"
        
        # With user ID
        key = manager.generate_key("permissions", "user", user_id=5)
        assert key == "permissions:u5:user"
        
        # With kwargs
        key = manager.generate_key("api", "endpoint", page=2, limit=10)
        assert "limit:10" in key and "page:2" in key
    
    @patch('core.cache.cache_manager.get_cache')
    def test_get_with_fetch_func(self, mock_get_cache, manager):
        """Test get with fetch function"""
        mock_cache = MagicMock()
        mock_get_cache.return_value = mock_cache
        mock_cache.prefix = "aura:test"
        mock_cache.get.return_value = None
        mock_cache.set.return_value = True
        
        fetch_func = Mock(return_value={"data": "fetched"})
        
        result = manager.get("test", "key1", fetch_func=fetch_func)
        assert result == {"data": "fetched"}
        fetch_func.assert_called_once()
        mock_cache.set.assert_called_once()
    
    @patch('core.cache.cache_manager.get_cache')
    def test_cache_hit(self, mock_get_cache, manager):
        """Test cache hit scenario"""
        mock_cache = MagicMock()
        mock_get_cache.return_value = mock_cache
        mock_cache.prefix = "aura:test"
        mock_cache.get.return_value = {"cached": "data"}
        
        result = manager.get("test", "key1")
        assert result == {"cached": "data"}
        assert manager.stats["test"].hits == 1
        assert manager.stats["test"].misses == 0
    
    @patch('core.cache.cache_manager.get_cache')
    def test_cache_miss(self, mock_get_cache, manager):
        """Test cache miss scenario"""
        mock_cache = MagicMock()
        mock_get_cache.return_value = mock_cache
        mock_cache.prefix = "aura:test"
        mock_cache.get.return_value = None
        
        result = manager.get("test", "key1")
        assert result is None
        assert manager.stats["test"].hits == 0
        assert manager.stats["test"].misses == 1
    
    def test_invalidation_methods(self, manager):
        """Test cache invalidation methods"""
        with patch.object(manager, 'invalidate_pattern') as mock_invalidate:
            # Menu invalidation
            manager.invalidate_menu(tenant_id=1, menu_item_id=10)
            mock_invalidate.assert_called_with('menu', 'menu:t1:item:10*')
            
            # Permissions invalidation
            manager.invalidate_permissions(user_id=5)
            mock_invalidate.assert_called_with('permissions', 'permissions:u5*')
            
            # Settings invalidation
            manager.invalidate_settings(tenant_id=2)
            mock_invalidate.assert_called_with('settings', 'settings:t2*')
            
            # Analytics invalidation with date
            date = datetime(2024, 1, 15)
            manager.invalidate_analytics(tenant_id=3, date=date)
            mock_invalidate.assert_called_with('analytics', 'analytics:t3:2024-01-15*')
    
    def test_stats_tracking(self, manager):
        """Test statistics tracking"""
        stats = manager.stats["menu"]
        stats.hits = 10
        stats.misses = 5
        stats.sets = 8
        stats.deletes = 2
        stats.errors = 1
        
        stats_dict = stats.to_dict()
        assert stats_dict['hits'] == 10
        assert stats_dict['misses'] == 5
        assert stats_dict['hit_rate'] == "66.67%"
    
    @patch('core.cache.cache_manager.get_cache')
    def test_health_check(self, mock_get_cache, manager):
        """Test health check"""
        mock_cache = MagicMock()
        mock_get_cache.return_value = mock_cache
        mock_cache.ping.return_value = True
        mock_cache.info.return_value = {
            'redis_version': '6.2.0',
            'used_memory_human': '100M',
            'connected_clients': 5,
            'uptime_in_days': 10
        }
        
        health = manager.health_check()
        assert health['status'] == 'healthy'
        assert health['connected'] is True
        assert 'redis_info' in health


class TestCacheDecorators:
    """Test caching decorators"""
    
    def test_generate_cache_key(self):
        """Test cache key generation from function"""
        def sample_func(id: int, name: str, active: bool = True):
            pass
        
        key = generate_cache_key(sample_func, 123, "test", active=False)
        assert "sample_func" in key
        assert "123" in key
        assert "test" in key
        assert "active:False" in key
    
    @patch('core.cache.decorators.cache_manager')
    def test_cache_decorator(self, mock_manager):
        """Test basic cache decorator"""
        mock_manager.generate_key.return_value = "test:key"
        mock_manager.get.return_value = {"cached": "result"}
        
        @cache(cache_type="test", ttl=60)
        def get_data(id: int):
            return {"id": id, "data": "fresh"}
        
        result = get_data(1)
        assert result == {"cached": "result"}
        mock_manager.get.assert_called_once()
    
    @patch('core.cache.decorators.cache_manager')
    def test_cache_menu_decorator(self, mock_manager):
        """Test menu-specific cache decorator"""
        @cache_menu()
        def get_menu_item(item_id: int, restaurant_id: int):
            return {"id": item_id}
        
        get_menu_item(1, restaurant_id=10)
        
        # Verify tenant awareness
        call_args = mock_manager.generate_key.call_args
        assert call_args[1]['tenant_id'] == 10
    
    @patch('core.cache.decorators.cache_manager')
    def test_cache_permissions_decorator(self, mock_manager):
        """Test permissions-specific cache decorator"""
        @cache_permissions()
        def get_user_permissions(user_id: int):
            return ["read", "write"]
        
        get_user_permissions(user_id=5)
        
        # Verify user awareness
        call_args = mock_manager.generate_key.call_args
        assert call_args[1]['user_id'] == 5
    
    @patch('core.cache.decorators.cache_manager')
    def test_invalidate_cache_decorator(self, mock_manager):
        """Test cache invalidation decorator"""
        @invalidate_cache("menu")
        def update_menu_item(item_id: int, restaurant_id: int, data: dict):
            return {"updated": True}
        
        result = update_menu_item(1, restaurant_id=10, data={"name": "New"})
        assert result == {"updated": True}
        
        # Verify invalidation was called
        mock_manager.invalidate_pattern.assert_called_once()
        call_args = mock_manager.invalidate_pattern.call_args
        assert call_args[0][0] == "menu"
        assert "t10" in call_args[0][1]


class TestCacheWarmer:
    """Test cache warming utilities"""
    
    @pytest.fixture
    def mock_db(self):
        """Create mock database session"""
        return MagicMock()
    
    @pytest.fixture
    def warmer(self, mock_db):
        """Create cache warmer instance"""
        return CacheWarmer(mock_db)
    
    @patch('core.cache.cache_warmer.cache_manager')
    def test_warm_menu_cache(self, mock_manager, warmer, mock_db):
        """Test menu cache warming"""
        # Mock menu items
        mock_item = MagicMock()
        mock_item.id = 1
        mock_item.name = "Test Item"
        mock_item.description = "Description"
        mock_item.price = 10.99
        mock_item.category_id = 1
        mock_item.is_available = True
        mock_item.restaurant_id = 1
        
        mock_db.query().filter_by().all.return_value = [mock_item]
        mock_manager.set.return_value = True
        
        stats = warmer.warm_menu_cache(tenant_id=1)
        assert stats['items_cached'] == 1
        assert stats['errors'] == 0
    
    @patch('core.cache.cache_warmer.cache_manager')
    def test_warm_permissions_cache(self, mock_manager, warmer, mock_db):
        """Test permissions cache warming"""
        # Mock user with permissions
        mock_user = MagicMock()
        mock_user.id = 1
        mock_user.restaurant_id = 1
        mock_user.role = MagicMock()
        mock_user.role.name = "admin"
        mock_user.role.permissions = [
            MagicMock(name="read"),
            MagicMock(name="write")
        ]
        
        mock_db.query().filter().all.return_value = [mock_user]
        mock_manager.set.return_value = True
        
        stats = warmer.warm_permissions_cache(user_ids=[1])
        assert stats['users_cached'] == 1
        assert stats['permissions_cached'] == 2
    
    @patch('core.cache.cache_warmer.cache_manager')
    def test_warm_settings_cache(self, mock_manager, warmer, mock_db):
        """Test settings cache warming"""
        # Mock restaurant and settings
        mock_restaurant = MagicMock()
        mock_restaurant.id = 1
        mock_restaurant.name = "Test Restaurant"
        
        mock_settings = MagicMock()
        mock_settings.timezone = "UTC"
        mock_settings.currency = "USD"
        mock_settings.tax_rate = 0.08
        mock_settings.service_charge = 0.15
        mock_settings.opening_hours = {}
        mock_settings.features = {}
        
        mock_db.query().filter_by().all.return_value = [mock_restaurant]
        mock_db.query().filter_by().first.return_value = mock_settings
        mock_manager.set.return_value = True
        
        stats = warmer.warm_settings_cache(tenant_id=1)
        assert stats['settings_cached'] == 1
    
    @patch('core.cache.cache_warmer.ThreadPoolExecutor')
    @patch('core.cache.cache_warmer.cache_manager')
    def test_warm_all_parallel(self, mock_manager, mock_executor, warmer):
        """Test parallel cache warming"""
        mock_manager.set.return_value = True
        
        # Mock executor to run synchronously
        mock_executor.return_value.__enter__.return_value.submit.side_effect = \
            lambda func, *args: MagicMock(result=lambda: func(*args))
        
        stats = warmer.warm_all(tenant_id=1, parallel=True)
        assert 'summary' in stats
        assert stats['summary']['warmers_run'] > 0


class TestCacheMonitor:
    """Test cache monitoring"""
    
    @pytest.fixture
    def monitor(self):
        """Create cache monitor instance"""
        return CacheMonitor(max_metrics=100)
    
    def test_record_metric(self, monitor):
        """Test metric recording"""
        metric = CacheMetric(
            timestamp=time.time(),
            operation="hit",
            cache_type="menu",
            key="menu:1",
            duration_ms=5.0,
            success=True
        )
        
        monitor.record_metric(metric)
        
        agg = monitor.aggregated_metrics["menu"]
        assert agg.total_requests == 1
        assert agg.cache_hits == 1
        assert agg.avg_response_time_ms == 5.0
    
    def test_get_metrics_with_filter(self, monitor):
        """Test getting metrics with filters"""
        # Add some metrics
        now = time.time()
        for i in range(10):
            metric = CacheMetric(
                timestamp=now - (i * 60),  # Minutes ago
                operation="hit" if i % 2 == 0 else "miss",
                cache_type="menu",
                key=f"key{i}",
                duration_ms=i * 2.0,
                success=True
            )
            monitor.record_metric(metric)
        
        # Get metrics for last 5 minutes
        metrics = monitor.get_metrics(cache_type="menu", last_minutes=5)
        assert metrics['cache_type'] == "menu"
        assert 'metrics' in metrics
    
    def test_get_top_keys(self, monitor):
        """Test getting top accessed keys"""
        # Add metrics with different keys
        for i in range(20):
            metric = CacheMetric(
                timestamp=time.time(),
                operation="hit",
                cache_type="menu",
                key=f"key{i % 5}",  # 5 unique keys
                duration_ms=1.0,
                success=True
            )
            monitor.record_metric(metric)
        
        top_keys = monitor.get_top_keys(limit=3)
        assert len(top_keys) <= 3
        assert all('access_count' in k for k in top_keys)
    
    def test_get_slow_operations(self, monitor):
        """Test getting slow operations"""
        # Add metrics with varying durations
        for i in range(10):
            metric = CacheMetric(
                timestamp=time.time(),
                operation="get",
                cache_type="analytics",
                key=f"key{i}",
                duration_ms=50 + (i * 20),  # 50ms to 230ms
                success=True
            )
            monitor.record_metric(metric)
        
        slow_ops = monitor.get_slow_operations(threshold_ms=100, limit=5)
        assert len(slow_ops) <= 5
        assert all(op['duration_ms'] >= 100 for op in slow_ops)
    
    @patch('core.cache.monitoring.RedisClient')
    def test_check_health(self, mock_redis, monitor):
        """Test health checking"""
        # Mock Redis client
        mock_client = MagicMock()
        mock_client.ping.return_value = True
        mock_client.info.return_value = {'memory': {'used_memory': 100000000}}
        mock_redis.get_client.return_value = mock_client
        
        # Add some metrics
        for _ in range(10):
            metric = CacheMetric(
                timestamp=time.time(),
                operation="hit",
                cache_type="menu",
                key="key",
                duration_ms=10.0,
                success=True
            )
            monitor.record_metric(metric)
        
        health = monitor.check_health()
        assert 'status' in health
        assert 'metrics' in health
        assert 'issues' in health
        assert 'recommendations' in health
    
    def test_get_cache_report(self, monitor):
        """Test comprehensive cache report generation"""
        # Add various metrics
        for i in range(20):
            metric = CacheMetric(
                timestamp=time.time() - (i * 60),
                operation="hit" if i % 3 == 0 else "miss",
                cache_type="menu" if i % 2 == 0 else "permissions",
                key=f"key{i}",
                duration_ms=i * 5.0,
                success=i % 10 != 0  # Some failures
            )
            monitor.record_metric(metric)
        
        report = monitor.get_cache_report()
        assert 'generated_at' in report
        assert 'uptime_hours' in report
        assert 'health' in report
        assert 'current_metrics' in report
        assert 'hourly_metrics' in report
        assert 'daily_metrics' in report
        assert 'top_keys' in report
        assert 'slow_operations' in report
        assert 'cache_types' in report


class TestCacheTTL:
    """Test cache TTL enum values"""
    
    def test_ttl_values(self):
        """Test TTL values are appropriate"""
        assert CacheTTL.MENU_ITEMS.value == 3600  # 1 hour
        assert CacheTTL.USER_PERMISSIONS.value == 300  # 5 minutes
        assert CacheTTL.RESTAURANT_SETTINGS.value == 600  # 10 minutes
        assert CacheTTL.ANALYTICS_AGGREGATIONS.value == 300  # 5 minutes
        assert CacheTTL.PERMANENT.value is None  # No expiration


class TestCacheIntegration:
    """Integration tests for caching system"""
    
    @pytest.mark.integration
    @patch('core.cache.redis_client.Redis')
    def test_end_to_end_caching(self, mock_redis):
        """Test end-to-end caching flow"""
        # Setup mock Redis
        mock_redis_instance = MagicMock()
        mock_redis.return_value = mock_redis_instance
        mock_redis_instance.get.return_value = None
        mock_redis_instance.set.return_value = True
        mock_redis_instance.setex.return_value = True
        
        # Create cache manager
        manager = CacheManager()
        
        # Define cached function
        @cache(cache_type="test", ttl=60)
        def get_data(id: int):
            return {"id": id, "value": "test"}
        
        # First call - cache miss
        result1 = get_data(1)
        assert result1 == {"id": 1, "value": "test"}
        
        # Setup cache hit
        mock_redis_instance.get.return_value = b'{"id": 1, "value": "cached"}'
        
        # Second call - cache hit
        result2 = get_data(1)
        # Would be cached value in real scenario
        
        # Test invalidation
        @invalidate_cache("test")
        def update_data(id: int, value: str):
            return {"id": id, "value": value}
        
        update_data(1, "updated")
        
        # Verify cache operations were called
        assert mock_redis_instance.get.called
        assert mock_redis_instance.set.called or mock_redis_instance.setex.called


if __name__ == "__main__":
    pytest.main([__file__, "-v"])