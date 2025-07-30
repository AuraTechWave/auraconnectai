# backend/modules/payroll/tests/test_payroll_performance.py

"""
Performance tests for payroll batch processing.

Tests system performance under various load conditions
to ensure scalability and identify bottlenecks.
"""

import pytest
import asyncio
import time
from datetime import date, datetime, timedelta
from decimal import Decimal
from unittest.mock import Mock, MagicMock, patch, AsyncMock
from concurrent.futures import ThreadPoolExecutor
import statistics
import random

from ..services.batch_payroll_service import BatchPayrollService
from ..services.payroll_service import PayrollService
from ..schemas.batch_processing_schemas import CalculationOptions
from ..models.employee_payment import EmployeePayment
from ....staff.models.staff import Staff
from ....staff.models.timesheet import Timesheet


class TestPayrollPerformance:
    """Test payroll system performance under load."""
    
    @pytest.fixture
    def mock_db(self):
        """Create mock database with simulated latency."""
        db = MagicMock()
        
        # Simulate database query latency
        async def query_with_delay(*args, **kwargs):
            await asyncio.sleep(0.001)  # 1ms latency
            return MagicMock()
        
        db.query = AsyncMock(side_effect=query_with_delay)
        db.commit = AsyncMock()
        db.add = Mock()
        db.refresh = Mock()
        return db
    
    @pytest.fixture
    def generate_employees(self):
        """Generate large number of test employees."""
        def _generate(count: int):
            employees = []
            for i in range(count):
                emp = Mock(spec=Staff)
                emp.id = i + 1
                emp.full_name = f"Employee {i + 1}"
                emp.employee_code = f"EMP{str(i + 1).zfill(6)}"
                emp.department = random.choice(["Engineering", "Sales", "Support", "HR", "Finance"])
                emp.location = random.choice(["california", "new_york", "texas", "florida"])
                emp.employment_type = random.choice(["salaried", "hourly"])
                if emp.employment_type == "salaried":
                    emp.annual_salary = Decimal(str(random.randint(50000, 150000)))
                else:
                    emp.hourly_rate = Decimal(str(random.randint(15, 75)))
                emp.is_active = True
                employees.append(emp)
            return employees
        return _generate
    
    @pytest.mark.asyncio
    @pytest.mark.performance
    async def test_batch_processing_100_employees(self, mock_db, generate_employees):
        """Test batch processing performance with 100 employees."""
        # Setup
        employees = generate_employees(100)
        batch_service = BatchPayrollService(mock_db)
        
        # Mock database responses
        mock_db.query.return_value.filter.return_value.all.return_value = employees
        
        # Mock payroll calculations
        with patch.object(batch_service.payroll_service, 'calculate_payroll') as mock_calc:
            mock_calc.return_value = Mock(
                employee_id=1,
                gross_pay=Decimal("2500.00"),
                net_pay=Decimal("1875.00")
            )
            
            # Measure performance
            start_time = time.time()
            
            results = await batch_service.process_batch(
                employee_ids=None,
                pay_period_start=date(2024, 1, 1),
                pay_period_end=date(2024, 1, 14)
            )
            
            end_time = time.time()
            processing_time = end_time - start_time
        
        # Verify results
        assert len(results) == 100
        assert processing_time < 5.0  # Should complete within 5 seconds
        
        # Calculate metrics
        avg_time_per_employee = processing_time / 100
        assert avg_time_per_employee < 0.05  # Less than 50ms per employee
    
    @pytest.mark.asyncio
    @pytest.mark.performance
    async def test_batch_processing_1000_employees(self, mock_db, generate_employees):
        """Test batch processing performance with 1000 employees."""
        # Setup
        employees = generate_employees(1000)
        batch_service = BatchPayrollService(mock_db)
        
        # Mock database responses
        mock_db.query.return_value.filter.return_value.all.return_value = employees
        
        # Track progress
        progress_updates = []
        
        async def progress_callback(current, total, name):
            progress_updates.append({
                "timestamp": time.time(),
                "current": current,
                "total": total
            })
        
        # Mock payroll calculations with variable processing time
        async def mock_calculation(*args, **kwargs):
            # Simulate variable processing time (1-5ms)
            await asyncio.sleep(random.uniform(0.001, 0.005))
            return Mock(
                employee_id=kwargs.get('employee_id', 1),
                gross_pay=Decimal(str(random.uniform(2000, 5000))),
                net_pay=Decimal(str(random.uniform(1500, 3750)))
            )
        
        with patch.object(batch_service.payroll_service, 'calculate_payroll', mock_calculation):
            # Measure performance
            start_time = time.time()
            
            results = await batch_service.process_batch(
                employee_ids=None,
                pay_period_start=date(2024, 1, 1),
                pay_period_end=date(2024, 1, 14),
                progress_callback=progress_callback
            )
            
            end_time = time.time()
            processing_time = end_time - start_time
        
        # Verify results
        assert len(results) == 1000
        assert processing_time < 30.0  # Should complete within 30 seconds
        
        # Analyze progress updates
        if len(progress_updates) > 1:
            # Calculate processing rate
            rates = []
            for i in range(1, len(progress_updates)):
                time_diff = progress_updates[i]["timestamp"] - progress_updates[i-1]["timestamp"]
                emp_diff = progress_updates[i]["current"] - progress_updates[i-1]["current"]
                if time_diff > 0:
                    rate = emp_diff / time_diff
                    rates.append(rate)
            
            avg_rate = statistics.mean(rates) if rates else 0
            assert avg_rate > 20  # Should process at least 20 employees per second
    
    @pytest.mark.asyncio
    @pytest.mark.performance
    async def test_concurrent_batch_processing(self, mock_db, generate_employees):
        """Test multiple concurrent batch processing jobs."""
        # Setup
        batch_service = BatchPayrollService(mock_db)
        
        # Create 5 departments with 50 employees each
        departments = ["Engineering", "Sales", "Support", "HR", "Finance"]
        all_employees = []
        
        for i, dept in enumerate(departments):
            employees = generate_employees(50)
            for emp in employees:
                emp.department = dept
                emp.id = i * 50 + emp.id
            all_employees.extend(employees)
        
        # Mock database to return different employees for each department
        def mock_query_filter(model):
            query = MagicMock()
            
            def filter_impl(**kwargs):
                if 'department' in str(kwargs):
                    # Return employees for specific department
                    dept_employees = [e for e in all_employees if e.department in str(kwargs)]
                    query.all.return_value = dept_employees
                else:
                    query.all.return_value = all_employees
                return query
            
            query.filter = filter_impl
            return query
        
        mock_db.query = mock_query_filter
        
        # Mock payroll calculations
        with patch.object(batch_service.payroll_service, 'calculate_payroll') as mock_calc:
            mock_calc.return_value = Mock(gross_pay=Decimal("2500.00"))
            
            # Run concurrent batch jobs
            start_time = time.time()
            
            tasks = []
            for dept in departments:
                task = batch_service.process_batch(
                    employee_ids=None,
                    pay_period_start=date(2024, 1, 1),
                    pay_period_end=date(2024, 1, 14),
                    department=dept
                )
                tasks.append(task)
            
            # Wait for all tasks to complete
            results = await asyncio.gather(*tasks)
            
            end_time = time.time()
            total_time = end_time - start_time
        
        # Verify results
        assert len(results) == 5  # 5 department batches
        total_employees = sum(len(r) for r in results)
        assert total_employees == 250
        
        # Performance check - concurrent processing should be faster
        assert total_time < 10.0  # Should complete within 10 seconds
        
        # Calculate speedup factor
        sequential_estimate = 0.05 * 250  # 50ms per employee
        speedup = sequential_estimate / total_time
        assert speedup > 2.0  # At least 2x speedup from concurrency
    
    @pytest.mark.asyncio
    @pytest.mark.performance
    async def test_memory_efficiency(self, mock_db, generate_employees):
        """Test memory efficiency with large batches."""
        # Setup
        batch_service = BatchPayrollService(mock_db)
        
        # Process in chunks to test memory efficiency
        chunk_sizes = [100, 500, 1000]
        memory_usage = []
        
        for chunk_size in chunk_sizes:
            employees = generate_employees(chunk_size)
            mock_db.query.return_value.filter.return_value.all.return_value = employees
            
            # Mock payroll calculations
            with patch.object(batch_service.payroll_service, 'calculate_payroll') as mock_calc:
                mock_calc.return_value = Mock(gross_pay=Decimal("2500.00"))
                
                # Measure memory before
                import psutil
                process = psutil.Process()
                mem_before = process.memory_info().rss / 1024 / 1024  # MB
                
                # Process batch
                results = await batch_service.process_batch(
                    employee_ids=None,
                    pay_period_start=date(2024, 1, 1),
                    pay_period_end=date(2024, 1, 14)
                )
                
                # Measure memory after
                mem_after = process.memory_info().rss / 1024 / 1024  # MB
                mem_increase = mem_after - mem_before
                
                memory_usage.append({
                    "chunk_size": chunk_size,
                    "memory_increase": mem_increase,
                    "memory_per_employee": mem_increase / chunk_size
                })
        
        # Verify memory scales linearly
        # Memory per employee should be relatively constant
        mem_per_emp_values = [m["memory_per_employee"] for m in memory_usage]
        avg_mem_per_emp = statistics.mean(mem_per_emp_values)
        std_dev = statistics.stdev(mem_per_emp_values) if len(mem_per_emp_values) > 1 else 0
        
        # Standard deviation should be small relative to mean
        if avg_mem_per_emp > 0:
            coefficient_of_variation = std_dev / avg_mem_per_emp
            assert coefficient_of_variation < 0.3  # Less than 30% variation
    
    @pytest.mark.asyncio
    @pytest.mark.performance
    async def test_database_query_optimization(self, mock_db):
        """Test database query optimization strategies."""
        # Setup
        batch_service = BatchPayrollService(mock_db)
        
        # Track database queries
        query_count = 0
        query_times = []
        
        async def track_query(*args, **kwargs):
            nonlocal query_count
            query_count += 1
            
            start = time.time()
            await asyncio.sleep(0.002)  # Simulate 2ms query
            end = time.time()
            query_times.append(end - start)
            
            return MagicMock()
        
        mock_db.query = AsyncMock(side_effect=track_query)
        
        # Test different query strategies
        strategies = [
            {"batch_size": 10, "prefetch": False},
            {"batch_size": 50, "prefetch": True},
            {"batch_size": 100, "prefetch": True}
        ]
        
        results = []
        for strategy in strategies:
            query_count = 0
            query_times.clear()
            
            # Process with strategy
            start_time = time.time()
            
            # Simulate processing with batching
            for i in range(0, 100, strategy["batch_size"]):
                if strategy["prefetch"]:
                    # Simulate prefetching related data
                    await mock_db.query()  # Main query
                    await mock_db.query()  # Prefetch timesheets
                    await mock_db.query()  # Prefetch policies
                else:
                    # Simulate N+1 queries
                    await mock_db.query()  # Main query
                    for _ in range(min(strategy["batch_size"], 100 - i)):
                        await mock_db.query()  # Individual queries
            
            end_time = time.time()
            
            results.append({
                "strategy": strategy,
                "total_time": end_time - start_time,
                "query_count": query_count,
                "avg_query_time": statistics.mean(query_times) if query_times else 0
            })
        
        # Verify optimization improves performance
        # Larger batches with prefetching should be faster
        assert results[2]["total_time"] < results[0]["total_time"]
        assert results[2]["query_count"] < results[0]["query_count"]
    
    @pytest.mark.asyncio
    @pytest.mark.performance 
    async def test_error_recovery_performance(self, mock_db, generate_employees):
        """Test performance impact of error handling and recovery."""
        # Setup
        employees = generate_employees(100)
        batch_service = BatchPayrollService(mock_db)
        
        mock_db.query.return_value.filter.return_value.all.return_value = employees
        
        # Simulate 10% failure rate
        calculation_count = 0
        
        async def mock_calculation_with_errors(*args, **kwargs):
            nonlocal calculation_count
            calculation_count += 1
            
            if calculation_count % 10 == 0:
                # Simulate error
                raise Exception("Calculation error")
            
            return Mock(
                employee_id=kwargs.get('employee_id', 1),
                gross_pay=Decimal("2500.00")
            )
        
        with patch.object(batch_service.payroll_service, 'calculate_payroll',
                         mock_calculation_with_errors):
            # Measure performance with error handling
            start_time = time.time()
            
            results = await batch_service.process_batch(
                employee_ids=None,
                pay_period_start=date(2024, 1, 1),
                pay_period_end=date(2024, 1, 14)
            )
            
            end_time = time.time()
            processing_time = end_time - start_time
        
        # Verify results
        successful = sum(1 for r in results if r.success)
        failed = sum(1 for r in results if not r.success)
        
        assert successful == 90
        assert failed == 10
        
        # Error handling shouldn't significantly impact performance
        # Should still be under 100ms per employee on average
        avg_time = processing_time / 100
        assert avg_time < 0.1
    
    @pytest.mark.asyncio
    @pytest.mark.performance
    async def test_export_performance(self, mock_db):
        """Test performance of payment export operations."""
        from ..services.payment_export_service import PaymentExportService
        
        export_service = PaymentExportService(mock_db)
        
        # Generate mock payments
        payments = []
        for i in range(1000):
            payment = Mock(spec=EmployeePayment)
            payment.id = i + 1
            payment.employee_id = i + 1
            payment.employee = Mock(
                full_name=f"Employee {i + 1}",
                employee_code=f"EMP{str(i + 1).zfill(6)}"
            )
            payment.gross_pay = Decimal(str(random.uniform(2000, 5000)))
            payment.net_pay = payment.gross_pay * Decimal("0.75")
            payments.append(payment)
        
        mock_db.query.return_value.filter.return_value.all.return_value = payments
        
        # Test different export formats
        formats = ["csv", "json", "excel"]
        export_times = {}
        
        for format in formats:
            with patch('builtins.open', create=True):
                start_time = time.time()
                
                result = await export_service.export_payments(
                    start_date=date(2024, 1, 1),
                    end_date=date(2024, 1, 31),
                    format=format
                )
                
                end_time = time.time()
                export_times[format] = end_time - start_time
        
        # Verify performance
        # CSV should be fastest, Excel slowest
        assert export_times["csv"] < export_times["json"]
        assert export_times["json"] < export_times["excel"]
        
        # All formats should complete within reasonable time
        for format, time_taken in export_times.items():
            assert time_taken < 5.0  # 5 seconds for 1000 records