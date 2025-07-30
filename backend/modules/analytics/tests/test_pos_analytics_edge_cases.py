# backend/modules/analytics/tests/test_pos_analytics_edge_cases.py

"""
Edge case tests for POS analytics API.
"""

import pytest
from datetime import datetime, timedelta
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from unittest.mock import Mock, patch, AsyncMock

from backend.modules.analytics.services.pos_dashboard_service import POSDashboardService
from backend.modules.analytics.schemas.pos_analytics_schemas import TimeRange


class TestPOSAnalyticsEdgeCases:
    """Test edge cases for POS analytics"""
    
    def test_dashboard_no_providers(
        self, client: TestClient, db: Session, auth_headers
    ):
        """Test dashboard when no providers exist"""
        response = client.post(
            "/analytics/pos/dashboard",
            json={"time_range": "last_24_hours"},
            headers=auth_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["total_providers"] == 0
        assert data["active_providers"] == 0
        assert data["total_terminals"] == 0
        assert data["providers"] == []
        assert data["transaction_trends"] == []
    
    def test_dashboard_empty_snapshots(
        self, client: TestClient, db: Session, auth_headers,
        mock_pos_provider
    ):
        """Test dashboard when provider exists but no snapshot data"""
        response = client.post(
            "/analytics/pos/dashboard",
            json={"time_range": "last_24_hours"},
            headers=auth_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        
        # Should still show provider with zero metrics
        assert data["total_providers"] >= 1
        assert len(data["providers"]) >= 1
        
        provider = data["providers"][0]
        assert provider["total_transactions"] == 0
        assert provider["transaction_success_rate"] == 0.0
    
    def test_dashboard_invalid_time_range(
        self, client: TestClient, db: Session, auth_headers
    ):
        """Test dashboard with invalid custom time range"""
        # End date before start date
        response = client.post(
            "/analytics/pos/dashboard",
            json={
                "time_range": "custom",
                "start_date": "2025-01-30T00:00:00Z",
                "end_date": "2025-01-29T00:00:00Z"
            },
            headers=auth_headers
        )
        
        assert response.status_code == 400
        assert "start_date must be before end_date" in response.json()["detail"]
    
    def test_dashboard_custom_range_too_long(
        self, client: TestClient, db: Session, auth_headers
    ):
        """Test dashboard with custom range exceeding 90 days"""
        start_date = datetime.utcnow() - timedelta(days=100)
        end_date = datetime.utcnow()
        
        response = client.post(
            "/analytics/pos/dashboard",
            json={
                "time_range": "custom",
                "start_date": start_date.isoformat(),
                "end_date": end_date.isoformat()
            },
            headers=auth_headers
        )
        
        assert response.status_code == 400
        assert "cannot exceed 90 days" in response.json()["detail"]
    
    def test_alerts_pagination_edge_cases(
        self, client: TestClient, db: Session, auth_headers
    ):
        """Test alert pagination edge cases"""
        # Test with offset beyond total
        response = client.get(
            "/analytics/pos/alerts/active?limit=10&offset=1000",
            headers=auth_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["alerts"] == []
        assert data["has_more"] is False
    
    def test_acknowledge_invalid_alert_id(
        self, client: TestClient, db: Session, auth_headers
    ):
        """Test acknowledging alert with invalid ID format"""
        with patch('backend.core.rbac.require_permissions', new_callable=AsyncMock):
            response = client.post(
                "/analytics/pos/alerts/invalid-uuid/acknowledge",
                headers=auth_headers
            )
            
            assert response.status_code == 404
            assert "Invalid alert ID format" in response.json()["detail"]
    
    def test_trends_no_data_period(
        self, client: TestClient, db: Session, auth_headers
    ):
        """Test trends for period with no data"""
        # Request trends for far future date
        future_date = datetime.utcnow() + timedelta(days=365)
        
        response = client.get(
            f"/analytics/pos/trends/transactions?time_range=custom"
            f"&start_date={future_date.isoformat()}"
            f"&end_date={(future_date + timedelta(days=1)).isoformat()}",
            headers=auth_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["trends"] == []
        assert data["data_points"] == 0
    
    def test_export_invalid_report_type(
        self, client: TestClient, db: Session, auth_headers
    ):
        """Test export with invalid report type"""
        with patch('backend.core.rbac.require_permissions', new_callable=AsyncMock):
            response = client.post(
                "/analytics/pos/export",
                json={
                    "report_type": "invalid_type",
                    "format": "csv",
                    "time_range": "last_7_days"
                },
                headers=auth_headers
            )
            
            assert response.status_code == 400
            assert "Invalid report type" in response.json()["detail"]
    
    def test_compare_single_provider(
        self, client: TestClient, db: Session, auth_headers,
        mock_pos_provider
    ):
        """Test comparison with only one provider (should fail)"""
        response = client.post(
            "/analytics/pos/compare",
            json={
                "provider_ids": [mock_pos_provider.id],
                "time_range": "last_7_days",
                "metrics": ["transactions"]
            },
            headers=auth_headers
        )
        
        assert response.status_code == 422  # Validation error
        assert "at least 2" in str(response.json()["detail"])
    
    def test_terminal_health_all_offline(
        self, client: TestClient, db: Session, auth_headers,
        mock_pos_provider
    ):
        """Test terminal health when all terminals are offline"""
        # Create offline terminals
        from backend.modules.analytics.models.pos_analytics_models import POSTerminalHealth
        
        for i in range(3):
            terminal = POSTerminalHealth(
                terminal_id=f"OFFLINE-{i}",
                provider_id=mock_pos_provider.id,
                is_online=False,
                last_seen_at=datetime.utcnow() - timedelta(hours=2),
                health_status="offline",
                recent_transaction_count=0,
                recent_error_count=0,
                recent_sync_failures=0,
                recent_success_rate=0.0,
                error_threshold_exceeded=False,
                sync_failure_threshold_exceeded=False,
                offline_duration_minutes=120,
                terminal_metadata={}
            )
            db.add(terminal)
        db.commit()
        
        response = client.get(
            "/analytics/pos/health/terminals",
            headers=auth_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        
        provider_summary = data["summary"].get(mock_pos_provider.provider_name, {})
        assert provider_summary["offline"] >= 3
        assert provider_summary["healthy"] == 0


class TestCachingBehavior:
    """Test caching functionality"""
    
    @patch('backend.modules.analytics.services.pos_dashboard_service.cache_service')
    async def test_dashboard_cache_hit(
        self, mock_cache, client: TestClient, auth_headers
    ):
        """Test dashboard returns cached data when available"""
        # Mock cache to return data
        cached_response = {
            "total_providers": 1,
            "active_providers": 1,
            # ... minimal valid response
        }
        mock_cache.get.return_value = json.dumps(cached_response)
        
        response = client.post(
            "/analytics/pos/dashboard",
            json={"time_range": "last_24_hours"},
            headers=auth_headers
        )
        
        assert response.status_code == 200
        # Should have called cache.get but not cache.set
        assert mock_cache.get.called
        assert not mock_cache.set.called
    
    @patch('backend.modules.analytics.services.pos_dashboard_service.cache_service')
    async def test_refresh_clears_cache(
        self, mock_cache, client: TestClient, auth_headers
    ):
        """Test refresh endpoint clears cache"""
        with patch('backend.core.rbac.require_permissions', new_callable=AsyncMock):
            response = client.post(
                "/analytics/pos/refresh",
                headers=auth_headers
            )
            
            assert response.status_code == 200
            # Should have cleared cache
            assert mock_cache.delete_pattern.called


class TestPerformanceScenarios:
    """Test performance with large datasets (mocked)"""
    
    @patch('backend.modules.analytics.services.pos_dashboard_service.POSDashboardService._get_provider_summaries')
    async def test_dashboard_large_dataset(
        self, mock_summaries, client: TestClient, auth_headers
    ):
        """Test dashboard performance with many providers"""
        # Mock 100 providers
        mock_summaries.return_value = [
            Mock(
                provider_id=i,
                provider_name=f"Provider {i}",
                total_transactions=1000,
                transaction_success_rate=95.0,
                total_terminals=10,
                active_terminals=8,
                # ... other required fields
            )
            for i in range(100)
        ]
        
        response = client.post(
            "/analytics/pos/dashboard",
            json={"time_range": "last_24_hours"},
            headers=auth_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["total_providers"] == 100