# backend/modules/tax/routes/tax_jurisdiction_routes.py

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import date
import uuid

from core.database import get_db
from core.auth import require_permission, get_current_tenant

from ..models import TaxJurisdiction, TaxRate, TaxNexus
from ..schemas import (
    TaxJurisdictionCreate,
    TaxJurisdictionUpdate,
    TaxJurisdictionResponse,
    TaxRateCreate,
    TaxRateUpdate,
    TaxRateResponse,
    TaxNexusCreate,
    TaxNexusUpdate,
    TaxNexusResponse,
)

router = APIRouter(prefix="/jurisdictions", tags=["Tax Jurisdictions"])


# Jurisdiction Management
@router.post("/", response_model=TaxJurisdictionResponse)
async def create_jurisdiction(
    jurisdiction_data: TaxJurisdictionCreate,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_permission("tax.admin")),
    tenant_id: Optional[int] = Depends(get_current_tenant),
):
    """Create a new tax jurisdiction"""
    try:
        # Check for duplicate
        existing = (
            db.query(TaxJurisdiction)
            .filter(
                TaxJurisdiction.code == jurisdiction_data.code,
                TaxJurisdiction.jurisdiction_type
                == jurisdiction_data.jurisdiction_type,
                TaxJurisdiction.tenant_id == tenant_id,
            )
            .first()
        )

        if existing:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Jurisdiction {jurisdiction_data.code} already exists",
            )

        jurisdiction = TaxJurisdiction(
            **jurisdiction_data.model_dump(), tenant_id=tenant_id
        )

        db.add(jurisdiction)
        db.commit()
        db.refresh(jurisdiction)

        return TaxJurisdictionResponse.model_validate(jurisdiction)

    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create jurisdiction: {str(e)}",
        )


@router.get("/", response_model=List[TaxJurisdictionResponse])
async def list_jurisdictions(
    jurisdiction_type: Optional[str] = Query(
        None, pattern="^(federal|state|county|city|special)$"
    ),
    country_code: Optional[str] = Query(None, min_length=2, max_length=2),
    state_code: Optional[str] = Query(None, max_length=10),
    is_active: Optional[bool] = Query(None),
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_permission("tax.view")),
    tenant_id: Optional[int] = Depends(get_current_tenant),
):
    """List tax jurisdictions with filters"""
    query = db.query(TaxJurisdiction).filter(TaxJurisdiction.tenant_id == tenant_id)

    if jurisdiction_type:
        query = query.filter(TaxJurisdiction.jurisdiction_type == jurisdiction_type)

    if country_code:
        query = query.filter(TaxJurisdiction.country_code == country_code)

    if state_code:
        query = query.filter(TaxJurisdiction.state_code == state_code)

    if is_active is not None:
        query = query.filter(TaxJurisdiction.is_active == is_active)

    jurisdictions = (
        query.order_by(TaxJurisdiction.jurisdiction_type, TaxJurisdiction.name)
        .limit(limit)
        .offset(offset)
        .all()
    )

    return [TaxJurisdictionResponse.model_validate(j) for j in jurisdictions]


@router.get("/{jurisdiction_id}", response_model=TaxJurisdictionResponse)
async def get_jurisdiction(
    jurisdiction_id: int,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_permission("tax.view")),
    tenant_id: Optional[int] = Depends(get_current_tenant),
):
    """Get a specific tax jurisdiction"""
    jurisdiction = (
        db.query(TaxJurisdiction)
        .filter(
            TaxJurisdiction.id == jurisdiction_id,
            TaxJurisdiction.tenant_id == tenant_id,
        )
        .first()
    )

    if not jurisdiction:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Jurisdiction {jurisdiction_id} not found",
        )

    return TaxJurisdictionResponse.model_validate(jurisdiction)


