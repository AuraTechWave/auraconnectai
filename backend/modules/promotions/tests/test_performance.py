# backend/modules/promotions/tests/test_performance.py

import pytest
import time
import asyncio
import concurrent.futures
from datetime import datetime, timedelta
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from core.database import Base
from modules.promotions.models.promotion_models import *
from modules.promotions.services.discount_service import DiscountCalculationService
from modules.promotions.services.coupon_service import CouponService
from modules.promotions.services.analytics_service import PromotionAnalyticsService


class TestPromotionPerformance:
    """Performance tests for promotion system components"""
    
    @pytest.fixture(scope="class")
    def perf_db_session(self):
        """Create performance test database with sample data"""
        engine = create_engine("sqlite:///:memory:", echo=False)
        Base.metadata.create_all(engine)
        TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
        session = TestingSessionLocal()
        
        # Create sample promotions for performance testing
        promotions = []
        for i in range(100):  # 100 promotions
            promotion = Promotion(
                name=f"Perf Test Promotion {i}",
                description=f"Performance test promotion {i}",
                promotion_type=PromotionType.PERCENTAGE_DISCOUNT,
                discount_type=DiscountType.PERCENTAGE,
                discount_value=10.0 + (i % 20),  # Vary discount values
                status=PromotionStatus.ACTIVE,
                start_date=datetime.utcnow() - timedelta(days=1),
                end_date=datetime.utcnow() + timedelta(days=30),
                max_uses=1000,
                current_uses=i % 50,  # Vary usage
                priority=i % 10,  # Vary priority
                minimum_order_amount=50.0 if i % 3 == 0 else None,
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow()
            )
            promotions.append(promotion)
        
        session.add_all(promotions)
        session.commit()
        
        yield session, promotions
        session.close()
    
    def test_bulk_discount_calculation_performance(self, perf_db_session):
        """Test performance of calculating discounts for multiple promotions"""
        session, promotions = perf_db_session
        discount_service = DiscountCalculationService(session)
        
        # Simulate large order with multiple items
        order_items = [
            {'product_id': i, 'quantity': 2, 'unit_price': 50.0 + i, 'subtotal': (50.0 + i) * 2}
            for i in range(50)  # 50 different products
        ]
        
        promotion_ids = [p.id for p in promotions[:20]]  # Test with 20 promotions
        
        # Measure performance
        start_time = time.time()
        
        result = discount_service.calculate_multiple_promotions(
            promotion_ids, order_items, customer_id=1
        )
        
        calculation_time = time.time() - start_time
        
        # Performance assertions
        assert calculation_time < 2.0  # Should complete within 2 seconds
        assert 'applied_promotions' in result
        assert 'total_discount' in result
        
        print(f"Bulk discount calculation time: {calculation_time:.3f}s for {len(promotion_ids)} promotions")
    
    def test_coupon_generation_performance(self, perf_db_session):
        """Test performance of bulk coupon generation"""
        session, promotions = perf_db_session
        coupon_service = CouponService(session)
        
        promotion = promotions[0]
        
        # Test different batch sizes
        batch_sizes = [100, 500, 1000, 2000]
        
        for batch_size in batch_sizes:
            start_time = time.time()
            
            coupons = coupon_service.create_bulk_coupons(
                promotion_id=promotion.id,
                count=batch_size,
                coupon_config={'max_uses': 1}
            )
            
            generation_time = time.time() - start_time
            
            # Performance assertions
            assert len(coupons) == batch_size
            assert generation_time < (batch_size / 100)  # Should generate ~100 coupons per second minimum
            
            # Verify uniqueness
            codes = [c.code for c in coupons]
            assert len(set(codes)) == len(codes)
            
            print(f"Generated {batch_size} coupons in {generation_time:.3f}s ({batch_size/generation_time:.1f} coupons/sec)")
    
    def test_promotion_eligibility_check_performance(self, perf_db_session):
        """Test performance of checking promotion eligibility for many promotions"""
        session, promotions = perf_db_session
        
        from modules.promotions.services.promotion_service import PromotionService
        promotion_service = PromotionService(session)
        
        # Test eligibility check for many promotions
        start_time = time.time()
        
        eligible_promotions = []
        for promotion in promotions:
            is_eligible, reason = promotion_service.check_promotion_eligibility(
                promotion.id, customer_id=1
            )
            if is_eligible:
                eligible_promotions.append(promotion)
        
        check_time = time.time() - start_time
        
        # Performance assertions
        assert check_time < 1.0  # Should check 100 promotions within 1 second
        assert len(eligible_promotions) > 0
        
        print(f"Checked eligibility for {len(promotions)} promotions in {check_time:.3f}s")
    
    def test_analytics_aggregation_performance(self, perf_db_session):
        """Test performance of analytics aggregation with large datasets"""
        session, promotions = perf_db_session
        
        # Create sample usage data
        usage_records = []
        for i in range(1000):  # 1000 usage records
            usage = PromotionUsage(
                promotion_id=promotions[i % len(promotions)].id,
                customer_id=(i % 100) + 1,  # 100 different customers
                order_id=i + 1,
                discount_amount=10.0 + (i % 50),
                final_order_amount=100.0 + (i % 200),
                created_at=datetime.utcnow() - timedelta(hours=i % 168)  # Spread over a week
            )
            usage_records.append(usage)
        
        session.add_all(usage_records)
        session.commit()
        
        analytics_service = PromotionAnalyticsService(session)
        
        # Test daily aggregation performance
        start_time = time.time()
        
        target_date = datetime.utcnow() - timedelta(days=1)
        aggregates = analytics_service.generate_daily_analytics_aggregates(target_date)
        
        aggregation_time = time.time() - start_time
        
        # Performance assertions
        assert aggregation_time < 5.0  # Should complete within 5 seconds
        assert 'promotion_aggregates' in aggregates
        
        print(f"Daily analytics aggregation completed in {aggregation_time:.3f}s")
        
        # Test performance report generation
        start_time = time.time()
        
        report = analytics_service.generate_promotion_performance_report(
            start_date=datetime.utcnow() - timedelta(days=7),
            end_date=datetime.utcnow()
        )
        
        report_time = time.time() - start_time
        
        # Performance assertions
        assert report_time < 3.0  # Should complete within 3 seconds
        assert 'promotion_details' in report
        
        print(f"Performance report generated in {report_time:.3f}s")
    
    def test_concurrent_coupon_validation_performance(self, perf_db_session):
        """Test performance under concurrent coupon validation requests"""
        session, promotions = perf_db_session
        coupon_service = CouponService(session)
        
        # Create test coupons
        promotion = promotions[0]
        coupons = coupon_service.create_bulk_coupons(
            promotion_id=promotion.id,
            count=100,
            coupon_config={'max_uses': 10}
        )
        
        def validate_coupon(coupon_code):
            """Function to validate a coupon (simulates concurrent requests)"""
            is_valid, reason, coupon = coupon_service.validate_coupon_code(
                coupon_code, customer_id=1
            )
            return is_valid
        
        # Test concurrent validation
        start_time = time.time()
        
        with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
            # Submit 100 concurrent validation requests
            futures = [
                executor.submit(validate_coupon, coupon.code)
                for coupon in coupons
            ]
            
            # Wait for all to complete
            results = [future.result() for future in concurrent.futures.as_completed(futures)]
        
        concurrent_time = time.time() - start_time
        
        # Performance assertions
        assert concurrent_time < 5.0  # Should handle 100 concurrent validations within 5 seconds
        assert all(results)  # All validations should succeed
        
        print(f"100 concurrent coupon validations completed in {concurrent_time:.3f}s")
    
    def test_database_query_optimization(self, perf_db_session):
        """Test database query performance and optimization"""
        session, promotions = perf_db_session
        
        # Test complex query performance
        start_time = time.time()
        
        # Simulate complex promotion lookup query
        complex_query = session.query(Promotion).filter(
            Promotion.status == PromotionStatus.ACTIVE,
            Promotion.start_date <= datetime.utcnow(),
            Promotion.end_date >= datetime.utcnow(),
            Promotion.current_uses < Promotion.max_uses
        ).order_by(
            Promotion.priority.desc(),
            Promotion.discount_value.desc()
        ).limit(20)
        
        results = complex_query.all()
        query_time = time.time() - start_time
        
        # Performance assertions
        assert query_time < 0.5  # Complex query should complete within 0.5 seconds
        assert len(results) > 0
        
        print(f"Complex promotion query completed in {query_time:.3f}s")
        
        # Test aggregation query performance
        start_time = time.time()
        
        from sqlalchemy import func
        aggregation_query = session.query(
            Promotion.promotion_type,
            func.count(Promotion.id).label('count'),
            func.avg(Promotion.discount_value).label('avg_discount'),
            func.sum(Promotion.current_uses).label('total_uses')
        ).filter(
            Promotion.status == PromotionStatus.ACTIVE
        ).group_by(Promotion.promotion_type)
        
        agg_results = aggregation_query.all()
        agg_time = time.time() - start_time
        
        # Performance assertions
        assert agg_time < 0.5  # Aggregation should complete within 0.5 seconds
        assert len(agg_results) > 0
        
        print(f"Aggregation query completed in {agg_time:.3f}s")
    
    def test_memory_usage_bulk_operations(self, perf_db_session):
        """Test memory usage during bulk operations"""
        session, promotions = perf_db_session
        
        import psutil
        import os
        
        process = psutil.Process(os.getpid())
        initial_memory = process.memory_info().rss / 1024 / 1024  # MB
        
        # Perform memory-intensive bulk operation
        coupon_service = CouponService(session)
        promotion = promotions[0]
        
        # Generate large batch of coupons
        large_batch_size = 5000
        coupons = coupon_service.create_bulk_coupons(
            promotion_id=promotion.id,
            count=large_batch_size,
            coupon_config={'max_uses': 1}
        )
        
        peak_memory = process.memory_info().rss / 1024 / 1024  # MB
        memory_increase = peak_memory - initial_memory
        
        # Memory usage assertions
        assert memory_increase < 100  # Should not use more than 100MB additional memory
        assert len(coupons) == large_batch_size
        
        print(f"Memory usage for {large_batch_size} coupons: {memory_increase:.1f}MB increase")
    
    def test_cache_performance_simulation(self, perf_db_session):
        """Simulate cache performance for repeated operations"""
        session, promotions = perf_db_session
        
        from modules.promotions.services.promotion_service import PromotionService
        promotion_service = PromotionService(session)
        
        # Simulate cache miss (first access)
        start_time = time.time()
        
        active_promotions = promotion_service.get_active_promotions()
        
        first_access_time = time.time() - start_time
        
        # Simulate cache hit (repeated access)
        start_time = time.time()
        
        # In a real implementation, this would hit cache
        active_promotions_cached = promotion_service.get_active_promotions()
        
        second_access_time = time.time() - start_time
        
        # Performance comparison
        assert len(active_promotions) == len(active_promotions_cached)
        
        print(f"First access (cache miss): {first_access_time:.3f}s")
        print(f"Second access (cache simulation): {second_access_time:.3f}s")
        
        # Note: In real implementation with Redis cache, second access should be much faster
    
    @pytest.mark.asyncio
    async def test_async_operations_performance(self, perf_db_session):
        """Test performance of async operations"""
        session, promotions = perf_db_session
        
        async def async_promotion_check(promotion_id):
            """Simulate async promotion eligibility check"""
            # Simulate async database operation
            await asyncio.sleep(0.01)  # 10ms simulated DB latency
            return True
        
        # Test concurrent async operations
        start_time = time.time()
        
        promotion_ids = [p.id for p in promotions[:50]]
        
        # Run 50 async operations concurrently
        tasks = [async_promotion_check(pid) for pid in promotion_ids]
        results = await asyncio.gather(*tasks)
        
        async_time = time.time() - start_time
        
        # Performance assertions
        assert async_time < 1.0  # Should complete much faster than sequential (0.5s vs 50*0.01=0.5s)
        assert all(results)
        assert len(results) == 50
        
        print(f"50 async operations completed in {async_time:.3f}s")


