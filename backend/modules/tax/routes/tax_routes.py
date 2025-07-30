from fastapi import APIRouter

# Import sub-routers
from .tax_jurisdiction_routes import router as jurisdiction_router
from .tax_calculation_routes import router as calculation_router
from .tax_compliance_routes import router as compliance_router

# Original simple calculation endpoint
from fastapi import Depends
from sqlalchemy.orm import Session
from backend.core.database import get_db
from ..controllers.tax_controller import calculate_tax_preview
from ..schemas.tax_schemas import TaxCalculationRequest, TaxCalculationResponse

# Create main tax router
router = APIRouter(prefix="/tax", tags=["Tax"])

# Include sub-routers
router.include_router(jurisdiction_router, tags=["Tax Jurisdictions"])
router.include_router(calculation_router, tags=["Tax Calculations"])
router.include_router(compliance_router, tags=["Tax Compliance"])


# Keep original simple calculation endpoint for backward compatibility
@router.post("/calculate", response_model=TaxCalculationResponse)
async def calculate_tax(
    request: TaxCalculationRequest,
    db: Session = Depends(get_db)
):
    """
    Calculate tax for draft order or cart data (Simple version).
    
    For advanced multi-jurisdiction calculations, use /calculations/calculate

    - **location**: Location for jurisdiction-based tax rules
    - **order_items**: List of items with quantities and prices
    - **customer_exemptions**: Optional tax exemptions to apply

    Returns detailed tax breakdown by line item and total amounts.
    """
    return await calculate_tax_preview(request, db)
