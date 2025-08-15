# backend/modules/analytics/tests/test_load_testing.py

import pytest
import asyncio
import time
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
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


class TestAnalyticsLoadTesting:
    """Load testing for analytics services under high concurrent usage"""

    @pytest.fixture
    def load_test_data(self, db_session: Session):
        """Create substantial dataset for load testing"""
        snapshots = []

        # Generate 5,000 snapshots across 1 year for load testing
        start_date = date.today() - timedelta(days=365)
        for i in range(5000):
            snapshot_date = start_date + timedelta(days=i % 365)

            snapshot = SalesAnalyticsSnapshot(
                snapshot_date=snapshot_date,
                period_type=AggregationPeriod.DAILY,
                total_orders=25 + (i % 75),
                total_revenue=Decimal(str(500 + (i * 5))),
                total_items_sold=50 + (i % 150),
                average_order_value=Decimal(str(15 + (i % 35))),
                total_discounts=Decimal(str(25 + (i % 15))),
                total_tax=Decimal(str(40 + (i % 10))),
                net_revenue=Decimal(str(475 + (i * 4.5))),
                unique_customers=20 + (i % 40),
                staff_id=(i % 20) + 1 if i % 4 == 0 else None,
                product_id=(i % 100) + 1 if i % 6 == 0 else None,
                calculated_at=datetime.now(),
            )
            snapshots.append(snapshot)

            # Batch insert every 500 records
            if len(snapshots) >= 500:
                db_session.bulk_save_objects(snapshots)
                db_session.commit()
                snapshots = []

        # Insert remaining snapshots
        if snapshots:
            db_session.bulk_save_objects(snapshots)
            db_session.commit()

    def test_concurrent_sales_report_generation(
        self, db_session: Session, load_test_data
    ):
        """Test concurrent sales report generation under load"""

        def generate_report(thread_id: int) -> Dict[str, Any]:
            """Generate a sales report in a thread"""
            service = SalesReportService(db_session)

            # Vary the date ranges to simulate different user requests
            days_back = 30 + (thread_id % 60)  # 30-90 days
            filters = SalesFilterRequest(
                date_from=date.today() - timedelta(days=days_back),
                date_to=date.today(),
                staff_ids=[1, 2, 3] if thread_id % 3 == 0 else None,
            )

            start_time = time.time()
            try:
                result = service.generate_sales_summary(filters)
                execution_time = time.time() - start_time

                return {
                    "thread_id": thread_id,
                    "success": True,
                    "execution_time": execution_time,
                    "total_revenue": float(result.total_revenue),
                    "total_orders": result.total_orders,
                }
            except Exception as e:
                return {
                    "thread_id": thread_id,
                    "success": False,
                    "execution_time": time.time() - start_time,
                    "error": str(e),
                }

        # Test with varying concurrent load levels
        concurrent_levels = [5, 10, 20, 50]

        for num_threads in concurrent_levels:
            print(f"\nTesting with {num_threads} concurrent threads...")

            start_time = time.time()

            with ThreadPoolExecutor(max_workers=num_threads) as executor:
                futures = [
                    executor.submit(generate_report, i) for i in range(num_threads)
                ]
                results = [future.result() for future in as_completed(futures)]

            total_time = time.time() - start_time

            # Analyze results
            successful_requests = [r for r in results if r["success"]]
            failed_requests = [r for r in results if not r["success"]]

            success_rate = len(successful_requests) / len(results) * 100
            avg_response_time = (
                sum(r["execution_time"] for r in successful_requests)
                / len(successful_requests)
                if successful_requests
                else 0
            )

            print(f"Success rate: {success_rate:.1f}%")
            print(f"Average response time: {avg_response_time:.3f}s")
            print(f"Total time: {total_time:.3f}s")
            print(f"Failed requests: {len(failed_requests)}")

            # Performance assertions
            assert (
                success_rate >= 95.0
            ), f"Success rate {success_rate:.1f}% too low with {num_threads} threads"
            assert (
                avg_response_time < 3.0
            ), f"Average response time {avg_response_time:.3f}s too high with {num_threads} threads"

            if failed_requests:
                print(
                    "Failed request errors:", [r["error"] for r in failed_requests[:3]]
                )

    def test_concurrent_detailed_report_generation(
        self, db_session: Session, load_test_data
    ):
        """Test concurrent detailed report generation with pagination"""

        def generate_detailed_report(thread_id: int) -> Dict[str, Any]:
            """Generate detailed report with pagination"""
            service = SalesReportService(db_session)

            # Vary pagination parameters
            page = (thread_id % 5) + 1  # Pages 1-5
            per_page = [50, 100, 200, 500][thread_id % 4]

            filters = SalesFilterRequest(
                date_from=date.today() - timedelta(days=30), date_to=date.today()
            )

            start_time = time.time()
            try:
                result = service.generate_detailed_sales_report(
                    filters=filters, page=page, per_page=per_page
                )
                execution_time = time.time() - start_time

                return {
                    "thread_id": thread_id,
                    "success": True,
                    "execution_time": execution_time,
                    "page": page,
                    "per_page": per_page,
                    "returned_items": len(result.items),
                    "total_items": result.total,
                }
            except Exception as e:
                return {
                    "thread_id": thread_id,
                    "success": False,
                    "execution_time": time.time() - start_time,
                    "error": str(e),
                }

        # Test with moderate concurrent load
        num_threads = 25

        with ThreadPoolExecutor(max_workers=num_threads) as executor:
            futures = [
                executor.submit(generate_detailed_report, i) for i in range(num_threads)
            ]
            results = [future.result() for future in as_completed(futures)]

        successful_requests = [r for r in results if r["success"]]

        success_rate = len(successful_requests) / len(results) * 100
        avg_response_time = sum(r["execution_time"] for r in successful_requests) / len(
            successful_requests
        )

        # Performance assertions for detailed reports
        assert (
            success_rate >= 90.0
        ), f"Detailed report success rate {success_rate:.1f}% too low"
        assert (
            avg_response_time < 5.0
        ), f"Detailed report average response time {avg_response_time:.3f}s too high"

    def test_mixed_workload_simulation(self, db_session: Session, load_test_data):
        """Test mixed workload simulating real user behavior"""

        operations = [
            ("sales_summary", 40),  # 40% of requests
            ("detailed_report", 30),  # 30% of requests
            ("staff_performance", 20),  # 20% of requests
            ("product_performance", 10),  # 10% of requests
        ]

        def mixed_operation(thread_id: int) -> Dict[str, Any]:
            """Execute mixed operations based on probability"""
            service = SalesReportService(db_session)

            # Determine operation based on thread_id
            operation_choice = thread_id % 100

            if operation_choice < 40:
                operation = "sales_summary"
            elif operation_choice < 70:
                operation = "detailed_report"
            elif operation_choice < 90:
                operation = "staff_performance"
            else:
                operation = "product_performance"

            filters = SalesFilterRequest(
                date_from=date.today() - timedelta(days=30), date_to=date.today()
            )

            start_time = time.time()
            try:
                if operation == "sales_summary":
                    result = service.generate_sales_summary(filters)
                elif operation == "detailed_report":
                    result = service.generate_detailed_sales_report(
                        filters, page=1, per_page=100
                    )
                elif operation == "staff_performance":
                    result = service.generate_staff_performance_report(
                        filters, page=1, per_page=50
                    )
                else:  # product_performance
                    result = service.generate_product_performance_report(
                        filters, page=1, per_page=50
                    )

                execution_time = time.time() - start_time

                return {
                    "thread_id": thread_id,
                    "operation": operation,
                    "success": True,
                    "execution_time": execution_time,
                }
            except Exception as e:
                return {
                    "thread_id": thread_id,
                    "operation": operation,
                    "success": False,
                    "execution_time": time.time() - start_time,
                    "error": str(e),
                }

        # Simulate 100 concurrent users with mixed operations
        num_threads = 100

        print(f"Simulating {num_threads} concurrent users with mixed workload...")

        start_time = time.time()

        with ThreadPoolExecutor(max_workers=min(num_threads, 50)) as executor:
            futures = [executor.submit(mixed_operation, i) for i in range(num_threads)]
            results = [future.result() for future in as_completed(futures)]

        total_time = time.time() - start_time

        # Analyze results by operation type
        operation_stats = {}
        for result in results:
            op = result["operation"]
            if op not in operation_stats:
                operation_stats[op] = {"success": 0, "failed": 0, "times": []}

            if result["success"]:
                operation_stats[op]["success"] += 1
                operation_stats[op]["times"].append(result["execution_time"])
            else:
                operation_stats[op]["failed"] += 1

        print(f"\nMixed workload results (Total time: {total_time:.2f}s):")
        for op, stats in operation_stats.items():
            total_ops = stats["success"] + stats["failed"]
            success_rate = stats["success"] / total_ops * 100 if total_ops > 0 else 0
            avg_time = (
                sum(stats["times"]) / len(stats["times"]) if stats["times"] else 0
            )

            print(
                f"{op}: {total_ops} requests, {success_rate:.1f}% success, {avg_time:.3f}s avg"
            )

            # Assert reasonable performance for each operation type
            assert (
                success_rate >= 85.0
            ), f"{op} success rate {success_rate:.1f}% too low"
            assert avg_time < 10.0, f"{op} average time {avg_time:.3f}s too high"

    def test_async_task_processor_load(self):
        """Test async task processor under high load"""
        import asyncio

        async def run_load_test():
            processor = AsyncTaskProcessor(max_workers=8)

            def mock_task_handler(task_data: Dict[str, Any], task) -> Dict[str, Any]:
                """Mock task handler with variable processing time"""
                import time
                import random

                # Simulate variable processing time (50-200ms)
                processing_time = 0.05 + (random.random() * 0.15)
                time.sleep(processing_time)

                task.progress = 100.0

                return {
                    "processed": True,
                    "data_size": len(str(task_data)),
                    "processing_time": processing_time,
                }

            processor.register_handler("load_test_task", mock_task_handler)

            # Submit many tasks with different priorities
            num_tasks = 200
            task_ids = []

            start_time = time.time()

            for i in range(num_tasks):
                priority = TaskPriority.HIGH if i % 10 == 0 else TaskPriority.NORMAL

                task_id = await processor.submit_task(
                    task_type="load_test_task",
                    task_data={"task_number": i, "data": "x" * (i % 1000)},
                    priority=priority,
                    created_by=1,
                )
                task_ids.append(task_id)

            submission_time = time.time() - start_time

            print(f"Submitted {num_tasks} tasks in {submission_time:.2f}s")
            assert (
                submission_time < 5.0
            ), f"Task submission took {submission_time:.2f}s, should be under 5s"

            # Wait for all tasks to complete
            completion_start = time.time()
            completed_tasks = 0

            while completed_tasks < num_tasks and (time.time() - completion_start) < 60:
                await asyncio.sleep(0.5)
                completed_tasks = sum(
                    1
                    for task_id in task_ids
                    if processor.get_task_status(task_id)
                    and processor.get_task_status(task_id).status.value
                    in ["completed", "failed"]
                )

                if completed_tasks % 50 == 0 and completed_tasks > 0:
                    print(f"Completed {completed_tasks}/{num_tasks} tasks...")

            completion_time = time.time() - completion_start

            # Analyze task completion
            final_stats = {"completed": 0, "failed": 0, "pending": 0, "running": 0}

            for task_id in task_ids:
                task = processor.get_task_status(task_id)
                if task:
                    final_stats[task.status.value] += 1

            completion_rate = final_stats["completed"] / num_tasks * 100

            print(f"Task completion: {completion_rate:.1f}% in {completion_time:.2f}s")
            print(f"Final stats: {final_stats}")

            # Performance assertions
            assert (
                completion_rate >= 95.0
            ), f"Task completion rate {completion_rate:.1f}% too low"
            assert (
                completion_time < 45.0
            ), f"Task completion took {completion_time:.2f}s, should be under 45s"

        # Run the async load test
        asyncio.run(run_load_test())

    def test_database_connection_pool_stress(self, db_session: Session, load_test_data):
        """Test database connection pool under stress"""

        def database_intensive_operation(thread_id: int) -> Dict[str, Any]:
            """Perform database-intensive operations"""
            service = SalesReportService(db_session)

            operations_per_thread = 10
            start_time = time.time()

            try:
                for i in range(operations_per_thread):
                    # Vary operations to stress different queries
                    if i % 3 == 0:
                        filters = SalesFilterRequest(
                            date_from=date.today() - timedelta(days=7),
                            date_to=date.today(),
                        )
                        service.generate_sales_summary(filters)
                    elif i % 3 == 1:
                        filters = SalesFilterRequest(
                            date_from=date.today() - timedelta(days=30),
                            date_to=date.today(),
                            staff_ids=[1, 2, 3],
                        )
                        service.generate_staff_performance_report(
                            filters, page=1, per_page=20
                        )
                    else:
                        filters = SalesFilterRequest(
                            date_from=date.today() - timedelta(days=14),
                            date_to=date.today(),
                            product_ids=[1, 2, 3, 4, 5],
                        )
                        service.generate_product_performance_report(
                            filters, page=1, per_page=20
                        )

                execution_time = time.time() - start_time

                return {
                    "thread_id": thread_id,
                    "success": True,
                    "execution_time": execution_time,
                    "operations_completed": operations_per_thread,
                }

            except Exception as e:
                return {
                    "thread_id": thread_id,
                    "success": False,
                    "execution_time": time.time() - start_time,
                    "error": str(e),
                }

        # Test with high concurrency to stress connection pool
        num_threads = 30

        print(f"Stress testing database connections with {num_threads} threads...")

        start_time = time.time()

        with ThreadPoolExecutor(max_workers=num_threads) as executor:
            futures = [
                executor.submit(database_intensive_operation, i)
                for i in range(num_threads)
            ]
            results = [future.result() for future in as_completed(futures)]

        total_time = time.time() - start_time

        successful_threads = [r for r in results if r["success"]]
        failed_threads = [r for r in results if not r["success"]]

        success_rate = len(successful_threads) / len(results) * 100
        total_operations = sum(
            r.get("operations_completed", 0) for r in successful_threads
        )
        avg_thread_time = (
            sum(r["execution_time"] for r in successful_threads)
            / len(successful_threads)
            if successful_threads
            else 0
        )

        print(f"Database stress test results:")
        print(f"Success rate: {success_rate:.1f}%")
        print(f"Total operations: {total_operations}")
        print(f"Average thread time: {avg_thread_time:.2f}s")
        print(f"Total test time: {total_time:.2f}s")
        print(f"Failed threads: {len(failed_threads)}")

        # Assert acceptable performance under stress
        assert (
            success_rate >= 85.0
        ), f"Database stress test success rate {success_rate:.1f}% too low"
        assert (
            avg_thread_time < 15.0
        ), f"Average thread time {avg_thread_time:.2f}s too high under stress"

        if failed_threads:
            print("Database stress failures:", [r["error"] for r in failed_threads[:3]])

    def test_memory_usage_under_load(self, db_session: Session, load_test_data):
        """Test memory usage patterns under sustained load"""
        import psutil
        import os

        process = psutil.Process(os.getpid())

        def monitor_memory():
            """Monitor memory usage during load test"""
            memory_samples = []

            for _ in range(30):  # Monitor for 30 seconds
                memory_mb = process.memory_info().rss / 1024 / 1024
                memory_samples.append(memory_mb)
                time.sleep(1)

            return memory_samples

        def sustained_load():
            """Generate sustained load"""
            service = SalesReportService(db_session)

            for i in range(50):  # 50 operations
                filters = SalesFilterRequest(
                    date_from=date.today() - timedelta(days=30), date_to=date.today()
                )

                # Alternate between different operations
                if i % 3 == 0:
                    service.generate_sales_summary(filters)
                elif i % 3 == 1:
                    service.generate_detailed_sales_report(
                        filters, page=1, per_page=100
                    )
                else:
                    service.generate_staff_performance_report(
                        filters, page=1, per_page=50
                    )

                time.sleep(0.5)  # Small delay between operations

        # Start memory monitoring in background
        memory_thread = threading.Thread(target=monitor_memory)
        memory_samples = []

        initial_memory = process.memory_info().rss / 1024 / 1024

        # Run sustained load
        load_thread = threading.Thread(target=sustained_load)
        load_thread.start()

        # Monitor memory during load
        for _ in range(30):
            memory_mb = process.memory_info().rss / 1024 / 1024
            memory_samples.append(memory_mb)
            time.sleep(1)

        load_thread.join()

        final_memory = process.memory_info().rss / 1024 / 1024
        max_memory = max(memory_samples)
        avg_memory = sum(memory_samples) / len(memory_samples)

        memory_growth = final_memory - initial_memory
        peak_memory_increase = max_memory - initial_memory

        print(f"Memory usage analysis:")
        print(f"Initial memory: {initial_memory:.1f} MB")
        print(f"Final memory: {final_memory:.1f} MB")
        print(f"Peak memory: {max_memory:.1f} MB")
        print(f"Average during load: {avg_memory:.1f} MB")
        print(f"Memory growth: {memory_growth:.1f} MB")
        print(f"Peak increase: {peak_memory_increase:.1f} MB")

        # Memory usage assertions
        assert memory_growth < 50, f"Memory growth {memory_growth:.1f} MB too high"
        assert (
            peak_memory_increase < 100
        ), f"Peak memory increase {peak_memory_increase:.1f} MB too high"

        # Force garbage collection and check for memory recovery
        import gc

        gc.collect()
        time.sleep(2)

        post_gc_memory = process.memory_info().rss / 1024 / 1024
        memory_recovery = max_memory - post_gc_memory

        print(f"Post-GC memory: {post_gc_memory:.1f} MB")
        print(f"Memory recovered: {memory_recovery:.1f} MB")

        # Should recover most of the memory
        assert (
            memory_recovery > peak_memory_increase * 0.5
        ), "Poor memory recovery after GC"
