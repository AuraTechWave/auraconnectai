# backend/modules/payroll/tests/test_audit_logs.py

"""
Functional tests for audit log functionality.

Tests audit log queries, filtering, and compliance reports.
"""

import pytest
from datetime import date, datetime, timedelta
from unittest.mock import Mock, MagicMock
from sqlalchemy import func

from ..routes.v1.audit.logs_routes import get_audit_logs
from ..routes.v1.audit.summary_routes import get_audit_summary
from ..routes.v1.audit.compliance_routes import get_compliance_report
from ..schemas.audit_schemas import AuditEventType
from ..models.payroll_audit import PayrollAuditLog


@pytest.fixture
def sample_audit_logs():
    """Create sample audit log entries."""
    logs = []
    base_time = datetime.utcnow() - timedelta(days=7)
    
    # Login events
    for i in range(5):
        log = Mock(spec=PayrollAuditLog)
        log.id = i + 1
        log.timestamp = base_time + timedelta(hours=i)
        log.event_type = AuditEventType.USER_LOGIN
        log.entity_type = "auth"
        log.entity_id = None
        log.user_id = i % 3 + 1
        log.user_email = f"user{i % 3 + 1}@example.com"
        log.ip_address = f"192.168.1.{i + 1}"
        log.action = "User logged in"
        log.old_values = None
        log.new_values = None
        log.metadata = {"browser": "Chrome"}
        logs.append(log)
    
    # Payroll calculation events
    for i in range(3):
        log = Mock(spec=PayrollAuditLog)
        log.id = i + 6
        log.timestamp = base_time + timedelta(days=i + 1)
        log.event_type = AuditEventType.PAYROLL_CALCULATED
        log.entity_type = "payroll"
        log.entity_id = i + 100
        log.user_id = 1
        log.user_email = "payroll@example.com"
        log.ip_address = "192.168.1.100"
        log.action = f"Calculated payroll for employee {i + 1}"
        log.old_values = None
        log.new_values = {"gross": 1000 + i * 100, "net": 800 + i * 80}
        log.metadata = {"pay_period": "2025-01"}
        logs.append(log)
    
    return logs


class TestAuditLogQueries:
    """Test audit log querying and filtering."""
    
    @pytest.mark.asyncio
    async def test_get_all_audit_logs(self, mock_db, mock_user, sample_audit_logs):
        """Test retrieving all audit logs."""
        # Setup
        mock_query = MagicMock()
        mock_db.query.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.order_by.return_value = mock_query
        mock_query.count.return_value = len(sample_audit_logs)
        mock_query.limit.return_value = mock_query
        mock_query.offset.return_value = mock_query
        mock_query.all.return_value = sample_audit_logs
        
        # Execute
        response = await get_audit_logs(
            start_date=None,
            end_date=None,
            event_type=None,
            entity_type=None,
            entity_id=None,
            user_id=None,
            limit=50,
            offset=0,
            sort_by="timestamp",
            sort_order="desc",
            db=mock_db,
            current_user=mock_user
        )
        
        # Verify
        assert response.total == len(sample_audit_logs)
        assert len(response.logs) == len(sample_audit_logs)
        assert response.limit == 50
        assert response.offset == 0
    
    @pytest.mark.asyncio
    async def test_filter_by_event_type(self, mock_db, mock_user, sample_audit_logs):
        """Test filtering logs by event type."""
        # Setup - filter only login events
        login_logs = [log for log in sample_audit_logs if log.event_type == AuditEventType.USER_LOGIN]
        
        mock_query = MagicMock()
        mock_db.query.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.order_by.return_value = mock_query
        mock_query.count.return_value = len(login_logs)
        mock_query.limit.return_value = mock_query
        mock_query.offset.return_value = mock_query
        mock_query.all.return_value = login_logs
        
        # Execute
        response = await get_audit_logs(
            event_type=AuditEventType.USER_LOGIN,
            limit=50,
            offset=0,
            sort_by="timestamp",
            sort_order="desc",
            db=mock_db,
            current_user=mock_user
        )
        
        # Verify
        assert response.total == 5  # 5 login events
        assert all(log.event_type == AuditEventType.USER_LOGIN for log in response.logs)
    
    @pytest.mark.asyncio
    async def test_date_range_filtering(self, mock_db, mock_user):
        """Test filtering logs by date range."""
        # Setup
        start_date = date.today() - timedelta(days=7)
        end_date = date.today()
        
        mock_query = MagicMock()
        mock_db.query.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.order_by.return_value = mock_query
        mock_query.count.return_value = 10
        mock_query.limit.return_value = mock_query
        mock_query.offset.return_value = mock_query
        mock_query.all.return_value = []
        
        # Execute
        response = await get_audit_logs(
            start_date=start_date,
            end_date=end_date,
            limit=50,
            offset=0,
            sort_by="timestamp",
            sort_order="desc",
            db=mock_db,
            current_user=mock_user
        )
        
        # Verify filter was applied
        filter_calls = mock_query.filter.call_args_list
        assert len(filter_calls) >= 2  # At least start and end date filters


