# backend/modules/payroll/tests/test_payment_export_service.py

"""
Unit tests for PaymentExportService.

Tests payment data export functionality in various formats.
"""

import pytest
from datetime import date, datetime
from decimal import Decimal
from unittest.mock import Mock, MagicMock, patch, AsyncMock
from sqlalchemy.orm import Session
import csv
import io
import json
import openpyxl
from reportlab.lib.pagesizes import letter

from ..services.payment_export_service import PaymentExportService
from ..models.payroll_models import EmployeePayment
from ..exceptions import PayrollException, AuditExportError
from ....staff.models.staff import Staff


class TestPaymentExportService:
    """Test PaymentExportService functionality."""
    
    @pytest.fixture
    def mock_db(self):
        """Create mock database session."""
        return Mock(spec=Session)
    
    @pytest.fixture
    def service(self, mock_db):
        """Create service instance with mock db."""
        return PaymentExportService(mock_db)
    
    @pytest.fixture
    def sample_payments(self):
        """Create sample payment data."""
        payments = []
        for i in range(3):
            staff = Mock(spec=Staff)
            staff.id = i + 1
            staff.full_name = f"Employee {i + 1}"
            staff.employee_code = f"EMP00{i + 1}"
            
            payment = Mock(spec=EmployeePayment)
            payment.id = i + 1
            payment.employee_id = staff.id
            payment.employee = staff
            payment.pay_period_start = date(2024, 1, 1)
            payment.pay_period_end = date(2024, 1, 15)
            payment.regular_hours = Decimal("80.0")
            payment.overtime_hours = Decimal("10.0")
            payment.gross_pay = Decimal("2500.00")
            payment.net_pay = Decimal("1875.00")
            payment.federal_tax = Decimal("375.00")
            payment.state_tax = Decimal("125.00")
            payment.social_security = Decimal("93.75")
            payment.medicare = Decimal("31.25")
            payment.health_insurance = Decimal("100.00")
            payment.retirement_401k = Decimal("125.00")
            
            payments.append(payment)
        return payments
    
    @pytest.mark.asyncio
    async def test_export_payments_csv_success(self, service, mock_db, sample_payments):
        """Test successful CSV export of payments."""
        # Setup
        mock_query = MagicMock()
        mock_db.query.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.all.return_value = sample_payments
        
        # Execute
        with patch('builtins.open', create=True) as mock_open:
            mock_file = MagicMock()
            mock_open.return_value.__enter__.return_value = mock_file
            
            result = await service.export_payments(
                start_date=date(2024, 1, 1),
                end_date=date(2024, 1, 31),
                format="csv",
                include_details=True
            )
        
        # Verify
        assert result["format"] == "csv"
        assert "file_path" in result
        assert result["record_count"] == 3
        assert result["total_gross"] == Decimal("7500.00")
        assert result["total_net"] == Decimal("5625.00")
        assert mock_file.write.called
    
    @pytest.mark.asyncio
    async def test_export_payments_excel_success(self, service, mock_db, sample_payments):
        """Test successful Excel export of payments."""
        # Setup
        mock_query = MagicMock()
        mock_db.query.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.all.return_value = sample_payments
        
        # Execute
        with patch('openpyxl.Workbook') as mock_workbook:
            mock_wb = MagicMock()
            mock_ws = MagicMock()
            mock_workbook.return_value = mock_wb
            mock_wb.active = mock_ws
            
            result = await service.export_payments(
                start_date=date(2024, 1, 1),
                end_date=date(2024, 1, 31),
                format="excel",
                include_details=True
            )
        
        # Verify
        assert result["format"] == "excel"
        assert result["record_count"] == 3
        assert mock_ws.append.called
        assert mock_wb.save.called
    
    @pytest.mark.asyncio
    async def test_export_payments_json_success(self, service, mock_db, sample_payments):
        """Test successful JSON export of payments."""
        # Setup
        mock_query = MagicMock()
        mock_db.query.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.all.return_value = sample_payments
        
        # Execute
        with patch('builtins.open', create=True) as mock_open:
            mock_file = MagicMock()
            mock_open.return_value.__enter__.return_value = mock_file
            
            result = await service.export_payments(
                start_date=date(2024, 1, 1),
                end_date=date(2024, 1, 31),
                format="json"
            )
        
        # Verify
        assert result["format"] == "json"
        assert result["record_count"] == 3
        # Verify JSON was written
        write_calls = mock_file.write.call_args_list
        assert len(write_calls) > 0
    
    @pytest.mark.asyncio
    async def test_export_payments_pdf_success(self, service, mock_db, sample_payments):
        """Test successful PDF export of payments."""
        # Setup
        mock_query = MagicMock()
        mock_db.query.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.all.return_value = sample_payments
        
        # Execute
        with patch('reportlab.platypus.SimpleDocTemplate') as mock_doc:
            mock_doc_instance = MagicMock()
            mock_doc.return_value = mock_doc_instance
            
            result = await service.export_payments(
                start_date=date(2024, 1, 1),
                end_date=date(2024, 1, 31),
                format="pdf",
                include_details=True
            )
        
        # Verify
        assert result["format"] == "pdf"
        assert result["record_count"] == 3
        assert mock_doc_instance.build.called
    
    @pytest.mark.asyncio
    async def test_export_payments_with_employee_filter(self, service, mock_db, sample_payments):
        """Test export with employee ID filter."""
        # Setup
        filtered_payments = [sample_payments[0]]  # Only first employee
        mock_query = MagicMock()
        mock_db.query.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.all.return_value = filtered_payments
        
        # Execute
        result = await service.export_payments(
            start_date=date(2024, 1, 1),
            end_date=date(2024, 1, 31),
            employee_ids=[1],
            format="csv"
        )
        
        # Verify
        assert result["record_count"] == 1
        assert result["total_gross"] == Decimal("2500.00")
        assert result["total_net"] == Decimal("1875.00")
    
    @pytest.mark.asyncio
    async def test_export_payments_empty_results(self, service, mock_db):
        """Test export with no payments found."""
        # Setup
        mock_query = MagicMock()
        mock_db.query.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.all.return_value = []
        
        # Execute
        result = await service.export_payments(
            start_date=date(2024, 1, 1),
            end_date=date(2024, 1, 31),
            format="csv"
        )
        
        # Verify
        assert result["record_count"] == 0
        assert result["total_gross"] == Decimal("0.00")
        assert result["total_net"] == Decimal("0.00")
    
    @pytest.mark.asyncio
    async def test_export_payments_invalid_format(self, service, mock_db):
        """Test export with invalid format."""
        # Execute and verify
        with pytest.raises(AuditExportError) as exc_info:
            await service.export_payments(
                start_date=date(2024, 1, 1),
                end_date=date(2024, 1, 31),
                format="invalid_format"
            )
        
        assert "Unsupported export format" in str(exc_info.value)
    
    @pytest.mark.asyncio
    async def test_export_bank_file_ach_format(self, service, mock_db, sample_payments):
        """Test ACH bank file export."""
        # Setup
        mock_query = MagicMock()
        mock_db.query.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.all.return_value = sample_payments
        
        # Mock bank details on employees
        for payment in sample_payments:
            payment.employee.bank_account_number = "123456789"
            payment.employee.bank_routing_number = "987654321"
            payment.employee.account_type = "checking"
        
        # Execute
        with patch('builtins.open', create=True) as mock_open:
            mock_file = MagicMock()
            mock_open.return_value.__enter__.return_value = mock_file
            
            result = await service.export_bank_file(
                payment_ids=[p.id for p in sample_payments],
                bank_format="ach",
                effective_date=date(2024, 1, 20)
            )
        
        # Verify
        assert result["format"] == "ach"
        assert result["payment_count"] == 3
        assert result["total_amount"] == Decimal("5625.00")
        assert "file_path" in result
    
    @pytest.mark.asyncio
    async def test_export_bank_file_wire_format(self, service, mock_db, sample_payments):
        """Test wire transfer bank file export."""
        # Setup
        mock_query = MagicMock()
        mock_db.query.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.all.return_value = sample_payments
        
        # Mock bank details
        for payment in sample_payments:
            payment.employee.bank_account_number = "123456789"
            payment.employee.bank_routing_number = "987654321"
            payment.employee.bank_swift_code = "TESTUSXX"
        
        # Execute
        result = await service.export_bank_file(
            payment_ids=[p.id for p in sample_payments],
            bank_format="wire"
        )
        
        # Verify
        assert result["format"] == "wire"
        assert result["payment_count"] == 3
    
    @pytest.mark.asyncio
    async def test_generate_payslips_pdf(self, service, mock_db, sample_payments):
        """Test payslip PDF generation."""
        # Setup
        mock_query = MagicMock()
        mock_db.query.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.all.return_value = sample_payments[:1]  # Single payment
        
        # Execute
        with patch('reportlab.pdfgen.canvas.Canvas') as mock_canvas:
            mock_canvas_instance = MagicMock()
            mock_canvas.return_value = mock_canvas_instance
            
            result = await service.generate_payslips(
                payment_ids=[1],
                format="pdf",
                delivery_method="email"
            )
        
        # Verify
        assert result["payslip_count"] == 1
        assert result["delivery_method"] == "email"
        assert mock_canvas_instance.save.called
    
    @pytest.mark.asyncio
    async def test_export_summary_report(self, service, mock_db, sample_payments):
        """Test summary report generation."""
        # Setup
        mock_query = MagicMock()
        mock_db.query.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.all.return_value = sample_payments
        
        # Execute
        result = await service.export_summary_report(
            start_date=date(2024, 1, 1),
            end_date=date(2024, 1, 31),
            group_by="department",
            format="excel"
        )
        
        # Verify
        assert result["format"] == "excel"
        assert "summary_data" in result
        assert result["total_employees"] == 3
        assert result["total_gross_pay"] == Decimal("7500.00")
    
    @pytest.mark.asyncio
    async def test_export_tax_report(self, service, mock_db, sample_payments):
        """Test tax report generation."""
        # Setup
        mock_query = MagicMock()
        mock_db.query.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.all.return_value = sample_payments
        
        # Execute
        result = await service.export_tax_report(
            year=2024,
            quarter=1,
            report_type="quarterly_941"
        )
        
        # Verify
        assert result["report_type"] == "quarterly_941"
        assert result["period"] == "Q1 2024"
        assert "total_wages" in result
        assert "federal_tax_withheld" in result
        assert "social_security_wages" in result
    
    @pytest.mark.asyncio
    async def test_export_with_custom_fields(self, service, mock_db, sample_payments):
        """Test export with custom field selection."""
        # Setup
        mock_query = MagicMock()
        mock_db.query.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.all.return_value = sample_payments
        
        # Execute
        custom_fields = ["employee_id", "employee_name", "net_pay", "pay_date"]
        result = await service.export_payments(
            start_date=date(2024, 1, 1),
            end_date=date(2024, 1, 31),
            format="csv",
            custom_fields=custom_fields
        )
        
        # Verify
        assert result["export_fields"] == custom_fields
        assert result["record_count"] == 3
    
    @pytest.mark.asyncio
    async def test_export_with_database_error(self, service, mock_db):
        """Test export with database error."""
        # Setup
        mock_db.query.side_effect = Exception("Database connection error")
        
        # Execute and verify
        with pytest.raises(PayrollException) as exc_info:
            await service.export_payments(
                start_date=date(2024, 1, 1),
                end_date=date(2024, 1, 31)
            )
        
        assert "Database connection error" in str(exc_info.value)
    
    @pytest.mark.asyncio
    async def test_batch_export_multiple_formats(self, service, mock_db, sample_payments):
        """Test batch export in multiple formats."""
        # Setup
        mock_query = MagicMock()
        mock_db.query.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.all.return_value = sample_payments
        
        # Execute
        formats = ["csv", "excel", "json"]
        results = await service.batch_export(
            start_date=date(2024, 1, 1),
            end_date=date(2024, 1, 31),
            formats=formats
        )
        
        # Verify
        assert len(results) == 3
        for i, format in enumerate(formats):
            assert results[i]["format"] == format
            assert results[i]["record_count"] == 3