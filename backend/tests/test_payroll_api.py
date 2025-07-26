"""
Comprehensive API tests for Enhanced Payroll Endpoints (AUR-278).

Tests cover:
- POST /payrolls/run - Payroll execution
- GET /payrolls/run/{job_id}/status - Job status tracking
- GET /payrolls/{staff_id} - Staff payroll history
- GET /payrolls/{staff_id}/detail - Detailed payroll information
- GET /payrolls/rules - Tax rules and policies
- Authentication and authorization
- Input validation and error handling
- Response format validation
"""

import pytest
import json
from decimal import Decimal
from datetime import datetime, date, timedelta
from unittest.mock import Mock, patch, MagicMock
from fastapi.testclient import TestClient
from fastapi import status

from ..main import app
from ..core.auth import create_access_token
from ..modules.staff.schemas.enhanced_payroll_schemas import (
    PayrollRunRequest, PayrollRunResponse, PayrollBatchStatus,
    PayrollHistoryResponse, StaffPayrollDetail, PayrollRulesResponse
)


# Create test client
client = TestClient(app)


class TestPayrollAPIAuthentication:
    """Test authentication and authorization for payroll endpoints."""
    
    def test_payroll_run_requires_authentication(self):
        """Test that payroll run endpoint requires authentication."""
        request_data = {
            "staff_ids": [1, 2, 3],
            "pay_period_start": "2024-06-01",
            "pay_period_end": "2024-06-15",
            "tenant_id": 1
        }
        
        response = client.post("/payrolls/run", json=request_data)
        assert response.status_code == status.HTTP_401_UNAUTHORIZED
    
    def test_payroll_run_requires_proper_role(self):
        """Test that payroll run requires payroll_write role."""
        # Create token with insufficient privileges
        token_data = {
            "sub": "viewer_user",
            "user_id": 1,
            "roles": ["viewer"],  # No payroll access
            "tenant_ids": [1]
        }
        token = create_access_token(token_data)
        headers = {"Authorization": f"Bearer {token}"}
        
        request_data = {
            "staff_ids": [1, 2, 3],
            "pay_period_start": "2024-06-01",
            "pay_period_end": "2024-06-15",
            "tenant_id": 1
        }
        
        response = client.post("/payrolls/run", json=request_data, headers=headers)
        assert response.status_code == status.HTTP_403_FORBIDDEN
    
    def test_payroll_history_requires_authentication(self):
        """Test that payroll history endpoint requires authentication."""
        response = client.get("/payrolls/123")
        assert response.status_code == status.HTTP_401_UNAUTHORIZED
    
    def test_job_status_requires_authentication(self):
        """Test that job status endpoint requires authentication."""
        response = client.get("/payrolls/run/test-job-id/status")
        assert response.status_code == status.HTTP_401_UNAUTHORIZED