class TestAuditSummary:
    """Test audit summary and analytics."""
    
    @pytest.mark.asyncio
    async def test_summary_by_event_type(self, mock_db, mock_user):
        """Test generating summary grouped by event type."""
        # Setup mock results
        mock_results = [
            Mock(group_key=AuditEventType.USER_LOGIN, count=25),
            Mock(group_key=AuditEventType.PAYROLL_CALCULATED, count=15),
            Mock(group_key=AuditEventType.PAYMENT_PROCESSED, count=10)
        ]
        
        mock_query = MagicMock()
        mock_db.query.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.add_columns.return_value = mock_query
        mock_query.group_by.return_value = mock_query
        mock_query.all.return_value = mock_results
        mock_query.scalar.return_value = 50  # Total events
        
        # Mock top users query
        mock_query.order_by.return_value = mock_query
        mock_query.limit.return_value = mock_query
        mock_query.all.return_value = [
            Mock(user_email="admin@example.com", action_count=30),
            Mock(user_email="payroll@example.com", action_count=20)
        ]
        
        # Execute
        response = await get_audit_summary(
            start_date=date.today() - timedelta(days=30),
            end_date=date.today(),
            group_by="event_type",
            db=mock_db,
            current_user=mock_user
        )
        
        # Verify
        assert response.total_events == 50
        assert len(response.summary_data) == 3
        assert response.summary_data[0]["count"] == 25
        assert response.summary_data[0]["percentage"] == 50.0
        assert len(response.top_users) == 2
        assert response.top_users[0]["user"] == "admin@example.com"


class TestComplianceReports:
    """Test compliance report generation."""
    
    @pytest.mark.asyncio
    async def test_access_compliance_report(self, mock_db, mock_user):
        """Test generating access compliance report."""
        # Setup
        mock_query = MagicMock()
        mock_db.query.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.scalar.return_value = 100  # Total access events
        
        # Execute
        response = await get_compliance_report(
            report_type="access",
            start_date=date.today() - timedelta(days=30),
            end_date=date.today(),
            db=mock_db,
            current_user=mock_user
        )
        
        # Verify
        assert response["report_type"] == "access"
        assert "access_summary" in response
        assert response["access_summary"]["total_access_events"] == 100
        assert "recommendations" in response
    
    @pytest.mark.asyncio
    async def test_sensitive_operations_report(self, mock_db, mock_user):
        """Test sensitive operations compliance report."""
        # Setup mock for sensitive operations
        mock_results = [
            Mock(event_type=AuditEventType.PAYMENT_APPROVED, count=50),
            Mock(event_type=AuditEventType.EXPORT_GENERATED, count=25),
            Mock(event_type=AuditEventType.CONFIGURATION_CHANGED, count=5)
        ]
        
        mock_query = MagicMock()
        mock_db.query.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.group_by.return_value = mock_query
        mock_query.all.return_value = mock_results
        mock_query.scalar.return_value = 25  # Export operations
        
        # Execute
        response = await get_compliance_report(
            report_type="sensitive",
            start_date=date.today() - timedelta(days=30),
            end_date=date.today(),
            db=mock_db,
            current_user=mock_user
        )
        
        # Verify
        assert response["report_type"] == "sensitive"
        assert "sensitive_operations" in response
        assert response["sensitive_operations"]["total_sensitive_events"] == 80
        assert response["sensitive_operations"]["export_operations"] == 25


class TestAuditExport:
    """Test audit log export functionality."""
    
    @pytest.mark.asyncio
    async def test_export_validation(self, mock_db, mock_user):
        """Test export date range validation."""
        from ..routes.v1.audit.compliance_routes import export_audit_logs
        from ..schemas.audit_schemas import AuditExportRequest, AuditLogFilter
        from fastapi import BackgroundTasks
        
        # Create export request with too large date range
        export_request = AuditExportRequest(
            format="csv",
            filters=AuditLogFilter(
                start_date=date.today() - timedelta(days=400),  # > 365 days
                end_date=date.today()
            )
        )
        
        background_tasks = BackgroundTasks()
        
        # Execute and verify
        with pytest.raises(Exception) as exc_info:
            await export_audit_logs(
                export_request=export_request,
                background_tasks=background_tasks,
                db=mock_db,
                current_user=mock_user
            )
        
        assert "ValidationError" in str(exc_info.value)
        assert "365 days" in str(exc_info.value)