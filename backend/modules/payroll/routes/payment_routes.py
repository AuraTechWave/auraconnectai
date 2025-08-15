# backend/modules/payroll/routes/payment_routes.py

"""
Employee payment management API endpoints - Optimized version.

Main router that aggregates all payment sub-routes:
- Payment history and details
- Payment summaries and analytics
- Payment export functionality
- Payment status management
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import Optional
from datetime import datetime

from core.database import get_db
from core.auth import require_payroll_write, get_current_user, User
from ..models.payroll_models import EmployeePayment
from ..schemas.payroll_schemas import PaymentStatusUpdate
from ..schemas.error_schemas import ErrorResponse, PayrollErrorCodes
from ..exceptions import PayrollNotFoundError
from ..enums.payroll_enums import PaymentStatus

# Import sub-routers
from .payment_history_routes import router as history_router
from .payment_summary_routes import router as summary_router
from .payment_export_routes import router as export_router

router = APIRouter()

# Include sub-routers
router.include_router(history_router, prefix="/history", tags=["Payment History"])
router.include_router(summary_router, prefix="/summary", tags=["Payment Summary"])
router.include_router(export_router, prefix="/export", tags=["Payment Export"])


# Core payment status management endpoints


@router.put("/{payment_id}/status")
async def update_payment_status(
    payment_id: int,
    status_update: PaymentStatusUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_payroll_write),
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
    Returns updated payment status information.

    ## Error Responses
    - **404**: Payment not found
    - **400**: Invalid status transition
    """
    try:
        payment = (
            db.query(EmployeePayment).filter(EmployeePayment.id == payment_id).first()
        )

        if not payment:
            raise PayrollNotFoundError("Payment", payment_id)

        # Validate status transition
        if (
            payment.status == PaymentStatus.PAID
            and status_update.status != PaymentStatus.PAID
        ):
            raise HTTPException(
                status_code=400,
                detail=ErrorResponse(
                    error="InvalidTransition",
                    message="Cannot change status of a paid payment",
                    code=PayrollErrorCodes.PAYMENT_ALREADY_PROCESSED,
                ).dict(),
            )

        # Update status
        payment.status = status_update.status

        # Update payment info if transitioning to paid
        if status_update.status == PaymentStatus.PAID:
            payment.paid_at = datetime.utcnow()
            payment.payment_method = status_update.payment_method
            payment.payment_reference = status_update.payment_reference

        payment.updated_at = datetime.utcnow()

        db.commit()
        db.refresh(payment)

        return {
            "id": payment.id,
            "status": payment.status.value,
            "paid_at": payment.paid_at.isoformat() if payment.paid_at else None,
            "payment_method": payment.payment_method,
            "payment_reference": payment.payment_reference,
            "updated_at": payment.updated_at.isoformat(),
        }

    except PayrollNotFoundError:
        raise HTTPException(
            status_code=404,
            detail=ErrorResponse(
                error="NotFound",
                message=f"Payment with ID {payment_id} not found",
                code=PayrollErrorCodes.RECORD_NOT_FOUND,
            ).dict(),
        )
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail=ErrorResponse(
                error="DatabaseError",
                message=f"Failed to update payment status: {str(e)}",
                code=PayrollErrorCodes.DATABASE_ERROR,
            ).dict(),
        )


@router.post("/{payment_id}/void")
async def void_payment(
    payment_id: int,
    reason: str = Query(..., description="Reason for voiding payment"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_payroll_write),
):
    """
    Void a payment.

    ## Path Parameters
    - **payment_id**: Payment record ID

    ## Query Parameters
    - **reason**: Reason for voiding (required)

    ## Response
    Returns voided payment information.

    ## Error Responses
    - **404**: Payment not found
    - **400**: Cannot void paid payment
    """
    try:
        payment = (
            db.query(EmployeePayment).filter(EmployeePayment.id == payment_id).first()
        )

        if not payment:
            raise PayrollNotFoundError("Payment", payment_id)

        if payment.status == PaymentStatus.PAID:
            raise HTTPException(
                status_code=400,
                detail=ErrorResponse(
                    error="InvalidOperation",
                    message="Cannot void a paid payment. Use reversal instead.",
                    code=PayrollErrorCodes.PAYMENT_ALREADY_PROCESSED,
                ).dict(),
            )

        # Void the payment
        payment.status = PaymentStatus.VOIDED
        payment.updated_at = datetime.utcnow()

        # Store void reason in metadata (would need to add this field)
        # payment.metadata = {"void_reason": reason, "voided_by": current_user.id}

        db.commit()

        return {
            "id": payment.id,
            "status": payment.status.value,
            "void_reason": reason,
            "voided_at": datetime.utcnow().isoformat(),
            "voided_by": current_user.email,
        }

    except (PayrollNotFoundError, HTTPException):
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail=ErrorResponse(
                error="DatabaseError",
                message=f"Failed to void payment: {str(e)}",
                code=PayrollErrorCodes.DATABASE_ERROR,
            ).dict(),
        )
