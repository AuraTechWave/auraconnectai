# backend/modules/analytics/tests/test_pos_analytics_api.py

"""
Tests for POS analytics API endpoints.
"""

import pytest
from datetime import datetime, timedelta, date
from decimal import Decimal
from uuid import uuid4
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from unittest.mock import Mock, patch, AsyncMock

from modules.orders.models.external_pos_models import ExternalPOSProvider
from modules.analytics.models.pos_analytics_models import (
    POSAnalyticsSnapshot,
    POSTerminalHealth,
    POSAnalyticsAlert,
)
from modules.analytics.schemas.pos_analytics_schemas import (
    TimeRange,
    POSHealthStatus,
    AlertSeverity,
)


@pytest.fixture
def mock_pos_provider(db: Session):
    """Create a test POS provider"""
    provider = ExternalPOSProvider(
        provider_code="square",
        provider_name="Square POS",
        webhook_endpoint_id="square_webhook",
        is_active=True,
        auth_type="hmac",
        auth_config={"webhook_signature_key": "test_key"},
        settings={},
        supported_events=["payment.updated", "payment.created"],
        rate_limit_per_minute=60,
    )
    db.add(provider)
    db.commit()
    db.refresh(provider)
    return provider


@pytest.fixture
def mock_terminal_health(db: Session, mock_pos_provider):
    """Create test terminal health records"""
    terminals = []

    # Healthy terminal
    terminal1 = POSTerminalHealth(
        terminal_id="POS-001",
        provider_id=mock_pos_provider.id,
        is_online=True,
        last_seen_at=datetime.utcnow(),
        health_status="healthy",
        recent_transaction_count=100,
        recent_error_count=2,
        recent_sync_failures=0,
        recent_success_rate=98.0,
        error_threshold_exceeded=False,
        sync_failure_threshold_exceeded=False,
        offline_duration_minutes=0,
        terminal_name="Main Terminal",
        terminal_location="Front Counter",
        terminal_metadata={},
    )
    terminals.append(terminal1)

    # Degraded terminal
    terminal2 = POSTerminalHealth(
        terminal_id="POS-002",
        provider_id=mock_pos_provider.id,
        is_online=True,
        last_seen_at=datetime.utcnow(),
        health_status="degraded",
        recent_transaction_count=50,
        recent_error_count=10,
        recent_sync_failures=5,
        recent_success_rate=80.0,
        error_threshold_exceeded=True,
        sync_failure_threshold_exceeded=False,
        offline_duration_minutes=0,
        terminal_name="Secondary Terminal",
        terminal_location="Back Office",
        terminal_metadata={},
    )
    terminals.append(terminal2)

    db.add_all(terminals)
    db.commit()
    return terminals


@pytest.fixture
def mock_analytics_snapshots(db: Session, mock_pos_provider):
    """Create test analytics snapshots"""
    snapshots = []

    # Generate hourly snapshots for last 24 hours
    now = datetime.utcnow()
    for hours_ago in range(24):
        snapshot_time = now - timedelta(hours=hours_ago)

        snapshot = POSAnalyticsSnapshot(
            snapshot_id=uuid4(),
            snapshot_date=snapshot_time.date(),
            snapshot_hour=snapshot_time.hour,
            provider_id=mock_pos_provider.id,
            terminal_id="POS-001",
            total_transactions=10 + hours_ago % 5,
            successful_transactions=9 + hours_ago % 5,
            failed_transactions=1,
            total_transaction_value=Decimal("1000.00") + Decimal(str(hours_ago * 100)),
            average_transaction_value=Decimal("100.00"),
            total_syncs=5,
            successful_syncs=4,
            failed_syncs=1,
            average_sync_time_ms=250.0,
            total_webhooks=8,
            successful_webhooks=7,
            failed_webhooks=1,
            average_webhook_processing_time_ms=150.0,
            total_errors=2,
            error_types={"timeout": 1, "validation": 1},
            uptime_percentage=99.5,
            response_time_p50=200.0,
            response_time_p95=450.0,
            response_time_p99=800.0,
        )
        snapshots.append(snapshot)

    db.add_all(snapshots)
    db.commit()
    return snapshots


