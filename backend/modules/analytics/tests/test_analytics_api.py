# backend/modules/analytics/tests/test_analytics_api.py

import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock
import json
from datetime import datetime, date, timedelta
from decimal import Decimal

from modules.analytics.models.analytics_models import AggregationPeriod


class TestAnalyticsAPI:
    """Test cases for Analytics API endpoints"""
    
    def test_health_check(self, client: TestClient):
        """Test analytics service health check"""
        response = client.get("/analytics/health")
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["status"] == "healthy"
        assert data["service"] == "analytics"
        assert "timestamp" in data
        assert data["version"] == "1.0.0"
    
    def test_get_dashboard_metrics_success(
        self, 
        client: TestClient, 
        auth_headers_staff,
        sample_orders
    ):
        """Test successful dashboard metrics retrieval"""
        with patch('backend.core.auth.get_current_user') as mock_auth:
            mock_auth.return_value = {"id": 1, "name": "Staff User"}
            
            response = client.get(
                "/analytics/dashboard",
                headers=auth_headers_staff
            )
        
        assert response.status_code == 200
        data = response.json()
        
        # Check required fields
        assert "today_revenue" in data
        assert "today_orders" in data
        assert "today_customers" in data
        assert "revenue_growth_percentage" in data
        assert "order_growth_percentage" in data
        assert "customer_growth_percentage" in data
        assert "top_staff" in data
        assert "top_products" in data
        assert "revenue_trend" in data
        assert "order_trend" in data
        assert "last_updated" in data
        
        # Check data types
        assert isinstance(data["top_staff"], list)
        assert isinstance(data["top_products"], list)
        assert isinstance(data["revenue_trend"], list)
        assert isinstance(data["order_trend"], list)
    
    def test_get_dashboard_metrics_with_date(
        self, 
        client: TestClient, 
        auth_headers_staff
    ):
        """Test dashboard metrics with specific date"""
        test_date = "2024-01-15"
        
        with patch('backend.core.auth.get_current_user') as mock_auth:
            mock_auth.return_value = {"id": 1, "name": "Staff User"}
            
            response = client.get(
                f"/analytics/dashboard?current_date={test_date}",
                headers=auth_headers_staff
            )
        
        assert response.status_code == 200
    
    def test_get_dashboard_metrics_unauthorized(self, client: TestClient):
        """Test dashboard metrics without authentication"""
        response = client.get("/analytics/dashboard")
        
        assert response.status_code == 401
    
    def test_generate_sales_summary_success(
        self, 
        client: TestClient, 
        auth_headers_staff,
        sample_orders
    ):
        """Test successful sales summary generation"""
        request_data = {
            "date_from": "2024-01-01",
            "date_to": "2024-01-07",
            "period_type": "daily",
            "include_discounts": True,
            "include_tax": True,
            "only_completed_orders": True
        }
        
        with patch('backend.core.auth.get_current_user') as mock_auth:
            mock_auth.return_value = {"id": 1, "name": "Staff User"}
            
            response = client.post(
                "/analytics/reports/sales-summary",
                json=request_data,
                headers=auth_headers_staff
            )
        
        assert response.status_code == 200
        data = response.json()
        
        # Check required fields
        assert "period_start" in data
        assert "period_end" in data
        assert "period_type" in data
        assert "total_orders" in data
        assert "total_revenue" in data
        assert "total_items_sold" in data
        assert "average_order_value" in data
        assert "gross_revenue" in data
        assert "total_discounts" in data
        assert "total_tax" in data
        assert "net_revenue" in data
        assert "unique_customers" in data
        
        # Check data types
        assert isinstance(data["total_orders"], int)
        assert isinstance(data["total_revenue"], (int, float))
        assert isinstance(data["average_order_value"], (int, float))
    
    def test_generate_sales_summary_with_filters(
        self, 
        client: TestClient, 
        auth_headers_staff,
        sample_staff_member
    ):
        """Test sales summary with entity filters"""
        request_data = {
            "date_from": "2024-01-01",
            "date_to": "2024-01-07",
            "staff_ids": [sample_staff_member.id],
            "period_type": "daily",
            "min_order_value": 10.00,
            "max_order_value": 100.00
        }
        
        with patch('backend.core.auth.get_current_user') as mock_auth:
            mock_auth.return_value = {"id": 1, "name": "Staff User"}
            
            response = client.post(
                "/analytics/reports/sales-summary",
                json=request_data,
                headers=auth_headers_staff
            )
        
        assert response.status_code == 200
    
    def test_generate_sales_summary_validation_error(
        self, 
        client: TestClient, 
        auth_headers_staff
    ):
        """Test sales summary with invalid data"""
        request_data = {
            "date_from": "2024-01-07",
            "date_to": "2024-01-01",  # End before start
            "period_type": "daily"
        }
        
        with patch('backend.core.auth.get_current_user') as mock_auth:
            mock_auth.return_value = {"id": 1, "name": "Staff User"}
            
            response = client.post(
                "/analytics/reports/sales-summary",
                json=request_data,
                headers=auth_headers_staff
            )
        
        assert response.status_code == 422  # Validation error
    
    def test_generate_detailed_sales_report_success(
        self, 
        client: TestClient, 
        auth_headers_staff,
        sample_sales_snapshots
    ):
        """Test detailed sales report generation"""
        request_data = {
            "date_from": "2024-01-01",
            "date_to": "2024-01-07",
            "period_type": "daily"
        }
        
        with patch('backend.core.auth.get_current_user') as mock_auth:
            mock_auth.return_value = {"id": 1, "name": "Staff User"}
            
            response = client.post(
                "/analytics/reports/sales-detailed?page=1&per_page=10&sort_by=total_revenue&sort_order=desc",
                json=request_data,
                headers=auth_headers_staff
            )
        
        assert response.status_code == 200
        data = response.json()
        
        # Check paginated response structure
        assert "items" in data
        assert "total" in data
        assert "page" in data
        assert "per_page" in data
        assert "total_pages" in data
        assert "has_next" in data
        assert "has_prev" in data
        
        # Check pagination values
        assert data["page"] == 1
        assert data["per_page"] == 10
        assert isinstance(data["total"], int)
        assert isinstance(data["has_next"], bool)
        assert isinstance(data["has_prev"], bool)
        
        # Check items structure
        assert isinstance(data["items"], list)
        if data["items"]:
            item = data["items"][0]
            assert "id" in item
            assert "snapshot_date" in item
            assert "total_orders" in item
            assert "total_revenue" in item
    
    def test_generate_detailed_sales_report_pagination(
        self, 
        client: TestClient, 
        auth_headers_staff
    ):
        """Test detailed sales report pagination"""
        request_data = {
            "date_from": "2024-01-01",
            "date_to": "2024-01-07",
            "period_type": "daily"
        }
        
        with patch('backend.core.auth.get_current_user') as mock_auth:
            mock_auth.return_value = {"id": 1, "name": "Staff User"}
            
            # Test different pagination parameters
            response = client.post(
                "/analytics/reports/sales-detailed?page=2&per_page=5",
                json=request_data,
                headers=auth_headers_staff
            )
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["page"] == 2
        assert data["per_page"] == 5
    
    def test_generate_staff_performance_report_success(
        self, 
        client: TestClient, 
        auth_headers_staff,
        sample_sales_snapshots
    ):
        """Test staff performance report generation"""
        request_data = {
            "date_from": "2024-01-01",
            "date_to": "2024-01-07",
            "period_type": "daily"
        }
        
        with patch('backend.core.auth.get_current_user') as mock_auth:
            mock_auth.return_value = {"id": 1, "name": "Staff User"}
            
            response = client.post(
                "/analytics/reports/staff-performance",
                json=request_data,
                headers=auth_headers_staff
            )
        
        assert response.status_code == 200
        data = response.json()
        
        assert isinstance(data, list)
        
        # Check item structure if data exists
        if data:
            staff_perf = data[0]
            assert "staff_id" in staff_perf
            assert "staff_name" in staff_perf
            assert "total_orders_handled" in staff_perf
            assert "total_revenue_generated" in staff_perf
            assert "average_order_value" in staff_perf
            assert "period_start" in staff_perf
            assert "period_end" in staff_perf
    
    def test_generate_product_performance_report_success(
        self, 
        client: TestClient, 
        auth_headers_staff,
        sample_orders
    ):
        """Test product performance report generation"""
        request_data = {
            "date_from": "2024-01-01",
            "date_to": "2024-01-07",
            "period_type": "daily"
        }
        
        with patch('backend.core.auth.get_current_user') as mock_auth:
            mock_auth.return_value = {"id": 1, "name": "Staff User"}
            
            response = client.post(
                "/analytics/reports/product-performance",
                json=request_data,
                headers=auth_headers_staff
            )
        
        assert response.status_code == 200
        data = response.json()
        
        assert isinstance(data, list)
        
        # Check item structure if data exists
        if data:
            product_perf = data[0]
            assert "product_id" in product_perf
            assert "quantity_sold" in product_perf
            assert "revenue_generated" in product_perf
            assert "average_price" in product_perf
            assert "order_frequency" in product_perf
            assert "period_start" in product_perf
            assert "period_end" in product_perf
    
    def test_get_quick_stats_success(
        self, 
        client: TestClient, 
        auth_headers_staff,
        sample_orders
    ):
        """Test quick stats endpoint"""
        with patch('backend.core.auth.get_current_user') as mock_auth:
            mock_auth.return_value = {"id": 1, "name": "Staff User"}
            
            response = client.get(
                "/analytics/reports/quick-stats?date_from=2024-01-01&date_to=2024-01-07",
                headers=auth_headers_staff
            )
        
        assert response.status_code == 200
        data = response.json()
        
        # Check structure
        assert "period" in data
        assert "metrics" in data
        assert "growth" in data
        
        # Check period
        assert "start" in data["period"]
        assert "end" in data["period"]
        
        # Check metrics
        metrics = data["metrics"]
        assert "total_revenue" in metrics
        assert "total_orders" in metrics
        assert "average_order_value" in metrics
        assert "unique_customers" in metrics
        
        # Check growth
        growth = data["growth"]
        assert "revenue_growth" in growth
        assert "order_growth" in growth
    
    def test_get_quick_stats_with_filters(
        self, 
        client: TestClient, 
        auth_headers_staff,
        sample_staff_member
    ):
        """Test quick stats with filters"""
        with patch('backend.core.auth.get_current_user') as mock_auth:
            mock_auth.return_value = {"id": 1, "name": "Staff User"}
            
            response = client.get(
                f"/analytics/reports/quick-stats?staff_id={sample_staff_member.id}",
                headers=auth_headers_staff
            )
        
        assert response.status_code == 200
    
    def test_get_top_performers_staff(
        self, 
        client: TestClient, 
        auth_headers_staff,
        sample_sales_snapshots
    ):
        """Test top performers endpoint for staff"""
        with patch('backend.core.auth.get_current_user') as mock_auth:
            mock_auth.return_value = {"id": 1, "name": "Staff User"}
            
            response = client.get(
                "/analytics/reports/top-performers?entity_type=staff&metric=revenue&limit=5",
                headers=auth_headers_staff
            )
        
        assert response.status_code == 200
        data = response.json()
        
        assert isinstance(data, list)
        assert len(data) <= 5
        
        # Check item structure if data exists
        if data:
            performer = data[0]
            assert "id" in performer
            assert "name" in performer
            assert "metric_value" in performer
            assert "rank" in performer
    
    def test_get_top_performers_products(
        self, 
        client: TestClient, 
        auth_headers_staff,
        sample_orders
    ):
        """Test top performers endpoint for products"""
        with patch('backend.core.auth.get_current_user') as mock_auth:
            mock_auth.return_value = {"id": 1, "name": "Staff User"}
            
            response = client.get(
                "/analytics/reports/top-performers?entity_type=product&metric=revenue&limit=5",
                headers=auth_headers_staff
            )
        
        assert response.status_code == 200
        data = response.json()
        
        assert isinstance(data, list)
        assert len(data) <= 5
    
    def test_get_top_performers_invalid_entity(
        self, 
        client: TestClient, 
        auth_headers_staff
    ):
        """Test top performers with invalid entity type"""
        with patch('backend.core.auth.get_current_user') as mock_auth:
            mock_auth.return_value = {"id": 1, "name": "Staff User"}
            
            response = client.get(
                "/analytics/reports/top-performers?entity_type=invalid&metric=revenue",
                headers=auth_headers_staff
            )
        
        assert response.status_code == 422  # Validation error
    
    def test_get_trends_success(
        self, 
        client: TestClient, 
        auth_headers_staff,
        sample_orders
    ):
        """Test trends endpoint"""
        with patch('backend.core.auth.get_current_user') as mock_auth:
            mock_auth.return_value = {"id": 1, "name": "Staff User"}
            
            response = client.get(
                "/analytics/reports/trends?metric=revenue&period_days=7&granularity=daily",
                headers=auth_headers_staff
            )
        
        assert response.status_code == 200
        data = response.json()
        
        # Check structure
        assert "metric" in data
        assert "period" in data
        assert "granularity" in data
        assert "data" in data
        
        # Check metric
        assert data["metric"] == "revenue"
        assert data["granularity"] == "daily"
        
        # Check period
        period = data["period"]
        assert "start" in period
        assert "end" in period
        assert "days" in period
        assert period["days"] == 7
        
        # Check data
        trend_data = data["data"]
        assert isinstance(trend_data, list)
        if trend_data:
            point = trend_data[0]
            assert "date" in point
            assert "value" in point
    
    def test_get_trends_different_metrics(
        self, 
        client: TestClient, 
        auth_headers_staff
    ):
        """Test trends endpoint with different metrics"""
        metrics = ["revenue", "orders", "customers"]
        
        with patch('backend.core.auth.get_current_user') as mock_auth:
            mock_auth.return_value = {"id": 1, "name": "Staff User"}
            
            for metric in metrics:
                response = client.get(
                    f"/analytics/reports/trends?metric={metric}&period_days=7",
                    headers=auth_headers_staff
                )
                
                assert response.status_code == 200
                data = response.json()
                assert data["metric"] == metric
    
    def test_export_endpoints_not_implemented(
        self, 
        client: TestClient, 
        auth_headers_staff
    ):
        """Test export endpoints return not implemented"""
        request_data = {
            "report_type": "sales_summary",
            "filters": {
                "date_from": "2024-01-01",
                "date_to": "2024-01-07"
            }
        }
        
        with patch('backend.core.auth.get_current_user') as mock_auth:
            mock_auth.return_value = {"id": 1, "name": "Staff User"}
            
            # Test CSV export
            response = client.post(
                "/analytics/export/csv",
                json=request_data,
                headers=auth_headers_staff
            )
            assert response.status_code == 501
            
            # Test PDF export
            response = client.post(
                "/analytics/export/pdf",
                json=request_data,
                headers=auth_headers_staff
            )
            assert response.status_code == 501
            
            # Test Excel export
            response = client.post(
                "/analytics/export/excel",
                json=request_data,
                headers=auth_headers_staff
            )
            assert response.status_code == 501
    
    def test_error_handling_internal_server_error(
        self, 
        client: TestClient, 
        auth_headers_staff
    ):
        """Test internal server error handling"""
        with patch('backend.core.auth.get_current_user') as mock_auth:
            mock_auth.return_value = {"id": 1, "name": "Staff User"}
            
            # Mock service to raise an exception
            with patch('backend.modules.analytics.services.sales_report_service.SalesReportService.get_dashboard_metrics') as mock_service:
                mock_service.side_effect = Exception("Database connection failed")
                
                response = client.get(
                    "/analytics/dashboard",
                    headers=auth_headers_staff
                )
        
        assert response.status_code == 500
        assert "Failed to retrieve dashboard metrics" in response.json()["detail"]
    
    def test_authentication_required_all_endpoints(self, client: TestClient):
        """Test that all endpoints require authentication"""
        endpoints = [
            ("/analytics/dashboard", "GET"),
            ("/analytics/reports/sales-summary", "POST"),
            ("/analytics/reports/sales-detailed", "POST"),
            ("/analytics/reports/staff-performance", "POST"),
            ("/analytics/reports/product-performance", "POST"),
            ("/analytics/reports/quick-stats", "GET"),
            ("/analytics/reports/top-performers", "GET"),
            ("/analytics/reports/trends", "GET")
        ]
        
        for endpoint, method in endpoints:
            if method == "GET":
                response = client.get(endpoint)
            else:
                response = client.post(endpoint, json={})
            
            assert response.status_code == 401, f"Endpoint {endpoint} should require authentication"


