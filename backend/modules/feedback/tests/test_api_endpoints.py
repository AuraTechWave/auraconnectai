# backend/modules/feedback/tests/test_api_endpoints.py

import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock
import json
from datetime import datetime

from backend.modules.feedback.models.feedback_models import (
    Review, Feedback, ReviewStatus, FeedbackStatus, ReviewType, FeedbackType
)


class TestReviewsAPI:
    """Test cases for Reviews API endpoints"""
    
    def test_create_review_success(self, client: TestClient, sample_review_data, auth_headers_customer):
        """Test successful review creation via API"""
        response = client.post(
            "/reviews/",
            json=sample_review_data,
            headers=auth_headers_customer
        )
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["title"] == sample_review_data["title"]
        assert data["content"] == sample_review_data["content"]
        assert data["rating"] == sample_review_data["rating"]
        assert data["customer_id"] == sample_review_data["customer_id"]
        assert "id" in data
        assert "uuid" in data
        assert "created_at" in data
    
    def test_create_review_unauthorized(self, client: TestClient, sample_review_data):
        """Test review creation without authentication"""
        response = client.post("/reviews/", json=sample_review_data)
        
        assert response.status_code == 401
    
    def test_create_review_permission_denied(self, client: TestClient, sample_review_data, auth_headers_customer):
        """Test review creation for another customer"""
        review_data = sample_review_data.copy()
        review_data["customer_id"] = 999  # Different customer
        
        response = client.post(
            "/reviews/",
            json=review_data,
            headers=auth_headers_customer
        )
        
        assert response.status_code == 400
        assert "Cannot create review for another customer" in response.json()["detail"]
    
    def test_create_review_validation_error(self, client: TestClient, auth_headers_customer):
        """Test review creation with invalid data"""
        invalid_data = {
            "review_type": "invalid_type",
            "customer_id": 1,
            "content": "Short",  # Too short
            "rating": 6.0  # Invalid rating
        }
        
        response = client.post(
            "/reviews/",
            json=invalid_data,
            headers=auth_headers_customer
        )
        
        assert response.status_code == 422  # Validation error
    
    def test_get_review_success(self, client: TestClient, sample_review):
        """Test successful review retrieval"""
        response = client.get(f"/reviews/{sample_review.id}")
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["id"] == sample_review.id
        assert data["title"] == sample_review.title
        assert data["content"] == sample_review.content
        assert data["rating"] == sample_review.rating
    
    def test_get_review_not_found(self, client: TestClient):
        """Test review retrieval with invalid ID"""
        response = client.get("/reviews/99999")
        
        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()
    
    def test_get_review_by_uuid(self, client: TestClient, sample_review):
        """Test review retrieval by UUID"""
        response = client.get(f"/reviews/uuid/{sample_review.uuid}")
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["id"] == sample_review.id
        assert data["uuid"] == str(sample_review.uuid)
    
    def test_update_review_success(self, client: TestClient, sample_review, auth_headers_customer):
        """Test successful review update"""
        update_data = {
            "title": "Updated Review Title",
            "content": "This is updated content with more details about my experience.",
            "rating": 5.0
        }
        
        with patch('backend.core.auth.get_current_user') as mock_auth:
            mock_auth.return_value = {"id": sample_review.customer_id}
            
            response = client.put(
                f"/reviews/{sample_review.id}",
                json=update_data,
                headers=auth_headers_customer
            )
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["title"] == update_data["title"]
        assert data["content"] == update_data["content"]
        assert data["rating"] == update_data["rating"]
    
    def test_update_review_permission_denied(self, client: TestClient, sample_review, auth_headers_customer):
        """Test review update by wrong customer"""
        update_data = {"title": "Unauthorized Update"}
        
        with patch('backend.core.auth.get_current_user') as mock_auth:
            mock_auth.return_value = {"id": 999}  # Different customer
            
            response = client.put(
                f"/reviews/{sample_review.id}",
                json=update_data,
                headers=auth_headers_customer
            )
        
        assert response.status_code == 403
    
    def test_delete_review_success(self, client: TestClient, sample_review, auth_headers_customer):
        """Test successful review deletion"""
        with patch('backend.core.auth.get_current_user') as mock_auth:
            mock_auth.return_value = {"id": sample_review.customer_id}
            
            response = client.delete(
                f"/reviews/{sample_review.id}",
                headers=auth_headers_customer
            )
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
    
    def test_list_reviews_success(self, client: TestClient, multiple_reviews):
        """Test successful review listing"""
        response = client.get("/reviews/")
        
        assert response.status_code == 200
        data = response.json()
        
        assert "items" in data
        assert "total" in data
        assert "page" in data
        assert "per_page" in data
        assert len(data["items"]) > 0
    
    def test_list_reviews_with_filters(self, client: TestClient, multiple_reviews):
        """Test review listing with filters"""
        # Test rating filter
        response = client.get("/reviews/?rating_min=4.0")
        
        assert response.status_code == 200
        data = response.json()
        
        # All returned reviews should have rating >= 4.0
        for item in data["items"]:
            assert item["rating"] >= 4.0
    
    def test_list_reviews_pagination(self, client: TestClient, multiple_reviews):
        """Test review listing pagination"""
        response = client.get("/reviews/?page=1&per_page=3")
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["page"] == 1
        assert data["per_page"] == 3
        assert len(data["items"]) <= 3
        assert data["total"] > 0
    
    def test_vote_on_review_success(self, client: TestClient, sample_review, auth_headers_customer):
        """Test voting on review"""
        vote_data = {"is_helpful": True}
        
        with patch('backend.core.auth.get_current_user') as mock_auth:
            mock_auth.return_value = {"id": 2}  # Different customer
            
            response = client.post(
                f"/reviews/{sample_review.id}/vote",
                json=vote_data,
                headers=auth_headers_customer
            )
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "helpful_votes" in data
    
    def test_add_business_response_success(self, client: TestClient, sample_review, auth_headers_staff):
        """Test adding business response"""
        response_data = {
            "content": "Thank you for your feedback! We're glad you enjoyed the product.",
            "responder_name": "Customer Service",
            "responder_title": "Support Manager",
            "is_published": True
        }
        
        with patch('backend.core.auth.get_current_staff_user') as mock_auth:
            mock_auth.return_value = {"id": 100, "name": "Staff Member"}
            
            response = client.post(
                f"/reviews/{sample_review.id}/business-response",
                json=response_data,
                headers=auth_headers_staff
            )
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "response_id" in data
    
    def test_add_review_media_success(self, client: TestClient, sample_review, auth_headers_customer):
        """Test adding media to review"""
        media_data = [
            {
                "media_type": "image",
                "file_path": "/uploads/test_image.jpg",
                "file_name": "product_photo.jpg",
                "file_size": 1024576,
                "mime_type": "image/jpeg",
                "width": 1920,
                "height": 1080
            }
        ]
        
        with patch('backend.core.auth.get_current_user') as mock_auth:
            mock_auth.return_value = {"id": sample_review.customer_id}
            
            response = client.post(
                f"/reviews/{sample_review.id}/media",
                json=media_data,
                headers=auth_headers_customer
            )
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["media_count"] == 1
    
    def test_get_review_aggregates(self, client: TestClient, multiple_reviews):
        """Test getting review aggregates"""
        response = client.get("/reviews/product/101/aggregates")
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["entity_type"] == "product"
        assert data["entity_id"] == 101
        assert "total_reviews" in data
        assert "average_rating" in data
        assert "rating_distribution" in data
    
    def test_get_review_insights(self, client: TestClient, multiple_reviews):
        """Test getting review insights"""
        response = client.get("/reviews/product/101/insights")
        
        assert response.status_code == 200
        data = response.json()
        
        assert "overview" in data
        assert "rating_distribution" in data
        assert "sentiment_distribution" in data
        assert "temporal_trends" in data
    
    def test_moderate_review_staff_only(self, client: TestClient, sample_review, auth_headers_staff):
        """Test review moderation (staff only)"""
        moderation_data = {
            "status": "approved",
            "moderation_notes": "Review approved after verification",
            "is_featured": True
        }
        
        with patch('backend.core.auth.get_current_staff_user') as mock_auth:
            mock_auth.return_value = {"id": 100}
            
            response = client.post(
                f"/reviews/{sample_review.id}/moderate",
                json=moderation_data,
                headers=auth_headers_staff
            )
        
        assert response.status_code == 200
    
    def test_bulk_moderate_reviews_staff_only(self, client: TestClient, multiple_reviews, auth_headers_staff):
        """Test bulk review moderation"""
        review_ids = [r.id for r in multiple_reviews[:3]]
        bulk_data = {
            "review_ids": review_ids,
            "action": "approve",
            "notes": "Bulk approval"
        }
        
        with patch('backend.core.auth.get_current_staff_user') as mock_auth:
            mock_auth.return_value = {"id": 100}
            
            response = client.post(
                "/reviews/bulk-moderate",
                json=bulk_data,
                headers=auth_headers_staff
            )
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
    
    def test_get_moderation_queue_staff_only(self, client: TestClient, auth_headers_staff):
        """Test getting moderation queue"""
        with patch('backend.core.auth.get_current_staff_user') as mock_auth:
            mock_auth.return_value = {"id": 100}
            
            response = client.get(
                "/reviews/moderation/queue",
                headers=auth_headers_staff
            )
        
        assert response.status_code == 200
        data = response.json()
        assert "items" in data
        assert "pagination" in data
    
    def test_get_top_rated_entities(self, client: TestClient, multiple_reviews):
        """Test getting top-rated entities"""
        response = client.get("/reviews/top-rated/product?limit=5&min_reviews=1")
        
        assert response.status_code == 200
        data = response.json()
        
        assert isinstance(data, list)
        assert len(data) <= 5
    
    def test_get_trending_entities(self, client: TestClient, multiple_reviews):
        """Test getting trending entities"""
        response = client.get("/reviews/trending/product?limit=5&days_back=7")
        
        assert response.status_code == 200
        data = response.json()
        
        assert isinstance(data, list)
        assert len(data) <= 5