@pytest.fixture
def mock_pos_alert(db: Session, mock_pos_provider):
    """Create test POS alert"""
    alert = POSAnalyticsAlert(
        alert_id=uuid4(),
        alert_type="high_error_rate",
        severity="warning",
        provider_id=mock_pos_provider.id,
        terminal_id="POS-002",
        title="High Error Rate Detected",
        description="Terminal POS-002 has error rate above threshold",
        metric_value=20.0,
        threshold_value=10.0,
        is_active=True,
        acknowledged=False,
        context_data={"error_types": ["timeout", "network"]},
        notification_sent=True,
    )
    db.add(alert)
    db.commit()
    db.refresh(alert)
    return alert


class TestPOSAnalyticsDashboard:
    """Test POS analytics dashboard endpoint"""

    def test_get_dashboard_default(
        self,
        client: TestClient,
        db: Session,
        auth_headers,
        mock_pos_provider,
        mock_terminal_health,
        mock_analytics_snapshots,
    ):
        """Test getting dashboard with default parameters"""
        response = client.post(
            "/analytics/pos/dashboard",
            json={"time_range": "last_24_hours"},
            headers=auth_headers,
        )

        assert response.status_code == 200
        data = response.json()

        # Check structure
        assert "total_providers" in data
        assert "active_providers" in data
        assert "total_terminals" in data
        assert "online_terminals" in data
        assert "total_transactions" in data
        assert "transaction_success_rate" in data
        assert "providers" in data
        assert "transaction_trends" in data
        assert "active_alerts" in data

        # Verify counts
        assert data["total_providers"] >= 1
        assert data["total_terminals"] >= 2
        assert len(data["providers"]) >= 1

        # Check provider summary
        provider = data["providers"][0]
        assert provider["provider_id"] == mock_pos_provider.id
        assert provider["provider_name"] == "Square POS"
        assert provider["total_terminals"] == 2

    def test_get_dashboard_custom_range(
        self,
        client: TestClient,
        db: Session,
        auth_headers,
        mock_pos_provider,
        mock_analytics_snapshots,
    ):
        """Test dashboard with custom date range"""
        start_date = (datetime.utcnow() - timedelta(days=7)).isoformat()
        end_date = datetime.utcnow().isoformat()

        response = client.post(
            "/analytics/pos/dashboard",
            json={
                "time_range": "custom",
                "start_date": start_date,
                "end_date": end_date,
            },
            headers=auth_headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert data["time_range"] == f"{start_date} to {end_date}"

    def test_get_dashboard_filtered_provider(
        self,
        client: TestClient,
        db: Session,
        auth_headers,
        mock_pos_provider,
        mock_analytics_snapshots,
    ):
        """Test dashboard filtered by provider"""
        response = client.post(
            "/analytics/pos/dashboard",
            json={
                "time_range": "last_24_hours",
                "provider_ids": [mock_pos_provider.id],
            },
            headers=auth_headers,
        )

        assert response.status_code == 200
        data = response.json()

        # Should only include specified provider
        assert len(data["providers"]) == 1
        assert data["providers"][0]["provider_id"] == mock_pos_provider.id

    def test_get_dashboard_no_permission(self, client: TestClient, db: Session):
        """Test dashboard without proper permissions"""
        response = client.post(
            "/analytics/pos/dashboard", json={"time_range": "last_24_hours"}
        )

        assert response.status_code == 401  # Unauthorized


class TestPOSProviderDetails:
    """Test POS provider details endpoint"""

    def test_get_provider_details(
        self,
        client: TestClient,
        db: Session,
        auth_headers,
        mock_pos_provider,
        mock_terminal_health,
        mock_analytics_snapshots,
    ):
        """Test getting detailed provider analytics"""
        response = client.post(
            f"/analytics/pos/provider/{mock_pos_provider.id}/details",
            json={
                "provider_id": mock_pos_provider.id,
                "time_range": "last_24_hours",
                "include_terminals": True,
                "include_errors": True,
            },
            headers=auth_headers,
        )

        assert response.status_code == 200
        data = response.json()

        # Check structure
        assert "provider" in data
        assert "sync_metrics" in data
        assert "webhook_metrics" in data
        assert "error_analysis" in data
        assert "performance_metrics" in data
        assert "terminals" in data

        # Verify provider info
        assert data["provider"]["provider_id"] == mock_pos_provider.id
        assert data["provider"]["provider_name"] == "Square POS"

        # Check terminals included
        assert len(data["terminals"]) == 2

    def test_get_provider_details_not_found(
        self, client: TestClient, db: Session, auth_headers
    ):
        """Test getting details for non-existent provider"""
        response = client.post(
            "/analytics/pos/provider/99999/details",
            json={"provider_id": 99999, "time_range": "last_24_hours"},
            headers=auth_headers,
        )

        assert response.status_code == 404
        assert "not found" in response.json()["detail"]


class TestPOSTerminalDetails:
    """Test POS terminal details endpoint"""

    def test_get_terminal_details(
        self,
        client: TestClient,
        db: Session,
        auth_headers,
        mock_pos_provider,
        mock_terminal_health,
        mock_analytics_snapshots,
    ):
        """Test getting detailed terminal analytics"""
        response = client.post(
            "/analytics/pos/terminal/POS-001/details",
            json={"terminal_id": "POS-001", "time_range": "last_24_hours"},
            headers=auth_headers,
        )

        assert response.status_code == 200
        data = response.json()

        # Check structure
        assert "terminal" in data
        assert "transaction_metrics" in data
        assert "sync_metrics" in data
        assert "error_analysis" in data
        assert "performance_metrics" in data

        # Verify terminal info
        assert data["terminal"]["terminal_id"] == "POS-001"
        assert data["terminal"]["terminal_name"] == "Main Terminal"
        assert data["terminal"]["health_status"] == "healthy"


class TestPOSAlerts:
    """Test POS alerts endpoints"""

    def test_get_active_alerts(
        self,
        client: TestClient,
        db: Session,
        auth_headers,
        mock_pos_provider,
        mock_pos_alert,
    ):
        """Test getting active alerts"""
        response = client.get("/analytics/pos/alerts/active", headers=auth_headers)

        assert response.status_code == 200
        data = response.json()

        assert "alerts" in data
        assert "total_count" in data
        assert data["total_count"] >= 1

        # Check alert structure
        alert = data["alerts"][0]
        assert alert["alert_type"] == "high_error_rate"
        assert alert["severity"] == "warning"
        assert alert["terminal_id"] == "POS-002"

    def test_get_alerts_filtered(
        self,
        client: TestClient,
        db: Session,
        auth_headers,
        mock_pos_provider,
        mock_pos_alert,
    ):
        """Test getting alerts with filters"""
        response = client.get(
            f"/analytics/pos/alerts/active?severity=warning&provider_id={mock_pos_provider.id}",
            headers=auth_headers,
        )

        assert response.status_code == 200
        data = response.json()

        # Should match filter criteria
        assert all(a["severity"] == "warning" for a in data["alerts"])
        assert all(a["provider_id"] == mock_pos_provider.id for a in data["alerts"])

    def test_acknowledge_alert(
        self,
        client: TestClient,
        db: Session,
        auth_headers,
        mock_pos_provider,
        mock_pos_alert,
        mock_staff_user,
    ):
        """Test acknowledging an alert"""
        # Need analytics.manage permission
        with patch("backend.core.rbac.require_permissions", new_callable=AsyncMock):
            response = client.post(
                f"/analytics/pos/alerts/{mock_pos_alert.alert_id}/acknowledge?notes=Investigating",
                headers=auth_headers,
            )

            assert response.status_code == 200
            data = response.json()
            assert data["success"] is True

            # Verify alert was acknowledged
            db.refresh(mock_pos_alert)
            assert mock_pos_alert.acknowledged is True
            assert mock_pos_alert.acknowledged_by is not None


class TestPOSHealthSummary:
    """Test terminal health summary endpoint"""

    def test_get_terminal_health(
        self,
        client: TestClient,
        db: Session,
        auth_headers,
        mock_pos_provider,
        mock_terminal_health,
    ):
        """Test getting terminal health summary"""
        response = client.get("/analytics/pos/health/terminals", headers=auth_headers)

        assert response.status_code == 200
        data = response.json()

        assert "summary" in data
        assert "total_terminals" in data
        assert data["total_terminals"] == 2

        # Check breakdown by provider
        provider_summary = data["summary"]["Square POS"]
        assert provider_summary["total"] == 2
        assert provider_summary["healthy"] == 1
        assert provider_summary["degraded"] == 1


class TestPOSTransactionTrends:
    """Test transaction trends endpoint"""

    def test_get_transaction_trends(
        self,
        client: TestClient,
        db: Session,
        auth_headers,
        mock_pos_provider,
        mock_analytics_snapshots,
    ):
        """Test getting transaction trend data"""
        response = client.get(
            "/analytics/pos/trends/transactions?time_range=last_24_hours&granularity=hourly",
            headers=auth_headers,
        )

        assert response.status_code == 200
        data = response.json()

        assert "trends" in data
        assert "data_points" in data
        assert data["granularity"] == "hourly"
        assert len(data["trends"]) > 0

        # Check trend data structure
        trend = data["trends"][0]
        assert "timestamp" in trend
        assert "transaction_count" in trend
        assert "transaction_value" in trend
        assert "success_rate" in trend


class TestPOSExport:
    """Test POS analytics export endpoint"""

    @patch(
        "backend.modules.analytics.services.pos_analytics_service.POSAnalyticsService.export_analytics"
    )
    async def test_export_analytics(
        self,
        mock_export,
        client: TestClient,
        db: Session,
        auth_headers,
        mock_pos_provider,
    ):
        """Test exporting analytics data"""
        # Mock the export service to return a file path
        mock_export.return_value = "/tmp/test_export.csv"

        # Need analytics.export permission
        with patch("backend.core.rbac.require_permissions", new_callable=AsyncMock):
            response = client.post(
                "/analytics/pos/export",
                json={
                    "report_type": "summary",
                    "format": "csv",
                    "time_range": "last_7_days",
                },
                headers=auth_headers,
            )

            # Should return file
            assert response.status_code == 200
            assert response.headers["content-type"] == "text/csv"


class TestPOSCompareProviders:
    """Test provider comparison endpoint"""

    def test_compare_providers(
        self, client: TestClient, db: Session, auth_headers, mock_pos_provider
    ):
        """Test comparing multiple providers"""
        # Create second provider
        provider2 = ExternalPOSProvider(
            provider_code="stripe",
            provider_name="Stripe Terminal",
            webhook_endpoint_id="stripe_webhook",
            is_active=True,
            auth_type="api_key",
            auth_config={"api_key": "test_key"},
            settings={},
            supported_events=["payment_intent.succeeded"],
            rate_limit_per_minute=100,
        )
        db.add(provider2)
        db.commit()

        response = client.post(
            "/analytics/pos/compare",
            json={
                "provider_ids": [mock_pos_provider.id, provider2.id],
                "time_range": "last_7_days",
                "metrics": ["transactions", "success_rate", "uptime"],
            },
            headers=auth_headers,
        )

        assert response.status_code == 200
        data = response.json()

        assert "providers" in data
        assert "comparison_data" in data
        assert "rankings" in data
        assert len(data["providers"]) == 2
