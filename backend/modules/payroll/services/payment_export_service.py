# backend/modules/payroll/services/payment_export_service.py

"""
Payment export service for generating export files.
"""

from sqlalchemy.orm import Session
from typing import List, Optional, Dict, Any
from datetime import date
import csv
import io
import json
from decimal import Decimal

from ..models.payroll_models import EmployeePayment


class PaymentExportService:
    """Service for exporting payment data in various formats."""

    def __init__(self, db: Session):
        self.db = db

    async def export_payments(
        self,
        start_date: date,
        end_date: date,
        employee_ids: Optional[List[int]] = None,
        format: str = "csv",
        include_details: bool = True,
    ) -> Dict[str, Any]:
        """
        Export payment data in the specified format.

        Args:
            start_date: Export period start
            end_date: Export period end
            employee_ids: Optional list of employee IDs
            format: Export format (csv, excel, pdf)
            include_details: Include detailed breakdown

        Returns:
            Export result with file path and metadata
        """
        # Query payments
        query = self.db.query(EmployeePayment).filter(
            EmployeePayment.pay_period_start >= start_date,
            EmployeePayment.pay_period_end <= end_date,
        )

        if employee_ids:
            query = query.filter(EmployeePayment.employee_id.in_(employee_ids))

        payments = query.order_by(
            EmployeePayment.employee_id, EmployeePayment.pay_period_start
        ).all()

        # Generate export based on format
        if format == "csv":
            result = self._export_to_csv(payments, include_details)
        elif format == "excel":
            result = self._export_to_excel(payments, include_details)
        elif format == "pdf":
            result = self._export_to_pdf(payments, include_details)
        else:
            raise ValueError(f"Unsupported export format: {format}")

        return {
            "file_path": result["file_path"],
            "record_count": len(payments),
            "file_size": result["file_size"],
            "format": format,
        }

    def _export_to_csv(
        self, payments: List[EmployeePayment], include_details: bool
    ) -> Dict[str, Any]:
        """Export payments to CSV format."""
        # Create CSV in memory
        output = io.StringIO()

        # Define columns
        if include_details:
            fieldnames = [
                "employee_id",
                "pay_period_start",
                "pay_period_end",
                "regular_hours",
                "overtime_hours",
                "regular_pay",
                "overtime_pay",
                "gross_amount",
                "federal_tax",
                "state_tax",
                "social_security",
                "medicare",
                "net_amount",
                "status",
                "paid_at",
            ]
        else:
            fieldnames = [
                "employee_id",
                "pay_period_start",
                "pay_period_end",
                "gross_amount",
                "net_amount",
                "status",
            ]

        writer = csv.DictWriter(output, fieldnames=fieldnames)
        writer.writeheader()

        # Write payment data
        for payment in payments:
            row = {
                "employee_id": payment.employee_id,
                "pay_period_start": payment.pay_period_start.isoformat(),
                "pay_period_end": payment.pay_period_end.isoformat(),
                "gross_amount": str(payment.gross_amount),
                "net_amount": str(payment.net_amount),
                "status": payment.status.value,
            }

            if include_details:
                row.update(
                    {
                        "regular_hours": str(payment.regular_hours),
                        "overtime_hours": str(payment.overtime_hours),
                        "regular_pay": str(payment.regular_pay),
                        "overtime_pay": str(payment.overtime_pay),
                        "federal_tax": str(payment.federal_tax_amount),
                        "state_tax": str(payment.state_tax_amount),
                        "social_security": str(payment.social_security_amount),
                        "medicare": str(payment.medicare_amount),
                        "paid_at": (
                            payment.paid_at.isoformat() if payment.paid_at else ""
                        ),
                    }
                )

            writer.writerow(row)

        # Get file content
        content = output.getvalue()
        file_size = len(content.encode("utf-8"))

        # In a real implementation, save to file storage
        # For now, return mock file path
        return {
            "file_path": f"/exports/payments_{date.today().isoformat()}.csv",
            "file_size": file_size,
        }

    def _export_to_excel(
        self, payments: List[EmployeePayment], include_details: bool
    ) -> Dict[str, Any]:
        """Export payments to Excel format."""
        # Placeholder for Excel export
        # In a real implementation, use openpyxl or xlsxwriter
        return {
            "file_path": f"/exports/payments_{date.today().isoformat()}.xlsx",
            "file_size": 0,
        }

    def _export_to_pdf(
        self, payments: List[EmployeePayment], include_details: bool
    ) -> Dict[str, Any]:
        """Export payments to PDF format."""
        # Placeholder for PDF export
        # In a real implementation, use reportlab or similar
        return {
            "file_path": f"/exports/payments_{date.today().isoformat()}.pdf",
            "file_size": 0,
        }
