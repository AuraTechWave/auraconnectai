# backend/modules/analytics/tests/test_negative_cases.py

import pytest
from datetime import date, datetime, timedelta
from decimal import Decimal, InvalidOperation
from unittest.mock import Mock, patch
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError, IntegrityError, DataError
from fastapi import HTTPException

from ..services.sales_report_service import SalesReportService
from ..services.trend_service import TrendService
from ..services.export_service import ExportService
from ..services.alerting_service import AlertingService
from ..services.permissions_service import PermissionsService, AnalyticsPermission
from ..services.async_processing import AsyncTaskProcessor, TaskStatus
from ..schemas.analytics_schemas import SalesFilterRequest
from ..models.analytics_models import AlertRule


class TestSalesReportServiceNegativeCases:
    """Test negative cases and edge conditions for SalesReportService"""

    def test_invalid_date_ranges(self, db_session: Session):
        """Test handling of invalid date ranges"""
        service = SalesReportService(db_session)

        # Future start date
        with pytest.raises(ValueError, match="Start date cannot be in the future"):
            filters = SalesFilterRequest(
                date_from=date.today() + timedelta(days=1), date_to=date.today()
            )
            service.generate_sales_summary(filters)

        # Start date after end date
        with pytest.raises(ValueError, match="Start date must be before end date"):
            filters = SalesFilterRequest(
                date_from=date.today(), date_to=date.today() - timedelta(days=1)
            )
            service.generate_sales_summary(filters)

        # Excessively large date range
        with pytest.raises(ValueError, match="Date range too large"):
            filters = SalesFilterRequest(
                date_from=date(2000, 1, 1), date_to=date(2025, 12, 31)
            )
            service.generate_sales_summary(filters)

    def test_invalid_filter_values(self, db_session: Session):
        """Test handling of invalid filter values"""
        service = SalesReportService(db_session)

        # Negative staff IDs
        with pytest.raises(ValueError, match="Invalid staff ID"):
            filters = SalesFilterRequest(staff_ids=[-1, 0])
            service.generate_sales_summary(filters)

        # Empty filter lists
        filters = SalesFilterRequest(staff_ids=[], product_ids=[], category_ids=[])
        result = service.generate_sales_summary(filters)
        assert result is not None  # Should handle empty filters gracefully

        # Excessively large filter lists
        with pytest.raises(ValueError, match="Too many filter values"):
            filters = SalesFilterRequest(staff_ids=list(range(1001)))  # Over limit
            service.generate_sales_summary(filters)

    def test_database_connection_errors(self, db_session: Session):
        """Test handling of database connection errors"""
        service = SalesReportService(db_session)

        # Mock database error
        with patch.object(
            db_session, "query", side_effect=SQLAlchemyError("Connection lost")
        ):
            filters = SalesFilterRequest(
                date_from=date.today() - timedelta(days=7), date_to=date.today()
            )

            with pytest.raises(HTTPException) as exc_info:
                service.generate_sales_summary(filters)

            assert exc_info.value.status_code == 500

    def test_empty_dataset_handling(self, db_session: Session):
        """Test behavior with empty datasets"""
        service = SalesReportService(db_session)

        # Mock empty query result
        with patch.object(db_session, "query") as mock_query:
            mock_query.return_value.filter.return_value.all.return_value = []
            mock_query.return_value.filter.return_value.first.return_value = None

            filters = SalesFilterRequest(
                date_from=date.today() - timedelta(days=7), date_to=date.today()
            )

            result = service.generate_sales_summary(filters)

            # Should return valid response with zero values
            assert result.total_orders == 0
            assert result.total_revenue == Decimal("0")
            assert result.unique_customers == 0

    def test_pagination_edge_cases(self, db_session: Session):
        """Test pagination with edge case values"""
        service = SalesReportService(db_session)

        filters = SalesFilterRequest(
            date_from=date.today() - timedelta(days=7), date_to=date.today()
        )

        # Page 0 or negative
        with pytest.raises(ValueError, match="Page must be positive"):
            service.generate_detailed_sales_report(filters, page=0, per_page=10)

        with pytest.raises(ValueError, match="Page must be positive"):
            service.generate_detailed_sales_report(filters, page=-1, per_page=10)

        # Per page 0 or negative
        with pytest.raises(ValueError, match="Per page must be positive"):
            service.generate_detailed_sales_report(filters, page=1, per_page=0)

        # Extremely large page number
        result = service.generate_detailed_sales_report(
            filters, page=999999, per_page=10
        )
        assert result.items == []
        assert result.total == 0

    def test_invalid_sort_parameters(self, db_session: Session):
        """Test invalid sort parameters"""
        service = SalesReportService(db_session)

        filters = SalesFilterRequest(
            date_from=date.today() - timedelta(days=7), date_to=date.today()
        )

        # Invalid sort field
        with pytest.raises(ValueError, match="Invalid sort field"):
            service.generate_detailed_sales_report(
                filters, page=1, per_page=10, sort_by="invalid_field"
            )

        # Invalid sort order
        with pytest.raises(ValueError, match="Invalid sort order"):
            service.generate_detailed_sales_report(
                filters, page=1, per_page=10, sort_order="invalid"
            )


