# backend/modules/payroll/services/batch_payroll_service.py

"""
Batch payroll processing service.

Handles batch processing of payroll calculations with
error handling and progress tracking.
"""

from typing import List, Optional, Dict, Any
from datetime import date
from decimal import Decimal
import logging
from sqlalchemy.orm import Session

from ..schemas.batch_processing_schemas import (
    EmployeePayrollResult,
    CalculationOptions
)
from .payroll_service import PayrollService
from ....staff.models.staff import Staff
from ....staff.models.timesheet import Timesheet
from ..models.employee_payment import EmployeePayment

logger = logging.getLogger(__name__)


class BatchPayrollService:
    """Service for batch payroll processing."""
    
    def __init__(self, db: Session):
        """Initialize batch payroll service.
        
        Args:
            db: Database session
        """
        self.db = db
        self.payroll_service = PayrollService(db)
    
    async def process_batch(
        self,
        employee_ids: Optional[List[int]],
        pay_period_start: date,
        pay_period_end: date,
        calculation_options: Optional[CalculationOptions] = None
    ) -> List[EmployeePayrollResult]:
        """Process payroll for multiple employees in batch.
        
        Args:
            employee_ids: List of employee IDs or None for all
            pay_period_start: Start of pay period
            pay_period_end: End of pay period
            calculation_options: Optional calculation settings
            
        Returns:
            List of employee payroll results
        """
        results = []
        options = calculation_options or CalculationOptions()
        
        # Get employees to process
        if employee_ids:
            employees = self.db.query(Staff).filter(
                Staff.id.in_(employee_ids),
                Staff.status == 'active'
            ).all()
        else:
            employees = self.db.query(Staff).filter(
                Staff.status == 'active'
            ).all()
        
        # Process each employee
        for employee in employees:
            result = await self._process_employee(
                employee=employee,
                pay_period_start=pay_period_start,
                pay_period_end=pay_period_end,
                options=options
            )
            results.append(result)
        
        return results
    
    async def _process_employee(
        self,
        employee: Staff,
        pay_period_start: date,
        pay_period_end: date,
        options: CalculationOptions
    ) -> EmployeePayrollResult:
        """Process payroll for a single employee.
        
        Args:
            employee: Employee to process
            pay_period_start: Start of pay period
            pay_period_end: End of pay period
            options: Calculation options
            
        Returns:
            Employee payroll result
        """
        import time
        start_time = time.time()
        
        try:
            # Check if payroll already exists
            if not options.force_recalculate:
                existing_payment = self.db.query(EmployeePayment).filter(
                    EmployeePayment.employee_id == employee.id,
                    EmployeePayment.pay_period_start == pay_period_start,
                    EmployeePayment.pay_period_end == pay_period_end
                ).first()
                
                if existing_payment:
                    return EmployeePayrollResult(
                        employee_id=employee.id,
                        employee_name=f"{employee.first_name} {employee.last_name}",
                        success=True,
                        gross_amount=existing_payment.gross_amount,
                        net_amount=existing_payment.net_amount,
                        total_deductions=existing_payment.total_deductions,
                        payment_id=existing_payment.id,
                        error_message=None,
                        processing_time=time.time() - start_time
                    )
            
            # Calculate payroll
            payment = await self.payroll_service.calculate_employee_payroll(
                employee_id=employee.id,
                pay_period_start=pay_period_start,
                pay_period_end=pay_period_end,
                include_bonuses=options.include_bonuses,
                include_commissions=options.include_commissions,
                include_overtime=options.include_overtime,
                include_deductions=options.include_deductions
            )
            
            # Save payment record
            self.db.add(payment)
            self.db.commit()
            
            return EmployeePayrollResult(
                employee_id=employee.id,
                employee_name=f"{employee.first_name} {employee.last_name}",
                success=True,
                gross_amount=payment.gross_amount,
                net_amount=payment.net_amount,
                total_deductions=payment.total_deductions,
                payment_id=payment.id,
                error_message=None,
                processing_time=time.time() - start_time
            )
            
        except Exception as e:
            logger.error(f"Error processing payroll for employee {employee.id}: {str(e)}")
            
            return EmployeePayrollResult(
                employee_id=employee.id,
                employee_name=f"{employee.first_name} {employee.last_name}",
                success=False,
                gross_amount=Decimal('0.00'),
                net_amount=Decimal('0.00'),
                total_deductions=Decimal('0.00'),
                payment_id=None,
                error_message=str(e),
                processing_time=time.time() - start_time
            )
    
    def get_batch_statistics(
        self,
        results: List[EmployeePayrollResult]
    ) -> Dict[str, Any]:
        """Calculate statistics from batch results.
        
        Args:
            results: List of employee payroll results
            
        Returns:
            Dictionary of statistics
        """
        successful = [r for r in results if r.success]
        failed = [r for r in results if not r.success]
        
        total_gross = sum(r.gross_amount for r in successful)
        total_net = sum(r.net_amount for r in successful)
        total_deductions = sum(r.total_deductions for r in successful)
        avg_processing_time = sum(r.processing_time for r in results) / len(results) if results else 0
        
        return {
            "total_processed": len(results),
            "successful_count": len(successful),
            "failed_count": len(failed),
            "total_gross_pay": total_gross,
            "total_net_pay": total_net,
            "total_deductions": total_deductions,
            "average_processing_time": avg_processing_time,
            "success_rate": len(successful) / len(results) * 100 if results else 0
        }
    
    def validate_batch_request(
        self,
        employee_ids: Optional[List[int]],
        pay_period_start: date,
        pay_period_end: date
    ) -> Dict[str, Any]:
        """Validate batch payroll request.
        
        Args:
            employee_ids: List of employee IDs or None
            pay_period_start: Start of pay period
            pay_period_end: End of pay period
            
        Returns:
            Validation results
        """
        validation_results = {
            "valid": True,
            "errors": [],
            "warnings": [],
            "employee_count": 0
        }
        
        # Validate date range
        if pay_period_start >= pay_period_end:
            validation_results["valid"] = False
            validation_results["errors"].append(
                "Pay period end must be after pay period start"
            )
        
        # Validate employees
        if employee_ids:
            # Check for duplicates
            if len(set(employee_ids)) != len(employee_ids):
                validation_results["valid"] = False
                validation_results["errors"].append(
                    "Employee ID list contains duplicates"
                )
            
            # Check if employees exist
            existing_ids = self.db.query(Staff.id).filter(
                Staff.id.in_(employee_ids)
            ).all()
            existing_ids = {id[0] for id in existing_ids}
            
            missing_ids = set(employee_ids) - existing_ids
            if missing_ids:
                validation_results["warnings"].append(
                    f"Following employee IDs not found: {list(missing_ids)}"
                )
            
            validation_results["employee_count"] = len(existing_ids)
        else:
            # Count all active employees
            count = self.db.query(Staff).filter(
                Staff.status == 'active'
            ).count()
            validation_results["employee_count"] = count
        
        return validation_results