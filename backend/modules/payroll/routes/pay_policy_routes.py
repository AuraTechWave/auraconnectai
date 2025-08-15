# backend/modules/payroll/routes/pay_policy_routes.py

"""
Staff pay policy management endpoints.
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import List, Optional, Dict, Any
from datetime import datetime
from decimal import Decimal

from core.database import get_db
from core.auth import require_payroll_write, get_current_user, User
from ..services.payroll_configuration_service import PayrollConfigurationService
from ..models.payroll_configuration import StaffPayPolicy
from ..schemas.payroll_schemas import StaffPayPolicyResponse, StaffPayPolicyCreate
from ..schemas.error_schemas import ErrorResponse, PayrollErrorCodes
from ..exceptions import (
    PayrollNotFoundError,
    PayrollValidationError,
    PayrollBusinessRuleError,
)

router = APIRouter()


@router.get("", response_model=List[StaffPayPolicyResponse])
async def get_staff_pay_policies(
    staff_id: Optional[int] = Query(None, description="Filter by staff ID"),
    active_only: bool = Query(True, description="Only return active policies"),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_payroll_write),
):
    """
    Get staff pay policies with optional filtering.

    ## Query Parameters
    - **staff_id**: Optional staff ID filter
    - **active_only**: Only return active policies (default: true)
    - **limit**: Maximum records to return
    - **offset**: Records to skip for pagination

    ## Response
    Returns list of staff pay policies.

    ## Error Responses
    - **404**: Staff not found
    - **422**: Invalid query parameters
    """
    try:
        config_service = PayrollConfigurationService(db)

        if staff_id:
            policy = config_service.get_staff_pay_policy(staff_id)
            if not policy:
                raise PayrollNotFoundError("Staff pay policy", staff_id)
            return [policy] if not active_only or policy.is_active else []

        # Get all policies with pagination
        query = db.query(StaffPayPolicy)

        if active_only:
            query = query.filter(StaffPayPolicy.is_active == True)

        total = query.count()
        policies = query.offset(offset).limit(limit).all()

        return policies

    except PayrollNotFoundError:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=ErrorResponse(
                error="DatabaseError",
                message="Failed to retrieve pay policies",
                code=PayrollErrorCodes.DATABASE_ERROR,
            ).dict(),
        )


@router.post("", response_model=StaffPayPolicyResponse, status_code=201)
async def create_staff_pay_policy(
    policy_data: StaffPayPolicyCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_payroll_write),
):
    """
    Create a new staff pay policy.

    ## Request Body
    See StaffPayPolicyCreate schema for required fields.

    ## Response
    Returns the created pay policy.

    ## Error Responses
    - **400**: Business rule violation (e.g., duplicate policy)
    - **422**: Invalid input data
    """
    try:
        # Check if active policy already exists
        existing = (
            db.query(StaffPayPolicy)
            .filter(
                StaffPayPolicy.staff_id == policy_data.staff_id,
                StaffPayPolicy.is_active == True,
            )
            .first()
        )

        if existing:
            raise PayrollBusinessRuleError(
                f"Active pay policy already exists for staff {policy_data.staff_id}",
                "DUPLICATE_POLICY",
            )

        # Create new policy
        policy = StaffPayPolicy(
            **policy_data.dict(),
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )

        db.add(policy)
        db.commit()
        db.refresh(policy)

        return policy

    except PayrollBusinessRuleError:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=400,
            detail=ErrorResponse(
                error="CreationError",
                message=f"Failed to create pay policy: {str(e)}",
                code=PayrollErrorCodes.DATABASE_ERROR,
            ).dict(),
        )


@router.get("/{staff_id}", response_model=StaffPayPolicyResponse)
async def get_staff_pay_policy(
    staff_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_payroll_write),
):
    """
    Get active pay policy for a specific staff member.

    ## Path Parameters
    - **staff_id**: Staff member ID

    ## Response
    Returns the active pay policy.

    ## Error Responses
    - **404**: No active policy found
    """
    config_service = PayrollConfigurationService(db)
    policy = config_service.get_staff_pay_policy(staff_id)

    if not policy:
        raise HTTPException(
            status_code=404,
            detail=ErrorResponse(
                error="NotFound",
                message=f"No active pay policy found for staff ID {staff_id}",
                code=PayrollErrorCodes.NO_PAY_POLICY,
            ).dict(),
        )

    return policy


@router.put("/{staff_id}", response_model=StaffPayPolicyResponse)
async def update_staff_pay_policy(
    staff_id: int,
    policy_update: Dict[str, Any],
    db: Session = Depends(get_db),
    current_user: User = Depends(require_payroll_write),
):
    """
    Update an existing staff pay policy.

    ## Path Parameters
    - **staff_id**: Staff member ID

    ## Request Body
    Partial update - only include fields to update.

    ## Response
    Returns the updated pay policy.

    ## Error Responses
    - **404**: Policy not found
    - **422**: Invalid update data
    """
    try:
        policy = (
            db.query(StaffPayPolicy)
            .filter(
                StaffPayPolicy.staff_id == staff_id, StaffPayPolicy.is_active == True
            )
            .first()
        )

        if not policy:
            raise PayrollNotFoundError("Staff pay policy", staff_id)

        # Validate numeric fields
        numeric_fields = [
            "base_hourly_rate",
            "overtime_multiplier",
            "double_time_multiplier",
            "health_insurance",
            "dental_insurance",
            "vision_insurance",
            "retirement_401k_percentage",
            "life_insurance",
            "disability_insurance",
            "parking_fee",
            "other_deductions",
        ]

        # Update fields
        for field, value in policy_update.items():
            if hasattr(policy, field) and field not in ["id", "staff_id", "created_at"]:
                if field in numeric_fields:
                    try:
                        setattr(policy, field, Decimal(str(value)))
                    except (ValueError, TypeError):
                        raise PayrollValidationError(
                            f"Invalid value for {field}: must be a number", field=field
                        )
                else:
                    setattr(policy, field, value)

        policy.updated_at = datetime.utcnow()

        db.commit()
        db.refresh(policy)
        return policy

    except (PayrollNotFoundError, PayrollValidationError):
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=400,
            detail=ErrorResponse(
                error="UpdateError",
                message=f"Failed to update pay policy: {str(e)}",
                code=PayrollErrorCodes.DATABASE_ERROR,
            ).dict(),
        )


@router.delete("/{staff_id}", status_code=204)
async def deactivate_staff_pay_policy(
    staff_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_payroll_write),
):
    """
    Deactivate a staff pay policy (soft delete).

    ## Path Parameters
    - **staff_id**: Staff member ID

    ## Response
    No content on success.

    ## Error Responses
    - **404**: Policy not found
    """
    policy = (
        db.query(StaffPayPolicy)
        .filter(StaffPayPolicy.staff_id == staff_id, StaffPayPolicy.is_active == True)
        .first()
    )

    if not policy:
        raise HTTPException(
            status_code=404,
            detail=ErrorResponse(
                error="NotFound",
                message=f"No active pay policy found for staff ID {staff_id}",
                code=PayrollErrorCodes.NO_PAY_POLICY,
            ).dict(),
        )

    policy.is_active = False
    policy.updated_at = datetime.utcnow()

    try:
        db.commit()
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail=ErrorResponse(
                error="DatabaseError",
                message="Failed to deactivate pay policy",
                code=PayrollErrorCodes.DATABASE_ERROR,
            ).dict(),
        )
