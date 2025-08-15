# backend/modules/tax/routes/tax_calculation_routes.py

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from typing import Optional, Dict, Any
from datetime import date

from core.database import get_db
from core.auth import require_permission, get_current_tenant

from ..schemas import (
    EnhancedTaxCalculationRequest,
    EnhancedTaxCalculationResponse,
    TaxCalculationLocation,
    TaxExemptionCertificateCreate,
    TaxExemptionCertificateVerify,
    TaxExemptionCertificateResponse,
)
from ..services import (
    TaxCalculationEngine,
    TaxIntegrationService,
    create_tax_integration_service,
)
from ..models import TaxExemptionCertificate

router = APIRouter(prefix="/calculations", tags=["Tax Calculations"])


@router.post("/calculate", response_model=EnhancedTaxCalculationResponse)
async def calculate_tax(
    request: EnhancedTaxCalculationRequest,
    provider: Optional[str] = Query(
        None, description="Tax provider to use (internal, avalara, taxjar)"
    ),
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_permission("tax.calculate")),
    tenant_id: Optional[int] = Depends(get_current_tenant),
):
    """
    Calculate tax for a transaction

    Supports multi-jurisdiction tax calculation with exemptions and special rules.
    Can use internal engine or external providers (Avalara, TaxJar).
    """
    try:
        if provider and provider != "internal":
            # Use external provider
            integration_service = create_tax_integration_service()
            try:
                response = await integration_service.calculate_tax(request, provider)
                return response
            finally:
                await integration_service.close()
        else:
            # Use internal calculation engine
            engine = TaxCalculationEngine(db)
            response = engine.calculate_tax(request, tenant_id)
            return response

    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Tax calculation failed: {str(e)}",
        )


@router.post("/validate-address")
async def validate_address(
    address: Dict[str, str],
    provider: Optional[str] = Query(
        "avalara", description="Address validation provider"
    ),
    current_user: dict = Depends(require_permission("tax.calculate")),
):
    """
    Validate and standardize an address

    Uses external providers for address validation and correction.
    Returns standardized address if valid.
    """
    try:
        integration_service = create_tax_integration_service()
        try:
            result = await integration_service.validate_address(address, provider)
            return result
        finally:
            await integration_service.close()

    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Address validation failed: {str(e)}",
        )


@router.get("/rates")
async def get_tax_rates(
    country_code: str = Query(..., min_length=2, max_length=2),
    state_code: Optional[str] = Query(None),
    city_name: Optional[str] = Query(None),
    zip_code: Optional[str] = Query(None),
    tax_date: Optional[date] = Query(None),
    provider: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_permission("tax.view")),
    tenant_id: Optional[int] = Depends(get_current_tenant),
):
    """
    Get tax rates for a location

    Returns all applicable tax rates including state, county, city, and special districts.
    """
    try:
        location = TaxCalculationLocation(
            country_code=country_code,
            state_code=state_code,
            city_name=city_name,
            zip_code=zip_code,
        )

        if not tax_date:
            tax_date = date.today()

        if provider and provider != "internal":
            # Use external provider
            integration_service = create_tax_integration_service()
            try:
                rates = await integration_service.get_tax_rates(
                    location, tax_date, provider
                )
                return {"rates": rates, "provider": provider}
            finally:
                await integration_service.close()
        else:
            # Use internal data
            engine = TaxCalculationEngine(db)
            jurisdictions = engine._get_applicable_jurisdictions(location, tenant_id)
            rates = engine._get_applicable_tax_rates(jurisdictions, tax_date, tenant_id)

            return {
                "rates": [
                    {
                        "jurisdiction": rate.jurisdiction.name,
                        "jurisdiction_type": rate.jurisdiction.jurisdiction_type,
                        "tax_type": rate.tax_type,
                        "rate": float(rate.rate_percent),
                        "effective_date": rate.effective_date,
                        "expiry_date": rate.expiry_date,
                    }
                    for rate in rates
                ],
                "provider": "internal",
            }

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get tax rates: {str(e)}",
        )


# Exemption Certificate Management
@router.post("/exemptions", response_model=TaxExemptionCertificateResponse)
async def create_exemption_certificate(
    certificate_data: TaxExemptionCertificateCreate,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_permission("tax.admin")),
    tenant_id: Optional[int] = Depends(get_current_tenant),
):
    """Create a tax exemption certificate"""
    try:
        # Check for duplicate certificate number
        existing = (
            db.query(TaxExemptionCertificate)
            .filter(
                TaxExemptionCertificate.certificate_number
                == certificate_data.certificate_number,
                TaxExemptionCertificate.tenant_id == tenant_id,
            )
            .first()
        )

        if existing:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Certificate {certificate_data.certificate_number} already exists",
            )

        certificate = TaxExemptionCertificate(
            **certificate_data.model_dump(), tenant_id=tenant_id
        )

        db.add(certificate)
        db.commit()
        db.refresh(certificate)

        return TaxExemptionCertificateResponse.model_validate(certificate)

    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create exemption certificate: {str(e)}",
        )


