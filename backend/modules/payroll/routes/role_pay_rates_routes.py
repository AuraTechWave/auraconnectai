# backend/modules/payroll/routes/role_pay_rates_routes.py

"""
Role-based pay rates management endpoints.
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import List, Optional, Dict, Any
from datetime import datetime
from decimal import Decimal

from core.database import get_db
from core.auth import require_payroll_write, get_current_user, User
from ..services.payroll_configuration_service import PayrollConfigurationService
from ..models.payroll_configuration import RoleBasedPayRate
from ..schemas.payroll_schemas import RoleBasedPayRateResponse, RoleBasedPayRateCreate
from ..schemas.error_schemas import ErrorResponse, PayrollErrorCodes
from ..exceptions import PayrollNotFoundError, PayrollBusinessRuleError

router = APIRouter()


@router.get("", response_model=List[RoleBasedPayRateResponse])
async def get_role_based_pay_rates(
    role_name: Optional[str] = Query(None, description="Filter by role name"),
    location: Optional[str] = Query(None, description="Filter by location"),
    effective_date: Optional[datetime] = Query(None, description="Get rates effective on date"),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_payroll_write)
):
    """
    Get role-based pay rates with optional filtering.
    
    ## Query Parameters
    - **role_name**: Optional role name filter
    - **location**: Optional location filter
    - **effective_date**: Get rates effective on specific date
    - **limit**: Maximum records to return
    - **offset**: Records to skip for pagination
    
    ## Response
    Returns list of role-based pay rates.
    
    ## Error Responses
    - **500**: Database error
    """
    try:
        config_service = PayrollConfigurationService(db)
        
        if role_name:
            rate = config_service.get_role_based_pay_rate(role_name, location)
            return [rate] if rate else []
        
        # Build query with filters
        query = db.query(RoleBasedPayRate)
        
        if location:
            query = query.filter(RoleBasedPayRate.location == location)
        
        if effective_date:
            query = query.filter(
                RoleBasedPayRate.effective_date <= effective_date,
                (RoleBasedPayRate.expiry_date.is_(None)) | 
                (RoleBasedPayRate.expiry_date >= effective_date)
            )
        
        total = query.count()
        rates = query.offset(offset).limit(limit).all()
        
        return rates
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=ErrorResponse(
                error="DatabaseError",
                message="Failed to retrieve role-based pay rates",
                code=PayrollErrorCodes.DATABASE_ERROR
            ).dict()
        )


@router.post("", response_model=RoleBasedPayRateResponse, status_code=201)
async def create_role_based_pay_rate(
    rate_data: RoleBasedPayRateCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_payroll_write)
):
    """
    Create a new role-based pay rate.
    
    ## Request Body
    See RoleBasedPayRateCreate schema for required fields.
    
    ## Response
    Returns the created role-based pay rate.
    
    ## Error Responses
    - **400**: Overlapping effective dates for same role/location
    - **422**: Validation error
    """
    try:
        # Check for overlapping rates
        query = db.query(RoleBasedPayRate).filter(
            RoleBasedPayRate.role_name == rate_data.role_name,
            RoleBasedPayRate.location == rate_data.location
        )
        
        if rate_data.effective_date:
            query = query.filter(
                RoleBasedPayRate.effective_date <= rate_data.effective_date,
                (RoleBasedPayRate.expiry_date.is_(None)) | 
                (RoleBasedPayRate.expiry_date >= rate_data.effective_date)
            )
        
        existing = query.first()
        if existing:
            raise PayrollBusinessRuleError(
                f"Overlapping pay rate exists for role {rate_data.role_name} in {rate_data.location}",
                "OVERLAPPING_RATES"
            )
        
        # Create new rate
        rate = RoleBasedPayRate(
            **rate_data.dict(),
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow()
        )
        
        db.add(rate)
        db.commit()
        db.refresh(rate)
        
        return rate
        
    except PayrollBusinessRuleError:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=400,
            detail=ErrorResponse(
                error="CreationError",
                message=f"Failed to create role-based pay rate: {str(e)}",
                code=PayrollErrorCodes.DATABASE_ERROR
            ).dict()
        )


@router.get("/{rate_id}", response_model=RoleBasedPayRateResponse)
async def get_role_based_pay_rate(
    rate_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_payroll_write)
):
    """
    Get a specific role-based pay rate.
    
    ## Path Parameters
    - **rate_id**: Pay rate ID
    
    ## Response
    Returns the pay rate.
    
    ## Error Responses
    - **404**: Rate not found
    """
    rate = db.query(RoleBasedPayRate).filter(RoleBasedPayRate.id == rate_id).first()
    
    if not rate:
        raise HTTPException(
            status_code=404,
            detail=ErrorResponse(
                error="NotFound",
                message=f"Role-based pay rate with ID {rate_id} not found",
                code=PayrollErrorCodes.RECORD_NOT_FOUND
            ).dict()
        )
    
    return rate


@router.put("/{rate_id}", response_model=RoleBasedPayRateResponse)
async def update_role_based_pay_rate(
    rate_id: int,
    rate_update: Dict[str, Any],
    db: Session = Depends(get_db),
    current_user: User = Depends(require_payroll_write)
):
    """
    Update an existing role-based pay rate.
    
    ## Path Parameters
    - **rate_id**: Pay rate ID
    
    ## Request Body
    Partial update - only include fields to update.
    
    ## Response
    Returns the updated pay rate.
    
    ## Error Responses
    - **404**: Rate not found
    - **400**: Invalid update would create overlapping rates
    """
    try:
        rate = db.query(RoleBasedPayRate).filter(RoleBasedPayRate.id == rate_id).first()
        
        if not rate:
            raise PayrollNotFoundError("Role-based pay rate", rate_id)
        
        # Update fields
        for field, value in rate_update.items():
            if hasattr(rate, field) and field not in ["id", "created_at"]:
                if field in ["base_hourly_rate", "overtime_multiplier"]:
                    setattr(rate, field, Decimal(str(value)))
                elif field in ["effective_date", "expiry_date"] and value:
                    setattr(rate, field, datetime.fromisoformat(value))
                else:
                    setattr(rate, field, value)
        
        rate.updated_at = datetime.utcnow()
        
        db.commit()
        db.refresh(rate)
        return rate
        
    except PayrollNotFoundError:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=400,
            detail=ErrorResponse(
                error="UpdateError",
                message=f"Failed to update role-based pay rate: {str(e)}",
                code=PayrollErrorCodes.DATABASE_ERROR
            ).dict()
        )


@router.delete("/{rate_id}", status_code=204)
async def expire_role_based_pay_rate(
    rate_id: int,
    expiry_date: Optional[datetime] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_payroll_write)
):
    """
    Expire a role-based pay rate (soft delete).
    
    ## Path Parameters
    - **rate_id**: Pay rate ID
    
    ## Query Parameters
    - **expiry_date**: Date to expire the rate (defaults to now)
    
    ## Response
    No content on success.
    
    ## Error Responses
    - **404**: Rate not found
    """
    rate = db.query(RoleBasedPayRate).filter(RoleBasedPayRate.id == rate_id).first()
    
    if not rate:
        raise HTTPException(
            status_code=404,
            detail=ErrorResponse(
                error="NotFound",
                message=f"Role-based pay rate with ID {rate_id} not found",
                code=PayrollErrorCodes.RECORD_NOT_FOUND
            ).dict()
        )
    
    rate.expiry_date = expiry_date or datetime.utcnow()
    rate.updated_at = datetime.utcnow()
    
    try:
        db.commit()
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail=ErrorResponse(
                error="DatabaseError",
                message="Failed to expire role-based pay rate",
                code=PayrollErrorCodes.DATABASE_ERROR
            ).dict()
        )