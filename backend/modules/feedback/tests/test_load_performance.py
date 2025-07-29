# backend/modules/feedback/tests/test_load_performance.py

import pytest
import asyncio
import time
import statistics
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List, Dict, Any
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from backend.modules.feedback.services.analytics_service import FeedbackAnalyticsService
from backend.modules.feedback.services.aggregation_service import ReviewAggregationService
from backend.modules.feedback.services.sentiment_service import SentimentAnalysisService


class TestLoadPerformance:
    """Load and performance tests for feedback analytics endpoints"""
    
    def test_analytics_overview_load(self, client: TestClient, large_dataset, auth_headers_staff):
        """Test analytics overview endpoint under load"""
        
        def make_request():
            """Make a single request to analytics overview"""
            start_time = time.time()
            response = client.get("/feedback/analytics/overview", headers=auth_headers_staff)
            end_time = time.time()
            
            return {
                "status_code": response.status_code,
                "response_time": end_time - start_time,
                "success": response.status_code == 200
            }
        
        # Run concurrent requests
        num_requests = 20
        with ThreadPoolExecutor(max_workers=5) as executor:
            futures = [executor.submit(make_request) for _ in range(num_requests)]
            results = [future.result() for future in as_completed(futures)]
        
        # Analyze results
        successful_requests = [r for r in results if r["success"]]
        response_times = [r["response_time"] for r in successful_requests]
        
        # Assertions
        assert len(successful_requests) == num_requests, "All requests should succeed"
        assert max(response_times) < 5.0, "No request should take longer than 5 seconds"
        assert statistics.mean(response_times) < 2.0, "Average response time should be under 2 seconds"
        
        print(f"Analytics Overview Load Test Results:")
        print(f"  Successful requests: {len(successful_requests)}/{num_requests}")
        print(f"  Average response time: {statistics.mean(response_times):.3f}s")
        print(f"  Max response time: {max(response_times):.3f}s")
        print(f"  Min response time: {min(response_times):.3f}s")
    
    def test_review_insights_load(self, client: TestClient, multiple_reviews, auth_headers_staff):
        """Test review insights endpoint under load"""
        
        def make_insights_request(entity_type: str, entity_id: int):
            """Make a single request to review insights"""
            start_time = time.time()
            response = client.get(
                f"/reviews/{entity_type}/{entity_id}/insights",
                headers=auth_headers_staff
            )
            end_time = time.time()
            
            return {
                "entity_type": entity_type,
                "entity_id": entity_id,
                "status_code": response.status_code,
                "response_time": end_time - start_time,
                "success": response.status_code == 200
            }
        
        # Test different entities concurrently
        test_entities = [
            ("product", 101),
            ("product", 102),
            ("service", 201),
            ("service", 202)
        ]
        
        # Run multiple requests for each entity
        with ThreadPoolExecutor(max_workers=8) as executor:
            futures = []
            for _ in range(5):  # 5 requests per entity
                for entity_type, entity_id in test_entities:
                    future = executor.submit(make_insights_request, entity_type, entity_id)
                    futures.append(future)
            
            results = [future.result() for future in as_completed(futures)]
        
        # Analyze results
        successful_requests = [r for r in results if r["success"]]
        response_times = [r["response_time"] for r in successful_requests]
        
        # Assertions
        assert len(successful_requests) >= len(results) * 0.9, "At least 90% of requests should succeed"
        assert max(response_times) < 3.0, "No insights request should take longer than 3 seconds"
        
        print(f"Review Insights Load Test Results:")
        print(f"  Successful requests: {len(successful_requests)}/{len(results)}")
        print(f"  Average response time: {statistics.mean(response_times):.3f}s")
        print(f"  Max response time: {max(response_times):.3f}s")
    
    def test_reviews_list_pagination_load(self, client: TestClient, large_dataset):
        """Test reviews list endpoint pagination under load"""
        
        def fetch_page(page: int, per_page: int = 20):
            """Fetch a single page of reviews"""
            start_time = time.time()
            response = client.get(f"/reviews/?page={page}&per_page={per_page}")
            end_time = time.time()
            
            return {
                "page": page,
                "status_code": response.status_code,
                "response_time": end_time - start_time,
                "success": response.status_code == 200,
                "item_count": len(response.json().get("items", [])) if response.status_code == 200 else 0
            }
        
        # Test multiple pages concurrently
        pages_to_test = list(range(1, 21))  # Test first 20 pages
        
        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(fetch_page, page) for page in pages_to_test]
            results = [future.result() for future in as_completed(futures)]
        
        # Analyze results
        successful_requests = [r for r in results if r["success"]]
        response_times = [r["response_time"] for r in successful_requests]
        
        # Assertions
        assert len(successful_requests) == len(pages_to_test), "All pagination requests should succeed"
        assert max(response_times) < 2.0, "Pagination should be fast"
        assert all(r["item_count"] <= 20 for r in successful_requests), "Page size should be respected"
        
        print(f"Reviews Pagination Load Test Results:")
        print(f"  Pages tested: {len(pages_to_test)}")
        print(f"  Successful requests: {len(successful_requests)}")
        print(f"  Average response time: {statistics.mean(response_times):.3f}s")
    
    @pytest.mark.asyncio
    async def test_sentiment_analysis_batch_performance(self, sentiment_service: SentimentAnalysisService):
        """Test sentiment analysis service performance with large batches"""
        
        # Generate test data
        test_items = []
        for i in range(100):
            test_items.append({
                "text": f"This is test review number {i}. The product is {'excellent' if i % 3 == 0 else 'terrible' if i % 3 == 1 else 'okay'} and I {'love' if i % 3 == 0 else 'hate' if i % 3 == 1 else 'accept'} it.",
                "context": {"review_id": i}
            })
        
        # Test batch processing performance
        start_time = time.time()
        results = await sentiment_service.analyze_batch_async(test_items, batch_size=20)
        end_time = time.time()
        
        processing_time = end_time - start_time
        
        # Assertions
        assert len(results) == 100, "All items should be processed"
        assert processing_time < 10.0, "Batch processing should complete within 10 seconds"
        assert all(hasattr(r, 'score') and hasattr(r, 'confidence') for r in results), "All results should have score and confidence"
        
        # Test performance metrics
        avg_time_per_item = processing_time / len(test_items)
        assert avg_time_per_item < 0.1, "Average processing time per item should be under 0.1 seconds"
        
        print(f"Sentiment Analysis Batch Performance:")
        print(f"  Items processed: {len(results)}")
        print(f"  Total time: {processing_time:.3f}s")
        print(f"  Average time per item: {avg_time_per_item:.4f}s")
    
    def test_aggregation_service_performance(self, aggregation_service: ReviewAggregationService, large_dataset):
        """Test review aggregation service performance"""
        
        def calculate_aggregates(entity_type: str, entity_id: int):
            """Calculate aggregates for a single entity"""
            start_time = time.time()
            result = aggregation_service.calculate_review_aggregates(
                entity_type, entity_id, force_recalculate=True
            )
            end_time = time.time()
            
            return {
                "entity_type": entity_type,
                "entity_id": entity_id,
                "processing_time": end_time - start_time,
                "total_reviews": result.get("total_reviews", 0)
            }
        
        # Test aggregation for multiple entities
        test_entities = [
            ("product", i) for i in range(1, 21)  # 20 products
        ]
        
        with ThreadPoolExecutor(max_workers=5) as executor:
            futures = [
                executor.submit(calculate_aggregates, entity_type, entity_id)
                for entity_type, entity_id in test_entities
            ]
            results = [future.result() for future in as_completed(futures)]
        
        # Analyze performance
        processing_times = [r["processing_time"] for r in results]
        total_reviews_processed = sum(r["total_reviews"] for r in results)
        
        # Assertions
        assert len(results) == len(test_entities), "All entities should be processed"
        assert max(processing_times) < 5.0, "No single aggregation should take longer than 5 seconds"
        assert statistics.mean(processing_times) < 2.0, "Average aggregation time should be under 2 seconds"
        
        print(f"Aggregation Service Performance:")
        print(f"  Entities processed: {len(results)}")
        print(f"  Total reviews in aggregations: {total_reviews_processed}")
        print(f"  Average processing time: {statistics.mean(processing_times):.3f}s")
        print(f"  Max processing time: {max(processing_times):.3f}s")
    
    def test_concurrent_read_write_operations(self, client: TestClient, auth_headers_customer, auth_headers_staff):
        """Test system performance under concurrent read/write load"""
        
        def create_review():
            """Create a new review"""
            review_data = {
                "review_type": "product",
                "customer_id": 1,
                "product_id": 101,
                "title": "Load test review",
                "content": "This is a review created during load testing to verify system performance.",
                "rating": 4.0
            }
            
            start_time = time.time()
            response = client.post("/reviews/", json=review_data, headers=auth_headers_customer)
            end_time = time.time()
            
            return {
                "operation": "create",
                "status_code": response.status_code,
                "response_time": end_time - start_time,
                "success": response.status_code == 200
            }
        
        def read_reviews():
            """Read reviews list"""
            start_time = time.time()
            response = client.get("/reviews/?per_page=10")
            end_time = time.time()
            
            return {
                "operation": "read",
                "status_code": response.status_code,
                "response_time": end_time - start_time,
                "success": response.status_code == 200
            }
        
        def read_analytics():
            """Read analytics data"""
            start_time = time.time()
            response = client.get("/feedback/analytics/overview", headers=auth_headers_staff)
            end_time = time.time()
            
            return {
                "operation": "analytics",
                "status_code": response.status_code,
                "response_time": end_time - start_time,
                "success": response.status_code == 200
            }
        
        # Mix of operations
        operations = []
        
        # Add write operations (fewer)
        operations.extend([create_review for _ in range(5)])
        
        # Add read operations (more)
        operations.extend([read_reviews for _ in range(15)])
        
        # Add analytics operations
        operations.extend([read_analytics for _ in range(10)])
        
        # Execute all operations concurrently
        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(op) for op in operations]
            results = [future.result() for future in as_completed(futures)]
        
        # Analyze results by operation type
        create_results = [r for r in results if r["operation"] == "create"]
        read_results = [r for r in results if r["operation"] == "read"]
        analytics_results = [r for r in results if r["operation"] == "analytics"]
        
        # Assertions
        create_success_rate = sum(1 for r in create_results if r["success"]) / len(create_results)
        read_success_rate = sum(1 for r in read_results if r["success"]) / len(read_results)
        analytics_success_rate = sum(1 for r in analytics_results if r["success"]) / len(analytics_results)
        
        assert create_success_rate >= 0.8, "At least 80% of create operations should succeed"
        assert read_success_rate >= 0.95, "At least 95% of read operations should succeed"
        assert analytics_success_rate >= 0.9, "At least 90% of analytics operations should succeed"
        
        print(f"Concurrent Operations Performance:")
        print(f"  Create operations: {len(create_results)} ({create_success_rate:.1%} success)")
        print(f"  Read operations: {len(read_results)} ({read_success_rate:.1%} success)")
        print(f"  Analytics operations: {len(analytics_results)} ({analytics_success_rate:.1%} success)")
    
    def test_memory_usage_under_load(self, client: TestClient, large_dataset):
        """Test memory usage doesn't grow excessively under load"""
        import psutil
        import os
        
        # Get initial memory usage
        process = psutil.Process(os.getpid())
        initial_memory = process.memory_info().rss / 1024 / 1024  # MB
        
        # Perform many operations
        def make_request():
            return client.get("/reviews/?per_page=50")
        
        # Make 100 requests
        with ThreadPoolExecutor(max_workers=5) as executor:
            futures = [executor.submit(make_request) for _ in range(100)]
            results = [future.result() for future in as_completed(futures)]
        
        # Check memory usage after operations
        final_memory = process.memory_info().rss / 1024 / 1024  # MB
        memory_increase = final_memory - initial_memory
        
        # Assertions
        successful_requests = sum(1 for r in results if r.status_code == 200)
        assert successful_requests >= 95, "Most requests should succeed"
        assert memory_increase < 100, f"Memory usage shouldn't increase by more than 100MB (increased by {memory_increase:.1f}MB)"
        
        print(f"Memory Usage Test:")
        print(f"  Initial memory: {initial_memory:.1f}MB")
        print(f"  Final memory: {final_memory:.1f}MB")
        print(f"  Memory increase: {memory_increase:.1f}MB")
        print(f"  Successful requests: {successful_requests}/100")


