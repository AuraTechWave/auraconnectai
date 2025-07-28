# backend/core/inventory_schemas.py

from pydantic import BaseModel, Field, validator
from typing import Optional, List, Dict, Any
from datetime import datetime, date
from enum import Enum

from .inventory_models import AlertStatus, AlertPriority, AdjustmentType, VendorStatus


# Vendor schemas
class VendorBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    description: Optional[str] = None
    contact_person: Optional[str] = Field(None, max_length=100)
    email: Optional[str] = Field(None, max_length=100)
    phone: Optional[str] = Field(None, max_length=20)
    address_line1: Optional[str] = Field(None, max_length=200)
    address_line2: Optional[str] = Field(None, max_length=200)
    city: Optional[str] = Field(None, max_length=100)
    state: Optional[str] = Field(None, max_length=50)
    postal_code: Optional[str] = Field(None, max_length=20)
    country: Optional[str] = Field(None, max_length=100)
    tax_id: Optional[str] = Field(None, max_length=50)
    payment_terms: Optional[str] = Field(None, max_length=100)
    delivery_lead_time: Optional[int] = Field(None, ge=0)
    minimum_order_amount: Optional[float] = Field(None, ge=0)
    status: VendorStatus = VendorStatus.ACTIVE
    rating: Optional[float] = Field(None, ge=1, le=5)
    notes: Optional[str] = None
    is_active: bool = True


class VendorCreate(VendorBase):
    pass


class VendorUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=200)
    description: Optional[str] = None
    contact_person: Optional[str] = Field(None, max_length=100)
    email: Optional[str] = Field(None, max_length=100)
    phone: Optional[str] = Field(None, max_length=20)
    address_line1: Optional[str] = Field(None, max_length=200)
    address_line2: Optional[str] = Field(None, max_length=200)
    city: Optional[str] = Field(None, max_length=100)
    state: Optional[str] = Field(None, max_length=50)
    postal_code: Optional[str] = Field(None, max_length=20)
    country: Optional[str] = Field(None, max_length=100)
    tax_id: Optional[str] = Field(None, max_length=50)
    payment_terms: Optional[str] = Field(None, max_length=100)
    delivery_lead_time: Optional[int] = Field(None, ge=0)
    minimum_order_amount: Optional[float] = Field(None, ge=0)
    status: Optional[VendorStatus] = None
    rating: Optional[float] = Field(None, ge=1, le=5)
    notes: Optional[str] = None
    is_active: Optional[bool] = None


class Vendor(VendorBase):
    id: int
    created_by: Optional[int] = None
    created_at: datetime
    updated_at: datetime
    deleted_at: Optional[datetime] = None

    class Config:
        from_attributes = True


# Enhanced Inventory schemas
class InventoryBase(BaseModel):
    item_name: str = Field(..., min_length=1, max_length=200)
    description: Optional[str] = None
    sku: Optional[str] = Field(None, max_length=50)
    category: Optional[str] = Field(None, max_length=100)
    quantity: float = Field(..., ge=0)
    unit: str = Field(..., min_length=1, max_length=20)
    threshold: float = Field(..., ge=0)
    reorder_quantity: Optional[float] = Field(None, ge=0)
    max_quantity: Optional[float] = Field(None, ge=0)
    cost_per_unit: Optional[float] = Field(None, ge=0)
    last_purchase_price: Optional[float] = Field(None, ge=0)
    average_cost: Optional[float] = Field(None, ge=0)
    vendor_id: Optional[int] = None
    vendor_item_code: Optional[str] = Field(None, max_length=100)
    lead_time_days: Optional[int] = Field(None, ge=0)
    storage_location: Optional[str] = Field(None, max_length=100)
    storage_temperature: Optional[str] = Field(None, max_length=50)
    shelf_life_days: Optional[int] = Field(None, ge=0)
    track_expiration: bool = False
    track_batches: bool = False
    perishable: bool = False
    enable_low_stock_alerts: bool = True
    alert_threshold_percentage: Optional[float] = Field(None, ge=0, le=100)
    is_active: bool = True

    @validator('max_quantity')
    def validate_max_quantity(cls, v, values):
        if v is not None and 'threshold' in values and v < values['threshold']:
            raise ValueError('max_quantity must be >= threshold')
        return v


