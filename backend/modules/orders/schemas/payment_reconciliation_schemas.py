from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime
from decimal import Decimal
from ..enums.payment_enums import (
    ReconciliationStatus,
    DiscrepancyType,
    ReconciliationAction,
)


class PaymentReconciliationBase(BaseModel):
    order_id: int
    external_payment_reference: str = Field(..., min_length=1, max_length=255)
    amount_expected: Decimal = Field(..., gt=0)
    amount_received: Decimal = Field(..., gt=0)
    reconciliation_status: ReconciliationStatus


class PaymentReconciliationCreate(PaymentReconciliationBase):
    discrepancy_type: Optional[DiscrepancyType] = None
    discrepancy_details: Optional[str] = None


class PaymentReconciliationUpdate(BaseModel):
    reconciliation_status: Optional[ReconciliationStatus] = None
    discrepancy_type: Optional[DiscrepancyType] = None
    discrepancy_details: Optional[str] = None
    reconciliation_action: Optional[ReconciliationAction] = None
    resolution_notes: Optional[str] = None
    resolved_by: Optional[int] = None


class PaymentReconciliationOut(PaymentReconciliationBase):
    id: int
    discrepancy_type: Optional[DiscrepancyType] = None
    discrepancy_details: Optional[str] = None
    reconciliation_action: Optional[ReconciliationAction] = None
    resolution_notes: Optional[str] = None
    resolved_at: Optional[datetime] = None
    resolved_by: Optional[int] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class ReconciliationRequest(BaseModel):
    order_ids: Optional[List[int]] = None
    external_payment_references: Optional[List[str]] = None
    amount_threshold: Optional[Decimal] = Field(default=Decimal("0.01"), gt=0)


class ReconciliationResponse(BaseModel):
    total_processed: int
    matched_count: int
    discrepancy_count: int
    reconciliations: List[PaymentReconciliationOut]


class ReconciliationFilter(BaseModel):
    reconciliation_status: Optional[ReconciliationStatus] = None
    discrepancy_type: Optional[DiscrepancyType] = None
    order_id: Optional[int] = None
    from_date: Optional[datetime] = None
    to_date: Optional[datetime] = None
    limit: int = Field(default=100, le=1000)
    offset: int = Field(default=0, ge=0)


class ResolutionRequest(BaseModel):
    reconciliation_action: ReconciliationAction
    resolution_notes: Optional[str] = None
    resolved_by: int


class ReconciliationMetrics(BaseModel):
    total_reconciled: int
    matched_count: int
    discrepancy_count: int
    resolved_count: int
    success_rate: float
    common_discrepancy_types: List[Dict[str, Any]]


class AutoReconcileResponse(BaseModel):
    total_processed: int
    auto_matched: int
    remaining_pending: int


class PaymentWebhookData(BaseModel):
    reference: str = Field(..., min_length=1)
    order_reference: str = Field(..., min_length=1)
    amount: Decimal = Field(..., gt=0)
    payment_method: Optional[str] = None
    timestamp: Optional[datetime] = None
    status: Optional[str] = None


class WebhookResponse(BaseModel):
    status: str
    reconciliation_id: Optional[int] = None
    reconciliation_status: Optional[str] = None
    message: str
