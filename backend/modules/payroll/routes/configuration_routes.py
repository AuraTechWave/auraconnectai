# backend/modules/payroll/routes/configuration_routes.py

"""
Payroll configuration management API endpoints.

Provides endpoints for managing payroll configurations:
- Payroll configurations
- Staff pay policies
- Overtime rules
- Tax approximation rules
- Role-based pay rates
"""

from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import datetime
from decimal import Decimal

from ....core.database import get_db
from ....core.auth import require_payroll_write, get_current_user, User
from ..services.payroll_configuration_service import PayrollConfigurationService
from ..models.payroll_configuration import (
    PayrollConfiguration,
    StaffPayPolicy,
    OvertimeRule,
    TaxApproximationRule,
    RoleBasedPayRate
)

router = APIRouter()


# Payroll Configuration Endpoints

@router.get("/payroll-configs")
async def get_payroll_configurations(
    tenant_id: Optional[int] = Query(None, description="Filter by tenant ID"),
    active_only: bool = Query(True, description="Only return active configurations"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_payroll_write)
):
    """
    Get all payroll configurations with optional filtering.
    
    ## Query Parameters
    - **tenant_id**: Optional tenant ID filter
    - **active_only**: Only return active configurations (default: true)
    
    ## Response
    Returns list of payroll configurations.
    
    ## Authentication
    Requires payroll write permissions.
    """
    config_service = PayrollConfigurationService(db)
    
    configs = config_service.get_all_payroll_configurations()
    
    # Apply filters
    if tenant_id:
        configs = [c for c in configs if c.tenant_id == tenant_id]
    
    if active_only:
        configs = [c for c in configs if c.is_active]
    
    return configs


@router.post("/payroll-configs")
async def create_payroll_configuration(
    config_data: dict,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_payroll_write)
):
    """
    Create a new payroll configuration.
    
    ## Request Body
    - **tenant_id**: Tenant ID
    - **config_key**: Configuration key
    - **config_value**: Configuration value
    - **is_active**: Whether configuration is active
    
    ## Response
    Returns the created configuration.
    
    ## Authentication
    Requires payroll write permissions.
    """
    try:
        config = PayrollConfiguration(
            tenant_id=config_data.get("tenant_id"),
            config_key=config_data["config_key"],
            config_value=config_data["config_value"],
            is_active=config_data.get("is_active", True),
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow()
        )
        
        db.add(config)
        db.commit()
        db.refresh(config)
        
        return config
        
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to create configuration: {str(e)}"
        )


# Staff Pay Policy Endpoints

@router.get("/pay-policies")
async def get_staff_pay_policies(
    staff_id: Optional[int] = Query(None, description="Filter by staff ID"),
    active_only: bool = Query(True, description="Only return active policies"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_payroll_write)
):
    """
    Get staff pay policies with optional filtering.
    
    ## Query Parameters
    - **staff_id**: Optional staff ID filter
    - **active_only**: Only return active policies (default: true)
    
    ## Response
    Returns list of staff pay policies.
    
    ## Authentication
    Requires payroll write permissions.
    """
    config_service = PayrollConfigurationService(db)
    
    if staff_id:
        policy = config_service.get_staff_pay_policy(staff_id)
        return [policy] if policy else []
    
    # Get all policies
    policies = db.query(StaffPayPolicy)
    
    if active_only:
        policies = policies.filter(StaffPayPolicy.is_active == True)
    
    return policies.all()


@router.post("/pay-policies")
async def create_staff_pay_policy(
    policy_data: dict,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_payroll_write)
):
    """
    Create a new staff pay policy.
    
    ## Request Body
    - **staff_id**: Staff member ID
    - **base_hourly_rate**: Base hourly rate
    - **overtime_multiplier**: Overtime rate multiplier
    - **location**: Location for tax calculations
    - **health_insurance**: Monthly health insurance deduction
    - **dental_insurance**: Monthly dental insurance deduction
    - **retirement_contribution**: Monthly retirement contribution
    - **other fields**: Additional policy fields
    
    ## Response
    Returns the created pay policy.
    
    ## Authentication
    Requires payroll write permissions.
    """
    try:
        policy = StaffPayPolicy(
            staff_id=policy_data["staff_id"],
            base_hourly_rate=Decimal(str(policy_data["base_hourly_rate"])),
            overtime_multiplier=Decimal(str(policy_data.get("overtime_multiplier", "1.5"))),
            double_time_multiplier=Decimal(str(policy_data.get("double_time_multiplier", "2.0"))),
            location=policy_data.get("location", "default"),
            health_insurance=Decimal(str(policy_data.get("health_insurance", "0"))),
            dental_insurance=Decimal(str(policy_data.get("dental_insurance", "0"))),
            vision_insurance=Decimal(str(policy_data.get("vision_insurance", "0"))),
            retirement_401k_percentage=Decimal(str(policy_data.get("retirement_401k_percentage", "0"))),
            life_insurance=Decimal(str(policy_data.get("life_insurance", "0"))),
            disability_insurance=Decimal(str(policy_data.get("disability_insurance", "0"))),
            parking_fee=Decimal(str(policy_data.get("parking_fee", "0"))),
            other_deductions=Decimal(str(policy_data.get("other_deductions", "0"))),
            is_active=policy_data.get("is_active", True),
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow()
        )
        
        db.add(policy)
        db.commit()
        db.refresh(policy)
        
        return policy
        
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to create pay policy: {str(e)}"
        )