class InventoryCreate(InventoryBase):
    pass


class InventoryUpdate(BaseModel):
    item_name: Optional[str] = Field(None, min_length=1, max_length=200)
    description: Optional[str] = None
    sku: Optional[str] = Field(None, max_length=50)
    category: Optional[str] = Field(None, max_length=100)
    quantity: Optional[float] = Field(None, ge=0)
    unit: Optional[str] = Field(None, min_length=1, max_length=20)
    threshold: Optional[float] = Field(None, ge=0)
    reorder_quantity: Optional[float] = Field(None, ge=0)
    max_quantity: Optional[float] = Field(None, ge=0)
    cost_per_unit: Optional[float] = Field(None, ge=0)
    last_purchase_price: Optional[float] = Field(None, ge=0)
    average_cost: Optional[float] = Field(None, ge=0)
    vendor_id: Optional[int] = None
    vendor_item_code: Optional[str] = Field(None, max_length=100)
    lead_time_days: Optional[int] = Field(None, ge=0)
    storage_location: Optional[str] = Field(None, max_length=100)
    storage_temperature: Optional[str] = Field(None, max_length=50)
    shelf_life_days: Optional[int] = Field(None, ge=0)
    track_expiration: Optional[bool] = None
    track_batches: Optional[bool] = None
    perishable: Optional[bool] = None
    enable_low_stock_alerts: Optional[bool] = None
    alert_threshold_percentage: Optional[float] = Field(None, ge=0, le=100)
    is_active: Optional[bool] = None


class Inventory(InventoryBase):
    id: int
    last_counted_at: Optional[datetime] = None
    last_adjusted_at: Optional[datetime] = None
    created_by: Optional[int] = None
    created_at: datetime
    updated_at: datetime
    deleted_at: Optional[datetime] = None
    is_low_stock: bool = False
    stock_percentage: float = 0.0
    days_until_empty: int = 0

    class Config:
        from_attributes = True


class InventoryWithDetails(Inventory):
    vendor: Optional[Vendor] = None
    alerts: List['InventoryAlert'] = []
    recent_adjustments: List['InventoryAdjustment'] = []


# Alert schemas
class InventoryAlertBase(BaseModel):
    inventory_id: int
    alert_type: str = Field(..., max_length=50)
    priority: AlertPriority = AlertPriority.MEDIUM
    title: str = Field(..., min_length=1, max_length=200)
    message: str = Field(..., min_length=1)
    threshold_value: Optional[float] = None
    current_value: Optional[float] = None
    auto_resolve: bool = False
    expires_at: Optional[datetime] = None


class InventoryAlertCreate(InventoryAlertBase):
    pass


class InventoryAlert(InventoryAlertBase):
    id: int
    status: AlertStatus
    acknowledged_by: Optional[int] = None
    acknowledged_at: Optional[datetime] = None
    resolved_by: Optional[int] = None
    resolved_at: Optional[datetime] = None
    resolution_notes: Optional[str] = None
    created_by: Optional[int] = None
    created_at: datetime
    updated_at: datetime
    is_active: bool

    class Config:
        from_attributes = True


class InventoryAlertWithItem(InventoryAlert):
    inventory_item: Inventory


# Adjustment schemas
class InventoryAdjustmentBase(BaseModel):
    inventory_id: int
    adjustment_type: AdjustmentType
    quantity_adjusted: float
    reason: str = Field(..., min_length=1, max_length=500)
    unit_cost: Optional[float] = Field(None, ge=0)
    reference_type: Optional[str] = Field(None, max_length=50)
    reference_id: Optional[str] = Field(None, max_length=100)
    batch_number: Optional[str] = Field(None, max_length=100)
    expiration_date: Optional[datetime] = None
    notes: Optional[str] = None
    location: Optional[str] = Field(None, max_length=100)


