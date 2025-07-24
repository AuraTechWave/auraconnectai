from sqlalchemy.orm import Session
from ..services.tax_engine import TaxEngine
from ..schemas.tax_schemas import TaxCalculationRequest, TaxCalculationResponse


async def calculate_tax_preview(
    request: TaxCalculationRequest,
    db: Session
) -> TaxCalculationResponse:
    tax_engine = TaxEngine(db)
    return await tax_engine.calculate_tax(request)