@router.get(
    "/exemptions/{certificate_id}", response_model=TaxExemptionCertificateResponse
)
async def get_exemption_certificate(
    certificate_id: str,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_permission("tax.view")),
    tenant_id: Optional[int] = Depends(get_current_tenant),
):
    """Get a specific exemption certificate"""
    certificate = (
        db.query(TaxExemptionCertificate)
        .filter(
            TaxExemptionCertificate.certificate_id == certificate_id,
            TaxExemptionCertificate.tenant_id == tenant_id,
        )
        .first()
    )

    if not certificate:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Certificate {certificate_id} not found",
        )

    return TaxExemptionCertificateResponse.model_validate(certificate)


@router.post(
    "/exemptions/{certificate_id}/verify",
    response_model=TaxExemptionCertificateResponse,
)
async def verify_exemption_certificate(
    certificate_id: str,
    verification_data: TaxExemptionCertificateVerify,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_permission("tax.admin")),
    tenant_id: Optional[int] = Depends(get_current_tenant),
):
    """Verify an exemption certificate"""
    certificate = (
        db.query(TaxExemptionCertificate)
        .filter(
            TaxExemptionCertificate.certificate_id == certificate_id,
            TaxExemptionCertificate.tenant_id == tenant_id,
        )
        .first()
    )

    if not certificate:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Certificate {certificate_id} not found",
        )

    certificate.is_verified = verification_data.is_verified
    certificate.verified_by = verification_data.verified_by
    certificate.verified_date = date.today()

    if verification_data.verification_notes:
        certificate.notes = (
            certificate.notes or ""
        ) + f"\n\nVerification: {verification_data.verification_notes}"

    db.commit()
    db.refresh(certificate)

    return TaxExemptionCertificateResponse.model_validate(certificate)


@router.get("/exemptions")
async def list_exemption_certificates(
    customer_id: Optional[int] = Query(None),
    exemption_type: Optional[str] = Query(None),
    is_active: Optional[bool] = Query(None),
    is_verified: Optional[bool] = Query(None),
    expires_before: Optional[date] = Query(None),
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_permission("tax.view")),
    tenant_id: Optional[int] = Depends(get_current_tenant),
):
    """List exemption certificates with filters"""
    query = db.query(TaxExemptionCertificate).filter(
        TaxExemptionCertificate.tenant_id == tenant_id
    )

    if customer_id:
        query = query.filter(TaxExemptionCertificate.customer_id == customer_id)

    if exemption_type:
        query = query.filter(TaxExemptionCertificate.exemption_type == exemption_type)

    if is_active is not None:
        query = query.filter(TaxExemptionCertificate.is_active == is_active)

    if is_verified is not None:
        query = query.filter(TaxExemptionCertificate.is_verified == is_verified)

    if expires_before:
        query = query.filter(
            TaxExemptionCertificate.expiry_date.isnot(None),
            TaxExemptionCertificate.expiry_date <= expires_before,
        )

    certificates = (
        query.order_by(
            TaxExemptionCertificate.expiry_date.asc().nullslast(),
            TaxExemptionCertificate.created_at.desc(),
        )
        .limit(limit)
        .offset(offset)
        .all()
    )

    return [TaxExemptionCertificateResponse.model_validate(c) for c in certificates]


# Test endpoints
@router.post("/test/calculate")
async def test_tax_calculation(
    current_user: dict = Depends(require_permission("tax.admin")),
):
    """Test tax calculation with sample data"""
    from decimal import Decimal
    import uuid

    test_request = EnhancedTaxCalculationRequest(
        transaction_id=str(uuid.uuid4()),
        transaction_date=date.today(),
        location=TaxCalculationLocation(
            country_code="US",
            state_code="CA",
            city_name="Los Angeles",
            zip_code="90001",
        ),
        line_items=[
            {
                "line_id": "item1",
                "amount": Decimal("100.00"),
                "quantity": 2,
                "category": "general",
                "is_exempt": False,
            },
            {
                "line_id": "item2",
                "amount": Decimal("50.00"),
                "quantity": 1,
                "category": "food",
                "is_exempt": False,
            },
        ],
        shipping_amount=Decimal("10.00"),
    )

    return {
        "message": "Test calculation endpoint",
        "request": test_request.model_dump(),
        "note": "Use the main /calculate endpoint with this request data",
    }