class InventoryAdjustmentCreate(InventoryAdjustmentBase):
    pass


class InventoryAdjustment(InventoryAdjustmentBase):
    id: int
    quantity_before: float
    quantity_after: float
    unit: str
    total_cost: Optional[float] = None
    requires_approval: bool
    approved_by: Optional[int] = None
    approved_at: Optional[datetime] = None
    approval_notes: Optional[str] = None
    created_by: int
    created_at: datetime
    updated_at: datetime
    is_active: bool

    class Config:
        from_attributes = True


class InventoryAdjustmentWithItem(InventoryAdjustment):
    inventory_item: Inventory


# Usage tracking schemas
class InventoryUsageLogBase(BaseModel):
    inventory_id: int
    menu_item_id: Optional[int] = None
    quantity_used: float = Field(..., gt=0)
    order_id: Optional[int] = None
    order_item_id: Optional[int] = None
    location: Optional[str] = Field(None, max_length=100)
    station: Optional[str] = Field(None, max_length=50)
    shift: Optional[str] = Field(None, max_length=20)
    notes: Optional[str] = None


class InventoryUsageLogCreate(InventoryUsageLogBase):
    pass


class InventoryUsageLog(InventoryUsageLogBase):
    id: int
    unit: str
    order_date: datetime
    unit_cost: Optional[float] = None
    total_cost: Optional[float] = None
    created_by: Optional[int] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# Purchase Order schemas
class PurchaseOrderBase(BaseModel):
    vendor_id: int
    po_number: Optional[str] = None
    expected_delivery_date: Optional[datetime] = None
    subtotal: float = Field(default=0.0, ge=0)
    tax_amount: float = Field(default=0.0, ge=0)
    shipping_cost: float = Field(default=0.0, ge=0)
    delivery_address: Optional[str] = None
    delivery_instructions: Optional[str] = None
    notes: Optional[str] = None


class PurchaseOrderCreate(PurchaseOrderBase):
    pass


class PurchaseOrderUpdate(BaseModel):
    vendor_id: Optional[int] = None
    status: Optional[str] = None
    expected_delivery_date: Optional[datetime] = None
    actual_delivery_date: Optional[datetime] = None
    subtotal: Optional[float] = Field(None, ge=0)
    tax_amount: Optional[float] = Field(None, ge=0)
    shipping_cost: Optional[float] = Field(None, ge=0)
    delivery_address: Optional[str] = None
    delivery_instructions: Optional[str] = None
    tracking_number: Optional[str] = None
    notes: Optional[str] = None
    internal_notes: Optional[str] = None


class PurchaseOrder(PurchaseOrderBase):
    id: int
    po_number: str
    status: str
    order_date: datetime
    actual_delivery_date: Optional[datetime] = None
    total_amount: float
    tracking_number: Optional[str] = None
    internal_notes: Optional[str] = None
    created_by: int
    approved_by: Optional[int] = None
    approved_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime
    is_active: bool

    class Config:
        from_attributes = True


class PurchaseOrderItemBase(BaseModel):
    inventory_id: int
    quantity_ordered: float = Field(..., gt=0)
    unit_cost: float = Field(..., ge=0)
    batch_number: Optional[str] = Field(None, max_length=100)
    expiration_date: Optional[datetime] = None
    notes: Optional[str] = None


class PurchaseOrderItemCreate(PurchaseOrderItemBase):
    pass


class PurchaseOrderItem(PurchaseOrderItemBase):
    id: int
    purchase_order_id: int
    quantity_received: float
    unit: str
    total_cost: float
    quality_rating: Optional[int] = None
    condition_notes: Optional[str] = None
    status: str
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class PurchaseOrderWithItems(PurchaseOrder):
    vendor: Vendor
    items: List[PurchaseOrderItem] = []


