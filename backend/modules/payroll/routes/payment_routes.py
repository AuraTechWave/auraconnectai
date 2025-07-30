# backend/modules/payroll/routes/payment_routes.py

"""
Employee payment management API endpoints.

Provides endpoints for managing employee payment records:
- View payment history
- Get payment details
- Export payment data
- Payment analytics
"""

from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import date, datetime
from decimal import Decimal

from ....core.database import get_db
from ....core.auth import require_payroll_access, require_payroll_write, get_current_user, User
from ..models.payroll_models import EmployeePayment, EmployeePaymentTaxApplication
from ..enums.payroll_enums import PaymentStatus

router = APIRouter()


@router.get("/history/{employee_id}")
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
    Get payment history for an employee.
    
    ## Path Parameters
    - **employee_id**: Employee ID
    
    ## Query Parameters
    - **start_date**: Filter payments from this date
    - **end_date**: Filter payments to this date
    - **status**: Filter by payment status
    - **limit**: Maximum records to return (default: 50, max: 100)
    - **offset**: Number of records to skip for pagination
    
    ## Response
    Returns list of employee payment records with summary.
    
    ## Authentication
    Requires payroll access permissions.
    """
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
    
    # Get total count for pagination
    total_count = query.count()
    
    # Get paginated results
    payments = query.order_by(
        EmployeePayment.pay_period_end.desc()
    ).limit(limit).offset(offset).all()
    
    # Calculate summary
    summary_query = query
    total_gross = sum(p.gross_amount for p in summary_query.all())
    total_net = sum(p.net_amount for p in summary_query.all())
    total_deductions = total_gross - total_net
    
    return {
        "employee_id": employee_id,
        "total_count": total_count,
        "limit": limit,
        "offset": offset,
        "summary": {
            "total_gross": str(total_gross),
            "total_net": str(total_net),
            "total_deductions": str(total_deductions),
            "payment_count": total_count
        },
        "payments": [
            {
                "id": p.id,
                "pay_period_start": p.pay_period_start.isoformat(),
                "pay_period_end": p.pay_period_end.isoformat(),
                "gross_amount": str(p.gross_amount),
                "net_amount": str(p.net_amount),
                "regular_hours": str(p.regular_hours),
                "overtime_hours": str(p.overtime_hours),
                "status": p.status.value,
                "processed_at": p.processed_at.isoformat() if p.processed_at else None,
                "paid_at": p.paid_at.isoformat() if p.paid_at else None
            }
            for p in payments
        ]
    }


@router.get("/{payment_id}")
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
    Returns complete payment details including:
    - Earnings breakdown
    - Deductions breakdown
    - Tax applications
    - Payment metadata
    
    ## Authentication
    Requires payroll access permissions.
    """
    payment = db.query(EmployeePayment).filter(
        EmployeePayment.id == payment_id
    ).first()
    
    if not payment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Payment with ID {payment_id} not found"
        )
    
    # Get tax applications
    tax_applications = db.query(EmployeePaymentTaxApplication).filter(
        EmployeePaymentTaxApplication.employee_payment_id == payment_id
    ).all()
    
    return {
        "id": payment.id,
        "employee_id": payment.employee_id,
        "pay_period_start": payment.pay_period_start.isoformat(),
        "pay_period_end": payment.pay_period_end.isoformat(),
        "hours": {
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
        "earnings": {
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
        "deductions": {
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
        "net_amount": str(payment.net_amount),
        "payment_info": {
            "status": payment.status.value,
            "method": payment.payment_method,
            "reference": payment.payment_reference,
            "processed_at": payment.processed_at.isoformat() if payment.processed_at else None,
            "paid_at": payment.paid_at.isoformat() if payment.paid_at else None
        },
        "tax_applications": [
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
        "metadata": {
            "tenant_id": payment.tenant_id,
            "created_at": payment.created_at.isoformat(),
            "updated_at": payment.updated_at.isoformat()
        }
    }


@router.get("/summary/by-period")
async def get_payment_summary_by_period(
    start_date: date = Query(..., description="Period start date"),
    end_date: date = Query(..., description="Period end date"),
    tenant_id: Optional[int] = Query(None, description="Filter by tenant"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_payroll_access)
):
    """
    Get payment summary for a specific period.
    
    ## Query Parameters
    - **start_date**: Period start date (required)
    - **end_date**: Period end date (required)
    - **tenant_id**: Optional tenant filter
    
    ## Response
    Returns aggregated payment data for the period.
    
    ## Authentication
    Requires payroll access permissions.
    """
    query = db.query(EmployeePayment).filter(
        EmployeePayment.pay_period_start >= start_date,
        EmployeePayment.pay_period_end <= end_date
    )
    
    if tenant_id:
        query = query.filter(EmployeePayment.tenant_id == tenant_id)
    
    payments = query.all()
    
    # Calculate aggregates
    total_employees = len(set(p.employee_id for p in payments))
    total_payments = len(payments)
    
    summary = {
        "period": {
            "start_date": start_date.isoformat(),
            "end_date": end_date.isoformat()
        },
        "employee_count": total_employees,
        "payment_count": total_payments,
        "totals": {
            "gross_pay": str(sum(p.gross_amount for p in payments)),
            "net_pay": str(sum(p.net_amount for p in payments)),
            "regular_pay": str(sum(p.regular_pay for p in payments)),
            "overtime_pay": str(sum(p.overtime_pay for p in payments)),
            "bonus_pay": str(sum(p.bonus_pay for p in payments)),
            "commission_pay": str(sum(p.commission_pay for p in payments))
        },
        "taxes": {
            "federal": str(sum(p.federal_tax_amount for p in payments)),
            "state": str(sum(p.state_tax_amount for p in payments)),
            "local": str(sum(p.local_tax_amount for p in payments)),
            "social_security": str(sum(p.social_security_amount for p in payments)),
            "medicare": str(sum(p.medicare_amount for p in payments)),
            "total": str(sum(
                p.federal_tax_amount + p.state_tax_amount + p.local_tax_amount +
                p.social_security_amount + p.medicare_amount + p.unemployment_amount
                for p in payments
            ))
        },
        "benefits": {
            "health_insurance": str(sum(p.health_insurance_amount for p in payments)),
            "retirement_401k": str(sum(p.retirement_401k_amount for p in payments)),
            "total": str(sum(
                p.health_insurance_amount + p.dental_insurance_amount +
                p.vision_insurance_amount + p.retirement_401k_amount +
                p.life_insurance_amount + p.disability_insurance_amount
                for p in payments
            ))
        },
        "hours": {
            "regular": str(sum(p.regular_hours for p in payments)),
            "overtime": str(sum(p.overtime_hours for p in payments)),
            "total": str(sum(
                p.regular_hours + p.overtime_hours + p.double_time_hours +
                p.holiday_hours + p.sick_hours + p.vacation_hours
                for p in payments
            ))
        }
    }
    
    return summary


@router.post("/export")
async def export_payment_data(
    export_request: dict,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_payroll_write)
):
    """
    Export payment data in various formats.
    
    ## Request Body
    - **start_date**: Export period start
    - **end_date**: Export period end
    - **employee_ids**: Optional list of employee IDs
    - **format**: Export format (csv, excel, pdf)
    - **include_details**: Include detailed breakdown
    
    ## Response
    Returns export file information or download link.
    
    ## Authentication
    Requires payroll write permissions.
    """
    # This would typically generate an export file and return a download link
    # For now, returning a mock response
    
    return {
        "status": "success",
        "message": "Export request received",
        "export_id": str(datetime.utcnow().timestamp()),
        "format": export_request.get("format", "csv"),
        "record_count": 0,
        "download_url": f"/api/payroll/payments/export/download/{datetime.utcnow().timestamp()}"
    }


@router.put("/{payment_id}/status")
async def update_payment_status(
    payment_id: int,
    status_update: dict,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_payroll_write)
):
    """
    Update payment status.
    
    ## Path Parameters
    - **payment_id**: Payment record ID
    
    ## Request Body
    - **status**: New payment status
    - **payment_method**: Payment method (if paid)
    - **payment_reference**: Payment reference number
    - **notes**: Optional notes
    
    ## Response
    Returns updated payment record.
    
    ## Authentication
    Requires payroll write permissions.
    """
    payment = db.query(EmployeePayment).filter(
        EmployeePayment.id == payment_id
    ).first()
    
    if not payment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Payment with ID {payment_id} not found"
        )
    
    try:
        # Update status
        new_status = PaymentStatus(status_update["status"])
        payment.status = new_status
        
        # Update payment info if transitioning to paid
        if new_status == PaymentStatus.PAID:
            payment.paid_at = datetime.utcnow()
            payment.payment_method = status_update.get("payment_method")
            payment.payment_reference = status_update.get("payment_reference")
        
        payment.updated_at = datetime.utcnow()
        
        db.commit()
        db.refresh(payment)
        
        return {
            "id": payment.id,
            "status": payment.status.value,
            "paid_at": payment.paid_at.isoformat() if payment.paid_at else None,
            "payment_method": payment.payment_method,
            "payment_reference": payment.payment_reference,
            "updated_at": payment.updated_at.isoformat()
        }
        
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid status value: {str(e)}"
        )
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update payment status: {str(e)}"
        )