class TestPayrollRunAPI:
    """Test payroll run endpoint functionality."""
    
    @pytest.fixture
    def auth_headers(self):
        """Create authentication headers with payroll permissions."""
        token_data = {
            "sub": "payroll_manager",
            "user_id": 1,
            "roles": ["payroll_manager", "payroll_write"],
            "tenant_ids": [1]
        }
        token = create_access_token(token_data)
        return {"Authorization": f"Bearer {token}"}
    
    def test_payroll_run_success(self, auth_headers):
        """Test successful payroll run initiation."""
        request_data = {
            "staff_ids": [1, 2, 3],
            "pay_period_start": "2024-06-01",
            "pay_period_end": "2024-06-15",
            "tenant_id": 1,
            "force_recalculate": False
        }
        
        with patch("modules.staff.services.enhanced_payroll_service.EnhancedPayrollService"):
            with patch("modules.payroll.services.payroll_configuration_service.PayrollConfigurationService") as mock_config:
                # Mock job tracking creation
                mock_job = Mock()
                mock_job.job_id = "test-job-123"
                mock_config.return_value.create_job_tracking.return_value = mock_job
                mock_config.return_value.update_job_progress.return_value = None
                
                response = client.post("/payrolls/run", json=request_data, headers=auth_headers)
                
                assert response.status_code == status.HTTP_202_ACCEPTED
                data = response.json()
                
                # Verify response structure
                assert "job_id" in data
                assert "status" in data
                assert "message" in data
                assert data["status"] == "accepted"
    
    def test_payroll_run_validation_invalid_dates(self, auth_headers):
        """Test payroll run with invalid date range."""
        request_data = {
            "staff_ids": [1, 2, 3],
            "pay_period_start": "2024-06-15",  # Start after end
            "pay_period_end": "2024-06-01",
            "tenant_id": 1
        }
        
        response = client.post("/payrolls/run", json=request_data, headers=auth_headers)
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
    
    def test_payroll_run_validation_missing_required_fields(self, auth_headers):
        """Test payroll run with missing required fields."""
        request_data = {
            "staff_ids": [1, 2, 3],
            # Missing pay_period_start and pay_period_end
            "tenant_id": 1
        }
        
        response = client.post("/payrolls/run", json=request_data, headers=auth_headers)
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
    
    def test_payroll_run_validation_empty_staff_ids(self, auth_headers):
        """Test payroll run with empty staff IDs (should process all staff)."""
        request_data = {
            "staff_ids": None,  # Process all staff
            "pay_period_start": "2024-06-01",
            "pay_period_end": "2024-06-15",
            "tenant_id": 1
        }
        
        with patch("modules.staff.services.enhanced_payroll_service.EnhancedPayrollService"):
            with patch("modules.payroll.services.payroll_configuration_service.PayrollConfigurationService") as mock_config:
                mock_job = Mock()
                mock_job.job_id = "test-job-456"
                mock_config.return_value.create_job_tracking.return_value = mock_job
                mock_config.return_value.update_job_progress.return_value = None
                
                response = client.post("/payrolls/run", json=request_data, headers=auth_headers)
                
                assert response.status_code == status.HTTP_202_ACCEPTED
                data = response.json()
                assert "job_id" in data
    
    def test_payroll_run_service_error(self, auth_headers):
        """Test payroll run when service encounters an error."""
        request_data = {
            "staff_ids": [1, 2, 3],
            "pay_period_start": "2024-06-01",
            "pay_period_end": "2024-06-15",
            "tenant_id": 1
        }
        
        with patch("modules.staff.services.enhanced_payroll_service.EnhancedPayrollService") as mock_service:
            mock_service.side_effect = Exception("Service unavailable")
            
            response = client.post("/payrolls/run", json=request_data, headers=auth_headers)
            
            assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
            data = response.json()
            assert "detail" in data


class TestJobStatusAPI:
    """Test job status tracking endpoint."""
    
    @pytest.fixture
    def auth_headers(self):
        """Create authentication headers with payroll access."""
        token_data = {
            "sub": "payroll_clerk",
            "user_id": 2,
            "roles": ["payroll_clerk", "payroll_access"],
            "tenant_ids": [1]
        }
        token = create_access_token(token_data)
        return {"Authorization": f"Bearer {token}"}
    
    def test_get_job_status_success(self, auth_headers):
        """Test successful job status retrieval."""
        job_id = "test-job-789"
        
        # Mock job status data
        mock_job_status = {
            "job_id": job_id,
            "status": "completed",
            "progress_percentage": 100,
            "total_items": 3,
            "completed_items": 3,
            "failed_items": 0,
            "started_at": "2024-06-15T10:00:00",
            "completed_at": "2024-06-15T10:05:00",
            "error_details": None,
            "result_data": {"total_processed": 3, "successful": 3, "failed": 0}
        }
        
        with patch("modules.payroll.services.payroll_configuration_service.PayrollConfigurationService") as mock_config:
            mock_config.return_value.get_job_status.return_value = mock_job_status
            
            response = client.get(f"/payrolls/run/{job_id}/status", headers=auth_headers)
            
            assert response.status_code == status.HTTP_200_OK
            data = response.json()
            
            # Verify response structure
            assert data["job_id"] == job_id
            assert data["status"] == "completed"
            assert data["progress"] == 100
            assert data["total_staff"] == 3
            assert data["completed_staff"] == 3
            assert data["failed_staff"] == 0
    
    def test_get_job_status_not_found(self, auth_headers):
        """Test job status retrieval for non-existent job."""
        job_id = "non-existent-job"
        
        with patch("modules.payroll.services.payroll_configuration_service.PayrollConfigurationService") as mock_config:
            mock_config.return_value.get_job_status.return_value = None
            
            response = client.get(f"/payrolls/run/{job_id}/status", headers=auth_headers)
            
            assert response.status_code == status.HTTP_404_NOT_FOUND
            data = response.json()
            assert "detail" in data
    
    def test_get_job_status_in_progress(self, auth_headers):
        """Test job status for in-progress job."""
        job_id = "in-progress-job"
        
        mock_job_status = {
            "job_id": job_id,
            "status": "running",
            "progress_percentage": 60,
            "total_items": 5,
            "completed_items": 3,
            "failed_items": 0,
            "started_at": "2024-06-15T10:00:00",
            "completed_at": None,
            "error_details": None
        }
        
        with patch("modules.payroll.services.payroll_configuration_service.PayrollConfigurationService") as mock_config:
            mock_config.return_value.get_job_status.return_value = mock_job_status
            
            response = client.get(f"/payrolls/run/{job_id}/status", headers=auth_headers)
            
            assert response.status_code == status.HTTP_200_OK
            data = response.json()
            
            assert data["status"] == "running"
            assert data["progress"] == 60
            assert data["completed_staff"] == 3
            assert data["total_staff"] == 5


