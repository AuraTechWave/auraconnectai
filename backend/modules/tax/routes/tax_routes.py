from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from backend.core.database import get_db
from ..controllers.tax_controller import calculate_tax_preview
from ..schemas.tax_schemas import TaxCalculationRequest, TaxCalculationResponse

router = APIRouter(prefix="/tax", tags=["Tax"])


@router.post("/calculate", response_model=TaxCalculationResponse)
async def calculate_tax(
    request: TaxCalculationRequest,
    db: Session = Depends(get_db)
):
    """
    Calculate tax for draft order or cart data.

    - **location**: Location for jurisdiction-based tax rules
    - **order_items**: List of items with quantities and prices
    - **customer_exemptions**: Optional tax exemptions to apply

    Returns detailed tax breakdown by line item and total amounts.
    """
    return await calculate_tax_preview(request, db)
