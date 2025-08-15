# backend/modules/payroll/routes/configuration_routes.py

"""
Payroll configuration management API endpoints.

Main router that aggregates all configuration sub-routes:
- Payroll configurations
- Staff pay policies
- Overtime rules
- Role-based pay rates
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import List, Optional, Dict, Any
from datetime import datetime

from core.database import get_db
from core.auth import require_payroll_write, get_current_user, User
from ..services.payroll_configuration_service import PayrollConfigurationService
from ..models.payroll_configuration import PayrollConfiguration
from ..schemas.payroll_schemas import (
    PayrollConfigurationResponse,
    PayrollConfigurationCreate,
)
from ..schemas.error_schemas import ErrorResponse, PayrollErrorCodes
from ..exceptions import PayrollNotFoundError

# Import sub-routers
from .pay_policy_routes import router as pay_policy_router
from .overtime_rules_routes import router as overtime_router
from .role_pay_rates_routes import router as role_rates_router

router = APIRouter()

# Include sub-routers
router.include_router(pay_policy_router, prefix="/pay-policies", tags=["Pay Policies"])
router.include_router(
    overtime_router, prefix="/overtime-rules", tags=["Overtime Rules"]
)
router.include_router(
    role_rates_router, prefix="/role-pay-rates", tags=["Role Pay Rates"]
)


# Core Payroll Configuration Endpoints


@router.get("/payroll-configs", response_model=List[PayrollConfigurationResponse])
async def get_payroll_configurations(
    tenant_id: Optional[int] = Query(None, description="Filter by tenant ID"),
    active_only: bool = Query(True, description="Only return active configurations"),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_payroll_write),
):
    """
    Get all payroll configurations with optional filtering.

    ## Query Parameters
    - **tenant_id**: Optional tenant ID filter
    - **active_only**: Only return active configurations (default: true)
    - **limit**: Maximum records to return
    - **offset**: Records to skip for pagination

    ## Response
    Returns list of payroll configurations.

    ## Error Responses
    - **500**: Database error
    """
    try:
        config_service = PayrollConfigurationService(db)
        configs = config_service.get_all_payroll_configurations()

        # Apply filters
        if tenant_id:
            configs = [c for c in configs if c.tenant_id == tenant_id]

        if active_only:
            configs = [c for c in configs if c.is_active]

        # Apply pagination
        return configs[offset : offset + limit]

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=ErrorResponse(
                error="DatabaseError",
                message="Failed to retrieve configurations",
                code=PayrollErrorCodes.DATABASE_ERROR,
            ).dict(),
        )


@router.post(
    "/payroll-configs", response_model=PayrollConfigurationResponse, status_code=201
)
async def create_payroll_configuration(
    config_data: PayrollConfigurationCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_payroll_write),
):
    """
    Create a new payroll configuration.

    ## Request Body
    See PayrollConfigurationCreate schema.

    ## Response
    Returns the created configuration.

    ## Error Responses
    - **400**: Invalid configuration data
    - **409**: Duplicate configuration key
    """
    try:
        # Check for duplicate key
        existing = (
            db.query(PayrollConfiguration)
            .filter(
                PayrollConfiguration.config_key == config_data.config_key,
                PayrollConfiguration.tenant_id == config_data.tenant_id,
                PayrollConfiguration.is_active == True,
            )
            .first()
        )

        if existing:
            raise HTTPException(
                status_code=409,
                detail=ErrorResponse(
                    error="DuplicateKey",
                    message=f"Configuration key '{config_data.config_key}' already exists",
                    code=PayrollErrorCodes.DUPLICATE_PAY_POLICY,
                ).dict(),
            )

        config = PayrollConfiguration(
            **config_data.dict(),
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )

        db.add(config)
        db.commit()
        db.refresh(config)

        return config

    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=400,
            detail=ErrorResponse(
                error="CreationError",
                message=f"Failed to create configuration: {str(e)}",
                code=PayrollErrorCodes.DATABASE_ERROR,
            ).dict(),
        )


@router.get("/payroll-configs/{config_id}", response_model=PayrollConfigurationResponse)
async def get_payroll_configuration(
    config_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_payroll_write),
):
    """
    Get a specific payroll configuration.

    ## Path Parameters
    - **config_id**: Configuration ID

    ## Response
    Returns the configuration.

    ## Error Responses
    - **404**: Configuration not found
    """
    config = (
        db.query(PayrollConfiguration)
        .filter(PayrollConfiguration.id == config_id)
        .first()
    )

    if not config:
        raise HTTPException(
            status_code=404,
            detail=ErrorResponse(
                error="NotFound",
                message=f"Configuration with ID {config_id} not found",
                code=PayrollErrorCodes.CONFIG_NOT_FOUND,
            ).dict(),
        )

    return config


@router.put("/payroll-configs/{config_id}", response_model=PayrollConfigurationResponse)
async def update_payroll_configuration(
    config_id: int,
    config_update: Dict[str, Any],
    db: Session = Depends(get_db),
    current_user: User = Depends(require_payroll_write),
):
    """
    Update a payroll configuration.

    ## Path Parameters
    - **config_id**: Configuration ID

    ## Request Body
    Partial update - only include fields to update.

    ## Response
    Returns the updated configuration.

    ## Error Responses
    - **404**: Configuration not found
    - **400**: Invalid update data
    """
    config = (
        db.query(PayrollConfiguration)
        .filter(PayrollConfiguration.id == config_id)
        .first()
    )

    if not config:
        raise HTTPException(
            status_code=404,
            detail=ErrorResponse(
                error="NotFound",
                message=f"Configuration with ID {config_id} not found",
                code=PayrollErrorCodes.CONFIG_NOT_FOUND,
            ).dict(),
        )

    try:
        for field, value in config_update.items():
            if hasattr(config, field) and field not in ["id", "created_at"]:
                setattr(config, field, value)

        config.updated_at = datetime.utcnow()

        db.commit()
        db.refresh(config)
        return config

    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=400,
            detail=ErrorResponse(
                error="UpdateError",
                message=f"Failed to update configuration: {str(e)}",
                code=PayrollErrorCodes.DATABASE_ERROR,
            ).dict(),
        )


@router.delete("/payroll-configs/{config_id}", status_code=204)
async def delete_payroll_configuration(
    config_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_payroll_write),
):
    """
    Delete (deactivate) a payroll configuration.

    ## Path Parameters
    - **config_id**: Configuration ID

    ## Response
    No content on success.

    ## Error Responses
    - **404**: Configuration not found
    """
    config = (
        db.query(PayrollConfiguration)
        .filter(PayrollConfiguration.id == config_id)
        .first()
    )

    if not config:
        raise HTTPException(
            status_code=404,
            detail=ErrorResponse(
                error="NotFound",
                message=f"Configuration with ID {config_id} not found",
                code=PayrollErrorCodes.CONFIG_NOT_FOUND,
            ).dict(),
        )

    config.is_active = False
    config.updated_at = datetime.utcnow()

    try:
        db.commit()
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail=ErrorResponse(
                error="DatabaseError",
                message="Failed to delete configuration",
                code=PayrollErrorCodes.DATABASE_ERROR,
            ).dict(),
        )
