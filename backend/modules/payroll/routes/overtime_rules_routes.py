# backend/modules/payroll/routes/overtime_rules_routes.py

"""
Overtime rules management endpoints.
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import List, Optional, Dict, Any
from datetime import datetime
from decimal import Decimal

from core.database import get_db
from core.auth import require_payroll_write, get_current_user, User
from ..services.payroll_configuration_service import PayrollConfigurationService
from ..models.payroll_configuration import OvertimeRule
from ..schemas.payroll_schemas import OvertimeRuleResponse, OvertimeRuleCreate
from ..schemas.error_schemas import ErrorResponse, PayrollErrorCodes
from ..exceptions import PayrollNotFoundError, PayrollValidationError

router = APIRouter()


@router.get("", response_model=List[OvertimeRuleResponse])
async def get_overtime_rules(
    location: Optional[str] = Query(None, description="Filter by location"),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_payroll_write),
):
    """
    Get overtime rules with optional location filtering.

    ## Query Parameters
    - **location**: Optional location filter
    - **limit**: Maximum records to return
    - **offset**: Records to skip for pagination

    ## Response
    Returns list of overtime rules.

    ## Error Responses
    - **500**: Database error
    """
    try:
        config_service = PayrollConfigurationService(db)

        if location:
            rules = config_service.get_overtime_rules(location)
            return rules[offset : offset + limit]

        # Get all rules with pagination
        query = db.query(OvertimeRule)
        total = query.count()
        rules = query.offset(offset).limit(limit).all()

        return rules

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=ErrorResponse(
                error="DatabaseError",
                message="Failed to retrieve overtime rules",
                code=PayrollErrorCodes.DATABASE_ERROR,
            ).dict(),
        )


@router.post("", response_model=OvertimeRuleResponse, status_code=201)
async def create_overtime_rule(
    rule_data: OvertimeRuleCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_payroll_write),
):
    """
    Create a new overtime rule.

    ## Request Body
    See OvertimeRuleCreate schema for required fields.

    ## Response
    Returns the created overtime rule.

    ## Error Responses
    - **400**: Invalid rule data or duplicate location
    - **422**: Validation error
    """
    try:
        # Check if rule already exists for location
        existing = (
            db.query(OvertimeRule)
            .filter(OvertimeRule.location == rule_data.location)
            .first()
        )

        if existing:
            raise HTTPException(
                status_code=400,
                detail=ErrorResponse(
                    error="DuplicateRule",
                    message=f"Overtime rule already exists for location {rule_data.location}",
                    code=PayrollErrorCodes.DUPLICATE_PAY_POLICY,
                ).dict(),
            )

        # Validate thresholds
        if (
            rule_data.daily_double_time_threshold
            and rule_data.daily_double_time_threshold
            <= rule_data.daily_overtime_threshold
        ):
            raise PayrollValidationError(
                "Daily double time threshold must be greater than overtime threshold",
                field="daily_double_time_threshold",
            )

        # Create new rule
        rule = OvertimeRule(
            **rule_data.dict(),
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )

        db.add(rule)
        db.commit()
        db.refresh(rule)

        return rule

    except (HTTPException, PayrollValidationError):
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=400,
            detail=ErrorResponse(
                error="CreationError",
                message=f"Failed to create overtime rule: {str(e)}",
                code=PayrollErrorCodes.DATABASE_ERROR,
            ).dict(),
        )


@router.get("/{location}", response_model=OvertimeRuleResponse)
async def get_overtime_rule_by_location(
    location: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_payroll_write),
):
    """
    Get overtime rule for a specific location.

    ## Path Parameters
    - **location**: Location/jurisdiction code

    ## Response
    Returns the overtime rule.

    ## Error Responses
    - **404**: Rule not found
    """
    config_service = PayrollConfigurationService(db)
    rules = config_service.get_overtime_rules(location)

    if not rules:
        raise HTTPException(
            status_code=404,
            detail=ErrorResponse(
                error="NotFound",
                message=f"No overtime rule found for location {location}",
                code=PayrollErrorCodes.RECORD_NOT_FOUND,
            ).dict(),
        )

    return rules[0]


@router.put("/{rule_id}", response_model=OvertimeRuleResponse)
async def update_overtime_rule(
    rule_id: int,
    rule_update: Dict[str, Any],
    db: Session = Depends(get_db),
    current_user: User = Depends(require_payroll_write),
):
    """
    Update an existing overtime rule.

    ## Path Parameters
    - **rule_id**: Overtime rule ID

    ## Request Body
    Partial update - only include fields to update.

    ## Response
    Returns the updated overtime rule.

    ## Error Responses
    - **404**: Rule not found
    - **422**: Invalid threshold values
    """
    try:
        rule = db.query(OvertimeRule).filter(OvertimeRule.id == rule_id).first()

        if not rule:
            raise PayrollNotFoundError("Overtime rule", rule_id)

        # Update fields
        for field, value in rule_update.items():
            if hasattr(rule, field) and field not in ["id", "created_at"]:
                if field in [
                    "daily_overtime_threshold",
                    "weekly_overtime_threshold",
                    "daily_double_time_threshold",
                    "weekly_double_time_threshold",
                ]:
                    setattr(rule, field, Decimal(str(value)))
                else:
                    setattr(rule, field, value)

        # Validate thresholds after update
        if (
            rule.daily_double_time_threshold
            and rule.daily_double_time_threshold <= rule.daily_overtime_threshold
        ):
            raise PayrollValidationError(
                "Daily double time threshold must be greater than overtime threshold"
            )

        rule.updated_at = datetime.utcnow()

        db.commit()
        db.refresh(rule)
        return rule

    except (PayrollNotFoundError, PayrollValidationError):
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=400,
            detail=ErrorResponse(
                error="UpdateError",
                message=f"Failed to update overtime rule: {str(e)}",
                code=PayrollErrorCodes.DATABASE_ERROR,
            ).dict(),
        )


@router.delete("/{rule_id}", status_code=204)
async def delete_overtime_rule(
    rule_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_payroll_write),
):
    """
    Delete an overtime rule.

    ## Path Parameters
    - **rule_id**: Overtime rule ID

    ## Response
    No content on success.

    ## Error Responses
    - **404**: Rule not found
    """
    rule = db.query(OvertimeRule).filter(OvertimeRule.id == rule_id).first()

    if not rule:
        raise HTTPException(
            status_code=404,
            detail=ErrorResponse(
                error="NotFound",
                message=f"Overtime rule with ID {rule_id} not found",
                code=PayrollErrorCodes.RECORD_NOT_FOUND,
            ).dict(),
        )

    try:
        db.delete(rule)
        db.commit()
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail=ErrorResponse(
                error="DatabaseError",
                message="Failed to delete overtime rule",
                code=PayrollErrorCodes.DATABASE_ERROR,
            ).dict(),
        )