@router.patch("/{jurisdiction_id}", response_model=TaxJurisdictionResponse)
async def update_jurisdiction(
    jurisdiction_id: int,
    update_data: TaxJurisdictionUpdate,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_permission("tax.admin")),
    tenant_id: Optional[int] = Depends(get_current_tenant),
):
    """Update a tax jurisdiction"""
    jurisdiction = (
        db.query(TaxJurisdiction)
        .filter(
            TaxJurisdiction.id == jurisdiction_id,
            TaxJurisdiction.tenant_id == tenant_id,
        )
        .first()
    )

    if not jurisdiction:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Jurisdiction {jurisdiction_id} not found",
        )

    for field, value in update_data.model_dump(exclude_unset=True).items():
        setattr(jurisdiction, field, value)

    db.commit()
    db.refresh(jurisdiction)

    return TaxJurisdictionResponse.model_validate(jurisdiction)


# Tax Rate Management
@router.post("/{jurisdiction_id}/rates", response_model=TaxRateResponse)
async def create_tax_rate(
    jurisdiction_id: int,
    rate_data: TaxRateCreate,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_permission("tax.admin")),
    tenant_id: Optional[int] = Depends(get_current_tenant),
):
    """Create a new tax rate for a jurisdiction"""
    # Verify jurisdiction exists
    jurisdiction = (
        db.query(TaxJurisdiction)
        .filter(
            TaxJurisdiction.id == jurisdiction_id,
            TaxJurisdiction.tenant_id == tenant_id,
        )
        .first()
    )

    if not jurisdiction:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Jurisdiction {jurisdiction_id} not found",
        )

    # Check for overlapping rates
    existing = db.query(TaxRate).filter(
        TaxRate.jurisdiction_id == jurisdiction_id,
        TaxRate.tax_type == rate_data.tax_type,
        TaxRate.tax_subtype == rate_data.tax_subtype,
        TaxRate.tax_category == rate_data.tax_category,
        TaxRate.is_active == True,
        TaxRate.effective_date <= rate_data.effective_date,
    )

    if rate_data.expiry_date:
        existing = existing.filter(
            db.or_(
                TaxRate.expiry_date.is_(None),
                TaxRate.expiry_date >= rate_data.effective_date,
            )
        )
    else:
        existing = existing.filter(TaxRate.expiry_date.is_(None))

    if existing.first():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Overlapping tax rate exists for this period",
        )

    tax_rate = TaxRate(
        **rate_data.model_dump(exclude={"jurisdiction_id"}),
        jurisdiction_id=jurisdiction_id,
        tenant_id=tenant_id,
    )

    db.add(tax_rate)
    db.commit()
    db.refresh(tax_rate)

    return TaxRateResponse.model_validate(tax_rate)


@router.get("/{jurisdiction_id}/rates", response_model=List[TaxRateResponse])
async def list_jurisdiction_rates(
    jurisdiction_id: int,
    tax_type: Optional[str] = Query(None),
    effective_date: Optional[date] = Query(None),
    is_active: Optional[bool] = Query(None),
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_permission("tax.view")),
    tenant_id: Optional[int] = Depends(get_current_tenant),
):
    """List tax rates for a jurisdiction"""
    query = db.query(TaxRate).filter(
        TaxRate.jurisdiction_id == jurisdiction_id, TaxRate.tenant_id == tenant_id
    )

    if tax_type:
        query = query.filter(TaxRate.tax_type == tax_type)

    if effective_date:
        query = query.filter(
            TaxRate.effective_date <= effective_date,
            db.or_(
                TaxRate.expiry_date.is_(None), TaxRate.expiry_date >= effective_date
            ),
        )

    if is_active is not None:
        query = query.filter(TaxRate.is_active == is_active)

    rates = query.order_by(TaxRate.tax_type, TaxRate.effective_date.desc()).all()

    return [TaxRateResponse.model_validate(r) for r in rates]


@router.patch("/rates/{rate_id}", response_model=TaxRateResponse)
async def update_tax_rate(
    rate_id: int,
    update_data: TaxRateUpdate,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_permission("tax.admin")),
    tenant_id: Optional[int] = Depends(get_current_tenant),
):
    """Update a tax rate"""
    tax_rate = (
        db.query(TaxRate)
        .filter(TaxRate.id == rate_id, TaxRate.tenant_id == tenant_id)
        .first()
    )

    if not tax_rate:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Tax rate {rate_id} not found",
        )

    for field, value in update_data.model_dump(exclude_unset=True).items():
        setattr(tax_rate, field, value)

    db.commit()
    db.refresh(tax_rate)

    return TaxRateResponse.model_validate(tax_rate)


