from pydantic import BaseModel
from typing import List, Optional
from decimal import Decimal


class TaxCalculationItem(BaseModel):
    menu_item_id: int
    quantity: int
    price: Decimal
    notes: Optional[str] = None


class TaxCalculationRequest(BaseModel):
    location: str
    order_items: List[TaxCalculationItem]
    customer_exemptions: Optional[List[str]] = []


class TaxBreakdownItem(BaseModel):
    menu_item_id: int
    subtotal: Decimal
    tax_amount: Decimal
    tax_rate: Decimal


class TaxCalculationResponse(BaseModel):
    subtotal: Decimal
    total_tax: Decimal
    total_amount: Decimal
    breakdown: List[TaxBreakdownItem]
    applied_rules: List[str]


class TaxRuleOut(BaseModel):
    id: int
    location: str
    category: str
    rate_percent: Decimal

    class Config:
        from_attributes = True