class TestTrendServiceNegativeCases:
    """Test negative cases for TrendService"""

    def test_insufficient_data_for_trends(self, db_session: Session):
        """Test trend calculation with insufficient data"""
        service = TrendService(db_session)

        # Mock empty snapshots
        with patch.object(db_session, "query") as mock_query:
            mock_query.return_value.filter.return_value.order_by.return_value.all.return_value = (
                []
            )

            start_date = date.today() - timedelta(days=30)
            end_date = date.today()

            trends = service.get_revenue_trend(start_date, end_date, "daily")
            assert trends == []

    def test_invalid_granularity(self, db_session: Session):
        """Test invalid granularity parameters"""
        service = TrendService(db_session)

        start_date = date.today() - timedelta(days=30)
        end_date = date.today()

        with pytest.raises(ValueError, match="Invalid granularity"):
            service.get_revenue_trend(start_date, end_date, "invalid_granularity")

    def test_trend_calculation_overflow(self, db_session: Session):
        """Test trend calculation with extreme values that might cause overflow"""
        service = TrendService(db_session)

        # Mock extreme values
        from ..models.analytics_models import SalesAnalyticsSnapshot

        with patch.object(db_session, "query") as mock_query:
            # Create mock snapshots with extreme values
            extreme_snapshot = Mock(spec=SalesAnalyticsSnapshot)
            extreme_snapshot.snapshot_date = date.today()
            extreme_snapshot.total_revenue = Decimal(
                "999999999999999999"
            )  # Very large number

            mock_query.return_value.filter.return_value.order_by.return_value.all.return_value = [
                extreme_snapshot
            ]

            start_date = date.today() - timedelta(days=7)
            end_date = date.today()

            # Should handle extreme values gracefully
            trends = service.get_revenue_trend(start_date, end_date, "daily")
            assert isinstance(trends, list)


class TestExportServiceNegativeCases:
    """Test negative cases for ExportService"""

    def test_unsupported_export_format(self, db_session: Session):
        """Test handling of unsupported export formats"""
        service = ExportService(db_session)

        from ..schemas.analytics_schemas import SalesReportRequest

        request = SalesReportRequest(
            report_type="sales_summary", filters=SalesFilterRequest()
        )

        with pytest.raises(ValueError, match="Unsupported format"):
            service.export_sales_report(request, "unsupported_format", 1)

    def test_missing_optional_libraries(self, db_session: Session):
        """Test behavior when optional export libraries are missing"""
        service = ExportService(db_session)

        # Mock missing ReportLab for PDF
        with patch(
            "builtins.__import__",
            side_effect=ImportError("No module named 'reportlab'"),
        ):
            from ..schemas.analytics_schemas import SalesReportRequest

            request = SalesReportRequest(
                report_type="sales_summary", filters=SalesFilterRequest()
            )

            with pytest.raises(HTTPException, match="PDF export requires reportlab"):
                service.export_sales_report(request, "pdf", 1)

    def test_export_with_no_data(self, db_session: Session):
        """Test export with empty datasets"""
        service = ExportService(db_session)

        # Mock empty data
        with patch.object(service, "_get_report_data", return_value=[]):
            from ..schemas.analytics_schemas import SalesReportRequest

            request = SalesReportRequest(
                report_type="sales_summary", filters=SalesFilterRequest()
            )

            # Should create empty export file
            response = service.export_sales_report(request, "csv", 1)
            assert response is not None

    def test_export_memory_exhaustion(self, db_session: Session):
        """Test export with datasets too large for memory"""
        service = ExportService(db_session)

        # Mock extremely large dataset
        with patch.object(service, "_get_report_data") as mock_get_data:
            # Simulate memory error
            mock_get_data.side_effect = MemoryError("Not enough memory")

            from ..schemas.analytics_schemas import SalesReportRequest

            request = SalesReportRequest(
                report_type="sales_summary", filters=SalesFilterRequest()
            )

            with pytest.raises(HTTPException, match="Export dataset too large"):
                service.export_sales_report(request, "csv", 1)