# Nexus Management
@router.post("/{jurisdiction_id}/nexus", response_model=TaxNexusResponse)
async def create_nexus(
    jurisdiction_id: int,
    nexus_data: TaxNexusCreate,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_permission("tax.admin")),
    tenant_id: Optional[int] = Depends(get_current_tenant),
):
    """Create tax nexus for a jurisdiction"""
    # Verify jurisdiction exists
    jurisdiction = (
        db.query(TaxJurisdiction)
        .filter(
            TaxJurisdiction.id == jurisdiction_id,
            TaxJurisdiction.tenant_id == tenant_id,
        )
        .first()
    )

    if not jurisdiction:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Jurisdiction {jurisdiction_id} not found",
        )

    # Check for duplicate nexus
    existing = (
        db.query(TaxNexus)
        .filter(
            TaxNexus.jurisdiction_id == jurisdiction_id,
            TaxNexus.nexus_type == nexus_data.nexus_type,
            TaxNexus.tenant_id == tenant_id,
        )
        .first()
    )

    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Nexus already exists for {nexus_data.nexus_type} in this jurisdiction",
        )

    nexus = TaxNexus(
        **nexus_data.model_dump(exclude={"jurisdiction_id"}),
        jurisdiction_id=jurisdiction_id,
        tenant_id=tenant_id,
    )

    db.add(nexus)
    db.commit()
    db.refresh(nexus)

    return TaxNexusResponse.model_validate(nexus)


@router.get("/nexus", response_model=List[TaxNexusResponse])
async def list_all_nexus(
    nexus_type: Optional[str] = Query(
        None, pattern="^(physical|economic|affiliate|click_through)$"
    ),
    is_active: Optional[bool] = Query(None),
    requires_filing: Optional[bool] = Query(None),
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_permission("tax.view")),
    tenant_id: Optional[int] = Depends(get_current_tenant),
):
    """List all tax nexus across jurisdictions"""
    query = db.query(TaxNexus).filter(TaxNexus.tenant_id == tenant_id)

    if nexus_type:
        query = query.filter(TaxNexus.nexus_type == nexus_type)

    if is_active is not None:
        query = query.filter(TaxNexus.is_active == is_active)

    if requires_filing is not None:
        query = query.filter(TaxNexus.requires_filing == requires_filing)

    nexus_list = query.join(TaxJurisdiction).order_by(TaxJurisdiction.name).all()

    return [TaxNexusResponse.model_validate(n) for n in nexus_list]


@router.patch("/nexus/{nexus_id}", response_model=TaxNexusResponse)
async def update_nexus(
    nexus_id: int,
    update_data: TaxNexusUpdate,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_permission("tax.admin")),
    tenant_id: Optional[int] = Depends(get_current_tenant),
):
    """Update tax nexus"""
    nexus = (
        db.query(TaxNexus)
        .filter(TaxNexus.id == nexus_id, TaxNexus.tenant_id == tenant_id)
        .first()
    )

    if not nexus:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=f"Nexus {nexus_id} not found"
        )

    for field, value in update_data.model_dump(exclude_unset=True).items():
        setattr(nexus, field, value)

    db.commit()
    db.refresh(nexus)

    return TaxNexusResponse.model_validate(nexus)


# Bulk operations
@router.post("/import/jurisdictions")
async def import_jurisdictions(
    file_url: str,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_permission("tax.admin")),
    tenant_id: Optional[int] = Depends(get_current_tenant),
):
    """Import jurisdictions from a file"""
    # TODO: Implement jurisdiction import from CSV/JSON
    return {"message": "Jurisdiction import not yet implemented", "file_url": file_url}


@router.post("/sync/rates")
async def sync_tax_rates(
    provider: str = Query(..., pattern="^(avalara|taxjar)$"),
    jurisdiction_ids: List[int] = Query(...),
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_permission("tax.admin")),
    tenant_id: Optional[int] = Depends(get_current_tenant),
):
    """Sync tax rates from external provider"""
    # TODO: Implement rate sync from external providers
    return {
        "message": "Tax rate sync not yet implemented",
        "provider": provider,
        "jurisdiction_count": len(jurisdiction_ids),
    }
