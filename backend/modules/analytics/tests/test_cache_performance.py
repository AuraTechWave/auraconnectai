# backend/modules/analytics/tests/test_cache_performance.py

"""
Cache performance and invalidation tests for analytics module.

These tests verify that caching systems work efficiently under load,
handle invalidation correctly, and maintain data consistency.
"""

import pytest
import asyncio
import time
from datetime import datetime, timedelta
from decimal import Decimal
from unittest.mock import Mock, patch, AsyncMock
from typing import Dict, Any, List
import threading
import concurrent.futures

from ..services.realtime_metrics_service import RealtimeMetricsService, DashboardSnapshot
from ..services.dashboard_widgets_service import DashboardWidgetsService, WidgetConfiguration, WidgetType
from ..schemas.realtime_schemas import WidgetDataResponse
from ..integrations.module_hooks import invalidate_analytics_cache_hook


class TestCachePerformance:
    """Test cache performance under various load conditions"""
    
    @pytest.fixture
    def metrics_service(self):
        """Create metrics service with in-memory cache"""
        return RealtimeMetricsService(redis_client=None)
    
    @pytest.fixture
    def widgets_service(self):
        """Create widgets service"""
        return DashboardWidgetsService()
    
    @pytest.fixture
    def sample_widget_configs(self):
        """Create sample widget configurations for testing"""
        configs = []
        
        for i in range(20):
            config = WidgetConfiguration(
                widget_id=f"test_widget_{i}",
                widget_type=WidgetType.METRIC_CARD,
                title=f"Test Widget {i}",
                position={"x": i % 4, "y": i // 4, "width": 2, "height": 2},
                data_source="realtime_metric",
                config={
                    "metric_name": f"test_metric_{i}",
                    "format": "number" if i % 2 == 0 else "currency"
                }
            )
            configs.append(config)
        
        return configs
    
    def test_cache_memory_usage(self, widgets_service, sample_widget_configs):
        """Test cache memory usage with many widgets"""
        
        # Populate cache with widget data
        for i, config in enumerate(sample_widget_configs):
            cache_key = f"{config.widget_id}_{hash(str(config.dict()))}"
            widgets_service.widget_data_cache[cache_key] = {
                "data": {
                    "value": i * 100,
                    "change_percentage": i * 2.5,
                    "status": "success"
                },
                "timestamp": datetime.now()
            }
        
        # Verify all widgets are cached
        assert len(widgets_service.widget_data_cache) == len(sample_widget_configs)
        
        # Test memory efficiency by checking cache size doesn't grow exponentially
        initial_cache_size = len(widgets_service.widget_data_cache)
        
        # Add more widgets with similar patterns
        for i in range(20, 40):
            cache_key = f"test_widget_{i}_{hash('test_config')}"
            widgets_service.widget_data_cache[cache_key] = {
                "data": {"value": i * 100},
                "timestamp": datetime.now()
            }
        
        final_cache_size = len(widgets_service.widget_data_cache)
        assert final_cache_size == initial_cache_size + 20
    
    @pytest.mark.asyncio
    async def test_concurrent_cache_access(self, widgets_service, sample_widget_configs):
        """Test concurrent cache access performance"""
        
        # Pre-populate cache
        for config in sample_widget_configs[:10]:
            cache_key = f"{config.widget_id}_{hash(str(config.dict()))}"
            widgets_service.widget_data_cache[cache_key] = {
                "data": {"value": 100, "status": "success"},
                "timestamp": datetime.now()
            }
        
        async def access_cache_concurrently(config_subset):
            """Access cache concurrently"""
            with patch.object(widgets_service, '_process_metric_card', 
                            return_value={"value": 200, "status": "fresh"}):
                
                tasks = []
                for config in config_subset:
                    task = asyncio.create_task(
                        widgets_service.get_widget_data(config, force_refresh=False)
                    )
                    tasks.append(task)
                
                results = await asyncio.gather(*tasks, return_exceptions=True)
                return results
        
        # Test concurrent access with different config subsets
        start_time = time.time()
        
        # Run multiple concurrent batches
        batch_tasks = []
        for i in range(0, 10, 3):
            batch = sample_widget_configs[i:i+3]
            task = asyncio.create_task(access_cache_concurrently(batch))
            batch_tasks.append(task)
        
        batch_results = await asyncio.gather(*batch_tasks)
        
        end_time = time.time()
        execution_time = end_time - start_time
        
        # Verify all results are successful
        for batch_result in batch_results:
            for result in batch_result:
                assert not isinstance(result, Exception)
                assert isinstance(result, WidgetDataResponse)
        
        # Performance should be reasonable (less than 1 second for this test)
        assert execution_time < 1.0
    
    def test_cache_expiration_handling(self, widgets_service):
        """Test cache expiration handling"""
        
        # Set a short cache TTL for testing
        widgets_service.cache_ttl = 0.1  # 100ms
        
        # Add item to cache
        cache_key = "test_widget_expired"
        widgets_service.widget_data_cache[cache_key] = {
            "data": {"value": 100},
            "timestamp": datetime.now()
        }
        
        # Verify item is in cache
        assert cache_key in widgets_service.widget_data_cache
        
        # Wait for expiration
        time.sleep(0.15)
        
        # Create a widget config
        config = WidgetConfiguration(
            widget_id="test_widget",
            widget_type=WidgetType.METRIC_CARD,
            title="Test Widget",
            position={"x": 0, "y": 0, "width": 2, "height": 2},
            data_source="realtime_metric",
            config={"metric_name": "test_metric"}
        )
        
        with patch.object(widgets_service, '_process_metric_card',
                         return_value={"value": 200, "status": "fresh"}):
            
            # This should trigger cache refresh due to expiration
            result = asyncio.run(widgets_service.get_widget_data(config, force_refresh=False))
            
            # Should get fresh data, not cached
            assert result.cache_status == "fresh"
    
    def test_cache_invalidation_patterns(self, widgets_service):
        """Test different cache invalidation patterns"""
        
        # Add widgets with different ID patterns
        test_widgets = [
            "revenue_widget_1", "revenue_widget_2", "revenue_summary",
            "orders_widget_1", "orders_widget_2", "orders_summary",
            "customers_widget_1", "customers_summary"
        ]
        
        for widget_id in test_widgets:
            widgets_service.widget_data_cache[f"{widget_id}_hash"] = {
                "data": {"value": 100},
                "timestamp": datetime.now()
            }
        
        assert len(widgets_service.widget_data_cache) == len(test_widgets)
        
        # Test specific widget invalidation
        widgets_service.invalidate_widget_cache("revenue_widget_1")
        
        remaining_widgets = [key for key in widgets_service.widget_data_cache.keys()]
        assert not any("revenue_widget_1" in key for key in remaining_widgets)
        assert any("revenue_widget_2" in key for key in remaining_widgets)
        
        # Test pattern-based invalidation  
        widgets_service.invalidate_widget_cache("orders_")
        
        remaining_widgets = [key for key in widgets_service.widget_data_cache.keys()]
        assert not any("orders_" in key for key in remaining_widgets)
        assert any("revenue_" in key for key in remaining_widgets)
        assert any("customers_" in key for key in remaining_widgets)
        
        # Test full invalidation
        widgets_service.invalidate_widget_cache()
        assert len(widgets_service.widget_data_cache) == 0
    
    @pytest.mark.asyncio
    async def test_cache_under_high_load(self, widgets_service):
        """Test cache performance under high load"""
        
        # Create many widget configurations
        num_widgets = 100
        widget_configs = []
        
        for i in range(num_widgets):
            config = WidgetConfiguration(
                widget_id=f"load_test_widget_{i}",
                widget_type=WidgetType.METRIC_CARD,
                title=f"Load Test Widget {i}",
                position={"x": i % 10, "y": i // 10, "width": 2, "height": 2},
                data_source="realtime_metric",
                config={"metric_name": f"load_metric_{i}"}
            )
            widget_configs.append(config)
        
        # Mock the processor to return consistent data
        with patch.object(widgets_service, '_process_metric_card') as mock_processor:
            mock_processor.return_value = {"value": 100, "status": "success"}
            
            # First pass - populate cache
            start_time = time.time()
            
            first_pass_tasks = [
                widgets_service.get_widget_data(config) for config in widget_configs
            ]
            first_results = await asyncio.gather(*first_pass_tasks)
            
            first_pass_time = time.time() - start_time
            
            # Verify all widgets processed
            assert len(first_results) == num_widgets
            assert all(result.cache_status == "fresh" for result in first_results)
            
            # Second pass - should hit cache
            start_time = time.time()
            
            second_pass_tasks = [
                widgets_service.get_widget_data(config) for config in widget_configs
            ]
            second_results = await asyncio.gather(*second_pass_tasks)
            
            second_pass_time = time.time() - start_time
            
            # Verify cache hits
            assert len(second_results) == num_widgets
            assert all(result.cache_status == "cached" for result in second_results)
            
            # Cache should be significantly faster
            assert second_pass_time < first_pass_time * 0.5
            
            # Mock processor should only be called once for each widget (first pass)
            assert mock_processor.call_count == num_widgets
    
    def test_cache_size_limits(self, widgets_service):
        """Test cache behavior when approaching size limits"""
        
        # Simulate cache size limit by manually managing cache
        max_cache_size = 50
        
        # Add items up to limit
        for i in range(max_cache_size):
            cache_key = f"size_test_widget_{i}"
            widgets_service.widget_data_cache[cache_key] = {
                "data": {"value": i},
                "timestamp": datetime.now()
            }
        
        assert len(widgets_service.widget_data_cache) == max_cache_size
        
        # In a real implementation, adding more items might trigger eviction
        # For this test, we'll just verify current behavior
        
        # Add one more item
        widgets_service.widget_data_cache["overflow_widget"] = {
            "data": {"value": 999},
            "timestamp": datetime.now()
        }
        
        # Currently no size limit is enforced, so it should just grow
        assert len(widgets_service.widget_data_cache) == max_cache_size + 1
    
    @pytest.mark.asyncio
    async def test_cache_consistency_across_services(self):
        """Test cache consistency across different services"""
        
        # Test coordination between metrics service and widgets service
        metrics_service = RealtimeMetricsService(redis_client=None)
        widgets_service = DashboardWidgetsService()
        
        # Mock metrics service cache operations
        with patch.object(metrics_service, 'invalidate_cache') as mock_invalidate:
            mock_invalidate.return_value = AsyncMock()
            
            # Trigger cache invalidation from module hooks
            await invalidate_analytics_cache_hook("test_pattern")
            await invalidate_analytics_cache_hook()  # Full invalidation
            
            # Verify metrics service cache was invalidated
            assert mock_invalidate.call_count == 2
        
        # Test widget cache invalidation
        widgets_service.widget_data_cache["test_widget"] = {
            "data": {"value": 100},
            "timestamp": datetime.now()
        }
        
        widgets_service.invalidate_widget_cache("test_widget")
        assert len(widgets_service.widget_data_cache) == 0


class TestCacheStressTest:
    """Stress tests for cache systems"""
    
    @pytest.fixture
    def widgets_service(self):
        """Create widgets service for stress testing"""
        return DashboardWidgetsService()
    
    def test_cache_thread_safety(self, widgets_service):
        """Test cache thread safety with concurrent access"""
        
        def worker_thread(thread_id, num_operations):
            """Worker thread that performs cache operations"""
            for i in range(num_operations):
                cache_key = f"thread_{thread_id}_item_{i}"
                
                # Add to cache
                widgets_service.widget_data_cache[cache_key] = {
                    "data": {"value": thread_id * 1000 + i},
                    "timestamp": datetime.now()
                }
                
                # Read from cache
                if cache_key in widgets_service.widget_data_cache:
                    data = widgets_service.widget_data_cache[cache_key]
                    assert data["data"]["value"] == thread_id * 1000 + i
                
                # Small delay to increase chance of race conditions
                time.sleep(0.001)
        
        # Create multiple threads
        num_threads = 5
        operations_per_thread = 20
        
        threads = []
        for thread_id in range(num_threads):
            thread = threading.Thread(
                target=worker_thread,
                args=(thread_id, operations_per_thread)
            )
            threads.append(thread)
        
        # Start all threads
        for thread in threads:
            thread.start()
        
        # Wait for all threads to complete
        for thread in threads:
            thread.join()
        
        # Verify final cache state
        expected_items = num_threads * operations_per_thread
        assert len(widgets_service.widget_data_cache) == expected_items
        
        # Verify data integrity
        for thread_id in range(num_threads):
            for i in range(operations_per_thread):
                cache_key = f"thread_{thread_id}_item_{i}"
                assert cache_key in widgets_service.widget_data_cache
                
                data = widgets_service.widget_data_cache[cache_key]
                expected_value = thread_id * 1000 + i
                assert data["data"]["value"] == expected_value
    
    def test_cache_memory_pressure(self, widgets_service):
        """Test cache behavior under memory pressure"""
        
        # Create large cache entries
        large_data_size = 1000  # Simulate large widget data
        num_large_entries = 100
        
        start_time = time.time()
        
        for i in range(num_large_entries):
            cache_key = f"large_entry_{i}"
            
            # Create large data structure
            large_data = {
                "data": {
                    "value": i,
                    "large_array": [j for j in range(large_data_size)],
                    "metadata": {f"key_{k}": f"value_{k}" for k in range(100)}
                },
                "timestamp": datetime.now()
            }
            
            widgets_service.widget_data_cache[cache_key] = large_data
        
        creation_time = time.time() - start_time
        
        # Verify all entries were created
        assert len(widgets_service.widget_data_cache) == num_large_entries
        
        # Test access performance with large entries
        start_time = time.time()
        
        for i in range(num_large_entries):
            cache_key = f"large_entry_{i}"
            data = widgets_service.widget_data_cache[cache_key]
            assert data["data"]["value"] == i
            assert len(data["data"]["large_array"]) == large_data_size
        
        access_time = time.time() - start_time
        
        # Access should be much faster than creation
        assert access_time < creation_time * 0.5
        
        # Test cache invalidation performance with large entries
        start_time = time.time()
        widgets_service.invalidate_widget_cache()
        invalidation_time = time.time() - start_time
        
        # Verify cache was cleared
        assert len(widgets_service.widget_data_cache) == 0
        
        # Invalidation should be reasonably fast
        assert invalidation_time < 1.0
    
    @pytest.mark.asyncio
    async def test_cache_performance_degradation(self, widgets_service):
        """Test cache performance doesn't degrade significantly with size"""
        
        # Test performance at different cache sizes
        cache_sizes = [10, 50, 100, 500, 1000]
        performance_results = []
        
        for cache_size in cache_sizes:
            # Clear cache
            widgets_service.invalidate_widget_cache()
            
            # Populate cache
            for i in range(cache_size):
                cache_key = f"perf_test_{i}"
                widgets_service.widget_data_cache[cache_key] = {
                    "data": {"value": i, "status": "success"},
                    "timestamp": datetime.now()
                }
            
            # Measure access time
            start_time = time.time()
            
            # Perform random access operations
            import random
            for _ in range(100):  # 100 random accesses
                random_key = f"perf_test_{random.randint(0, cache_size - 1)}"
                if random_key in widgets_service.widget_data_cache:
                    data = widgets_service.widget_data_cache[random_key]
                    assert "value" in data["data"]
            
            access_time = time.time() - start_time
            performance_results.append((cache_size, access_time))
        
        # Verify performance doesn't degrade significantly
        # (allowing for some variation due to system load)
        for i in range(1, len(performance_results)):
            prev_size, prev_time = performance_results[i-1]
            curr_size, curr_time = performance_results[i]
            
            # Performance shouldn't degrade more than linearly with size
            size_ratio = curr_size / prev_size
            time_ratio = curr_time / prev_time if prev_time > 0 else 1
            
            # Allow up to 2x performance degradation for 10x size increase
            assert time_ratio <= size_ratio * 2
    
    def test_cache_recovery_after_failure(self, widgets_service):
        """Test cache recovery after simulated failures"""
        
        # Populate cache
        for i in range(50):
            cache_key = f"recovery_test_{i}"
            widgets_service.widget_data_cache[cache_key] = {
                "data": {"value": i},
                "timestamp": datetime.now()
            }
        
        initial_size = len(widgets_service.widget_data_cache)
        assert initial_size == 50
        
        # Simulate partial corruption by removing some entries
        keys_to_remove = list(widgets_service.widget_data_cache.keys())[:10]
        for key in keys_to_remove:
            del widgets_service.widget_data_cache[key]
        
        # Verify partial data loss
        assert len(widgets_service.widget_data_cache) == 40
        
        # Simulate recovery by repopulating missing entries
        for i in range(10):  # Repopulate first 10 entries
            cache_key = f"recovery_test_{i}"
            if cache_key not in widgets_service.widget_data_cache:
                widgets_service.widget_data_cache[cache_key] = {
                    "data": {"value": i, "status": "recovered"},
                    "timestamp": datetime.now()
                }
        
        # Verify recovery
        assert len(widgets_service.widget_data_cache) == 50
        
        # Verify recovered data is correct
        for i in range(10):
            cache_key = f"recovery_test_{i}"
            assert cache_key in widgets_service.widget_data_cache
            data = widgets_service.widget_data_cache[cache_key]
            assert data["data"]["value"] == i


class TestCacheIntegrationBenchmarks:
    """Integration benchmarks for cache performance"""
    
    @pytest.mark.asyncio
    async def test_end_to_end_dashboard_performance(self):
        """Test end-to-end dashboard loading performance"""
        
        widgets_service = DashboardWidgetsService()
        
        # Create a realistic dashboard layout
        from ..schemas.realtime_schemas import DashboardLayout
        
        layout = await widgets_service.create_default_dashboard_layout(user_id=1)
        
        # Mock all widget processors for consistent timing
        mock_data = {"value": 100, "status": "success", "change_percentage": 5.0}
        
        with patch.object(widgets_service, '_process_metric_card', return_value=mock_data), \
             patch.object(widgets_service, '_process_line_chart', return_value=mock_data), \
             patch.object(widgets_service, '_process_bar_chart', return_value=mock_data), \
             patch.object(widgets_service, '_process_pie_chart', return_value=mock_data), \
             patch.object(widgets_service, '_process_table', return_value=mock_data):
            
            # First load (cold cache)
            start_time = time.time()
            first_results = await widgets_service.get_dashboard_layout_data(layout)
            cold_load_time = time.time() - start_time
            
            # Second load (warm cache)
            start_time = time.time()
            second_results = await widgets_service.get_dashboard_layout_data(layout)
            warm_load_time = time.time() - start_time
            
            # Verify results
            assert len(first_results) == len(layout.widgets)
            assert len(second_results) == len(layout.widgets)
            
            # Warm cache should be significantly faster
            assert warm_load_time < cold_load_time * 0.3
            
            # Verify cache hits
            for widget_id, result in second_results.items():
                assert result.cache_status == "cached"
    
    def test_cache_invalidation_impact(self, widgets_service):
        """Test performance impact of cache invalidation"""
        
        # Populate large cache
        cache_size = 1000
        for i in range(cache_size):
            cache_key = f"impact_test_{i}"
            widgets_service.widget_data_cache[cache_key] = {
                "data": {"value": i},
                "timestamp": datetime.now()
            }
        
        # Measure selective invalidation performance  
        start_time = time.time()
        widgets_service.invalidate_widget_cache("impact_test_1")
        selective_time = time.time() - start_time
        
        # Measure full invalidation performance
        start_time = time.time()
        widgets_service.invalidate_widget_cache()
        full_invalidation_time = time.time() - start_time
        
        # Both operations should be reasonably fast
        assert selective_time < 0.1  # Less than 100ms
        assert full_invalidation_time < 0.5  # Less than 500ms


if __name__ == "__main__":
    # Run tests with: python -m pytest backend/modules/analytics/tests/test_cache_performance.py -v
    pytest.main([__file__, "-v"])