class TestAnalyticsAPIValidation:
    """Test input validation for Analytics API"""
    
    def test_sales_filter_validation(self, client: TestClient, auth_headers_staff):
        """Test sales filter validation"""
        with patch('backend.core.auth.get_current_user') as mock_auth:
            mock_auth.return_value = {"id": 1, "name": "Staff User"}
            
            # Test invalid period type
            response = client.post(
                "/analytics/reports/sales-summary",
                json={
                    "date_from": "2024-01-01",
                    "date_to": "2024-01-07",
                    "period_type": "invalid_period"
                },
                headers=auth_headers_staff
            )
            assert response.status_code == 422
            
            # Test invalid staff IDs
            response = client.post(
                "/analytics/reports/sales-summary",
                json={
                    "date_from": "2024-01-01",
                    "date_to": "2024-01-07",
                    "staff_ids": ["not_an_integer"]
                },
                headers=auth_headers_staff
            )
            assert response.status_code == 422
    
    def test_pagination_validation(self, client: TestClient, auth_headers_staff):
        """Test pagination parameter validation"""
        with patch('backend.core.auth.get_current_user') as mock_auth:
            mock_auth.return_value = {"id": 1, "name": "Staff User"}
            
            # Test invalid page number
            response = client.post(
                "/analytics/reports/sales-detailed?page=0",
                json={"date_from": "2024-01-01", "date_to": "2024-01-07"},
                headers=auth_headers_staff
            )
            assert response.status_code == 422
            
            # Test invalid per_page
            response = client.post(
                "/analytics/reports/sales-detailed?per_page=0",
                json={"date_from": "2024-01-01", "date_to": "2024-01-07"},
                headers=auth_headers_staff
            )
            assert response.status_code == 422
            
            # Test per_page too large
            response = client.post(
                "/analytics/reports/sales-detailed?per_page=2000",
                json={"date_from": "2024-01-01", "date_to": "2024-01-07"},
                headers=auth_headers_staff
            )
            assert response.status_code == 422
    
    def test_sort_order_validation(self, client: TestClient, auth_headers_staff):
        """Test sort order validation"""
        with patch('backend.core.auth.get_current_user') as mock_auth:
            mock_auth.return_value = {"id": 1, "name": "Staff User"}
            
            # Test invalid sort order
            response = client.post(
                "/analytics/reports/sales-detailed?sort_order=invalid",
                json={"date_from": "2024-01-01", "date_to": "2024-01-07"},
                headers=auth_headers_staff
            )
            assert response.status_code == 422
    
    def test_query_parameter_validation(self, client: TestClient, auth_headers_staff):
        """Test query parameter validation"""
        with patch('backend.core.auth.get_current_user') as mock_auth:
            mock_auth.return_value = {"id": 1, "name": "Staff User"}
            
            # Test invalid metric in top performers
            response = client.get(
                "/analytics/reports/top-performers?metric=invalid_metric",
                headers=auth_headers_staff
            )
            assert response.status_code == 422
            
            # Test invalid entity type in top performers
            response = client.get(
                "/analytics/reports/top-performers?entity_type=invalid_entity",
                headers=auth_headers_staff
            )
            assert response.status_code == 422