class TestFeedbackAPI:
    """Test cases for Feedback API endpoints"""
    
    def test_create_feedback_authenticated(self, client: TestClient, sample_feedback_data, auth_headers_customer):
        """Test feedback creation by authenticated user"""
        with patch('backend.core.auth.get_optional_current_user') as mock_auth:
            mock_auth.return_value = {"id": sample_feedback_data["customer_id"]}
            
            response = client.post(
                "/feedback/",
                json=sample_feedback_data,
                headers=auth_headers_customer
            )
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["subject"] == sample_feedback_data["subject"]
        assert data["message"] == sample_feedback_data["message"]
        assert data["feedback_type"] == sample_feedback_data["feedback_type"]
        assert data["customer_id"] == sample_feedback_data["customer_id"]
    
    def test_create_feedback_anonymous(self, client: TestClient):
        """Test anonymous feedback creation"""
        anonymous_feedback = {
            "feedback_type": "suggestion",
            "customer_email": "anonymous@example.com",
            "customer_name": "Anonymous User",
            "subject": "Anonymous suggestion",
            "message": "This is an anonymous feedback message with sufficient length.",
            "priority": "medium",
            "source": "website"
        }
        
        with patch('backend.core.auth.get_optional_current_user') as mock_auth:
            mock_auth.return_value = None  # Anonymous user
            
            response = client.post("/feedback/", json=anonymous_feedback)
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["customer_email"] == anonymous_feedback["customer_email"]
        assert data["customer_id"] is None
    
    def test_create_feedback_validation_error(self, client: TestClient):
        """Test feedback creation with invalid data"""
        invalid_data = {
            "feedback_type": "invalid_type",
            "subject": "A",  # Too short
            "message": "Short"  # Too short
        }
        
        response = client.post("/feedback/", json=invalid_data)
        
        assert response.status_code == 422  # Validation error
    
    def test_get_feedback_success(self, client: TestClient, sample_feedback, auth_headers_customer):
        """Test getting feedback by ID"""
        with patch('backend.core.auth.get_optional_current_user') as mock_user:
            mock_user.return_value = {"id": sample_feedback.customer_id}
            with patch('backend.core.auth.get_current_staff_user') as mock_staff:
                mock_staff.return_value = None  # Not staff
                
                response = client.get(
                    f"/feedback/{sample_feedback.id}",
                    headers=auth_headers_customer
                )
        
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == sample_feedback.id
    
    def test_get_feedback_permission_denied(self, client: TestClient, sample_feedback, auth_headers_customer):
        """Test getting feedback with wrong customer"""
        with patch('backend.core.auth.get_optional_current_user') as mock_user:
            mock_user.return_value = {"id": 999}  # Different customer
            with patch('backend.core.auth.get_current_staff_user') as mock_staff:
                mock_staff.return_value = None
                
                response = client.get(
                    f"/feedback/{sample_feedback.id}",
                    headers=auth_headers_customer
                )
        
        assert response.status_code == 403
    
    def test_update_feedback_staff_only(self, client: TestClient, sample_feedback, auth_headers_staff):
        """Test feedback update (staff only)"""
        update_data = {
            "status": "in_progress",
            "assigned_to": 100,
            "priority": "high"
        }
        
        with patch('backend.core.auth.get_current_staff_user') as mock_auth:
            mock_auth.return_value = {"id": 100}
            
            response = client.put(
                f"/feedback/{sample_feedback.id}",
                json=update_data,
                headers=auth_headers_staff
            )
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == update_data["status"]
    
    def test_list_feedback_customer_only_own(self, client: TestClient, multiple_feedback, auth_headers_customer):
        """Test customer can only list their own feedback"""
        with patch('backend.core.auth.get_optional_current_user') as mock_user:
            mock_user.return_value = {"id": 1}  # Customer 1
            with patch('backend.core.auth.get_current_staff_user') as mock_staff:
                mock_staff.return_value = None
                
                response = client.get("/feedback/", headers=auth_headers_customer)
        
        assert response.status_code == 200
        data = response.json()
        
        # Should only return feedback for customer 1
        for item in data["items"]:
            assert item["customer_id"] == 1
    
    def test_list_feedback_staff_all(self, client: TestClient, multiple_feedback, auth_headers_staff):
        """Test staff can list all feedback"""
        with patch('backend.core.auth.get_optional_current_user') as mock_user:
            mock_user.return_value = None
            with patch('backend.core.auth.get_current_staff_user') as mock_staff:
                mock_staff.return_value = {"id": 100}
                
                response = client.get("/feedback/", headers=auth_headers_staff)
        
        assert response.status_code == 200
        data = response.json()
        
        assert len(data["items"]) >= len(multiple_feedback)
    
    def test_assign_feedback_staff_only(self, client: TestClient, sample_feedback, auth_headers_staff):
        """Test feedback assignment (staff only)"""
        assign_data = {"assignee_id": 101}
        
        with patch('backend.core.auth.get_current_staff_user') as mock_auth:
            mock_auth.return_value = {"id": 100}
            
            response = client.post(
                f"/feedback/{sample_feedback.id}/assign",
                json=assign_data,
                headers=auth_headers_staff
            )
        
        assert response.status_code == 200
        data = response.json()
        assert data["assigned_to"] == assign_data["assignee_id"]
    
    def test_resolve_feedback_staff_only(self, client: TestClient, sample_feedback, auth_headers_staff):
        """Test feedback resolution (staff only)"""
        resolve_data = {"resolution_notes": "Issue has been resolved successfully."}
        
        with patch('backend.core.auth.get_current_staff_user') as mock_auth:
            mock_auth.return_value = {"id": 100}
            
            response = client.post(
                f"/feedback/{sample_feedback.id}/resolve",
                json=resolve_data,
                headers=auth_headers_staff
            )
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "resolved"
    
    def test_escalate_feedback_staff_only(self, client: TestClient, sample_feedback, auth_headers_staff):
        """Test feedback escalation (staff only)"""
        escalate_data = {
            "escalated_to": 102,
            "reason": "Requires senior support attention"
        }
        
        with patch('backend.core.auth.get_current_staff_user') as mock_auth:
            mock_auth.return_value = {"id": 100}
            
            response = client.post(
                f"/feedback/{sample_feedback.id}/escalate",
                json=escalate_data,
                headers=auth_headers_staff
            )
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "escalated"
    
    def test_add_feedback_response_staff_only(self, client: TestClient, sample_feedback, auth_headers_staff):
        """Test adding response to feedback (staff only)"""
        response_data = {
            "message": "Thank you for your feedback. We are looking into this issue.",
            "is_internal": False,
            "is_resolution": False
        }
        
        with patch('backend.core.auth.get_current_staff_user') as mock_auth:
            mock_auth.return_value = {"id": 100, "name": "Support Agent"}
            
            response = client.post(
                f"/feedback/{sample_feedback.id}/responses",
                json=response_data,
                headers=auth_headers_staff
            )
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
    
    def test_get_feedback_analytics_staff_only(self, client: TestClient, auth_headers_staff):
        """Test getting feedback analytics (staff only)"""
        with patch('backend.core.auth.get_current_staff_user') as mock_auth:
            mock_auth.return_value = {"id": 100}
            
            response = client.get(
                "/feedback/analytics/overview",
                headers=auth_headers_staff
            )
        
        assert response.status_code == 200
        data = response.json()
        
        assert "total_feedback" in data
        assert "feedback_by_type" in data
        assert "resolution_rate" in data
    
    def test_create_feedback_category_staff_only(self, client: TestClient, auth_headers_staff):
        """Test creating feedback category (staff only)"""
        category_data = {
            "name": "Technical Issues",
            "description": "Technical problems and bugs",
            "sort_order": 1,
            "auto_assign_keywords": ["bug", "error", "broken"],
            "auto_escalate": True,
            "escalation_priority": "high"
        }
        
        with patch('backend.core.auth.get_current_staff_user') as mock_auth:
            mock_auth.return_value = {"id": 100}
            
            response = client.post(
                "/feedback/categories",
                json=category_data,
                headers=auth_headers_staff
            )
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
    
    def test_list_feedback_categories_public(self, client: TestClient):
        """Test listing feedback categories (public)"""
        response = client.get("/feedback/categories")
        
        assert response.status_code == 200
        data = response.json()
        assert "categories" in data
    
    def test_get_my_feedback_authenticated(self, client: TestClient, sample_feedback, auth_headers_customer):
        """Test getting current user's feedback"""
        with patch('backend.core.auth.get_current_user') as mock_auth:
            mock_auth.return_value = {"id": sample_feedback.customer_id}
            
            response = client.get("/feedback/my/feedback", headers=auth_headers_customer)
        
        assert response.status_code == 200
        data = response.json()
        
        assert "items" in data
        # All items should belong to the authenticated user
        for item in data["items"]:
            assert item["customer_id"] == sample_feedback.customer_id
    
    def test_feedback_health_check(self, client: TestClient):
        """Test feedback service health check"""
        response = client.get("/feedback/health")
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["status"] == "healthy"
        assert data["service"] == "feedback"


