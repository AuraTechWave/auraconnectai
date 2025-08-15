# backend/modules/payroll/tests/test_batch_payroll_service.py

"""
Unit tests for BatchPayrollService.

Tests batch payroll processing logic including error handling
and progress tracking.
"""

import pytest
from datetime import date, datetime, timedelta
from decimal import Decimal
from unittest.mock import Mock, MagicMock, patch, AsyncMock, call
from sqlalchemy.orm import Session
import logging

from ..services.batch_payroll_service import BatchPayrollService
from ..services.payroll_service import PayrollService
from ..schemas.batch_processing_schemas import (
    EmployeePayrollResult,
    CalculationOptions,
    PayrollError,
    PayrollBreakdown,
)
from ..models.employee_payment import EmployeePayment
from ..exceptions import (
    BatchProcessingError,
    PayrollCalculationError,
    PayrollValidationError,
)
from ....staff.models.staff import Staff
from ....staff.models.timesheet import Timesheet


class TestBatchPayrollService:
    """Test BatchPayrollService functionality."""

    @pytest.fixture
    def mock_db(self):
        """Create mock database session."""
        return Mock(spec=Session)

    @pytest.fixture
    def mock_payroll_service(self):
        """Create mock PayrollService."""
        service = Mock(spec=PayrollService)
        service.calculate_payroll = AsyncMock()
        return service

    @pytest.fixture
    def service(self, mock_db, mock_payroll_service):
        """Create service instance with mocks."""
        service = BatchPayrollService(mock_db)
        service.payroll_service = mock_payroll_service
        return service

    @pytest.fixture
    def sample_employees(self):
        """Create sample employee data."""
        employees = []
        for i in range(3):
            employee = Mock(spec=Staff)
            employee.id = i + 1
            employee.full_name = f"Employee {i + 1}"
            employee.employee_code = f"EMP00{i + 1}"
            employee.department = "Sales"
            employee.location = "california"
            employee.is_active = True
            employees.append(employee)
        return employees

    @pytest.fixture
    def sample_timesheets(self):
        """Create sample timesheet data."""
        timesheets = []
        for emp_id in range(1, 4):
            timesheet = Mock(spec=Timesheet)
            timesheet.staff_id = emp_id
            timesheet.work_date = date(2024, 1, 15)
            timesheet.regular_hours = Decimal("8.0")
            timesheet.overtime_hours = Decimal("2.0") if emp_id == 1 else Decimal("0.0")
            timesheet.is_approved = True
            timesheets.append(timesheet)
        return timesheets

    @pytest.fixture
    def calculation_options(self):
        """Create sample calculation options."""
        return CalculationOptions(
            include_overtime=True,
            include_benefits=True,
            include_deductions=True,
            use_ytd_calculations=True,
            prorate_benefits=False,
        )

    @pytest.mark.asyncio
    async def test_process_batch_all_employees_success(
        self, service, mock_db, mock_payroll_service, sample_employees
    ):
        """Test successful batch processing for all employees."""
        # Setup
        mock_query = MagicMock()
        mock_db.query.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.all.return_value = sample_employees

        # Mock successful payroll calculations
        payroll_results = []
        for emp in sample_employees:
            result = Mock(spec=EmployeePayment)
            result.employee_id = emp.id
            result.gross_pay = Decimal("2500.00")
            result.net_pay = Decimal("1875.00")
            payroll_results.append(result)

        mock_payroll_service.calculate_payroll.side_effect = payroll_results

        # Execute
        results = await service.process_batch(
            employee_ids=None,  # Process all
            pay_period_start=date(2024, 1, 1),
            pay_period_end=date(2024, 1, 15),
        )

        # Verify
        assert len(results) == 3
        assert all(r.success for r in results)
        assert all(r.gross_pay == Decimal("2500.00") for r in results)
        assert mock_payroll_service.calculate_payroll.call_count == 3

    @pytest.mark.asyncio
    async def test_process_batch_specific_employees(
        self, service, mock_db, mock_payroll_service, sample_employees
    ):
        """Test batch processing for specific employees only."""
        # Setup
        employee_ids = [1, 3]
        filtered_employees = [e for e in sample_employees if e.id in employee_ids]

        mock_query = MagicMock()
        mock_db.query.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.all.return_value = filtered_employees

        # Mock payroll calculations
        mock_payroll_service.calculate_payroll.return_value = Mock(
            employee_id=1, gross_pay=Decimal("3000.00"), net_pay=Decimal("2250.00")
        )

        # Execute
        results = await service.process_batch(
            employee_ids=employee_ids,
            pay_period_start=date(2024, 1, 1),
            pay_period_end=date(2024, 1, 15),
        )

        # Verify
        assert len(results) == 2
        assert mock_payroll_service.calculate_payroll.call_count == 2

    @pytest.mark.asyncio
    async def test_process_batch_with_calculation_error(
        self, service, mock_db, mock_payroll_service, sample_employees
    ):
        """Test batch processing with calculation errors."""
        # Setup
        mock_query = MagicMock()
        mock_db.query.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.all.return_value = sample_employees

        # First employee succeeds, second fails, third succeeds
        mock_payroll_service.calculate_payroll.side_effect = [
            Mock(employee_id=1, gross_pay=Decimal("2500.00")),
            PayrollCalculationError("Tax calculation failed"),
            Mock(employee_id=3, gross_pay=Decimal("2500.00")),
        ]

        # Execute
        results = await service.process_batch(
            employee_ids=None,
            pay_period_start=date(2024, 1, 1),
            pay_period_end=date(2024, 1, 15),
        )

        # Verify
        assert len(results) == 3
        assert results[0].success is True
        assert results[1].success is False
        assert results[1].error.message == "Tax calculation failed"
        assert results[2].success is True

    @pytest.mark.asyncio
    async def test_process_batch_with_validation_error(
        self, service, mock_db, mock_payroll_service, sample_employees
    ):
        """Test batch processing with validation errors."""
        # Setup
        mock_query = MagicMock()
        mock_db.query.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.all.return_value = sample_employees[:1]

        # Mock validation error
        mock_payroll_service.calculate_payroll.side_effect = PayrollValidationError(
            "Invalid pay rate", field="base_rate"
        )

        # Execute
        results = await service.process_batch(
            employee_ids=[1],
            pay_period_start=date(2024, 1, 1),
            pay_period_end=date(2024, 1, 15),
        )

        # Verify
        assert len(results) == 1
        assert results[0].success is False
        assert results[0].error.code == "INVALID_AMOUNT"
        assert "Invalid pay rate" in results[0].error.message

    @pytest.mark.asyncio
    async def test_process_batch_with_calculation_options(
        self,
        service,
        mock_db,
        mock_payroll_service,
        sample_employees,
        calculation_options,
    ):
        """Test batch processing with custom calculation options."""
        # Setup
        mock_query = MagicMock()
        mock_db.query.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.all.return_value = sample_employees[:1]

        mock_payroll_service.calculate_payroll.return_value = Mock(
            employee_id=1, gross_pay=Decimal("3000.00"), net_pay=Decimal("2100.00")
        )

        # Execute
        results = await service.process_batch(
            employee_ids=[1],
            pay_period_start=date(2024, 1, 1),
            pay_period_end=date(2024, 1, 15),
            calculation_options=calculation_options,
        )

        # Verify
        assert len(results) == 1
        # Verify calculation options were passed
        call_args = mock_payroll_service.calculate_payroll.call_args
        assert call_args[1]["include_overtime"] is True
        assert call_args[1]["include_benefits"] is True

    @pytest.mark.asyncio
    async def test_process_batch_empty_employee_list(
        self, service, mock_db, mock_payroll_service
    ):
        """Test batch processing with no employees found."""
        # Setup
        mock_query = MagicMock()
        mock_db.query.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.all.return_value = []

        # Execute
        results = await service.process_batch(
            employee_ids=None,
            pay_period_start=date(2024, 1, 1),
            pay_period_end=date(2024, 1, 15),
        )

        # Verify
        assert len(results) == 0
        assert mock_payroll_service.calculate_payroll.call_count == 0

    @pytest.mark.asyncio
    async def test_process_batch_with_progress_callback(
        self, service, mock_db, mock_payroll_service, sample_employees
    ):
        """Test batch processing with progress tracking."""
        # Setup
        mock_query = MagicMock()
        mock_db.query.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.all.return_value = sample_employees

        mock_payroll_service.calculate_payroll.return_value = Mock(
            employee_id=1, gross_pay=Decimal("2500.00")
        )

        progress_updates = []

        async def progress_callback(current: int, total: int, employee_name: str):
            progress_updates.append(
                {"current": current, "total": total, "employee": employee_name}
            )

        # Execute
        results = await service.process_batch(
            employee_ids=None,
            pay_period_start=date(2024, 1, 1),
            pay_period_end=date(2024, 1, 15),
            progress_callback=progress_callback,
        )

        # Verify
        assert len(progress_updates) == 3
        assert progress_updates[0]["current"] == 1
        assert progress_updates[0]["total"] == 3
        assert progress_updates[2]["current"] == 3

    @pytest.mark.asyncio
    async def test_validate_batch_request(self, service, mock_db, sample_employees):
        """Test batch request validation."""
        # Test valid date range
        is_valid, error = await service.validate_batch_request(
            pay_period_start=date(2024, 1, 1),
            pay_period_end=date(2024, 1, 15),
            employee_ids=None,
        )
        assert is_valid is True
        assert error is None

        # Test invalid date range
        is_valid, error = await service.validate_batch_request(
            pay_period_start=date(2024, 1, 15),
            pay_period_end=date(2024, 1, 1),
            employee_ids=None,
        )
        assert is_valid is False
        assert "End date must be after start date" in error

        # Test future dates
        future_date = date.today() + timedelta(days=30)
        is_valid, error = await service.validate_batch_request(
            pay_period_start=future_date,
            pay_period_end=future_date + timedelta(days=14),
            employee_ids=None,
        )
        assert is_valid is False
        assert "Cannot process payroll for future dates" in error

    @pytest.mark.asyncio
    async def test_get_batch_summary(self, service):
        """Test batch processing summary generation."""
        # Setup
        results = [
            EmployeePayrollResult(
                employee_id=1,
                employee_name="Employee 1",
                success=True,
                gross_pay=Decimal("2500.00"),
                net_pay=Decimal("1875.00"),
                breakdown=Mock(),
            ),
            EmployeePayrollResult(
                employee_id=2,
                employee_name="Employee 2",
                success=False,
                error=PayrollError(code="CALC_ERROR", message="Calculation failed"),
            ),
            EmployeePayrollResult(
                employee_id=3,
                employee_name="Employee 3",
                success=True,
                gross_pay=Decimal("3000.00"),
                net_pay=Decimal("2250.00"),
                breakdown=Mock(),
            ),
        ]

        # Execute
        summary = await service.get_batch_summary(results)

        # Verify
        assert summary["total_employees"] == 3
        assert summary["successful_count"] == 2
        assert summary["failed_count"] == 1
        assert summary["total_gross_pay"] == Decimal("5500.00")
        assert summary["total_net_pay"] == Decimal("4125.00")
        assert len(summary["errors"]) == 1
        assert summary["errors"][0]["employee_id"] == 2

    @pytest.mark.asyncio
    async def test_save_batch_results(self, service, mock_db):
        """Test saving batch results to database."""
        # Setup
        results = [
            EmployeePayrollResult(
                employee_id=1,
                employee_name="Employee 1",
                success=True,
                gross_pay=Decimal("2500.00"),
                net_pay=Decimal("1875.00"),
                breakdown=PayrollBreakdown(
                    regular_pay=Decimal("2000.00"),
                    overtime_pay=Decimal("500.00"),
                    gross_pay=Decimal("2500.00"),
                    federal_tax=Decimal("375.00"),
                    state_tax=Decimal("125.00"),
                    social_security=Decimal("93.75"),
                    medicare=Decimal("31.25"),
                    total_deductions=Decimal("625.00"),
                    net_pay=Decimal("1875.00"),
                ),
            )
        ]

        mock_db.add = Mock()
        mock_db.commit = Mock()
        mock_db.refresh = Mock()

        # Execute
        saved_ids = await service.save_batch_results(
            results=results,
            pay_period_start=date(2024, 1, 1),
            pay_period_end=date(2024, 1, 15),
        )

        # Verify
        assert len(saved_ids) == 1
        assert mock_db.add.called
        assert mock_db.commit.called

        # Check the payment object that was added
        payment = mock_db.add.call_args[0][0]
        assert payment.employee_id == 1
        assert payment.gross_pay == Decimal("2500.00")
        assert payment.net_pay == Decimal("1875.00")

    @pytest.mark.asyncio
    async def test_process_batch_with_database_error(
        self, service, mock_db, mock_payroll_service
    ):
        """Test batch processing with database error."""
        # Setup
        mock_db.query.side_effect = Exception("Database connection failed")

        # Execute and verify
        with pytest.raises(BatchProcessingError) as exc_info:
            await service.process_batch(
                employee_ids=None,
                pay_period_start=date(2024, 1, 1),
                pay_period_end=date(2024, 1, 15),
            )

        assert "Database connection failed" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_process_batch_with_duplicate_prevention(
        self, service, mock_db, mock_payroll_service, sample_employees
    ):
        """Test batch processing with duplicate payment prevention."""
        # Setup
        mock_query = MagicMock()
        mock_db.query.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.all.return_value = sample_employees[:1]

        # Mock existing payment check
        existing_payment = Mock(spec=EmployeePayment)
        existing_payment.id = 999
        mock_query.first.return_value = existing_payment

        # Execute
        results = await service.process_batch(
            employee_ids=[1],
            pay_period_start=date(2024, 1, 1),
            pay_period_end=date(2024, 1, 15),
            allow_duplicates=False,
        )

        # Verify
        assert len(results) == 1
        assert results[0].success is False
        assert "already exists" in results[0].error.message.lower()

    @pytest.mark.asyncio
    async def test_process_batch_with_logging(
        self, service, mock_db, mock_payroll_service, sample_employees, caplog
    ):
        """Test batch processing logging."""
        # Setup
        with caplog.at_level(logging.INFO):
            mock_query = MagicMock()
            mock_db.query.return_value = mock_query
            mock_query.filter.return_value = mock_query
            mock_query.all.return_value = sample_employees[:1]

            mock_payroll_service.calculate_payroll.return_value = Mock(
                employee_id=1, gross_pay=Decimal("2500.00")
            )

            # Execute
            await service.process_batch(
                employee_ids=[1],
                pay_period_start=date(2024, 1, 1),
                pay_period_end=date(2024, 1, 15),
            )

        # Verify logging
        assert "Starting batch payroll processing" in caplog.text
        assert "Processing employee 1" in caplog.text
        assert "Batch processing completed" in caplog.text
