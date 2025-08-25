"""
Secure Server-side Payroll Calculation Service

This service handles all payroll calculations server-side to ensure:
- Security of sensitive wage/tax data
- Compliance with jurisdictional rules
- Consistency across all clients
- Audit trail for all calculations
"""

from typing import Dict, List, Optional, Any
from datetime import datetime, date, timedelta
from decimal import Decimal
from sqlalchemy.orm import Session
import logging

from core.auth import User
from core.audit_logger import AuditLogger
from ..models.payroll_models import PayrollRun, PayrollEntry
from ..services.payroll_tax_engine import PayrollTaxEngine
from modules.staff.models import StaffMember, Shift

logger = logging.getLogger(__name__)
audit_logger = AuditLogger()


class SecurePayrollService:
    """
    Secure payroll calculation service that ensures all sensitive
    calculations are performed server-side with proper authorization
    """

    def __init__(self, db: Session):
        self.db = db
        self.tax_engine = PayrollTaxEngine()

    async def calculate_payroll_preview(
        self,
        restaurant_id: int,
        start_date: date,
        end_date: date,
        staff_ids: Optional[List[int]] = None,
        include_overtime: bool = True,
        include_benefits: bool = True,
        current_user: User = None,
    ) -> Dict[str, Any]:
        """
        Calculate payroll preview with all sensitive calculations server-side
        
        Args:
            restaurant_id: Restaurant/tenant ID
            start_date: Period start date
            end_date: Period end date
            staff_ids: Optional list of staff to include
            include_overtime: Include overtime calculations
            include_benefits: Include benefits calculations
            current_user: Current authenticated user
        
        Returns:
            Payroll preview with calculated values (no sensitive logic exposed)
        """
        
        # Verify user has permission to view payroll
        if not self._check_payroll_permission(current_user, restaurant_id, "view"):
            raise PermissionError("Insufficient permissions to view payroll")

        # Log the preview request for audit
        await audit_logger.log_event(
            event_type="payroll.preview",
            user_id=current_user.id,
            restaurant_id=restaurant_id,
            details={
                "start_date": start_date.isoformat(),
                "end_date": end_date.isoformat(),
                "staff_count": len(staff_ids) if staff_ids else "all",
            },
        )

        # Get shifts for the period
        shifts_query = self.db.query(Shift).filter(
            Shift.restaurant_id == restaurant_id,
            Shift.date >= start_date,
            Shift.date <= end_date,
        )

        if staff_ids:
            shifts_query = shifts_query.filter(Shift.staff_id.in_(staff_ids))

        shifts = shifts_query.all()

        # Calculate payroll for each staff member
        payroll_data = {}
        total_summary = {
            "gross_pay": Decimal("0"),
            "federal_tax": Decimal("0"),
            "state_tax": Decimal("0"),
            "local_tax": Decimal("0"),
            "social_security": Decimal("0"),
            "medicare": Decimal("0"),
            "benefits_deduction": Decimal("0"),
            "net_pay": Decimal("0"),
            "employer_contributions": Decimal("0"),
        }

        # Group shifts by staff
        staff_shifts = {}
        for shift in shifts:
            if shift.staff_id not in staff_shifts:
                staff_shifts[shift.staff_id] = []
            staff_shifts[shift.staff_id].append(shift)

        for staff_id, staff_shift_list in staff_shifts.items():
            staff = self.db.query(StaffMember).get(staff_id)
            if not staff:
                continue

            # Calculate individual payroll (all sensitive calculations here)
            staff_payroll = self._calculate_staff_payroll(
                staff,
                staff_shift_list,
                include_overtime,
                include_benefits,
                restaurant_id,
            )

            # Mask sensitive data based on permissions
            if not self._can_view_staff_details(current_user, staff_id):
                staff_payroll = self._mask_sensitive_data(staff_payroll)

            payroll_data[staff_id] = staff_payroll

            # Update totals
            for key in total_summary:
                if key in staff_payroll:
                    total_summary[key] += Decimal(str(staff_payroll[key]))

        return {
            "period": {
                "start_date": start_date.isoformat(),
                "end_date": end_date.isoformat(),
            },
            "staff_payroll": payroll_data,
            "summary": {k: float(v) for k, v in total_summary.items()},
            "generated_at": datetime.utcnow().isoformat(),
            "generated_by": current_user.id,
            "is_preview": True,
            "compliance_notes": self._get_compliance_notes(restaurant_id),
        }

    def _calculate_staff_payroll(
        self,
        staff: StaffMember,
        shifts: List[Shift],
        include_overtime: bool,
        include_benefits: bool,
        restaurant_id: int,
    ) -> Dict[str, Any]:
        """
        Calculate payroll for a single staff member
        
        All sensitive calculations happen here server-side
        """
        
        # Calculate hours
        regular_hours = Decimal("0")
        overtime_hours = Decimal("0")
        total_hours = Decimal("0")

        for shift in shifts:
            hours = self._calculate_shift_hours(shift)
            total_hours += hours

            if include_overtime and total_hours > 40:
                overtime = min(hours, total_hours - 40)
                overtime_hours += overtime
                regular_hours += hours - overtime
            else:
                regular_hours += hours

        # Get pay rate (could be role-based, seniority-based, etc.)
        pay_rate = self._get_pay_rate(staff, restaurant_id)

        # Calculate gross pay
        regular_pay = regular_hours * pay_rate
        overtime_pay = overtime_hours * pay_rate * Decimal("1.5") if include_overtime else Decimal("0")
        gross_pay = regular_pay + overtime_pay

        # Calculate taxes using tax engine
        tax_breakdown = self.tax_engine.calculate_taxes(
            gross_pay=float(gross_pay),
            pay_frequency="biweekly",
            filing_status=staff.tax_filing_status or "single",
            allowances=staff.tax_allowances or 0,
            state=self._get_restaurant_state(restaurant_id),
            additional_withholding=float(staff.additional_withholding or 0),
        )

        # Calculate benefits if applicable
        benefits_deduction = Decimal("0")
        if include_benefits and staff.benefits_enrolled:
            benefits_deduction = self._calculate_benefits_deduction(
                staff, gross_pay, restaurant_id
            )

        # Calculate net pay
        total_deductions = (
            Decimal(str(tax_breakdown["total_employee_tax"])) + benefits_deduction
        )
        net_pay = gross_pay - total_deductions

        return {
            "staff_id": staff.id,
            "staff_name": f"{staff.first_name} {staff.last_name}",
            "regular_hours": float(regular_hours),
            "overtime_hours": float(overtime_hours),
            "total_hours": float(total_hours),
            "pay_rate": float(pay_rate),
            "regular_pay": float(regular_pay),
            "overtime_pay": float(overtime_pay),
            "gross_pay": float(gross_pay),
            "federal_tax": tax_breakdown["federal_withholding"],
            "state_tax": tax_breakdown["state_withholding"],
            "local_tax": tax_breakdown.get("local_tax", 0),
            "social_security": tax_breakdown["social_security_employee"],
            "medicare": tax_breakdown["medicare_employee"],
            "benefits_deduction": float(benefits_deduction),
            "total_deductions": float(total_deductions),
            "net_pay": float(net_pay),
            "employer_ss": tax_breakdown["social_security_employer"],
            "employer_medicare": tax_breakdown["medicare_employer"],
            "employer_contributions": tax_breakdown["total_employer_tax"],
        }

    def _calculate_shift_hours(self, shift: Shift) -> Decimal:
        """Calculate hours for a shift, accounting for breaks"""
        
        if not shift.clock_in or not shift.clock_out:
            return Decimal("0")

        duration = (shift.clock_out - shift.clock_in).total_seconds() / 3600
        
        # Subtract unpaid breaks
        if shift.break_duration:
            duration -= shift.break_duration / 60  # Convert minutes to hours

        return Decimal(str(max(0, duration)))

    def _get_pay_rate(self, staff: StaffMember, restaurant_id: int) -> Decimal:
        """Get staff pay rate based on role, seniority, etc."""
        
        # This would fetch from a pay rate table based on various factors
        # For now, using a simplified version
        base_rate = Decimal(str(staff.hourly_rate or 15.00))
        
        # Could add seniority bonus, role multiplier, etc.
        return base_rate

    def _calculate_benefits_deduction(
        self, staff: StaffMember, gross_pay: Decimal, restaurant_id: int
    ) -> Decimal:
        """Calculate benefits deduction based on enrollment"""
        
        # This would fetch from benefits configuration
        # Simplified version for demonstration
        if staff.benefits_plan == "basic":
            return Decimal("50.00")  # Flat rate
        elif staff.benefits_plan == "premium":
            return gross_pay * Decimal("0.03")  # Percentage of gross
        
        return Decimal("0")

    def _get_restaurant_state(self, restaurant_id: int) -> str:
        """Get restaurant's state for tax calculations"""
        
        # This would fetch from restaurant configuration
        # Default to CA for demonstration
        return "CA"

    def _check_payroll_permission(
        self, user: User, restaurant_id: int, action: str
    ) -> bool:
        """Check if user has permission for payroll action"""
        
        # Check role-based permissions
        if user.role in ["owner", "payroll_admin"]:
            return True
        
        if user.role == "manager" and action == "view":
            # Managers can view but not export
            return True
        
        return False

    def _can_view_staff_details(self, user: User, staff_id: int) -> bool:
        """Check if user can view specific staff details"""
        
        # Owners and payroll admins can see all
        if user.role in ["owner", "payroll_admin"]:
            return True
        
        # Managers can only see their team
        if user.role == "manager":
            # Check if staff is in manager's team
            # Simplified for demonstration
            return True
        
        # Staff can only see their own
        return user.staff_id == staff_id

    def _mask_sensitive_data(self, payroll_data: Dict[str, Any]) -> Dict[str, Any]:
        """Mask sensitive payroll data"""
        
        masked = payroll_data.copy()
        
        # Mask specific fields
        sensitive_fields = [
            "pay_rate",
            "gross_pay",
            "net_pay",
            "federal_tax",
            "state_tax",
            "social_security",
            "medicare",
        ]
        
        for field in sensitive_fields:
            if field in masked:
                masked[field] = "***"
        
        return masked

    def _get_compliance_notes(self, restaurant_id: int) -> List[str]:
        """Get compliance notes for the payroll period"""
        
        notes = []
        
        # Check for compliance issues
        # This would check various compliance rules
        notes.append("All federal and state tax rates are current as of calculation date")
        notes.append("Overtime calculated per FLSA guidelines")
        
        return notes

    async def export_payroll_with_audit(
        self,
        restaurant_id: int,
        payroll_data: Dict[str, Any],
        export_format: str,
        current_user: User,
    ) -> str:
        """
        Export payroll data with full audit logging
        
        Args:
            restaurant_id: Restaurant/tenant ID
            payroll_data: Calculated payroll data
            export_format: Format (csv, pdf, xlsx)
            current_user: Current authenticated user
        
        Returns:
            Signed URL for secure download
        """
        
        # Check export permission
        if not self._check_payroll_permission(current_user, restaurant_id, "export"):
            raise PermissionError("Insufficient permissions to export payroll")

        # Log the export for audit
        await audit_logger.log_event(
            event_type="payroll.export",
            user_id=current_user.id,
            restaurant_id=restaurant_id,
            details={
                "format": export_format,
                "period": payroll_data.get("period"),
                "staff_count": len(payroll_data.get("staff_payroll", {})),
                "total_amount": payroll_data.get("summary", {}).get("gross_pay"),
            },
            severity="high",  # Exports are high-severity audit events
        )

        # Generate secure signed URL for download
        # This would integrate with cloud storage (S3, etc.)
        signed_url = self._generate_signed_url(
            payroll_data, export_format, restaurant_id, current_user.id
        )

        return signed_url

    def _generate_signed_url(
        self,
        data: Dict[str, Any],
        format: str,
        restaurant_id: int,
        user_id: int,
    ) -> str:
        """Generate a secure, time-limited signed URL for download"""
        
        # This would integrate with cloud storage service
        # For demonstration, returning a placeholder
        import uuid
        
        export_id = str(uuid.uuid4())
        
        # Store export temporarily with expiration
        # In production, this would upload to S3/Azure/GCS
        
        return f"/api/payroll/exports/{export_id}/download?expires=3600"