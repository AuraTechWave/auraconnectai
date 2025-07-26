"""
Enhanced Payroll Engine for Phase 3 - Comprehensive payroll computation.

This module integrates with:
- Staff hours and attendance data
- Tax services (AUR-276) for accurate deductions
- Policy-based benefit deductions
- EmployeePayment record generation
"""

from sqlalchemy.orm import Session
from typing import Dict, List, Optional, Tuple
from decimal import Decimal, ROUND_HALF_UP
from datetime import datetime, date
from dataclasses import dataclass

from ..models.attendance_models import AttendanceLog
from ..models.staff_models import StaffMember
from ..schemas.payroll_schemas import PayrollBreakdown
from ...payroll.services.payroll_tax_engine import PayrollTaxEngine
from ...payroll.services.payroll_tax_service import PayrollTaxService
from ...payroll.schemas.payroll_tax_schemas import (
    PayrollTaxCalculationRequest, PayrollTaxServiceRequest
)
from ...payroll.models.payroll_models import EmployeePayment


@dataclass
class StaffPayPolicy:
    """Staff member pay policy configuration."""
    base_hourly_rate: Decimal
    overtime_multiplier: Decimal = Decimal('1.5')
    regular_hours_threshold: Decimal = Decimal('40.0')  # per week
    location: str = "default"
    
    # Benefit deductions (monthly amounts)
    health_insurance: Decimal = Decimal('0.00')
    dental_insurance: Decimal = Decimal('0.00')
    retirement_contribution: Decimal = Decimal('0.00')
    parking_fee: Decimal = Decimal('0.00')


@dataclass
class HoursBreakdown:
    """Detailed breakdown of hours worked."""
    regular_hours: Decimal
    overtime_hours: Decimal
    double_time_hours: Decimal = Decimal('0.00')
    holiday_hours: Decimal = Decimal('0.00')
    sick_hours: Decimal = Decimal('0.00')
    vacation_hours: Decimal = Decimal('0.00')


@dataclass
class EarningsBreakdown:
    """Detailed breakdown of earnings."""
    regular_pay: Decimal
    overtime_pay: Decimal
    double_time_pay: Decimal = Decimal('0.00')
    holiday_pay: Decimal = Decimal('0.00')
    sick_pay: Decimal = Decimal('0.00')
    vacation_pay: Decimal = Decimal('0.00')
    bonus: Decimal = Decimal('0.00')
    commission: Decimal = Decimal('0.00')
    
    @property
    def gross_pay(self) -> Decimal:
        """Calculate total gross pay."""
        return (
            self.regular_pay + self.overtime_pay + self.double_time_pay +
            self.holiday_pay + self.sick_pay + self.vacation_pay +
            self.bonus + self.commission
        )


@dataclass
class DeductionsBreakdown:
    """Detailed breakdown of deductions."""
    # Tax deductions (from tax engine)
    federal_tax: Decimal = Decimal('0.00')
    state_tax: Decimal = Decimal('0.00')
    local_tax: Decimal = Decimal('0.00')
    social_security: Decimal = Decimal('0.00')
    medicare: Decimal = Decimal('0.00')
    unemployment: Decimal = Decimal('0.00')
    
    # Benefit deductions
    health_insurance: Decimal = Decimal('0.00')
    dental_insurance: Decimal = Decimal('0.00')
    retirement_contribution: Decimal = Decimal('0.00')
    parking_fee: Decimal = Decimal('0.00')
    
    # Other deductions
    garnishments: Decimal = Decimal('0.00')
    loan_repayments: Decimal = Decimal('0.00')
    
    @property
    def total_tax_deductions(self) -> Decimal:
        """Calculate total tax deductions."""
        return (
            self.federal_tax + self.state_tax + self.local_tax +
            self.social_security + self.medicare + self.unemployment
        )
    
    @property
    def total_benefit_deductions(self) -> Decimal:
        """Calculate total benefit deductions."""
        return (
            self.health_insurance + self.dental_insurance +
            self.retirement_contribution + self.parking_fee
        )
    
    @property
    def total_other_deductions(self) -> Decimal:
        """Calculate total other deductions."""
        return self.garnishments + self.loan_repayments
    
    @property
    def total_deductions(self) -> Decimal:
        """Calculate total deductions."""
        return (
            self.total_tax_deductions + 
            self.total_benefit_deductions + 
            self.total_other_deductions
        )


