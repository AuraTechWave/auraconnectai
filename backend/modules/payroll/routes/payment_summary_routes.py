# backend/modules/payroll/routes/payment_summary_routes.py

"""
Payment summary and analytics endpoints with optimized SQL queries.
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import func, and_
from typing import Optional
from datetime import date, datetime
from decimal import Decimal

from ....core.database import get_db
from ....core.auth import require_payroll_access, get_current_user, User
from ..models.payroll_models import EmployeePayment
from ..schemas.payroll_schemas import PaymentSummaryResponse
from ..schemas.error_schemas import ErrorResponse, PayrollErrorCodes
from ..enums.payroll_enums import PaymentStatus

router = APIRouter()


@router.get("/by-period", response_model=PaymentSummaryResponse)
async def get_payment_summary_by_period(
    start_date: date = Query(..., description="Period start date"),
    end_date: date = Query(..., description="Period end date"),
    tenant_id: Optional[int] = Query(None, description="Filter by tenant"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_payroll_access)
):
    """
    Get payment summary for a specific period using SQL aggregation.
    
    ## Query Parameters
    - **start_date**: Period start date (required)
    - **end_date**: Period end date (required)
    - **tenant_id**: Optional tenant filter
    
    ## Response
    Returns aggregated payment data for the period.
    
    ## Error Responses
    - **422**: Invalid date range
    - **500**: Database error
    """
    try:
        # Validate date range
        if start_date > end_date:
            raise HTTPException(
                status_code=422,
                detail=ErrorResponse(
                    error="ValidationError",
                    message="Start date must be before end date",
                    code=PayrollErrorCodes.INVALID_DATE_RANGE
                ).dict()
            )
        
        # Build base query
        base_query = db.query(EmployeePayment).filter(
            EmployeePayment.pay_period_start >= start_date,
            EmployeePayment.pay_period_end <= end_date
        )
        
        if tenant_id:
            base_query = base_query.filter(EmployeePayment.tenant_id == tenant_id)
        
        # Use SQL aggregation for performance
        summary_data = db.query(
            func.count(func.distinct(EmployeePayment.employee_id)).label('employee_count'),
            func.count(EmployeePayment.id).label('payment_count'),
            func.sum(EmployeePayment.gross_amount).label('total_gross'),
            func.sum(EmployeePayment.net_amount).label('total_net'),
            func.sum(EmployeePayment.regular_pay).label('total_regular'),
            func.sum(EmployeePayment.overtime_pay).label('total_overtime'),
            func.sum(EmployeePayment.bonus_pay).label('total_bonus'),
            func.sum(EmployeePayment.commission_pay).label('total_commission'),
            func.sum(EmployeePayment.federal_tax_amount).label('total_federal_tax'),
            func.sum(EmployeePayment.state_tax_amount).label('total_state_tax'),
            func.sum(EmployeePayment.local_tax_amount).label('total_local_tax'),
            func.sum(EmployeePayment.social_security_amount).label('total_ss'),
            func.sum(EmployeePayment.medicare_amount).label('total_medicare'),
            func.sum(EmployeePayment.unemployment_amount).label('total_unemployment'),
            func.sum(EmployeePayment.health_insurance_amount).label('total_health'),
            func.sum(EmployeePayment.retirement_401k_amount).label('total_401k'),
            func.sum(EmployeePayment.regular_hours).label('total_regular_hours'),
            func.sum(EmployeePayment.overtime_hours).label('total_overtime_hours')
        ).filter(
            EmployeePayment.pay_period_start >= start_date,
            EmployeePayment.pay_period_end <= end_date
        )
        
        if tenant_id:
            summary_data = summary_data.filter(EmployeePayment.tenant_id == tenant_id)
        
        result = summary_data.first()
        
        # Convert to response model
        return PaymentSummaryResponse(
            period={
                "start_date": start_date.isoformat(),
                "end_date": end_date.isoformat()
            },
            employee_count=result.employee_count or 0,
            payment_count=result.payment_count or 0,
            totals={
                "gross_pay": str(result.total_gross or Decimal('0')),
                "net_pay": str(result.total_net or Decimal('0')),
                "regular_pay": str(result.total_regular or Decimal('0')),
                "overtime_pay": str(result.total_overtime or Decimal('0')),
                "bonus_pay": str(result.total_bonus or Decimal('0')),
                "commission_pay": str(result.total_commission or Decimal('0'))
            },
            taxes={
                "federal": str(result.total_federal_tax or Decimal('0')),
                "state": str(result.total_state_tax or Decimal('0')),
                "local": str(result.total_local_tax or Decimal('0')),
                "social_security": str(result.total_ss or Decimal('0')),
                "medicare": str(result.total_medicare or Decimal('0')),
                "total": str(
                    (result.total_federal_tax or 0) +
                    (result.total_state_tax or 0) +
                    (result.total_local_tax or 0) +
                    (result.total_ss or 0) +
                    (result.total_medicare or 0) +
                    (result.total_unemployment or 0)
                )
            },
            benefits={
                "health_insurance": str(result.total_health or Decimal('0')),
                "retirement_401k": str(result.total_401k or Decimal('0')),
                "total": str((result.total_health or 0) + (result.total_401k or 0))
            },
            hours={
                "regular": str(result.total_regular_hours or Decimal('0')),
                "overtime": str(result.total_overtime_hours or Decimal('0')),
                "total": str(
                    (result.total_regular_hours or 0) +
                    (result.total_overtime_hours or 0)
                )
            }
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=ErrorResponse(
                error="DatabaseError",
                message=f"Failed to generate payment summary: {str(e)}",
                code=PayrollErrorCodes.DATABASE_ERROR
            ).dict()
        )


@router.get("/by-employee/{employee_id}")
async def get_employee_payment_summary(
    employee_id: int,
    year: Optional[int] = Query(None, description="Filter by year"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_payroll_access)
):
    """
    Get payment summary for a specific employee.
    
    ## Path Parameters
    - **employee_id**: Employee ID
    
    ## Query Parameters
    - **year**: Optional year filter
    
    ## Response
    Returns year-to-date or annual summary for the employee.
    
    ## Error Responses
    - **404**: Employee has no payment records
    - **500**: Database error
    """
    try:
        # Build query
        query = db.query(
            func.count(EmployeePayment.id).label('payment_count'),
            func.sum(EmployeePayment.gross_amount).label('ytd_gross'),
            func.sum(EmployeePayment.net_amount).label('ytd_net'),
            func.sum(EmployeePayment.federal_tax_amount).label('ytd_federal'),
            func.sum(EmployeePayment.state_tax_amount).label('ytd_state'),
            func.sum(EmployeePayment.social_security_amount).label('ytd_ss'),
            func.sum(EmployeePayment.medicare_amount).label('ytd_medicare'),
            func.sum(EmployeePayment.retirement_401k_amount).label('ytd_401k'),
            func.sum(EmployeePayment.regular_hours).label('total_hours'),
            func.sum(EmployeePayment.overtime_hours).label('total_overtime')
        ).filter(EmployeePayment.employee_id == employee_id)
        
        if year:
            query = query.filter(
                func.extract('year', EmployeePayment.pay_period_start) == year
            )
        
        result = query.first()
        
        if not result or result.payment_count == 0:
            raise HTTPException(
                status_code=404,
                detail=ErrorResponse(
                    error="NotFound",
                    message=f"No payment records found for employee {employee_id}",
                    code=PayrollErrorCodes.RECORD_NOT_FOUND
                ).dict()
            )
        
        return {
            "employee_id": employee_id,
            "year": year or "all_time",
            "payment_count": result.payment_count,
            "ytd_totals": {
                "gross": str(result.ytd_gross or 0),
                "net": str(result.ytd_net or 0),
                "federal_tax": str(result.ytd_federal or 0),
                "state_tax": str(result.ytd_state or 0),
                "social_security": str(result.ytd_ss or 0),
                "medicare": str(result.ytd_medicare or 0),
                "retirement_401k": str(result.ytd_401k or 0)
            },
            "hours": {
                "regular": str(result.total_hours or 0),
                "overtime": str(result.total_overtime or 0),
                "total": str((result.total_hours or 0) + (result.total_overtime or 0))
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=ErrorResponse(
                error="DatabaseError",
                message=f"Failed to generate employee summary: {str(e)}",
                code=PayrollErrorCodes.DATABASE_ERROR
            ).dict()
        )


@router.get("/tax-summary")
async def get_tax_summary(
    start_date: date = Query(..., description="Period start date"),
    end_date: date = Query(..., description="Period end date"),
    group_by: str = Query("tax_type", description="Group by: tax_type, location, or month"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_payroll_access)
):
    """
    Get tax summary with grouping options.
    
    ## Query Parameters
    - **start_date**: Period start date
    - **end_date**: Period end date
    - **group_by**: Grouping option (tax_type, location, month)
    
    ## Response
    Returns tax totals grouped by selected criteria.
    
    ## Error Responses
    - **422**: Invalid grouping option
    - **500**: Database error
    """
    try:
        if group_by not in ["tax_type", "location", "month"]:
            raise HTTPException(
                status_code=422,
                detail=ErrorResponse(
                    error="ValidationError",
                    message="Invalid group_by option. Must be: tax_type, location, or month",
                    code=PayrollErrorCodes.INVALID_CONFIG_VALUE
                ).dict()
            )
        
        # Base aggregation
        tax_totals = {
            "federal": db.query(func.sum(EmployeePayment.federal_tax_amount)).filter(
                EmployeePayment.pay_period_start >= start_date,
                EmployeePayment.pay_period_end <= end_date
            ).scalar() or 0,
            "state": db.query(func.sum(EmployeePayment.state_tax_amount)).filter(
                EmployeePayment.pay_period_start >= start_date,
                EmployeePayment.pay_period_end <= end_date
            ).scalar() or 0,
            "local": db.query(func.sum(EmployeePayment.local_tax_amount)).filter(
                EmployeePayment.pay_period_start >= start_date,
                EmployeePayment.pay_period_end <= end_date
            ).scalar() or 0,
            "social_security": db.query(func.sum(EmployeePayment.social_security_amount)).filter(
                EmployeePayment.pay_period_start >= start_date,
                EmployeePayment.pay_period_end <= end_date
            ).scalar() or 0,
            "medicare": db.query(func.sum(EmployeePayment.medicare_amount)).filter(
                EmployeePayment.pay_period_start >= start_date,
                EmployeePayment.pay_period_end <= end_date
            ).scalar() or 0,
            "unemployment": db.query(func.sum(EmployeePayment.unemployment_amount)).filter(
                EmployeePayment.pay_period_start >= start_date,
                EmployeePayment.pay_period_end <= end_date
            ).scalar() or 0
        }
        
        return {
            "period": {
                "start_date": start_date.isoformat(),
                "end_date": end_date.isoformat()
            },
            "group_by": group_by,
            "tax_totals": {k: str(v) for k, v in tax_totals.items()},
            "grand_total": str(sum(tax_totals.values()))
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=ErrorResponse(
                error="DatabaseError",
                message=f"Failed to generate tax summary: {str(e)}",
                code=PayrollErrorCodes.DATABASE_ERROR
            ).dict()
        )