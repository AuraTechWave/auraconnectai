"""
Integration tests for Phase 4: Enhanced Payroll API endpoints.

Tests cover:
- Authentication and authorization
- Request/response validation
- Error handling
- OpenAPI documentation compliance
"""

import pytest
from fastapi.testclient import TestClient
from unittest.mock import Mock, patch, AsyncMock
from datetime import date, datetime
from decimal import Decimal

from ....app.main import app


@pytest.fixture
def client():
    """Create test client."""
    return TestClient(app)


@pytest.fixture
def auth_headers():
    """Get authentication headers for testing."""
    # In a real test, you would authenticate and get a real token
    return {"Authorization": "Bearer test_token"}


class TestAuthenticationEndpoints:
    """Test authentication endpoints."""

    def test_login_success(self, client):
        """Test successful login."""
        response = client.post(
            "/auth/login", data={"username": "admin", "password": "secret"}
        )

        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert data["token_type"] == "bearer"
        assert "user_info" in data
        assert data["user_info"]["username"] == "admin"

    def test_login_invalid_credentials(self, client):
        """Test login with invalid credentials."""
        response = client.post(
            "/auth/login", data={"username": "admin", "password": "wrong_password"}
        )

        assert response.status_code == 401
        assert "Incorrect username or password" in response.json()["detail"]

    def test_get_current_user_without_token(self, client):
        """Test accessing protected endpoint without token."""
        response = client.get("/auth/me")

        assert response.status_code == 401

    @patch("backend.core.auth.verify_token")
    @patch("backend.core.auth.get_user")
    def test_get_current_user_with_valid_token(
        self, mock_get_user, mock_verify_token, client
    ):
        """Test accessing user info with valid token."""
        # Mock token verification
        mock_verify_token.return_value = Mock(
            user_id=1, username="admin", roles=["admin"], tenant_ids=[1, 2]
        )
        mock_get_user.return_value = Mock(
            id=1,
            username="admin",
            email="admin@example.com",
            roles=["admin"],
            tenant_ids=[1, 2],
            is_active=True,
        )

        response = client.get(
            "/auth/me", headers={"Authorization": "Bearer valid_token"}
        )

        assert response.status_code == 200
        data = response.json()
        assert data["username"] == "admin"
        assert "admin" in data["roles"]