class TestAlertingServiceNegativeCases:
    """Test negative cases for AlertingService"""

    def test_invalid_alert_rule_parameters(self, db_session: Session):
        """Test creation of alert rules with invalid parameters"""
        service = AlertingService(db_session)

        # Invalid condition type
        with pytest.raises(ValueError, match="Invalid condition type"):
            service.create_alert_rule(
                name="Test Alert",
                description="Test",
                metric_name="revenue",
                condition_type="invalid_condition",
                threshold_value=Decimal("100"),
                evaluation_period="daily",
                notification_channels=["email"],
                notification_recipients=["test@example.com"],
                created_by=1,
            )

        # Invalid threshold value
        with pytest.raises(ValueError, match="Invalid threshold"):
            service.create_alert_rule(
                name="Test Alert",
                description="Test",
                metric_name="revenue",
                condition_type="above",
                threshold_value=Decimal("-100"),  # Negative threshold
                evaluation_period="daily",
                notification_channels=["email"],
                notification_recipients=["test@example.com"],
                created_by=1,
            )

        # Empty notification channels
        with pytest.raises(
            ValueError, match="At least one notification channel required"
        ):
            service.create_alert_rule(
                name="Test Alert",
                description="Test",
                metric_name="revenue",
                condition_type="above",
                threshold_value=Decimal("100"),
                evaluation_period="daily",
                notification_channels=[],
                notification_recipients=["test@example.com"],
                created_by=1,
            )

    def test_alert_evaluation_with_missing_data(self, db_session: Session):
        """Test alert evaluation when metric data is missing"""
        service = AlertingService(db_session)

        # Create alert rule
        rule = AlertRule(
            id=1,
            name="Test Alert",
            metric_name="nonexistent_metric",
            condition_type="above",
            threshold_value=Decimal("100"),
            evaluation_period="daily",
            notification_channels=["email"],
            notification_recipients=["test@example.com"],
        )

        # Mock empty metric data
        with patch.object(service, "_get_metric_value", return_value=None):
            result = service.evaluate_alert_rule(rule)
            # Should not trigger when data is missing
            assert result is False

    def test_notification_failures(self, db_session: Session):
        """Test handling of notification delivery failures"""
        service = AlertingService(db_session)

        rule = AlertRule(
            id=1,
            name="Test Alert",
            metric_name="revenue",
            condition_type="above",
            threshold_value=Decimal("100"),
            evaluation_period="daily",
            notification_channels=["email", "slack"],
            notification_recipients=["test@example.com"],
        )

        # Mock notification failures
        with patch.object(
            service, "_send_email_alert", side_effect=Exception("SMTP error")
        ):
            with patch.object(
                service, "_send_slack_alert", side_effect=Exception("Slack API error")
            ):
                # Should handle notification failures gracefully
                service._trigger_alert(rule, 150.0, None)
                # Test passes if no exception is raised

    def test_alert_throttling_edge_cases(self, db_session: Session):
        """Test alert throttling with edge cases"""
        service = AlertingService(db_session)

        rule = AlertRule(
            id=1,
            name="Test Alert",
            metric_name="revenue",
            condition_type="above",
            threshold_value=Decimal("100"),
            evaluation_period="daily",
            notification_channels=["email"],
            notification_recipients=["test@example.com"],
            last_triggered_at=datetime.now()
            - timedelta(minutes=59),  # Just under throttle limit
        )

        # Should be throttled
        assert service._should_throttle_alert(rule) is True

        # Test with exactly at throttle limit
        rule.last_triggered_at = datetime.now() - timedelta(minutes=60)
        assert service._should_throttle_alert(rule) is False