class TestPayrollHistoryAPI:
    """Test payroll history endpoint."""
    
    @pytest.fixture
    def auth_headers(self):
        """Create authentication headers."""
        token_data = {
            "sub": "staff_viewer",
            "user_id": 3,
            "roles": ["staff_access"],
            "tenant_ids": [1]
        }
        token = create_access_token(token_data)
        return {"Authorization": f"Bearer {token}"}
    
    def test_get_staff_payroll_history_success(self, auth_headers):
        """Test successful staff payroll history retrieval."""
        staff_id = 123
        
        # Mock payroll service response
        mock_payment_history = [
            {
                "pay_period_end": date(2024, 6, 15),
                "gross_amount": Decimal("1000.00"),
                "net_amount": Decimal("750.00"),
                "regular_hours": Decimal("40.00"),
                "overtime_hours": Decimal("5.00"),
                "processed_at": datetime(2024, 6, 16, 10, 0, 0)
            },
            {
                "pay_period_end": date(2024, 5, 31),
                "gross_amount": Decimal("950.00"),
                "net_amount": Decimal("720.00"),
                "regular_hours": Decimal("40.00"),
                "overtime_hours": Decimal("2.50"),
                "processed_at": datetime(2024, 6, 1, 10, 0, 0)
            }
        ]
        
        with patch("modules.staff.services.enhanced_payroll_service.EnhancedPayrollService") as mock_service:
            mock_service.return_value.get_employee_payment_history.return_value = mock_payment_history
            
            response = client.get(f"/payrolls/{staff_id}", params={"limit": 10}, headers=auth_headers)
            
            assert response.status_code == status.HTTP_200_OK
            data = response.json()
            
            # Verify response structure
            assert data["staff_id"] == staff_id
            assert "staff_name" in data
            assert "payroll_history" in data
            assert "total_records" in data
            assert len(data["payroll_history"]) == 2
            
            # Verify payroll history items
            first_payroll = data["payroll_history"][0]
            assert "period" in first_payroll
            assert "gross_pay" in first_payroll
            assert "net_pay" in first_payroll
            assert "total_hours" in first_payroll
    
    def test_get_staff_payroll_history_with_limit(self, auth_headers):
        """Test payroll history with limit parameter."""
        staff_id = 123
        
        with patch("modules.staff.services.enhanced_payroll_service.EnhancedPayrollService") as mock_service:
            mock_service.return_value.get_employee_payment_history.return_value = []
            
            response = client.get(f"/payrolls/{staff_id}", params={"limit": 5}, headers=auth_headers)
            
            assert response.status_code == status.HTTP_200_OK
            
            # Verify limit was passed to service
            mock_service.return_value.get_employee_payment_history.assert_called_with(
                staff_id=staff_id,
                limit=5,
                tenant_id=None
            )
    
    def test_get_staff_payroll_history_invalid_limit(self, auth_headers):
        """Test payroll history with invalid limit."""
        staff_id = 123
        
        # Test limit too high
        response = client.get(f"/payrolls/{staff_id}", params={"limit": 200}, headers=auth_headers)
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
        
        # Test negative limit
        response = client.get(f"/payrolls/{staff_id}", params={"limit": -1}, headers=auth_headers)
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
    
    def test_get_staff_payroll_history_service_error(self, auth_headers):
        """Test payroll history when service fails."""
        staff_id = 123
        
        with patch("modules.staff.services.enhanced_payroll_service.EnhancedPayrollService") as mock_service:
            mock_service.return_value.get_employee_payment_history.side_effect = Exception("Database error")
            
            response = client.get(f"/payrolls/{staff_id}", headers=auth_headers)
            
            assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
            data = response.json()
            assert "detail" in data


