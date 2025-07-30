# backend/modules/payroll/tests/e2e/test_basic_workflow.py

"""
End-to-end tests for basic payroll workflow.

Tests the standard payroll process from timesheet submission
through payment generation.
"""

import pytest
from datetime import date, datetime, timedelta
from decimal import Decimal
from unittest.mock import Mock, MagicMock, patch
from sqlalchemy.orm import Session

from ...services.batch_payroll_service import BatchPayrollService
from ...services.payment_export_service import PaymentExportService
from ...models.employee_payment import EmployeePayment
from ...models.payroll_configuration import PayrollJobTracking, StaffPayPolicy
from ...schemas.batch_processing_schemas import CalculationOptions
from ...enums.payroll_enums import PayrollJobStatus, PaymentStatus
from .conftest import create_sample_employees, create_sample_timesheets


class TestBasicPayrollWorkflow:
    """Test basic payroll workflow end-to-end."""
    
    @pytest.mark.e2e
    async def test_complete_payroll_workflow(
        self, mock_db, sample_company_setup, sample_employees, 
        sample_timesheets, sample_pay_policies
    ):
        """Test complete payroll workflow from start to finish."""
        
        # Step 1: Setup database mocks
        self._setup_database_mocks(
            mock_db, sample_employees, sample_timesheets, sample_pay_policies
        )
        
        # Step 2: Create batch payroll job
        batch_service = BatchPayrollService(mock_db)
        job_id = "batch_" + str(date.today()).replace("-", "") + "_001"
        
        job_tracking = Mock(spec=PayrollJobTracking)
        job_tracking.job_id = job_id
        job_tracking.status = PayrollJobStatus.PENDING
        job_tracking.total_employees = len(sample_employees)
        job_tracking.processed_count = 0
        
        # Step 3: Process payroll batch
        with patch.object(batch_service, 'payroll_service') as mock_payroll_service:
            # Mock individual payroll calculations
            self._setup_payroll_calculations(mock_payroll_service, sample_employees)
            
            results = await batch_service.process_batch(
                employee_ids=None,  # Process all
                pay_period_start=sample_company_setup["pay_period_start"],
                pay_period_end=sample_company_setup["pay_period_end"],
                calculation_options=CalculationOptions(
                    include_overtime=True,
                    include_benefits=True,
                    include_deductions=True,
                    use_ytd_calculations=True
                )
            )
        
        # Step 4: Verify results
        assert len(results) == 3
        assert all(r.success for r in results)
        
        # Verify engineer (salaried)
        engineer_result = next(r for r in results if r.employee_id == 1)
        assert engineer_result.gross_pay == Decimal("4615.38")  # Bi-weekly salary
        assert engineer_result.breakdown.regular_pay == Decimal("4615.38")
        assert engineer_result.breakdown.overtime_pay == Decimal("0.00")
        
        # Verify sales rep (hourly with overtime)
        sales_result = next(r for r in results if r.employee_id == 2)
        assert sales_result.gross_pay == Decimal("2300.00")  # 80 regular + 4 OT hours
        assert sales_result.breakdown.regular_pay == Decimal("2000.00")
        assert sales_result.breakdown.overtime_pay == Decimal("150.00")
        
        # Verify support agent (part-time)
        support_result = next(r for r in results if r.employee_id == 3)
        assert support_result.gross_pay == Decimal("800.00")  # 40 hours * $20
        
        # Step 5: Generate payments
        payment_service = PaymentExportService(mock_db)
        payments = self._create_payments_from_results(results, sample_company_setup)
        
        # Step 6: Export payroll data
        with patch('builtins.open', create=True):
            export_result = await payment_service.export_payments(
                start_date=sample_company_setup["pay_period_start"],
                end_date=sample_company_setup["pay_period_end"],
                format="csv"
            )
        
        assert export_result["record_count"] == 3
        assert export_result["total_gross"] == Decimal("7715.38")
        
        # Step 7: Update job status
        job_tracking.status = PayrollJobStatus.COMPLETED
        job_tracking.processed_count = 3
        job_tracking.completed_at = datetime.utcnow()
    
    def _setup_database_mocks(self, mock_db, employees, timesheets, policies):
        """Setup database query mocks."""
        # Implementation moved to shared test utilities
        from .test_utils import setup_database_mocks
        setup_database_mocks(mock_db, employees, timesheets, policies)
    
    def _setup_payroll_calculations(self, mock_service, employees):
        """Setup mock payroll calculations."""
        from .test_utils import setup_payroll_calculations
        setup_payroll_calculations(mock_service, employees)
    
    def _create_payments_from_results(self, results, company_setup):
        """Create payment records from calculation results."""
        from .test_utils import create_payments_from_results
        return create_payments_from_results(results, company_setup)