class EnhancedPayrollEngine:
    """
    Enhanced payroll engine that integrates with tax services and handles
    comprehensive payroll calculations including policy-based deductions.
    """
    
    def __init__(self, db: Session):
        self.db = db
        self.tax_engine = PayrollTaxEngine(db)
        self.tax_service = PayrollTaxService(db)
    
    def get_staff_pay_policy(self, staff_id: int) -> StaffPayPolicy:
        """
        Get staff member's pay policy. In a real implementation, this would
        fetch from a database table. For now, using defaults with some variation.
        """
        staff = self.db.query(StaffMember).filter(StaffMember.id == staff_id).first()
        if not staff:
            raise ValueError(f"Staff member with ID {staff_id} not found")
        
        # TODO: Replace with actual policy lookup from database
        # For now, varying rates based on role or other criteria
        base_rate = Decimal('15.00')  # Default rate
        
        if staff.role and staff.role.name:
            role_rates = {
                'manager': Decimal('25.00'),
                'supervisor': Decimal('20.00'),
                'server': Decimal('12.00'),
                'cook': Decimal('16.00'),
                'cashier': Decimal('14.00')
            }
            base_rate = role_rates.get(staff.role.name.lower(), base_rate)
        
        return StaffPayPolicy(
            base_hourly_rate=base_rate,
            overtime_multiplier=Decimal('1.5'),
            regular_hours_threshold=Decimal('40.0'),
            location="restaurant_main",  # Would come from staff location
            health_insurance=Decimal('120.00'),  # Monthly amount
            dental_insurance=Decimal('25.00'),
            retirement_contribution=Decimal('50.00'),
            parking_fee=Decimal('15.00')
        )
    
    def calculate_hours_for_period(
        self, 
        staff_id: int, 
        start_date: date, 
        end_date: date
    ) -> HoursBreakdown:
        """
        Calculate detailed hours breakdown for a pay period.
        
        Args:
            staff_id: Staff member ID
            start_date: Pay period start date
            end_date: Pay period end date
            
        Returns:
            HoursBreakdown with regular and overtime hours
        """
        # Get attendance logs for the period
        attendance_logs = self.db.query(AttendanceLog).filter(
            AttendanceLog.staff_id == staff_id,
            AttendanceLog.check_in >= datetime.combine(start_date, datetime.min.time()),
            AttendanceLog.check_in < datetime.combine(end_date, datetime.min.time()),
            AttendanceLog.check_out.isnot(None)
        ).all()
        
        total_hours = Decimal('0.00')
        daily_hours: List[Decimal] = []
        
        # Calculate hours by day to properly handle daily overtime rules
        current_day = start_date
        while current_day < end_date:
            day_start = datetime.combine(current_day, datetime.min.time())
            day_end = datetime.combine(current_day, datetime.max.time())
            
            day_logs = [
                log for log in attendance_logs 
                if day_start <= log.check_in <= day_end
            ]
            
            day_hours = Decimal('0.00')
            for log in day_logs:
                if log.check_out and log.check_in:
                    hours = (log.check_out - log.check_in).total_seconds() / 3600
                    day_hours += Decimal(str(hours))
            
            daily_hours.append(day_hours)
            total_hours += day_hours
            current_day = datetime.combine(current_day, datetime.min.time()).date()
            current_day = datetime.combine(current_day + datetime.timedelta(days=1), datetime.min.time()).date()
        
        # Calculate regular vs overtime hours
        # Standard rule: Over 40 hours per week is overtime
        regular_hours = min(total_hours, Decimal('40.0'))
        overtime_hours = max(Decimal('0.00'), total_hours - Decimal('40.0'))
        
        return HoursBreakdown(
            regular_hours=regular_hours.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP),
            overtime_hours=overtime_hours.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
        )
    
    def calculate_earnings(
        self, 
        hours: HoursBreakdown, 
        policy: StaffPayPolicy
    ) -> EarningsBreakdown:
        """
        Calculate detailed earnings breakdown based on hours and pay policy.
        
        Args:
            hours: Hours breakdown for the period
            policy: Staff pay policy
            
        Returns:
            EarningsBreakdown with detailed pay components
        """
        regular_pay = hours.regular_hours * policy.base_hourly_rate
        overtime_rate = policy.base_hourly_rate * policy.overtime_multiplier
        overtime_pay = hours.overtime_hours * overtime_rate
        
        # Additional pay types would be calculated here
        double_time_pay = hours.double_time_hours * (policy.base_hourly_rate * Decimal('2.0'))
        holiday_pay = hours.holiday_hours * (policy.base_hourly_rate * Decimal('1.5'))
        sick_pay = hours.sick_hours * policy.base_hourly_rate
        vacation_pay = hours.vacation_hours * policy.base_hourly_rate
        
        return EarningsBreakdown(
            regular_pay=regular_pay.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP),
            overtime_pay=overtime_pay.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP),
            double_time_pay=double_time_pay.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP),
            holiday_pay=holiday_pay.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP),
            sick_pay=sick_pay.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP),
            vacation_pay=vacation_pay.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP),
            bonus=Decimal('0.00'),  # Would be set based on performance/policy
            commission=Decimal('0.00')  # Would be calculated for commission-based roles
        )
    
    async def calculate_tax_deductions(
        self, 
        staff_id: int,
        gross_pay: Decimal,
        pay_date: date,
        location: str,
        tenant_id: Optional[int] = None
    ) -> DeductionsBreakdown:
        """
        Calculate tax deductions using the integrated tax engine.
        
        Args:
            staff_id: Staff member ID
            gross_pay: Gross pay amount
            pay_date: Pay date for tax rule lookup
            location: Location for tax jurisdiction
            tenant_id: Tenant ID for multi-tenant support
            
        Returns:
            DeductionsBreakdown with calculated tax amounts
        """
        # Create tax calculation request
        tax_request = PayrollTaxServiceRequest(
            employee_id=staff_id,
            gross_amount=gross_pay,
            pay_period_start=pay_date,
            pay_period_end=pay_date,  # Single pay date for this calculation
            location=location,
            tenant_id=tenant_id
        )
        
        # Calculate taxes using the tax service
        tax_response = await self.tax_service.calculate_and_save_taxes(tax_request)
        
        # Map tax response to deductions breakdown
        deductions = DeductionsBreakdown()
        
        for tax_detail in tax_response.tax_breakdown.tax_applications:
            if tax_detail.tax_rule.tax_type.value.lower() == 'federal':
                deductions.federal_tax += tax_detail.calculated_amount
            elif tax_detail.tax_rule.tax_type.value.lower() == 'state':
                deductions.state_tax += tax_detail.calculated_amount
            elif tax_detail.tax_rule.tax_type.value.lower() == 'local':
                deductions.local_tax += tax_detail.calculated_amount
            elif 'social_security' in tax_detail.tax_rule.tax_type.value.lower():
                deductions.social_security += tax_detail.calculated_amount
            elif 'medicare' in tax_detail.tax_rule.tax_type.value.lower():
                deductions.medicare += tax_detail.calculated_amount
            elif 'unemployment' in tax_detail.tax_rule.tax_type.value.lower():
                deductions.unemployment += tax_detail.calculated_amount
        
        return deductions
    
    def apply_benefit_deductions(
        self, 
        deductions: DeductionsBreakdown, 
        policy: StaffPayPolicy
    ) -> DeductionsBreakdown:
        """
        Apply benefit and other policy-based deductions.
        
        Args:
            deductions: Current deductions breakdown
            policy: Staff pay policy with benefit amounts
            
        Returns:
            Updated DeductionsBreakdown with benefit deductions
        """
        # Apply monthly benefit deductions (prorated for pay period)
        # Assuming bi-weekly pay, so divide monthly amounts by 2.17 (52 weeks / 24 pay periods)
        proration_factor = Decimal('0.46')  # Approximate bi-weekly proration
        
        deductions.health_insurance = (policy.health_insurance * proration_factor).quantize(
            Decimal('0.01'), rounding=ROUND_HALF_UP
        )
        deductions.dental_insurance = (policy.dental_insurance * proration_factor).quantize(
            Decimal('0.01'), rounding=ROUND_HALF_UP
        )
        deductions.retirement_contribution = (policy.retirement_contribution * proration_factor).quantize(
            Decimal('0.01'), rounding=ROUND_HALF_UP
        )
        deductions.parking_fee = (policy.parking_fee * proration_factor).quantize(
            Decimal('0.01'), rounding=ROUND_HALF_UP
        )
        
        return deductions
    
    async def compute_comprehensive_payroll(
        self,
        staff_id: int,
        pay_period_start: date,
        pay_period_end: date,
        tenant_id: Optional[int] = None
    ) -> Dict:
        """
        Compute comprehensive payroll for a staff member and pay period.
        
        Args:
            staff_id: Staff member ID
            pay_period_start: Pay period start date
            pay_period_end: Pay period end date
            tenant_id: Tenant ID for multi-tenant support
            
        Returns:
            Comprehensive payroll calculation dictionary
        """
        # Get staff pay policy
        policy = self.get_staff_pay_policy(staff_id)
        
        # Calculate hours worked
        hours = self.calculate_hours_for_period(staff_id, pay_period_start, pay_period_end)
        
        # Calculate earnings
        earnings = self.calculate_earnings(hours, policy)
        
        # Calculate tax deductions
        tax_deductions = await self.calculate_tax_deductions(
            staff_id=staff_id,
            gross_pay=earnings.gross_pay,
            pay_date=pay_period_end,
            location=policy.location,
            tenant_id=tenant_id
        )
        
        # Apply benefit deductions
        total_deductions = self.apply_benefit_deductions(tax_deductions, policy)
        
        # Calculate net pay
        net_pay = earnings.gross_pay - total_deductions.total_deductions
        
        return {
            'staff_id': staff_id,
            'pay_period_start': pay_period_start,
            'pay_period_end': pay_period_end,
            'hours_breakdown': hours,
            'earnings_breakdown': earnings,
            'deductions_breakdown': total_deductions,
            'gross_pay': earnings.gross_pay,
            'total_deductions': total_deductions.total_deductions,
            'net_pay': net_pay.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP),
            'policy': policy
        }
    
    async def create_employee_payment_record(
        self,
        payroll_calculation: Dict,
        tenant_id: Optional[int] = None
    ) -> EmployeePayment:
        """
        Create an EmployeePayment record from payroll calculation.
        
        Args:
            payroll_calculation: Result from compute_comprehensive_payroll
            tenant_id: Tenant ID for multi-tenant support
            
        Returns:
            Created EmployeePayment record
        """
        earnings = payroll_calculation['earnings_breakdown']
        deductions = payroll_calculation['deductions_breakdown']
        
        # Create EmployeePayment record
        payment = EmployeePayment(
            employee_id=payroll_calculation['staff_id'],
            pay_period_start=payroll_calculation['pay_period_start'],
            pay_period_end=payroll_calculation['pay_period_end'],
            gross_amount=payroll_calculation['gross_pay'],
            net_amount=payroll_calculation['net_pay'],
            
            # Hours information
            regular_hours=payroll_calculation['hours_breakdown'].regular_hours,
            overtime_hours=payroll_calculation['hours_breakdown'].overtime_hours,
            
            # Earnings breakdown
            regular_pay=earnings.regular_pay,
            overtime_pay=earnings.overtime_pay,
            bonus_pay=earnings.bonus,
            commission_pay=earnings.commission,
            
            # Tax deductions
            federal_tax_amount=deductions.federal_tax,
            state_tax_amount=deductions.state_tax,
            local_tax_amount=deductions.local_tax,
            social_security_amount=deductions.social_security,
            medicare_amount=deductions.medicare,
            
            # Benefit deductions
            health_insurance_amount=deductions.health_insurance,
            retirement_amount=deductions.retirement_contribution,
            other_deductions_amount=(
                deductions.dental_insurance + deductions.parking_fee +
                deductions.garnishments + deductions.loan_repayments
            ),
            
            tenant_id=tenant_id,
            processed_at=datetime.utcnow()
        )
        
        self.db.add(payment)
        self.db.commit()
        self.db.refresh(payment)
        
        return payment