class TestPayrollDetailAPI:
    """Test detailed payroll information endpoint."""
    
    @pytest.fixture
    def auth_headers(self):
        """Create authentication headers."""
        token_data = {
            "sub": "payroll_manager",
            "user_id": 1,
            "roles": ["payroll_manager"],
            "tenant_ids": [1]
        }
        token = create_access_token(token_data)
        return {"Authorization": f"Bearer {token}"}
    
    def test_get_staff_payroll_detail_success(self, auth_headers):
        """Test successful detailed payroll information retrieval."""
        staff_id = 123
        pay_period_start = "2024-06-01"
        pay_period_end = "2024-06-15"
        
        # Mock comprehensive payroll calculation
        mock_payroll_detail = {
            "staff_id": staff_id,
            "pay_period_start": date(2024, 6, 1),
            "pay_period_end": date(2024, 6, 15),
            "hours_breakdown": {
                "regular_hours": 40.0,
                "overtime_hours": 5.0,
                "total_hours": 45.0
            },
            "earnings_breakdown": {
                "regular_pay": 800.0,
                "overtime_pay": 150.0,
                "gross_pay": 950.0
            },
            "deductions_breakdown": {
                "federal_tax": 190.0,
                "state_tax": 76.0,
                "health_insurance": 69.0,
                "total_deductions": 335.0
            },
            "net_pay": 615.0
        }
        
        with patch("modules.staff.services.enhanced_payroll_engine.EnhancedPayrollEngine") as mock_engine:
            mock_engine.return_value.compute_comprehensive_payroll.return_value = mock_payroll_detail
            
            response = client.get(
                f"/payrolls/{staff_id}/detail",
                params={
                    "pay_period_start": pay_period_start,
                    "pay_period_end": pay_period_end
                },
                headers=auth_headers
            )
            
            assert response.status_code == status.HTTP_200_OK
            data = response.json()
            
            # Verify response structure
            assert data["staff_id"] == staff_id
            assert "hours_breakdown" in data
            assert "earnings_breakdown" in data
            assert "deductions_breakdown" in data
            assert "net_pay" in data
            
            # Verify calculations
            assert data["earnings_breakdown"]["gross_pay"] == 950.0
            assert data["net_pay"] == 615.0
    
    def test_get_staff_payroll_detail_missing_params(self, auth_headers):
        """Test payroll detail with missing required parameters."""
        staff_id = 123
        
        # Missing pay_period_end
        response = client.get(
            f"/payrolls/{staff_id}/detail",
            params={"pay_period_start": "2024-06-01"},
            headers=auth_headers
        )
        
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
    
    def test_get_staff_payroll_detail_invalid_dates(self, auth_headers):
        """Test payroll detail with invalid date format."""
        staff_id = 123
        
        response = client.get(
            f"/payrolls/{staff_id}/detail",
            params={
                "pay_period_start": "invalid-date",
                "pay_period_end": "2024-06-15"
            },
            headers=auth_headers
        )
        
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY


class TestPayrollRulesAPI:
    """Test payroll rules and policies endpoint."""
    
    @pytest.fixture
    def auth_headers(self):
        """Create authentication headers."""
        token_data = {
            "sub": "admin_user",
            "user_id": 1,
            "roles": ["admin"],
            "tenant_ids": [1]
        }
        token = create_access_token(token_data)
        return {"Authorization": f"Bearer {token}"}
    
    def test_get_payroll_rules_success(self, auth_headers):
        """Test successful payroll rules retrieval."""
        # Mock tax rules
        mock_tax_rules = [
            {
                "id": 1,
                "rule_name": "Federal Income Tax",
                "tax_type": "federal",
                "rate_percent": 0.22,
                "location": "US",
                "effective_date": "2024-01-01T00:00:00",
                "is_active": True
            },
            {
                "id": 2,
                "rule_name": "California State Tax",
                "tax_type": "state", 
                "rate_percent": 0.08,
                "location": "California",
                "effective_date": "2024-01-01T00:00:00",
                "is_active": True
            }
        ]
        
        # Mock payroll policies
        mock_payroll_policies = [
            {
                "id": 1,
                "policy_name": "Standard Policy",
                "location": "Restaurant Main",
                "pay_frequency": "biweekly",
                "overtime_threshold_hours": 40.0,
                "overtime_multiplier": 1.5,
                "is_active": True
            }
        ]
        
        with patch("modules.payroll.models.payroll_models.TaxRule") as mock_tax_model:
            with patch("modules.payroll.models.payroll_models.PayrollPolicy") as mock_policy_model:
                # Mock database queries
                mock_db_session = Mock()
                mock_db_session.query.return_value.filter.return_value.all.return_value = mock_tax_rules
                
                with patch("backend.core.database.get_db", return_value=iter([mock_db_session])):
                    response = client.get("/payrolls/rules", headers=auth_headers)
                    
                    assert response.status_code == status.HTTP_200_OK
                    data = response.json()
                    
                    # Verify response structure
                    assert "tax_rules" in data
                    assert "payroll_policies" in data
                    assert "jurisdiction_summary" in data
    
    def test_get_payroll_rules_with_location_filter(self, auth_headers):
        """Test payroll rules with location filter."""
        location = "California"
        
        with patch("modules.payroll.models.payroll_models.TaxRule"):
            with patch("modules.payroll.models.payroll_models.PayrollPolicy"):
                mock_db_session = Mock()
                mock_db_session.query.return_value.filter.return_value.all.return_value = []
                
                with patch("backend.core.database.get_db", return_value=iter([mock_db_session])):
                    response = client.get(
                        "/payrolls/rules",
                        params={"location": location},
                        headers=auth_headers
                    )
                    
                    assert response.status_code == status.HTTP_200_OK