class TestPayrollRunEndpoint:
    """Test POST /payrolls/run endpoint."""

    @patch("backend.core.auth.verify_token")
    @patch("backend.core.auth.get_user")
    @patch(
        "backend.modules.staff.services.enhanced_payroll_service.EnhancedPayrollService"
    )
    def test_run_payroll_success(
        self, mock_service, mock_get_user, mock_verify_token, client
    ):
        """Test successful payroll run."""
        # Mock authentication
        mock_verify_token.return_value = Mock(
            user_id=1, username="admin", roles=["admin"], tenant_ids=[1]
        )
        mock_get_user.return_value = Mock(
            id=1, username="admin", roles=["admin"], tenant_ids=[1], is_active=True
        )

        request_data = {
            "staff_ids": [1, 2, 3],
            "pay_period_start": "2024-01-15",
            "pay_period_end": "2024-01-29",
            "tenant_id": 1,
            "force_recalculate": False,
        }

        response = client.post(
            "/payrolls/run",
            json=request_data,
            headers={"Authorization": "Bearer valid_token"},
        )

        assert response.status_code == 202
        data = response.json()
        assert "job_id" in data
        assert data["status"] == "processing"
        assert data["total_staff"] == 3
        assert data["pay_period_start"] == "2024-01-15"
        assert data["pay_period_end"] == "2024-01-29"

    def test_run_payroll_unauthorized(self, client):
        """Test payroll run without authentication."""
        request_data = {
            "staff_ids": [1, 2, 3],
            "pay_period_start": "2024-01-15",
            "pay_period_end": "2024-01-29",
        }

        response = client.post("/payrolls/run", json=request_data)
        assert response.status_code == 401

    @patch("backend.core.auth.verify_token")
    @patch("backend.core.auth.get_user")
    def test_run_payroll_insufficient_permissions(
        self, mock_get_user, mock_verify_token, client
    ):
        """Test payroll run with insufficient permissions."""
        # Mock authentication with insufficient role
        mock_verify_token.return_value = Mock(
            user_id=3, username="manager", roles=["manager"], tenant_ids=[1]
        )
        mock_get_user.return_value = Mock(
            id=3, username="manager", roles=["manager"], tenant_ids=[1], is_active=True
        )

        request_data = {
            "staff_ids": [1, 2, 3],
            "pay_period_start": "2024-01-15",
            "pay_period_end": "2024-01-29",
        }

        response = client.post(
            "/payrolls/run",
            json=request_data,
            headers={"Authorization": "Bearer valid_token"},
        )

        assert response.status_code == 403
        assert "requires one of these roles" in response.json()["detail"]

    @patch("backend.core.auth.verify_token")
    @patch("backend.core.auth.get_user")
    def test_run_payroll_invalid_date_range(
        self, mock_get_user, mock_verify_token, client
    ):
        """Test payroll run with invalid date range."""
        # Mock authentication
        mock_verify_token.return_value = Mock(
            user_id=1, username="admin", roles=["admin"], tenant_ids=[1]
        )
        mock_get_user.return_value = Mock(
            id=1, username="admin", roles=["admin"], tenant_ids=[1], is_active=True
        )

        request_data = {
            "staff_ids": [1, 2, 3],
            "pay_period_start": "2024-01-29",  # End before start
            "pay_period_end": "2024-01-15",
        }

        response = client.post(
            "/payrolls/run",
            json=request_data,
            headers={"Authorization": "Bearer valid_token"},
        )

        assert response.status_code == 422  # Validation error

    @patch("backend.core.auth.verify_token")
    @patch("backend.core.auth.get_user")
    def test_run_payroll_empty_staff_list(
        self, mock_get_user, mock_verify_token, client
    ):
        """Test payroll run with empty staff list."""
        # Mock authentication
        mock_verify_token.return_value = Mock(
            user_id=1, username="admin", roles=["admin"], tenant_ids=[1]
        )
        mock_get_user.return_value = Mock(
            id=1, username="admin", roles=["admin"], tenant_ids=[1], is_active=True
        )

        request_data = {
            "staff_ids": [],  # Empty list should fail validation
            "pay_period_start": "2024-01-15",
            "pay_period_end": "2024-01-29",
        }

        response = client.post(
            "/payrolls/run",
            json=request_data,
            headers={"Authorization": "Bearer valid_token"},
        )

        assert response.status_code == 422  # Validation error