class TestPermissionsServiceNegativeCases:
    """Test negative cases for PermissionsService"""

    def test_user_without_permissions(self):
        """Test user with no permissions"""
        user = {"id": 1, "role": "guest"}  # No analytics permissions

        permissions = PermissionsService.get_user_permissions(user)
        assert permissions == []

        # Should deny access
        has_view_permission = PermissionsService.has_permission(
            user, AnalyticsPermission.VIEW_DASHBOARD
        )
        assert has_view_permission is False

    def test_malformed_user_object(self):
        """Test handling of malformed user objects"""
        # Missing required fields
        malformed_users = [
            {},  # Empty user
            {"role": None},  # Null role
            {"id": "invalid"},  # Invalid ID type
            {"analytics_permissions": "not_a_list"},  # Invalid permissions format
        ]

        for user in malformed_users:
            # Should handle gracefully without crashing
            permissions = PermissionsService.get_user_permissions(user)
            assert isinstance(permissions, list)

    def test_permission_denial_exceptions(self):
        """Test permission denial raises proper exceptions"""
        user = {"id": 1, "role": "guest"}

        with pytest.raises(HTTPException) as exc_info:
            PermissionsService.require_permission(
                user, AnalyticsPermission.VIEW_DASHBOARD
            )

        assert exc_info.value.status_code == 403
        assert "permission required" in str(exc_info.value.detail).lower()

    def test_data_filtering_edge_cases(self):
        """Test data filtering with edge cases"""
        user = {"id": 1, "role": "viewer"}  # Limited permissions

        # Test with None data
        filtered = PermissionsService.filter_data_by_permissions(user, None, "sales")
        assert filtered is None

        # Test with empty data
        filtered = PermissionsService.filter_data_by_permissions(user, {}, "sales")
        assert filtered == {}

        # Test with data containing sensitive fields
        sensitive_data = {
            "total_revenue": 1000,
            "staff_id": 999,  # Different from user ID
            "orders": 50,
        }

        filtered = PermissionsService.filter_data_by_permissions(
            user, sensitive_data, "staff_performance"
        )

        # Should restrict financial data and other staff data
        assert filtered["total_revenue"] == "[RESTRICTED]"


class TestAsyncProcessingNegativeCases:
    """Test negative cases for AsyncTaskProcessor"""

    def test_unregistered_task_handler(self):
        """Test submitting task with unregistered handler"""
        import asyncio

        async def run_unregistered_test():
            processor = AsyncTaskProcessor()

            with pytest.raises(ValueError, match="No handler registered"):
                await processor.submit_task("nonexistent_task", {})

        asyncio.run(run_unregistered_test())

    def test_task_handler_exceptions(self):
        """Test handling of exceptions in task handlers"""
        import asyncio

        async def run_exception_test():
            processor = AsyncTaskProcessor()

            def failing_handler(task_data, task):
                raise ValueError("Handler failed")

            processor.register_handler("failing_task", failing_handler)

            task_id = await processor.submit_task("failing_task", {})

            # Wait for task to complete
            await asyncio.sleep(0.2)

            task = processor.get_task_status(task_id)
            assert task.status == TaskStatus.FAILED
            assert "Handler failed" in task.error

        asyncio.run(run_exception_test())

    def test_task_cancellation_edge_cases(self):
        """Test task cancellation edge cases"""
        import asyncio

        async def run_cancellation_test():
            processor = AsyncTaskProcessor()

            # Try to cancel non-existent task
            result = processor.cancel_task("nonexistent_task")
            assert result is False

            # Try to cancel already completed task
            def quick_handler(task_data, task):
                return {"done": True}

            processor.register_handler("quick_task", quick_handler)
            task_id = await processor.submit_task("quick_task", {})

            # Wait for completion
            await asyncio.sleep(0.2)

            result = processor.cancel_task(task_id)
            assert result is False  # Cannot cancel completed task

        asyncio.run(run_cancellation_test())

    def test_processor_shutdown_with_running_tasks(self):
        """Test processor shutdown while tasks are running"""
        import asyncio

        async def run_shutdown_test():
            processor = AsyncTaskProcessor()

            def long_running_handler(task_data, task):
                import time

                time.sleep(1.0)  # Long running task
                return {"done": True}

            processor.register_handler("long_task", long_running_handler)

            # Submit task and immediately shutdown
            task_id = await processor.submit_task("long_task", {})
            await processor.stop()

            # Task should be cancelled
            task = processor.get_task_status(task_id)
            assert task.status in [TaskStatus.CANCELLED, TaskStatus.FAILED]

        asyncio.run(run_shutdown_test())

    def test_memory_leaks_with_many_tasks(self):
        """Test for memory leaks with many task submissions"""
        import asyncio

        async def run_memory_leak_test():
            processor = AsyncTaskProcessor()

            def simple_handler(task_data, task):
                return {"processed": True}

            processor.register_handler("simple_task", simple_handler)

            # Submit many tasks
            task_ids = []
            for i in range(1000):
                task_id = await processor.submit_task("simple_task", {"data": i})
                task_ids.append(task_id)

            # Wait for processing
            await asyncio.sleep(2.0)

            # Check that old tasks are cleaned up
            active_tasks = len(
                [
                    t
                    for t in processor.tasks.values()
                    if t.status in [TaskStatus.PENDING, TaskStatus.RUNNING]
                ]
            )

            # Should not have too many active tasks
            assert active_tasks < 100, f"Too many active tasks: {active_tasks}"

        asyncio.run(run_memory_leak_test())


