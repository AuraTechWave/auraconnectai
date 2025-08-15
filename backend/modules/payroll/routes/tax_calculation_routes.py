# backend/modules/payroll/routes/tax_calculation_routes.py

"""
Tax calculation API endpoints for payroll module.

Provides direct access to tax calculation services:
- Calculate payroll taxes for employees
- Get tax rules by jurisdiction
- Validate tax calculations
- Get effective tax rates
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import date
from decimal import Decimal

from core.database import get_db
from core.auth import require_payroll_access, get_current_user, User
from ..services.payroll_tax_engine import PayrollTaxEngine
from ..services.payroll_tax_service import PayrollTaxService
from ..schemas.payroll_tax_schemas import (
    PayrollTaxCalculationRequest,
    PayrollTaxCalculationResponse,
    PayrollTaxServiceRequest,
    PayrollTaxServiceResponse,
    TaxRuleResponse,
)
from ..models.payroll_models import TaxRule
from ..enums.payroll_enums import TaxRuleType, TaxRuleStatus

router = APIRouter()


@router.post("/calculate", response_model=PayrollTaxCalculationResponse)
async def calculate_payroll_taxes(
    request: PayrollTaxCalculationRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_payroll_access),
):
    """
    Calculate payroll taxes for a given gross amount and parameters.

    ## Request Body
    - **gross_amount**: Gross pay amount to calculate taxes on
    - **pay_date**: Date for tax rule lookup
    - **location**: Location/jurisdiction for tax calculation
    - **employee_id**: Optional employee ID for specific calculations
    - **year_to_date_gross**: Optional YTD gross for cap calculations
    - **year_to_date_ss**: Optional YTD social security for cap tracking
    - **year_to_date_medicare**: Optional YTD medicare for cap tracking

    ## Response
    Returns detailed tax calculations including:
    - Federal, state, and local taxes
    - Social security and medicare
    - Employee and employer portions
    - Applied tax rules

    ## Authentication
    Requires payroll access permissions.
    """
    try:
        tax_engine = PayrollTaxEngine(db)

        # Calculate taxes
        result = tax_engine.calculate_taxes(
            gross_amount=request.gross_amount,
            pay_date=request.pay_date,
            location=request.location,
            employee_id=request.employee_id,
            year_to_date_gross=request.year_to_date_gross,
            year_to_date_ss=request.year_to_date_ss,
            year_to_date_medicare=request.year_to_date_medicare,
        )

        return result

    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Tax calculation failed: {str(e)}",
        )


@router.post("/calculate-and-save", response_model=PayrollTaxServiceResponse)
async def calculate_and_save_taxes(
    request: PayrollTaxServiceRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_payroll_access),
):
    """
    Calculate payroll taxes and save the results with audit trail.

    ## Request Body
    - **employee_id**: Employee ID for tax calculation
    - **gross_amount**: Gross pay amount
    - **pay_period_start**: Start of pay period
    - **pay_period_end**: End of pay period
    - **location**: Tax jurisdiction location
    - **tenant_id**: Optional tenant ID for multi-tenant support

    ## Response
    Returns tax calculation results with:
    - All calculated tax amounts
    - Total deductions
    - Net pay amount
    - Applied tax rules audit trail

    ## Authentication
    Requires payroll access permissions.
    """
    try:
        tax_service = PayrollTaxService(db)

        # Calculate and save taxes
        result = await tax_service.calculate_and_save_taxes(request)

        return result

    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Tax calculation and save failed: {str(e)}",
        )


@router.get("/rules", response_model=List[TaxRuleResponse])
async def get_tax_rules(
    location: Optional[str] = None,
    tax_type: Optional[TaxRuleType] = None,
    status: Optional[TaxRuleStatus] = None,
    effective_date: Optional[date] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_payroll_access),
):
    """
    Get tax rules with optional filtering.

    ## Query Parameters
    - **location**: Filter by location/jurisdiction
    - **tax_type**: Filter by tax type (FEDERAL, STATE, LOCAL, etc.)
    - **status**: Filter by status (ACTIVE, INACTIVE, PENDING)
    - **effective_date**: Get rules effective on specific date

    ## Response
    Returns list of tax rules matching the criteria.

    ## Authentication
    Requires payroll access permissions.
    """
    try:
        query = db.query(TaxRule)

        if location:
            query = query.filter(TaxRule.location == location)

        if tax_type:
            query = query.filter(TaxRule.tax_type == tax_type)

        if status:
            query = query.filter(TaxRule.status == status)

        if effective_date:
            query = query.filter(
                TaxRule.effective_date <= effective_date,
                (TaxRule.expiry_date.is_(None))
                | (TaxRule.expiry_date >= effective_date),
            )

        rules = query.all()

        return [
            TaxRuleResponse(
                id=rule.id,
                tax_type=rule.tax_type,
                location=rule.location,
                rate=rule.rate,
                cap_amount=rule.cap_amount,
                employer_rate=rule.employer_rate,
                description=rule.description,
                effective_date=rule.effective_date,
                expiry_date=rule.expiry_date,
                status=rule.status,
                created_at=rule.created_at,
                updated_at=rule.updated_at,
            )
            for rule in rules
        ]

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve tax rules: {str(e)}",
        )


@router.get("/rules/{rule_id}", response_model=TaxRuleResponse)
async def get_tax_rule(
    rule_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_payroll_access),
):
    """
    Get a specific tax rule by ID.

    ## Path Parameters
    - **rule_id**: Tax rule ID

    ## Response
    Returns the tax rule details.

    ## Authentication
    Requires payroll access permissions.
    """
    rule = db.query(TaxRule).filter(TaxRule.id == rule_id).first()

    if not rule:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Tax rule with ID {rule_id} not found",
        )

    return TaxRuleResponse(
        id=rule.id,
        tax_type=rule.tax_type,
        location=rule.location,
        rate=rule.rate,
        cap_amount=rule.cap_amount,
        employer_rate=rule.employer_rate,
        description=rule.description,
        effective_date=rule.effective_date,
        expiry_date=rule.expiry_date,
        status=rule.status,
        created_at=rule.created_at,
        updated_at=rule.updated_at,
    )


@router.get("/effective-rates")
async def get_effective_tax_rates(
    location: str,
    gross_amount: Decimal,
    pay_date: Optional[date] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_payroll_access),
):
    """
    Get effective tax rates for a location and gross amount.

    ## Query Parameters
    - **location**: Tax jurisdiction location
    - **gross_amount**: Gross pay amount for rate calculation
    - **pay_date**: Optional date for rate lookup (defaults to today)

    ## Response
    Returns effective tax rates and estimated tax amounts.

    ## Authentication
    Requires payroll access permissions.
    """
    try:
        tax_engine = PayrollTaxEngine(db)

        if not pay_date:
            pay_date = date.today()

        # Get applicable tax rules
        rules = tax_engine.get_applicable_tax_rules(location, pay_date)

        # Calculate estimated taxes
        result = tax_engine.calculate_taxes(
            gross_amount=gross_amount, pay_date=pay_date, location=location
        )

        return {
            "location": location,
            "gross_amount": str(gross_amount),
            "pay_date": pay_date.isoformat(),
            "effective_rates": {
                "federal": str(
                    next(
                        (r.rate for r in rules if r.tax_type == TaxRuleType.FEDERAL),
                        Decimal("0"),
                    )
                ),
                "state": str(
                    next(
                        (r.rate for r in rules if r.tax_type == TaxRuleType.STATE),
                        Decimal("0"),
                    )
                ),
                "local": str(
                    next(
                        (r.rate for r in rules if r.tax_type == TaxRuleType.LOCAL),
                        Decimal("0"),
                    )
                ),
                "social_security": str(
                    next(
                        (
                            r.rate
                            for r in rules
                            if r.tax_type == TaxRuleType.SOCIAL_SECURITY
                        ),
                        Decimal("0"),
                    )
                ),
                "medicare": str(
                    next(
                        (r.rate for r in rules if r.tax_type == TaxRuleType.MEDICARE),
                        Decimal("0"),
                    )
                ),
            },
            "estimated_taxes": {
                "federal": str(result.federal_tax),
                "state": str(result.state_tax),
                "local": str(result.local_tax),
                "social_security": str(result.social_security_employee),
                "medicare": str(result.medicare_employee),
                "total": str(result.total_employee_taxes),
            },
        }

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get effective tax rates: {str(e)}",
        )
