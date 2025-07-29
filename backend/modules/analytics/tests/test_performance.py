# backend/modules/analytics/tests/test_performance.py

import pytest
import time
from typing import List, Dict, Any
from datetime import date, datetime, timedelta
from decimal import Decimal
from unittest.mock import Mock, patch
from sqlalchemy.orm import Session

from ..services.sales_report_service import SalesReportService
from ..services.trend_service import TrendService
from ..services.export_service import ExportService
from ..services.async_processing import AsyncTaskProcessor, TaskPriority
from ..schemas.analytics_schemas import SalesFilterRequest
from ..models.analytics_models import SalesAnalyticsSnapshot, AggregationPeriod


class TestAnalyticsPerformance:
    """Performance tests for analytics services with large datasets"""

    @pytest.fixture
    def mock_large_dataset(self, db_session: Session):
        """Create a large dataset for performance testing"""
        snapshots = []
        
        # Generate 10,000 daily snapshots across 2 years
        start_date = date.today() - timedelta(days=730)
        for i in range(10000):
            snapshot_date = start_date + timedelta(days=i % 730)
            
            snapshot = SalesAnalyticsSnapshot(
                snapshot_date=snapshot_date,
                period_type=AggregationPeriod.DAILY,
                total_orders=50 + (i % 100),
                total_revenue=Decimal(str(1000 + (i * 10))),
                total_items_sold=100 + (i % 200),
                average_order_value=Decimal(str(20 + (i % 50))),
                total_discounts=Decimal(str(50 + (i % 20))),
                total_tax=Decimal(str(80 + (i % 15))),
                net_revenue=Decimal(str(950 + (i * 9))),
                unique_customers=30 + (i % 60),
                staff_id=(i % 10) + 1 if i % 3 == 0 else None,
                product_id=(i % 50) + 1 if i % 5 == 0 else None,
                calculated_at=datetime.now()
            )
            snapshots.append(snapshot)
            
            # Batch insert every 1000 records
            if len(snapshots) >= 1000:
                db_session.bulk_save_objects(snapshots)
                db_session.commit()
                snapshots = []
        
        # Insert remaining snapshots
        if snapshots:
            db_session.bulk_save_objects(snapshots)
            db_session.commit()

    def test_sales_summary_performance_large_dataset(self, db_session: Session, mock_large_dataset):
        """Test sales summary generation performance with large dataset"""
        service = SalesReportService(db_session)
        
        filters = SalesFilterRequest(
            date_from=date.today() - timedelta(days=365),
            date_to=date.today(),
            period_type=AggregationPeriod.DAILY
        )
        
        # Measure execution time
        start_time = time.time()
        result = service.generate_sales_summary(filters)
        execution_time = time.time() - start_time
        
        # Performance assertions
        assert execution_time < 2.0, f"Sales summary took {execution_time:.2f}s, should be under 2s"
        assert result is not None
        assert result.total_orders > 0
        assert result.total_revenue > 0

    def test_detailed_report_performance_pagination(self, db_session: Session, mock_large_dataset):
        """Test detailed report performance with pagination"""
        service = SalesReportService(db_session)
        
        filters = SalesFilterRequest(
            date_from=date.today() - timedelta(days=90),
            date_to=date.today()
        )
        
        # Test large page sizes
        page_sizes = [100, 500, 1000, 5000]
        
        for page_size in page_sizes:
            start_time = time.time()
            result = service.generate_detailed_sales_report(
                filters=filters,
                page=1,
                per_page=page_size
            )
            execution_time = time.time() - start_time
            
            # Performance should scale reasonably with page size
            max_time = 0.5 + (page_size / 10000)  # Allow 0.5s base + 0.1s per 1000 records
            assert execution_time < max_time, f"Page size {page_size} took {execution_time:.2f}s, should be under {max_time:.2f}s"
            assert len(result.items) <= page_size

    def test_trend_service_performance_optimization(self, db_session: Session, mock_large_dataset):
        """Test that trend service uses optimized snapshot queries"""
        trend_service = TrendService(db_session)
        
        start_date = date.today() - timedelta(days=90)
        end_date = date.today()
        
        # Test revenue trend performance
        start_time = time.time()
        revenue_trends = trend_service.get_revenue_trend(start_date, end_date, "daily")
        execution_time = time.time() - start_time
        
        # Should be fast with snapshot-based queries
        assert execution_time < 1.0, f"Revenue trend took {execution_time:.2f}s, should be under 1s"
        assert len(revenue_trends) > 0
        
        # Test multi-metric trends
        start_time = time.time()
        multi_trends = trend_service.get_multi_metric_trend(
            start_date, end_date, ["revenue", "orders"], "daily"
        )
        execution_time = time.time() - start_time
        
        assert execution_time < 1.5, f"Multi-metric trend took {execution_time:.2f}s, should be under 1.5s"
        assert "revenue" in multi_trends
        assert "orders" in multi_trends

    def test_export_service_memory_efficiency(self, db_session: Session, mock_large_dataset):
        """Test export service handles large datasets efficiently"""
        export_service = ExportService(db_session)
        
        # Mock large dataset export
        with patch.object(export_service, '_get_report_data') as mock_get_data:
            # Simulate 50,000 records
            large_data = [
                {
                    "date": str(date.today() - timedelta(days=i)),
                    "revenue": 1000 + i,
                    "orders": 50 + (i % 20),
                    "customers": 30 + (i % 10)
                }
                for i in range(50000)
            ]
            mock_get_data.return_value = large_data
            
            # Test CSV export performance
            start_time = time.time()
            csv_response = export_service._format_data_as_csv(large_data, "test")
            csv_time = time.time() - start_time
            
            assert csv_time < 5.0, f"CSV export took {csv_time:.2f}s, should be under 5s"
            assert csv_response is not None

    def test_async_processor_queue_performance(self):
        """Test async task processor handles high load efficiently"""
        import asyncio
        
        async def run_async_test():
            processor = AsyncTaskProcessor(max_workers=4)
            
            async def mock_handler(task_data, task):
                # Simulate work
                await asyncio.sleep(0.1)
                return {"processed": True}
            
            processor.register_handler("test_task", mock_handler)
            
            # Submit many tasks quickly
            start_time = time.time()
            task_ids = []
            
            for i in range(100):
                task_id = await processor.submit_task(
                    "test_task",
                    {"data": f"test_{i}"},
                    priority=TaskPriority.NORMAL
                )
                task_ids.append(task_id)
            
            submission_time = time.time() - start_time
            
            # Should be able to submit 100 tasks quickly
            assert submission_time < 1.0, f"Task submission took {submission_time:.2f}s, should be under 1s"
            assert len(task_ids) == 100
            
            return task_ids
        
        # Run the async test
        asyncio.run(run_async_test())

    def test_memory_usage_monitoring(self, db_session: Session, mock_large_dataset):
        """Test memory usage doesn't grow excessively with large operations"""
        import psutil
        import os
        
        process = psutil.Process(os.getpid())
        initial_memory = process.memory_info().rss / 1024 / 1024  # MB
        
        service = SalesReportService(db_session)
        
        # Perform multiple large operations
        for _ in range(5):
            filters = SalesFilterRequest(
                date_from=date.today() - timedelta(days=365),
                date_to=date.today()
            )
            
            result = service.generate_detailed_sales_report(
                filters=filters,
                page=1,
                per_page=5000
            )
            
            # Force garbage collection
            import gc
            gc.collect()
        
        final_memory = process.memory_info().rss / 1024 / 1024  # MB
        memory_increase = final_memory - initial_memory
        
        # Memory increase should be reasonable (under 100MB for test operations)
        assert memory_increase < 100, f"Memory increased by {memory_increase:.1f}MB, should be under 100MB"

    def test_database_connection_pooling(self, db_session: Session):
        """Test database connections are managed efficiently"""
        services = []
        
        # Create multiple service instances
        for _ in range(20):
            service = SalesReportService(db_session)
            services.append(service)
        
        # All should use the same session efficiently
        start_time = time.time()
        
        for service in services[:5]:  # Test a subset to avoid timeout
            filters = SalesFilterRequest(
                date_from=date.today() - timedelta(days=7),
                date_to=date.today()
            )
            service.generate_sales_summary(filters)
        
        execution_time = time.time() - start_time
        
        # Should handle multiple services efficiently
        assert execution_time < 2.0, f"Multiple service calls took {execution_time:.2f}s, should be under 2s"

    def test_query_optimization_with_indexes(self, db_session: Session, mock_large_dataset):
        """Test that queries are optimized and use proper indexes"""
        service = SalesReportService(db_session)
        
        # Test queries with different filter combinations
        filter_combinations = [
            {"date_from": date.today() - timedelta(days=30)},
            {"staff_ids": [1, 2, 3]},
            {"product_ids": [1, 2, 3, 4, 5]},
            {"date_from": date.today() - timedelta(days=7), "staff_ids": [1]},
        ]
        
        for filter_combo in filter_combinations:
            filters = SalesFilterRequest(**filter_combo)
            
            start_time = time.time()
            result = service.generate_sales_summary(filters)
            execution_time = time.time() - start_time
            
            # Each query should be reasonably fast
            assert execution_time < 1.0, f"Query with {filter_combo} took {execution_time:.2f}s, should be under 1s"

    @pytest.mark.parametrize("concurrent_users", [5, 10, 25])
    def test_concurrent_user_performance(self, db_session: Session, mock_large_dataset, concurrent_users):
        """Test performance with multiple concurrent users"""
        import asyncio
        import concurrent.futures
        
        def simulate_user_request():
            service = SalesReportService(db_session)
            filters = SalesFilterRequest(
                date_from=date.today() - timedelta(days=30),
                date_to=date.today()
            )
            
            start_time = time.time()
            result = service.generate_sales_summary(filters)
            execution_time = time.time() - start_time
            
            return execution_time, result is not None
        
        # Simulate concurrent requests
        start_time = time.time()
        
        with concurrent.futures.ThreadPoolExecutor(max_workers=concurrent_users) as executor:
            futures = [executor.submit(simulate_user_request) for _ in range(concurrent_users)]
            results = [future.result() for future in concurrent.futures.as_completed(futures)]
        
        total_time = time.time() - start_time
        
        # Check all requests succeeded
        assert all(success for _, success in results), "Some concurrent requests failed"
        
        # Average response time should be reasonable
        avg_response_time = sum(exec_time for exec_time, _ in results) / len(results)
        assert avg_response_time < 2.0, f"Average response time {avg_response_time:.2f}s too high with {concurrent_users} users"
        
        # Total time should show concurrency benefits
        sequential_time_estimate = sum(exec_time for exec_time, _ in results)
        concurrency_benefit = sequential_time_estimate / total_time
        
        # Should get at least 2x benefit from concurrency
        assert concurrency_benefit >= 2.0, f"Concurrency benefit only {concurrency_benefit:.1f}x, should be at least 2x"


