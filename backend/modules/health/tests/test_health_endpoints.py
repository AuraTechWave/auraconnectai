"""
Tests for health monitoring endpoints.
"""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from datetime import datetime, timedelta

from modules.health.schemas.health_schemas import (
    HealthStatus, AlertSeverity, AlertType, ErrorLogCreate
)
from modules.health.services.health_service import HealthService


class TestHealthEndpoints:
    """Test health monitoring endpoints"""
    
    def test_basic_health_check(self, client: TestClient):
        """Test basic health check endpoint"""
        response = client.get("/api/v1/health/")
        
        assert response.status_code == 200
        data = response.json()
        
        assert "status" in data
        assert data["status"] in ["healthy", "degraded", "unhealthy"]
        assert "timestamp" in data
        assert "version" in data
        assert "components" in data
        assert len(data["components"]) >= 2  # At least database and Redis
    
    def test_detailed_health_check_unauthorized(self, client: TestClient):
        """Test detailed health check requires authentication"""
        response = client.get("/api/v1/health/detailed")
        
        assert response.status_code == 401
    
    def test_detailed_health_check_authorized(
        self, client: TestClient, admin_token: str
    ):
        """Test detailed health check with admin token"""
        response = client.get(
            "/api/v1/health/detailed",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        
        assert response.status_code == 200
        data = response.json()
        
        # Check component details
        for component in data["components"]:
            assert "name" in component
            assert "status" in component
            assert "last_checked" in component
            if component["name"] in ["database", "redis"]:
                assert "details" in component
                assert "response_time_ms" in component
    
    def test_system_metrics(
        self, client: TestClient, admin_token: str
    ):
        """Test system metrics endpoint"""
        response = client.get(
            "/api/v1/health/metrics",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        
        assert response.status_code == 200
        data = response.json()
        
        assert "cpu_usage_percent" in data
        assert "memory_usage_mb" in data
        assert "disk_usage_percent" in data
        assert "request_rate_per_second" in data
        assert "error_rate_per_second" in data
        assert "average_response_time_ms" in data
    
    def test_performance_metrics(
        self, client: TestClient, admin_token: str
    ):
        """Test performance metrics endpoint"""
        response = client.get(
            "/api/v1/health/performance?time_window_minutes=5",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        
        assert response.status_code == 200
        data = response.json()
        
        assert isinstance(data, list)
        # May be empty if no requests in last 5 minutes
        if data:
            metric = data[0]
            assert "endpoint" in metric
            assert "method" in metric
            assert "avg_response_time_ms" in metric
            assert "request_count" in metric
            assert "error_rate" in metric
    
    def test_create_alert(
        self, client: TestClient, admin_token: str
    ):
        """Test alert creation"""
        alert_data = {
            "alert_type": "error_rate",
            "severity": "warning",
            "component": "api",
            "title": "High Error Rate Test",
            "description": "Test alert creation",
            "threshold_value": 5.0,
            "actual_value": 7.5
        }
        
        response = client.post(
            "/api/v1/health/alerts",
            json=alert_data,
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        
        assert response.status_code == 200
        data = response.json()
        
        assert "id" in data
        assert data["alert_type"] == alert_data["alert_type"]
        assert data["severity"] == alert_data["severity"]
        assert data["acknowledged"] is False
        assert data["resolved"] is False
        
        return data["id"]
    
    def test_get_alerts(
        self, client: TestClient, admin_token: str
    ):
        """Test getting alerts"""
        # Create an alert first
        alert_id = self.test_create_alert(client, admin_token)
        
        # Get all alerts
        response = client.get(
            "/api/v1/health/alerts",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        
        assert response.status_code == 200
        data = response.json()
        
        assert isinstance(data, list)
        assert len(data) > 0
        
        # Find our alert
        alert = next((a for a in data if a["id"] == alert_id), None)
        assert alert is not None
    
    def test_acknowledge_alert(
        self, client: TestClient, admin_token: str
    ):
        """Test acknowledging an alert"""
        # Create an alert first
        alert_id = self.test_create_alert(client, admin_token)
        
        # Acknowledge it
        response = client.put(
            f"/api/v1/health/alerts/{alert_id}/acknowledge",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        
        assert response.status_code == 200
        
        # Verify it's acknowledged
        response = client.get(
            f"/api/v1/health/alerts?resolved=false",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        
        data = response.json()
        alert = next((a for a in data if a["id"] == alert_id), None)
        assert alert is not None
        assert alert["acknowledged"] is True
        assert alert["acknowledged_at"] is not None
    
    def test_resolve_alert(
        self, client: TestClient, admin_token: str
    ):
        """Test resolving an alert"""
        # Create an alert first
        alert_id = self.test_create_alert(client, admin_token)
        
        # Resolve it
        response = client.put(
            f"/api/v1/health/alerts/{alert_id}/resolve",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        
        assert response.status_code == 200
        
        # Verify it's resolved
        response = client.get(
            f"/api/v1/health/alerts?resolved=true",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        
        data = response.json()
        alert = next((a for a in data if a["id"] == alert_id), None)
        assert alert is not None
        assert alert["resolved"] is True
        assert alert["resolved_at"] is not None
    
    def test_log_error(self, client: TestClient):
        """Test error logging endpoint"""
        error_data = {
            "error_type": "ValueError",
            "error_message": "Test error message",
            "stack_trace": "Test stack trace",
            "endpoint": "/api/v1/test",
            "method": "POST",
            "status_code": 500
        }
        
        response = client.post(
            "/api/v1/health/errors/log",
            json=error_data
        )
        
        assert response.status_code == 201
    
    def test_get_errors(
        self, client: TestClient, admin_token: str
    ):
        """Test getting error logs"""
        # Log an error first
        self.test_log_error(client)
        
        # Get errors
        response = client.get(
            "/api/v1/health/errors?hours=1",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        
        assert response.status_code == 200
        data = response.json()
        
        assert isinstance(data, list)
        if data:
            error = data[0]
            assert "id" in error
            assert "error_type" in error
            assert "error_message" in error
            assert "created_at" in error
    
    def test_error_summary(
        self, client: TestClient, admin_token: str
    ):
        """Test error summary endpoint"""
        response = client.get(
            "/api/v1/health/errors/summary?hours=24",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        
        assert response.status_code == 200
        data = response.json()
        
        assert "total_errors" in data
        assert "unique_errors" in data
        assert "error_rate_per_hour" in data
        assert "top_errors" in data
        assert "affected_endpoints" in data
    
    def test_monitoring_dashboard(
        self, client: TestClient, admin_token: str
    ):
        """Test complete monitoring dashboard"""
        response = client.get(
            "/api/v1/health/dashboard",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        
        assert response.status_code == 200
        data = response.json()
        
        assert "health" in data
        assert "system_metrics" in data
        assert "performance" in data
        assert "recent_errors" in data
        assert "active_alerts" in data
        assert "error_summary" in data
        
        # Verify health structure
        assert data["health"]["status"] in ["healthy", "degraded", "unhealthy"]
        assert len(data["health"]["components"]) >= 2


class TestHealthService:
    """Test health monitoring service"""
    
    def test_check_database_health(self, db: Session):
        """Test database health check"""
        service = HealthService(db)
        
        # Run async method
        import asyncio
        db_health = asyncio.run(service.check_database_health())
        
        assert db_health.status in [HealthStatus.HEALTHY, HealthStatus.DEGRADED]
        assert db_health.can_connect is True
        assert db_health.response_time_ms > 0
        assert db_health.connection_pool_size >= 0
    
    def test_create_and_check_alerts(self, db: Session):
        """Test alert creation and retrieval"""
        service = HealthService(db)
        
        # Create alert
        alert_data = {
            "alert_type": AlertType.PERFORMANCE,
            "severity": AlertSeverity.WARNING,
            "component": "test",
            "title": "Test Alert",
            "description": "Unit test alert"
        }
        
        alert = service.create_alert(alert_data)
        
        assert alert.id is not None
        assert alert.acknowledged is False
        assert alert.resolved is False
    
    def test_log_error(self, db: Session):
        """Test error logging"""
        service = HealthService(db)
        
        error_data = ErrorLogCreate(
            error_type="TestError",
            error_message="Test error message",
            endpoint="/test",
            method="GET",
            status_code=500
        )
        
        # Should not raise an exception
        service.log_error(error_data)
    
    def test_record_performance_metric(self, db: Session):
        """Test performance metric recording"""
        service = HealthService(db)
        
        # Should not raise an exception
        service.record_performance_metric(
            endpoint="/api/v1/test",
            method="GET",
            response_time_ms=123.45,
            status_code=200,
            request_size_bytes=1024,
            response_size_bytes=2048
        )