class TestIntegrationNegativeCases:
    """Test negative cases for integration between services"""

    def test_service_dependency_failures(self, db_session: Session):
        """Test handling when service dependencies fail"""
        # Mock database session failure
        broken_session = Mock(spec=Session)
        broken_session.query.side_effect = SQLAlchemyError("Database unavailable")

        service = SalesReportService(broken_session)

        with pytest.raises(HTTPException):
            filters = SalesFilterRequest()
            service.generate_sales_summary(filters)

    def test_circular_dependency_prevention(self, db_session: Session):
        """Test prevention of circular dependencies between services"""
        # This test ensures services don't create circular imports or dependencies
        from ..services import sales_report_service, trend_service, export_service

        # Should be able to import all services without circular dependency errors
        assert sales_report_service.SalesReportService is not None
        assert trend_service.TrendService is not None
        assert export_service.ExportService is not None

    def test_configuration_errors(self):
        """Test handling of configuration errors"""
        # Test with missing configuration
        with patch.dict("os.environ", {}, clear=True):
            # Services should handle missing environment variables gracefully
            processor = AsyncTaskProcessor()
            assert processor.max_workers > 0  # Should have default

    def test_version_compatibility_issues(self, db_session: Session):
        """Test handling of potential version compatibility issues"""
        service = SalesReportService(db_session)

        # Mock version incompatibility in database schema
        with patch.object(
            db_session,
            "execute",
            side_effect=DataError("column does not exist", None, None),
        ):
            filters = SalesFilterRequest()

            with pytest.raises(HTTPException):
                service.generate_sales_summary(filters)

    def test_resource_exhaustion_scenarios(self):
        """Test behavior under resource exhaustion"""
        # Test file descriptor exhaustion
        with patch("builtins.open", side_effect=OSError("Too many open files")):
            export_service = ExportService(Mock())

            with pytest.raises(HTTPException, match="Resource exhaustion"):
                export_service._write_temp_file("test data", "test.csv")

    def test_unicode_and_encoding_issues(self, db_session: Session):
        """Test handling of unicode and encoding issues"""
        service = SalesReportService(db_session)

        # Test with data containing special characters
        with patch.object(db_session, "query") as mock_query:
            # Mock data with unicode characters
            mock_result = Mock()
            mock_result.staff_name = "José 测试 🚀"  # Mixed unicode
            mock_result.total_revenue = Decimal("100")

            mock_query.return_value.filter.return_value.all.return_value = [mock_result]

            filters = SalesFilterRequest()
            # Should handle unicode gracefully
            result = service.generate_sales_summary(filters)
            assert result is not None