class TestStressTests:
    """Stress tests to find system limits"""
    
    @pytest.mark.slow
    def test_maximum_concurrent_requests(self, client: TestClient):
        """Test system behavior under maximum concurrent load"""
        
        def make_request():
            try:
                response = client.get("/reviews/", timeout=10)
                return response.status_code == 200
            except Exception:
                return False
        
        # Start with a reasonable number and increase
        max_workers_tested = []
        success_rates = []
        
        for max_workers in [10, 20, 50, 100]:
            with ThreadPoolExecutor(max_workers=max_workers) as executor:
                futures = [executor.submit(make_request) for _ in range(max_workers)]
                results = [future.result() for future in as_completed(futures, timeout=30)]
            
            success_rate = sum(results) / len(results)
            max_workers_tested.append(max_workers)
            success_rates.append(success_rate)
            
            print(f"Max workers {max_workers}: {success_rate:.1%} success rate")
            
            # Stop if success rate drops too much
            if success_rate < 0.7:
                break
        
        # Find the point where system performance degrades
        acceptable_performance = [i for i, rate in enumerate(success_rates) if rate >= 0.9]
        
        if acceptable_performance:
            max_acceptable_load = max_workers_tested[max(acceptable_performance)]
            print(f"System can handle up to {max_acceptable_load} concurrent requests with 90%+ success rate")
        else:
            print("System shows performance degradation even at low concurrency levels")
    
    @pytest.mark.slow
    def test_large_response_handling(self, client: TestClient, large_dataset):
        """Test handling of large response payloads"""
        
        # Request large page sizes
        page_sizes = [100, 500, 1000]
        
        for page_size in page_sizes:
            start_time = time.time()
            response = client.get(f"/reviews/?per_page={page_size}")
            end_time = time.time()
            
            response_time = end_time - start_time
            
            if response.status_code == 200:
                data = response.json()
                actual_items = len(data.get("items", []))
                
                print(f"Page size {page_size}: {actual_items} items in {response_time:.3f}s")
                
                # Assertions
                assert response_time < 10.0, f"Large response ({page_size} items) should complete within 10 seconds"
                assert actual_items <= page_size, "Response shouldn't exceed requested page size"
            else:
                print(f"Page size {page_size}: Failed with status {response.status_code}")
    
    @pytest.mark.slow  
    def test_sustained_load_endurance(self, client: TestClient):
        """Test system stability under sustained load"""
        
        def continuous_requests(duration_seconds: int = 60):
            """Make continuous requests for specified duration"""
            start_time = time.time()
            request_count = 0
            successful_requests = 0
            
            while time.time() - start_time < duration_seconds:
                try:
                    response = client.get("/reviews/?per_page=20")
                    request_count += 1
                    if response.status_code == 200:
                        successful_requests += 1
                    
                    # Small delay to prevent overwhelming
                    time.sleep(0.1)
                    
                except Exception as e:
                    print(f"Request failed: {e}")
                    request_count += 1
            
            return request_count, successful_requests
        
        # Run sustained load test
        print("Starting sustained load test (60 seconds)...")
        total_requests, successful_requests = continuous_requests(60)
        success_rate = successful_requests / total_requests if total_requests > 0 else 0
        
        print(f"Sustained Load Test Results:")
        print(f"  Total requests: {total_requests}")
        print(f"  Successful requests: {successful_requests}")
        print(f"  Success rate: {success_rate:.1%}")
        print(f"  Requests per second: {total_requests / 60:.1f}")
        
        # Assertions
        assert total_requests > 100, "Should have made at least 100 requests in 60 seconds"
        assert success_rate >= 0.95, "Should maintain 95%+ success rate under sustained load"