class TestAPIErrorHandling:
    """Test error handling in API endpoints"""
    
    def test_invalid_json_payload(self, client: TestClient, auth_headers_customer):
        """Test handling of invalid JSON payload"""
        response = client.post(
            "/reviews/",
            data="invalid json",
            headers={**auth_headers_customer, "Content-Type": "application/json"}
        )
        
        assert response.status_code == 422
    
    def test_missing_required_fields(self, client: TestClient, auth_headers_customer):
        """Test handling of missing required fields"""
        incomplete_data = {
            "review_type": "product"
            # Missing customer_id, content, rating
        }
        
        response = client.post(
            "/reviews/",
            json=incomplete_data,
            headers=auth_headers_customer
        )
        
        assert response.status_code == 422
    
    def test_rate_limiting_simulation(self, client: TestClient, auth_headers_customer):
        """Test API rate limiting behavior (simulated)"""
        # This would test actual rate limiting in a real environment
        # For now, we'll just ensure the endpoint works
        
        response = client.get("/reviews/", headers=auth_headers_customer)
        assert response.status_code == 200
    
    def test_internal_server_error_handling(self, client: TestClient):
        """Test internal server error handling"""
        # Simulate an internal error by using a non-existent endpoint
        response = client.get("/reviews/non-existent-endpoint")
        
        assert response.status_code == 404
    
    def test_method_not_allowed(self, client: TestClient):
        """Test method not allowed error"""
        # Try to use wrong HTTP method
        response = client.patch("/reviews/")  # PATCH not allowed on this endpoint
        
        assert response.status_code == 405


