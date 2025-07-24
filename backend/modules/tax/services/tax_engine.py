from sqlalchemy.orm import Session
from typing import List
from decimal import Decimal
from ..models.tax_models import TaxRule
from ..schemas.tax_schemas import (
    TaxCalculationRequest, TaxCalculationResponse,
    TaxBreakdownItem, TaxCalculationItem
)


class TaxEngine:
    def __init__(self, db: Session):
        self.db = db

    async def calculate_tax(
        self, request: TaxCalculationRequest
    ) -> TaxCalculationResponse:
        tax_rules = self.db.query(TaxRule).filter(
            TaxRule.location == request.location
        ).all()

        if not tax_rules:
            return self._create_zero_tax_response(request.order_items)

        breakdown = []
        subtotal = Decimal('0.00')
        total_tax = Decimal('0.00')
        applied_rules = []

        for item in request.order_items:
            item_subtotal = Decimal(str(item.price)) * item.quantity
            subtotal += item_subtotal

            tax_rule = tax_rules[0]
            tax_rate = tax_rule.rate_percent / 100
            item_tax = item_subtotal * tax_rate
            total_tax += item_tax

            breakdown.append(TaxBreakdownItem(
                menu_item_id=item.menu_item_id,
                subtotal=item_subtotal,
                tax_amount=item_tax,
                tax_rate=tax_rate
            ))

            if tax_rule.location not in applied_rules:
                rule_desc = f"{tax_rule.location} - {tax_rule.rate_percent}%"
                applied_rules.append(rule_desc)

        return TaxCalculationResponse(
            subtotal=subtotal,
            total_tax=total_tax,
            total_amount=subtotal + total_tax,
            breakdown=breakdown,
            applied_rules=applied_rules
        )
    
    def _create_zero_tax_response(
        self, items: List[TaxCalculationItem]
    ) -> TaxCalculationResponse:
        breakdown = []
        subtotal = Decimal('0.00')

        for item in items:
            item_subtotal = Decimal(str(item.price)) * item.quantity
            subtotal += item_subtotal
            breakdown.append(TaxBreakdownItem(
                menu_item_id=item.menu_item_id,
                subtotal=item_subtotal,
                tax_amount=Decimal('0.00'),
                tax_rate=Decimal('0.00')
            ))

        return TaxCalculationResponse(
            subtotal=subtotal,
            total_tax=Decimal('0.00'),
            total_amount=subtotal,
            breakdown=breakdown,
            applied_rules=[]
        )