class TestPromotionLoadTesting:
    """Load testing scenarios for promotion system"""
    
    def test_high_volume_coupon_usage_simulation(self):
        """Simulate high volume coupon usage scenario"""
        # This would typically use a separate load testing framework
        # but we can simulate basic load patterns
        
        start_time = time.time()
        
        # Simulate 1000 rapid coupon validations
        validation_count = 0
        for i in range(1000):
            # Simulate validation logic (without actual DB calls for speed)
            coupon_code = f"TEST{i:04d}"
            if len(coupon_code) == 8:  # Basic validation
                validation_count += 1
        
        simulation_time = time.time() - start_time
        
        # Performance expectations
        assert validation_count == 1000
        assert simulation_time < 1.0  # Should handle 1000 validations per second
        
        throughput = validation_count / simulation_time
        print(f"Simulated validation throughput: {throughput:.1f} validations/second")
    
    def test_promotion_calculation_load_simulation(self):
        """Simulate load on promotion calculation system"""
        
        def calculate_discount_simulation(order_total, discount_percentage):
            """Simulate discount calculation"""
            return order_total * (discount_percentage / 100)
        
        start_time = time.time()
        
        # Simulate 10,000 discount calculations
        calculation_count = 0
        total_discount = 0
        
        for i in range(10000):
            order_total = 100.0 + (i % 500)  # Vary order totals
            discount_percentage = 10.0 + (i % 20)  # Vary discount percentages
            
            discount = calculate_discount_simulation(order_total, discount_percentage)
            total_discount += discount
            calculation_count += 1
        
        calculation_time = time.time() - start_time
        
        # Performance expectations
        assert calculation_count == 10000
        assert calculation_time < 2.0  # Should handle 5000+ calculations per second
        
        throughput = calculation_count / calculation_time
        print(f"Discount calculation throughput: {throughput:.1f} calculations/second")
        print(f"Total discount calculated: ${total_discount:.2f}")