class TestPayrollRetrievalEndpoints:
    """Test payroll retrieval endpoints."""

    @patch("backend.core.auth.verify_token")
    @patch("backend.core.auth.get_user")
    @patch(
        "backend.modules.staff.services.enhanced_payroll_service.EnhancedPayrollService"
    )
    def test_get_staff_payroll_success(
        self, mock_service, mock_get_user, mock_verify_token, client
    ):
        """Test successful staff payroll retrieval."""
        # Mock authentication
        mock_verify_token.return_value = Mock(
            user_id=1, username="admin", roles=["admin"], tenant_ids=[1]
        )
        mock_get_user.return_value = Mock(
            id=1, username="admin", roles=["admin"], tenant_ids=[1], is_active=True
        )

        # Mock service response
        mock_service_instance = Mock()
        mock_service.return_value = mock_service_instance
        mock_service_instance.get_employee_payment_history = AsyncMock(
            return_value=[
                {
                    "id": 1,
                    "pay_period_start": date(2024, 1, 15),
                    "pay_period_end": date(2024, 1, 29),
                    "gross_amount": Decimal("800.00"),
                    "net_amount": Decimal("600.00"),
                    "regular_hours": Decimal("40.00"),
                    "overtime_hours": Decimal("5.00"),
                    "processed_at": datetime(2024, 1, 30, 10, 0, 0),
                }
            ]
        )

        response = client.get(
            "/payrolls/1?limit=10", headers={"Authorization": "Bearer valid_token"}
        )

        assert response.status_code == 200
        data = response.json()
        assert data["staff_id"] == 1
        assert len(data["payroll_history"]) == 1
        assert data["payroll_history"][0]["gross_pay"] == 800.0
        assert data["payroll_history"][0]["net_pay"] == 600.0

    @patch("backend.core.auth.verify_token")
    @patch("backend.core.auth.get_user")
    @patch(
        "backend.modules.staff.services.enhanced_payroll_service.EnhancedPayrollService"
    )
    def test_get_staff_payroll_detail_success(
        self, mock_service, mock_get_user, mock_verify_token, client
    ):
        """Test successful detailed payroll retrieval."""
        # Mock authentication
        mock_verify_token.return_value = Mock(
            user_id=1, username="admin", roles=["admin"], tenant_ids=[1]
        )
        mock_get_user.return_value = Mock(
            id=1, username="admin", roles=["admin"], tenant_ids=[1], is_active=True
        )

        # Mock service response
        mock_service_instance = Mock()
        mock_service.return_value = mock_service_instance

        mock_breakdown = Mock()
        mock_breakdown.hours_worked = 40.0
        mock_breakdown.overtime_hours = 5.0
        mock_breakdown.hourly_rate = 15.0
        mock_breakdown.overtime_rate = 22.5
        mock_breakdown.tax_deductions = 160.0
        mock_breakdown.other_deductions = 55.0

        mock_payroll_response = Mock()
        mock_payroll_response.gross_pay = 787.5
        mock_payroll_response.deductions = 215.0
        mock_payroll_response.net_pay = 572.5
        mock_payroll_response.breakdown = mock_breakdown
        mock_payroll_response.created_at = datetime(2024, 1, 30, 10, 0, 0)

        mock_service_instance.process_payroll_for_staff = AsyncMock(
            return_value=mock_payroll_response
        )

        response = client.get(
            "/payrolls/1/detail?pay_period_start=2024-01-15&pay_period_end=2024-01-29",
            headers={"Authorization": "Bearer valid_token"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["staff_id"] == 1
        assert data["regular_hours"] == 40.0
        assert data["overtime_hours"] == 5.0
        assert data["gross_pay"] == 787.5
        assert data["net_pay"] == 572.5


class TestTaxRulesEndpoint:
    """Test GET /payrolls/rules endpoint."""

    @patch("backend.core.auth.verify_token")
    @patch("backend.core.auth.get_user")
    def test_get_tax_rules_success(self, mock_get_user, mock_verify_token, client):
        """Test successful tax rules retrieval."""
        # Mock authentication
        mock_verify_token.return_value = Mock(
            user_id=1, username="admin", roles=["admin"], tenant_ids=[1]
        )
        mock_get_user.return_value = Mock(
            id=1, username="admin", roles=["admin"], tenant_ids=[1], is_active=True
        )

        with patch("sqlalchemy.orm.Session") as mock_session:
            # Mock database query
            mock_rule = Mock()
            mock_rule.id = 1
            mock_rule.tax_type.value = "federal"
            mock_rule.jurisdiction = "US"
            mock_rule.rate = Decimal("0.12")
            mock_rule.description = "Federal income tax"
            mock_rule.effective_date = date(2024, 1, 1)
            mock_rule.expiry_date = None
            mock_rule.is_active = True

            mock_query = Mock()
            mock_query.all.return_value = [mock_rule]
            mock_query.filter.return_value = mock_query
            mock_session.return_value.query.return_value = mock_query

            response = client.get(
                "/payrolls/rules?location=US&active_only=true",
                headers={"Authorization": "Bearer valid_token"},
            )

            assert response.status_code == 200
            data = response.json()
            assert data["location"] == "US"
            assert data["total_rules"] == 1
            assert data["active_rules"] == 1
            assert len(data["tax_rules"]) == 1
            assert data["tax_rules"][0]["tax_type"] == "federal"
            assert data["tax_rules"][0]["rate"] == 0.12

    def test_get_tax_rules_unauthorized(self, client):
        """Test tax rules retrieval without authentication."""
        response = client.get("/payrolls/rules")
        assert response.status_code == 401


class TestPayrollStatsEndpoint:
    """Test GET /payrolls/stats endpoint."""

    @patch("backend.core.auth.verify_token")
    @patch("backend.core.auth.get_user")
    @patch(
        "backend.modules.staff.services.enhanced_payroll_service.EnhancedPayrollService"
    )
    def test_get_payroll_stats_success(
        self, mock_service, mock_get_user, mock_verify_token, client
    ):
        """Test successful payroll statistics retrieval."""
        # Mock authentication
        mock_verify_token.return_value = Mock(
            user_id=1, username="admin", roles=["admin"], tenant_ids=[1]
        )
        mock_get_user.return_value = Mock(
            id=1, username="admin", roles=["admin"], tenant_ids=[1], is_active=True
        )

        # Mock service response
        mock_service_instance = Mock()
        mock_service.return_value = mock_service_instance
        mock_service_instance.get_payroll_summary = AsyncMock(
            return_value={
                "total_employees": 5,
                "total_gross_pay": Decimal("4000.00"),
                "total_net_pay": Decimal("3200.00"),
                "total_tax_deductions": Decimal("600.00"),
                "total_benefit_deductions": Decimal("200.00"),
                "average_hours_per_employee": Decimal("42.5"),
            }
        )

        response = client.get(
            "/payrolls/stats?period_start=2024-01-15&period_end=2024-01-29",
            headers={"Authorization": "Bearer valid_token"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["total_employees"] == 5
        assert data["total_gross_pay"] == 4000.0
        assert data["total_net_pay"] == 3200.0
        assert data["average_hours_per_employee"] == 42.5
        assert "deduction_breakdown" in data
        assert "earnings_breakdown" in data


class TestPayrollExportEndpoint:
    """Test POST /payrolls/export endpoint."""

    @patch("backend.core.auth.verify_token")
    @patch("backend.core.auth.get_user")
    def test_export_payroll_success(self, mock_get_user, mock_verify_token, client):
        """Test successful payroll export initiation."""
        # Mock authentication
        mock_verify_token.return_value = Mock(
            user_id=1, username="admin", roles=["admin"], tenant_ids=[1]
        )
        mock_get_user.return_value = Mock(
            id=1, username="admin", roles=["admin"], tenant_ids=[1], is_active=True
        )

        request_data = {
            "format": "csv",
            "pay_period_start": "2024-01-15",
            "pay_period_end": "2024-01-29",
            "include_details": True,
            "tenant_id": 1,
        }

        response = client.post(
            "/payrolls/export",
            json=request_data,
            headers={"Authorization": "Bearer valid_token"},
        )

        assert response.status_code == 200
        data = response.json()
        assert "export_id" in data
        assert data["status"] == "processing"

    @patch("backend.core.auth.verify_token")
    @patch("backend.core.auth.get_user")
    def test_export_payroll_invalid_format(
        self, mock_get_user, mock_verify_token, client
    ):
        """Test payroll export with invalid format."""
        # Mock authentication
        mock_verify_token.return_value = Mock(
            user_id=1, username="admin", roles=["admin"], tenant_ids=[1]
        )
        mock_get_user.return_value = Mock(
            id=1, username="admin", roles=["admin"], tenant_ids=[1], is_active=True
        )

        request_data = {
            "format": "invalid_format",  # Should fail validation
            "pay_period_start": "2024-01-15",
            "pay_period_end": "2024-01-29",
        }

        response = client.post(
            "/payrolls/export",
            json=request_data,
            headers={"Authorization": "Bearer valid_token"},
        )

        assert response.status_code == 422  # Validation error


class TestAPIDocumentation:
    """Test OpenAPI documentation generation."""

    def test_openapi_schema_generation(self, client):
        """Test that OpenAPI schema is generated correctly."""
        response = client.get("/openapi.json")

        assert response.status_code == 200
        schema = response.json()

        # Verify basic structure
        assert "openapi" in schema
        assert "info" in schema
        assert schema["info"]["title"] == "AuraConnect AI - Restaurant Management API"
        assert schema["info"]["version"] == "4.0.0"

        # Verify payroll endpoints are documented
        paths = schema["paths"]
        assert "/payrolls/run" in paths
        assert "/payrolls/{staff_id}" in paths
        assert "/payrolls/rules" in paths
        assert "/auth/login" in paths

        # Verify authentication scheme is documented
        assert "components" in schema
        assert "securitySchemes" in schema["components"]

    def test_interactive_docs_available(self, client):
        """Test that interactive API documentation is available."""
        response = client.get("/docs")
        assert response.status_code == 200
        assert "text/html" in response.headers["content-type"]

    def test_redoc_available(self, client):
        """Test that ReDoc documentation is available."""
        response = client.get("/redoc")
        assert response.status_code == 200
        assert "text/html" in response.headers["content-type"]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