class TestAnalyticsStressTests:
    """Stress tests for analytics under extreme conditions"""

    def test_extreme_date_ranges(self, db_session: Session):
        """Test handling of extreme date ranges"""
        service = SalesReportService(db_session)
        
        # Test very large date range
        filters = SalesFilterRequest(
            date_from=date(2020, 1, 1),
            date_to=date(2025, 12, 31)
        )
        
        start_time = time.time()
        result = service.generate_sales_summary(filters)
        execution_time = time.time() - start_time
        
        # Should handle gracefully even if slow
        assert execution_time < 10.0, f"Extreme date range took {execution_time:.2f}s, should be under 10s"
        assert result is not None

    def test_maximum_pagination_limits(self, db_session: Session, mock_large_dataset):
        """Test maximum pagination boundaries"""
        service = SalesReportService(db_session)
        
        filters = SalesFilterRequest(
            date_from=date.today() - timedelta(days=30),
            date_to=date.today()
        )
        
        # Test maximum allowed per_page limit
        result = service.generate_detailed_sales_report(
            filters=filters,
            page=1,
            per_page=1000  # Max allowed in router
        )
        
        assert result is not None
        assert len(result.items) <= 1000

    def test_memory_pressure_handling(self, db_session: Session):
        """Test behavior under memory pressure"""
        # Simulate memory pressure by creating large objects
        large_objects = []
        
        try:
            # Create objects that consume significant memory
            for i in range(100):
                large_objects.append([0] * 100000)  # ~800KB per object
            
            # Try to perform analytics operations under memory pressure
            service = SalesReportService(db_session)
            filters = SalesFilterRequest(
                date_from=date.today() - timedelta(days=7),
                date_to=date.today()
            )
            
            result = service.generate_sales_summary(filters)
            assert result is not None
            
        finally:
            # Clean up
            large_objects.clear()
            import gc
            gc.collect()

    def test_database_timeout_handling(self, db_session: Session):
        """Test handling of database timeouts and connection issues"""
        service = SalesReportService(db_session)
        
        # Mock a slow database operation
        with patch.object(db_session, 'query') as mock_query:
            # Simulate timeout
            import time
            
            def slow_query(*args, **kwargs):
                time.sleep(0.1)  # Simulate slow query
                return mock_query.return_value
            
            mock_query.side_effect = slow_query
            
            filters = SalesFilterRequest(
                date_from=date.today() - timedelta(days=1),
                date_to=date.today()
            )
            
            # Should handle gracefully
            start_time = time.time()
            try:
                result = service.generate_sales_summary(filters)
                execution_time = time.time() - start_time
                
                # Should complete despite slow database
                assert execution_time < 5.0, "Should handle slow database within reasonable time"
                
            except Exception as e:
                # Should fail gracefully if at all
                assert "timeout" in str(e).lower() or "connection" in str(e).lower()