# backend/modules/payroll/routes/payment_history_routes.py

"""
Payment history and details endpoints with optimized queries.
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import List, Optional
from datetime import date, datetime
from decimal import Decimal

from ....core.database import get_db
from ....core.auth import require_payroll_access, get_current_user, User
from ..models.payroll_models import EmployeePayment, EmployeePaymentTaxApplication
from ..schemas.payroll_schemas import (
    PaymentHistoryResponse,
    PaymentDetailResponse,
    PaymentHistoryItem
)
from ..schemas.error_schemas import ErrorResponse, PayrollErrorCodes
from ..exceptions import PayrollNotFoundError
from ..enums.payroll_enums import PaymentStatus

router = APIRouter()


@router.get("/{employee_id}", response_model=PaymentHistoryResponse)
async def get_employee_payment_history(
    employee_id: int,
    start_date: Optional[date] = Query(None, description="Start date filter"),
    end_date: Optional[date] = Query(None, description="End date filter"),
    status: Optional[PaymentStatus] = Query(None, description="Payment status filter"),
    limit: int = Query(50, ge=1, le=100, description="Maximum records to return"),
    offset: int = Query(0, ge=0, description="Number of records to skip"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_payroll_access)
):
    """
    Get payment history for an employee with pagination.
    
    ## Path Parameters
    - **employee_id**: Employee ID
    
    ## Query Parameters
    - **start_date**: Filter payments from this date
    - **end_date**: Filter payments to this date
    - **status**: Filter by payment status
    - **limit**: Maximum records to return (default: 50, max: 100)
    - **offset**: Number of records to skip for pagination
    
    ## Response
    Returns paginated payment history with summary statistics.
    
    ## Error Responses
    - **404**: Employee not found
    - **422**: Invalid query parameters
    """
    try:
        # Build base query
        query = db.query(EmployeePayment).filter(
            EmployeePayment.employee_id == employee_id
        )
        
        # Apply filters
        if start_date:
            query = query.filter(EmployeePayment.pay_period_start >= start_date)
        
        if end_date:
            query = query.filter(EmployeePayment.pay_period_end <= end_date)
        
        if status:
            query = query.filter(EmployeePayment.status == status)
        
        # Get total count
        total_count = query.count()
        
        # Get summary statistics using SQL aggregation
        summary_stats = db.query(
            func.sum(EmployeePayment.gross_amount).label('total_gross'),
            func.sum(EmployeePayment.net_amount).label('total_net'),
            func.avg(EmployeePayment.gross_amount).label('avg_gross'),
            func.avg(EmployeePayment.net_amount).label('avg_net')
        ).filter(
            EmployeePayment.employee_id == employee_id
        )
        
        if start_date:
            summary_stats = summary_stats.filter(EmployeePayment.pay_period_start >= start_date)
        if end_date:
            summary_stats = summary_stats.filter(EmployeePayment.pay_period_end <= end_date)
        if status:
            summary_stats = summary_stats.filter(EmployeePayment.status == status)
        
        stats = summary_stats.first()
        
        # Get paginated payments
        payments = query.order_by(
            EmployeePayment.pay_period_end.desc()
        ).limit(limit).offset(offset).all()
        
        # Convert to response model
        payment_items = [
            PaymentHistoryItem(
                id=p.id,
                pay_period_start=p.pay_period_start,
                pay_period_end=p.pay_period_end,
                gross_amount=p.gross_amount,
                net_amount=p.net_amount,
                regular_hours=p.regular_hours,
                overtime_hours=p.overtime_hours,
                status=p.status,
                processed_at=p.processed_at,
                paid_at=p.paid_at
            )
            for p in payments
        ]
        
        return PaymentHistoryResponse(
            employee_id=employee_id,
            total_count=total_count,
            limit=limit,
            offset=offset,
            summary={
                "total_gross": str(stats.total_gross or 0),
                "total_net": str(stats.total_net or 0),
                "total_deductions": str((stats.total_gross or 0) - (stats.total_net or 0)),
                "average_gross": str(stats.avg_gross or 0),
                "average_net": str(stats.avg_net or 0),
                "payment_count": total_count
            },
            payments=payment_items
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=ErrorResponse(
                error="DatabaseError",
                message=f"Failed to retrieve payment history: {str(e)}",
                code=PayrollErrorCodes.DATABASE_ERROR
            ).dict()
        )


@router.get("/details/{payment_id}", response_model=PaymentDetailResponse)
async def get_payment_details(
    payment_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_payroll_access)
):
    """
    Get detailed information for a specific payment.
    
    ## Path Parameters
    - **payment_id**: Payment record ID
    
    ## Response
    Returns complete payment details with structured breakdown.
    
    ## Error Responses
    - **404**: Payment not found
    """
    try:
        payment = db.query(EmployeePayment).filter(
            EmployeePayment.id == payment_id
        ).first()
        
        if not payment:
            raise PayrollNotFoundError("Payment", payment_id)
        
        # Get tax applications
        tax_applications = db.query(EmployeePaymentTaxApplication).filter(
            EmployeePaymentTaxApplication.employee_payment_id == payment_id
        ).all()
        
        # Build response using Pydantic model
        return PaymentDetailResponse(
            id=payment.id,
            employee_id=payment.employee_id,
            pay_period_start=payment.pay_period_start,
            pay_period_end=payment.pay_period_end,
            hours={
                "regular": str(payment.regular_hours),
                "overtime": str(payment.overtime_hours),
                "double_time": str(payment.double_time_hours),
                "holiday": str(payment.holiday_hours),
                "sick": str(payment.sick_hours),
                "vacation": str(payment.vacation_hours),
                "total": str(
                    payment.regular_hours + payment.overtime_hours + 
                    payment.double_time_hours + payment.holiday_hours +
                    payment.sick_hours + payment.vacation_hours
                )
            },
            earnings={
                "regular_pay": str(payment.regular_pay),
                "overtime_pay": str(payment.overtime_pay),
                "double_time_pay": str(payment.double_time_pay),
                "holiday_pay": str(payment.holiday_pay),
                "sick_pay": str(payment.sick_pay),
                "vacation_pay": str(payment.vacation_pay),
                "bonus_pay": str(payment.bonus_pay),
                "commission_pay": str(payment.commission_pay),
                "other_earnings": str(payment.other_earnings),
                "gross_amount": str(payment.gross_amount)
            },
            deductions={
                "taxes": {
                    "federal": str(payment.federal_tax_amount),
                    "state": str(payment.state_tax_amount),
                    "local": str(payment.local_tax_amount),
                    "social_security": str(payment.social_security_amount),
                    "medicare": str(payment.medicare_amount),
                    "unemployment": str(payment.unemployment_amount),
                    "total": str(
                        payment.federal_tax_amount + payment.state_tax_amount +
                        payment.local_tax_amount + payment.social_security_amount +
                        payment.medicare_amount + payment.unemployment_amount
                    )
                },
                "benefits": {
                    "health_insurance": str(payment.health_insurance_amount),
                    "dental_insurance": str(payment.dental_insurance_amount),
                    "vision_insurance": str(payment.vision_insurance_amount),
                    "retirement_401k": str(payment.retirement_401k_amount),
                    "life_insurance": str(payment.life_insurance_amount),
                    "disability_insurance": str(payment.disability_insurance_amount),
                    "parking_fee": str(payment.parking_fee_amount),
                    "total": str(
                        payment.health_insurance_amount + payment.dental_insurance_amount +
                        payment.vision_insurance_amount + payment.retirement_401k_amount +
                        payment.life_insurance_amount + payment.disability_insurance_amount +
                        payment.parking_fee_amount
                    )
                },
                "other": {
                    "garnishments": str(payment.garnishment_amount),
                    "loan_repayments": str(payment.loan_repayment_amount),
                    "other": str(payment.other_deductions),
                    "total": str(
                        payment.garnishment_amount + payment.loan_repayment_amount +
                        payment.other_deductions
                    )
                }
            },
            net_amount=str(payment.net_amount),
            payment_info={
                "status": payment.status.value,
                "method": payment.payment_method,
                "reference": payment.payment_reference,
                "processed_at": payment.processed_at.isoformat() if payment.processed_at else None,
                "paid_at": payment.paid_at.isoformat() if payment.paid_at else None
            },
            tax_applications=[
                {
                    "tax_rule_id": ta.tax_rule_id,
                    "tax_type": ta.tax_type.value,
                    "rate": str(ta.rate),
                    "employee_amount": str(ta.employee_amount),
                    "employer_amount": str(ta.employer_amount),
                    "location": ta.location
                }
                for ta in tax_applications
            ],
            metadata={
                "tenant_id": payment.tenant_id,
                "created_at": payment.created_at.isoformat(),
                "updated_at": payment.updated_at.isoformat()
            }
        )
        
    except PayrollNotFoundError:
        raise HTTPException(
            status_code=404,
            detail=ErrorResponse(
                error="NotFound",
                message=f"Payment with ID {payment_id} not found",
                code=PayrollErrorCodes.RECORD_NOT_FOUND
            ).dict()
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=ErrorResponse(
                error="DatabaseError",
                message=f"Failed to retrieve payment details: {str(e)}",
                code=PayrollErrorCodes.DATABASE_ERROR
            ).dict()
        )