# Count schemas
class InventoryCountBase(BaseModel):
    count_number: Optional[str] = None
    count_type: str = Field(..., max_length=20)
    location: Optional[str] = Field(None, max_length=100)
    notes: Optional[str] = None


class InventoryCountCreate(InventoryCountBase):
    pass


class InventoryCount(InventoryCountBase):
    id: int
    count_date: datetime
    status: str
    total_items_counted: int
    total_discrepancies: int
    total_value_variance: float
    counted_by: int
    verified_by: Optional[int] = None
    approved_by: Optional[int] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    discrepancy_notes: Optional[str] = None
    created_by: int
    created_at: datetime
    updated_at: datetime
    is_active: bool

    class Config:
        from_attributes = True


class InventoryCountItemBase(BaseModel):
    inventory_id: int
    counted_quantity: float = Field(..., ge=0)
    batch_number: Optional[str] = Field(None, max_length=100)
    expiration_date: Optional[datetime] = None
    location: Optional[str] = Field(None, max_length=100)
    condition: Optional[str] = Field(None, max_length=50)
    notes: Optional[str] = None


class InventoryCountItemCreate(InventoryCountItemBase):
    pass


class InventoryCountItem(InventoryCountItemBase):
    id: int
    inventory_count_id: int
    system_quantity: float
    variance: float
    unit: str
    unit_cost: Optional[float] = None
    variance_value: Optional[float] = None
    counted_by: int
    verified_by: Optional[int] = None
    count_timestamp: datetime
    adjustment_created: bool
    adjustment_id: Optional[int] = None

    class Config:
        from_attributes = True


# Search and filter schemas
class InventorySearchParams(BaseModel):
    query: Optional[str] = None
    category: Optional[str] = None
    vendor_id: Optional[int] = None
    low_stock_only: Optional[bool] = None
    active_only: Optional[bool] = True
    limit: int = Field(default=50, ge=1, le=500)
    offset: int = Field(default=0, ge=0)
    sort_by: Optional[str] = Field(default="item_name", regex=r'^(item_name|quantity|threshold|category|created_at)$')
    sort_order: Optional[str] = Field(default="asc", regex=r'^(asc|desc)$')


class AlertSearchParams(BaseModel):
    status: Optional[AlertStatus] = None
    priority: Optional[AlertPriority] = None
    alert_type: Optional[str] = None
    inventory_id: Optional[int] = None
    limit: int = Field(default=50, ge=1, le=500)
    offset: int = Field(default=0, ge=0)


# Analytics schemas
class InventoryAnalytics(BaseModel):
    total_usage: float
    total_cost: float
    average_daily_usage: float
    usage_count: int


class InventoryDashboardStats(BaseModel):
    total_items: int
    low_stock_items: int
    pending_alerts: int
    total_inventory_value: float
    stock_percentage: float


class UsageReportParams(BaseModel):
    inventory_id: Optional[int] = None
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    group_by: Optional[str] = Field(default="day", regex=r'^(day|week|month)$')


# Bulk operation schemas
class BulkAdjustmentRequest(BaseModel):
    adjustments: List[InventoryAdjustmentCreate]
    reason: str = Field(..., min_length=1)
    notes: Optional[str] = None


class BulkInventoryUpdate(BaseModel):
    inventory_ids: List[int]
    updates: InventoryUpdate


# Response schemas
class PaginatedResponse(BaseModel):
    items: List[Any]
    total: int
    page: int
    size: int
    pages: int


class InventoryResponse(PaginatedResponse):
    items: List[Inventory]


class AlertResponse(PaginatedResponse):
    items: List[InventoryAlert]


class AdjustmentResponse(PaginatedResponse):
    items: List[InventoryAdjustment]


# Update forward references
InventoryWithDetails.model_rebuild()
InventoryAlertWithItem.model_rebuild()
InventoryAdjustmentWithItem.model_rebuild()
PurchaseOrderWithItems.model_rebuild()