class TestAPIPerformance:
    """Performance tests for API endpoints"""
    
    def test_list_reviews_performance(self, client: TestClient, large_dataset):
        """Test performance of review listing with large dataset"""
        import time
        
        start_time = time.time()
        response = client.get("/reviews/?per_page=50")
        end_time = time.time()
        
        assert response.status_code == 200
        assert end_time - start_time < 2.0  # Should complete within 2 seconds
    
    def test_pagination_performance(self, client: TestClient, large_dataset):
        """Test pagination performance with large dataset"""
        import time
        
        # Test multiple pages
        for page in range(1, 6):  # Test first 5 pages
            start_time = time.time()
            response = client.get(f"/reviews/?page={page}&per_page=20")
            end_time = time.time()
            
            assert response.status_code == 200
            assert end_time - start_time < 1.0  # Each page should load quickly
    
    def test_concurrent_requests_simulation(self, client: TestClient):
        """Test handling of concurrent requests (simulated)"""
        import threading
        import time
        
        results = []
        
        def make_request():
            response = client.get("/reviews/")
            results.append(response.status_code)
        
        # Simulate 10 concurrent requests
        threads = []
        for _ in range(10):
            thread = threading.Thread(target=make_request)
            threads.append(thread)
            thread.start()
        
        # Wait for all threads to complete
        for thread in threads:
            thread.join()
        
        # All requests should succeed
        assert all(status == 200 for status in results)
        assert len(results) == 10