@router.put("/pay-policies/{staff_id}")
async def update_staff_pay_policy(
    staff_id: int,
    policy_data: dict,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_payroll_write)
):
    """
    Update an existing staff pay policy.
    
    ## Path Parameters
    - **staff_id**: Staff member ID
    
    ## Request Body
    Same as create, but all fields are optional.
    
    ## Response
    Returns the updated pay policy.
    
    ## Authentication
    Requires payroll write permissions.
    """
    policy = db.query(StaffPayPolicy).filter(
        StaffPayPolicy.staff_id == staff_id,
        StaffPayPolicy.is_active == True
    ).first()
    
    if not policy:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No active pay policy found for staff ID {staff_id}"
        )
    
    # Update fields
    for field, value in policy_data.items():
        if hasattr(policy, field) and field not in ["id", "staff_id", "created_at"]:
            if field in ["base_hourly_rate", "overtime_multiplier", "double_time_multiplier",
                        "health_insurance", "dental_insurance", "vision_insurance",
                        "retirement_401k_percentage", "life_insurance", "disability_insurance",
                        "parking_fee", "other_deductions"]:
                setattr(policy, field, Decimal(str(value)))
            else:
                setattr(policy, field, value)
    
    policy.updated_at = datetime.utcnow()
    
    try:
        db.commit()
        db.refresh(policy)
        return policy
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to update pay policy: {str(e)}"
        )


# Overtime Rules Endpoints

@router.get("/overtime-rules")
async def get_overtime_rules(
    location: Optional[str] = Query(None, description="Filter by location"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_payroll_write)
):
    """
    Get overtime rules with optional location filtering.
    
    ## Query Parameters
    - **location**: Optional location filter
    
    ## Response
    Returns list of overtime rules.
    
    ## Authentication
    Requires payroll write permissions.
    """
    config_service = PayrollConfigurationService(db)
    
    if location:
        rules = config_service.get_overtime_rules(location)
        return rules
    
    # Get all rules
    return db.query(OvertimeRule).all()


@router.post("/overtime-rules")
async def create_overtime_rule(
    rule_data: dict,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_payroll_write)
):
    """
    Create a new overtime rule.
    
    ## Request Body
    - **location**: Location/jurisdiction
    - **daily_overtime_threshold**: Hours before daily overtime
    - **weekly_overtime_threshold**: Hours before weekly overtime
    - **daily_double_time_threshold**: Hours before daily double time
    - **weekly_double_time_threshold**: Hours before weekly double time
    
    ## Response
    Returns the created overtime rule.
    
    ## Authentication
    Requires payroll write permissions.
    """
    try:
        rule = OvertimeRule(
            location=rule_data["location"],
            daily_overtime_threshold=Decimal(str(rule_data.get("daily_overtime_threshold", "8.0"))),
            weekly_overtime_threshold=Decimal(str(rule_data.get("weekly_overtime_threshold", "40.0"))),
            daily_double_time_threshold=Decimal(str(rule_data.get("daily_double_time_threshold", "12.0"))),
            weekly_double_time_threshold=Decimal(str(rule_data.get("weekly_double_time_threshold", "60.0"))),
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow()
        )
        
        db.add(rule)
        db.commit()
        db.refresh(rule)
        
        return rule
        
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to create overtime rule: {str(e)}"
        )


# Role-Based Pay Rates Endpoints

@router.get("/role-pay-rates")
async def get_role_based_pay_rates(
    role_name: Optional[str] = Query(None, description="Filter by role name"),
    location: Optional[str] = Query(None, description="Filter by location"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_payroll_write)
):
    """
    Get role-based pay rates with optional filtering.
    
    ## Query Parameters
    - **role_name**: Optional role name filter
    - **location**: Optional location filter
    
    ## Response
    Returns list of role-based pay rates.
    
    ## Authentication
    Requires payroll write permissions.
    """
    config_service = PayrollConfigurationService(db)
    
    if role_name:
        rate = config_service.get_role_based_pay_rate(role_name, location)
        return [rate] if rate else []
    
    # Get all rates
    query = db.query(RoleBasedPayRate)
    
    if location:
        query = query.filter(RoleBasedPayRate.location == location)
    
    return query.all()


@router.post("/role-pay-rates")
async def create_role_based_pay_rate(
    rate_data: dict,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_payroll_write)
):
    """
    Create a new role-based pay rate.
    
    ## Request Body
    - **role_name**: Role name
    - **location**: Location (optional)
    - **base_hourly_rate**: Base hourly rate for the role
    - **overtime_multiplier**: Overtime multiplier (optional)
    - **effective_date**: When the rate becomes effective
    - **expiry_date**: When the rate expires (optional)
    
    ## Response
    Returns the created role-based pay rate.
    
    ## Authentication
    Requires payroll write permissions.
    """
    try:
        rate = RoleBasedPayRate(
            role_name=rate_data["role_name"],
            location=rate_data.get("location", "default"),
            base_hourly_rate=Decimal(str(rate_data["base_hourly_rate"])),
            overtime_multiplier=Decimal(str(rate_data.get("overtime_multiplier", "1.5"))),
            effective_date=datetime.fromisoformat(rate_data.get("effective_date", datetime.utcnow().isoformat())),
            expiry_date=datetime.fromisoformat(rate_data["expiry_date"]) if rate_data.get("expiry_date") else None,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow()
        )
        
        db.add(rate)
        db.commit()
        db.refresh(rate)
        
        return rate
        
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to create role-based pay rate: {str(e)}"
        )