class TestAPIInputValidation:
    """Test input validation across all endpoints."""
    
    @pytest.fixture
    def auth_headers(self):
        """Create authentication headers."""
        token_data = {
            "sub": "test_user",
            "user_id": 1,
            "roles": ["payroll_manager"],
            "tenant_ids": [1]
        }
        token = create_access_token(token_data)
        return {"Authorization": f"Bearer {token}"}
    
    def test_payroll_run_request_validation(self, auth_headers):
        """Test request validation for payroll run."""
        # Test with invalid staff_ids type
        invalid_request = {
            "staff_ids": "not-a-list",  # Should be list
            "pay_period_start": "2024-06-01",
            "pay_period_end": "2024-06-15",
            "tenant_id": 1
        }
        
        response = client.post("/payrolls/run", json=invalid_request, headers=auth_headers)
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
    
    def test_date_format_validation(self, auth_headers):
        """Test date format validation."""
        invalid_request = {
            "staff_ids": [1, 2, 3],
            "pay_period_start": "06/01/2024",  # Wrong format
            "pay_period_end": "2024-06-15",
            "tenant_id": 1
        }
        
        response = client.post("/payrolls/run", json=invalid_request, headers=auth_headers)
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
    
    def test_negative_staff_id_validation(self, auth_headers):
        """Test validation of negative staff IDs."""
        response = client.get("/payrolls/-1", headers=auth_headers)
        # Should handle gracefully (specific behavior depends on implementation)
        assert response.status_code in [400, 404, 422]


class TestAPIResponseFormats:
    """Test API response format consistency."""
    
    @pytest.fixture
    def auth_headers(self):
        """Create authentication headers."""
        token_data = {
            "sub": "test_user",
            "user_id": 1,
            "roles": ["payroll_manager"],
            "tenant_ids": [1]
        }
        token = create_access_token(token_data)
        return {"Authorization": f"Bearer {token}"}
    
    def test_error_response_format(self, auth_headers):
        """Test consistent error response format."""
        # Test with invalid endpoint
        response = client.get("/payrolls/non-existent-endpoint", headers=auth_headers)
        assert response.status_code == status.HTTP_404_NOT_FOUND
        
        data = response.json()
        # FastAPI standard error format
        assert "detail" in data
    
    def test_success_response_format(self, auth_headers):
        """Test consistent success response format."""
        with patch("modules.payroll.services.payroll_configuration_service.PayrollConfigurationService") as mock_config:
            mock_job = Mock()
            mock_job.job_id = "test-job"
            mock_config.return_value.create_job_tracking.return_value = mock_job
            mock_config.return_value.update_job_progress.return_value = None
            
            request_data = {
                "staff_ids": [1],
                "pay_period_start": "2024-06-01",
                "pay_period_end": "2024-06-15",
                "tenant_id": 1
            }
            
            with patch("modules.staff.services.enhanced_payroll_service.EnhancedPayrollService"):
                response = client.post("/payrolls/run", json=request_data, headers=auth_headers)
                
                assert response.status_code == status.HTTP_202_ACCEPTED
                data = response.json()
                
                # Verify response has expected fields
                required_fields = ["job_id", "status", "message"]
                for field in required_fields:
                    assert field in data


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--cov=modules.staff.routes"])