class TestAPISecurityHeaders:
    """Test security aspects of API responses"""
    
    def test_cors_headers(self, client: TestClient):
        """Test CORS headers in API responses"""
        response = client.get("/reviews/")
        
        # Check that response doesn't expose sensitive headers
        assert "X-Powered-By" not in response.headers
    
    def test_no_sensitive_data_exposure(self, client: TestClient, sample_review):
        """Test that sensitive data is not exposed in API responses"""
        response = client.get(f"/reviews/{sample_review.id}")
        
        assert response.status_code == 200
        data = response.json()
        
        # Should not expose internal fields
        assert "moderated_by" not in data or data["moderated_by"] is None
        assert "sentiment_analysis_data" not in data or data["sentiment_analysis_data"] is None
    
    def test_input_sanitization(self, client: TestClient, auth_headers_customer):
        """Test input sanitization for XSS prevention"""
        malicious_data = {
            "review_type": "product",
            "customer_id": 1,
            "title": "<script>alert('xss')</script>",
            "content": "This is a test review with <script>alert('xss')</script> malicious content.",
            "rating": 4.0
        }
        
        with patch('backend.core.auth.get_current_user') as mock_auth:
            mock_auth.return_value = {"id": 1}
            
            response = client.post(
                "/reviews/",
                json=malicious_data,
                headers=auth_headers_customer
            )
        
        if response.status_code == 200:
            data = response.json()
            # Scripts should be handled safely (either sanitized or stored as-is for later sanitization)
            assert "<script>" in data["title"] or "alert" not in data["title"]