# Benchmark utilities
class PromotionBenchmark:
    """Utility class for benchmarking promotion operations"""
    
    @staticmethod
    def benchmark_function(func, *args, **kwargs):
        """Benchmark a function execution"""
        start_time = time.time()
        result = func(*args, **kwargs)
        execution_time = time.time() - start_time
        return result, execution_time
    
    @staticmethod
    def benchmark_async_function(async_func, *args, **kwargs):
        """Benchmark an async function execution"""
        async def _benchmark():
            start_time = time.time()
            result = await async_func(*args, **kwargs)
            execution_time = time.time() - start_time
            return result, execution_time
        
        return asyncio.run(_benchmark())
    
    @staticmethod
    def memory_profile(func, *args, **kwargs):
        """Profile memory usage of a function"""
        import psutil
        import os
        
        process = psutil.Process(os.getpid())
        initial_memory = process.memory_info().rss
        
        result = func(*args, **kwargs)
        
        final_memory = process.memory_info().rss
        memory_delta = final_memory - initial_memory
        
        return result, memory_delta
    
    @staticmethod
    def stress_test(func, iterations=1000, *args, **kwargs):
        """Perform stress testing on a function"""
        start_time = time.time()
        errors = 0
        
        for i in range(iterations):
            try:
                func(*args, **kwargs)
            except Exception as e:
                errors += 1
                if errors > iterations * 0.01:  # Allow 1% error rate
                    raise Exception(f"Too many errors in stress test: {errors}/{i+1}")
        
        total_time = time.time() - start_time
        success_rate = ((iterations - errors) / iterations) * 100
        
        return {
            'iterations': iterations,
            'total_time': total_time,
            'errors': errors,
            'success_rate': success_rate,
            'throughput': iterations / total_time
        }