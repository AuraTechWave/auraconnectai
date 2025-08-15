# backend/modules/inventory/routes/vendor_routes.py

from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from typing import List, Optional
from math import ceil

from core.database import get_db
from core.inventory_service import InventoryService
from core.inventory_schemas import (
    Vendor,
    VendorCreate,
    VendorUpdate,
    PurchaseOrder,
    PurchaseOrderCreate,
    PurchaseOrderUpdate,
    PurchaseOrderWithItems,
    PurchaseOrderItem,
    PurchaseOrderItemCreate,
    VendorStatus,
)
from core.auth import require_permission, User


router = APIRouter(prefix="/vendors", tags=["Vendor Management"])


def get_inventory_service(db: Session = Depends(get_db)) -> InventoryService:
    """Dependency to get inventory service instance"""
    return InventoryService(db)


# Vendor Management
@router.post("/", response_model=Vendor, status_code=status.HTTP_201_CREATED)
async def create_vendor(
    vendor_data: VendorCreate,
    inventory_service: InventoryService = Depends(get_inventory_service),
    current_user: User = Depends(require_permission("inventory:create")),
):
    """Create a new vendor"""
    return inventory_service.create_vendor(vendor_data.dict(), current_user.id)


@router.get("/", response_model=List[Vendor])
async def get_vendors(
    active_only: bool = Query(True, description="Show only active vendors"),
    status_filter: Optional[VendorStatus] = Query(
        None, description="Filter by vendor status"
    ),
    search: Optional[str] = Query(None, description="Search vendors by name"),
    inventory_service: InventoryService = Depends(get_inventory_service),
    current_user: User = Depends(require_permission("inventory:read")),
):
    """Get all vendors"""
    vendors = inventory_service.get_vendors(active_only)

    # Apply additional filters
    if status_filter:
        vendors = [v for v in vendors if v.status == status_filter]

    if search:
        search_term = search.lower()
        vendors = [
            v
            for v in vendors
            if search_term in v.name.lower()
            or (v.contact_person and search_term in v.contact_person.lower())
        ]

    return vendors


@router.get("/{vendor_id}", response_model=Vendor)
async def get_vendor(
    vendor_id: int,
    inventory_service: InventoryService = Depends(get_inventory_service),
    current_user: User = Depends(require_permission("inventory:read")),
):
    """Get vendor by ID"""
    vendor = inventory_service.get_vendor_by_id(vendor_id)
    if not vendor:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Vendor not found"
        )
    return vendor


@router.put("/{vendor_id}", response_model=Vendor)
async def update_vendor(
    vendor_id: int,
    vendor_data: VendorUpdate,
    inventory_service: InventoryService = Depends(get_inventory_service),
    current_user: User = Depends(require_permission("inventory:update")),
):
    """Update vendor"""
    vendor = inventory_service.get_vendor_by_id(vendor_id)
    if not vendor:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Vendor not found"
        )

    update_data = vendor_data.dict(exclude_unset=True)
    for key, value in update_data.items():
        setattr(vendor, key, value)

    inventory_service.db.commit()
    inventory_service.db.refresh(vendor)

    return vendor


@router.delete("/{vendor_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_vendor(
    vendor_id: int,
    inventory_service: InventoryService = Depends(get_inventory_service),
    current_user: User = Depends(require_permission("inventory:delete")),
):
    """Soft delete vendor"""
    vendor = inventory_service.get_vendor_by_id(vendor_id)
    if not vendor:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Vendor not found"
        )

    from datetime import datetime

    vendor.deleted_at = datetime.utcnow()
    vendor.is_active = False
    inventory_service.db.commit()


@router.get("/{vendor_id}/inventory", response_model=List[dict])
async def get_vendor_inventory(
    vendor_id: int,
    inventory_service: InventoryService = Depends(get_inventory_service),
    current_user: User = Depends(require_permission("inventory:read")),
):
    """Get inventory items supplied by vendor"""
    from core.inventory_models import Inventory

    items = (
        inventory_service.db.query(Inventory)
        .filter(
            Inventory.vendor_id == vendor_id,
            Inventory.is_active == True,
            Inventory.deleted_at.is_(None),
        )
        .all()
    )

    return [
        {
            "id": item.id,
            "item_name": item.item_name,
            "sku": item.sku,
            "vendor_item_code": item.vendor_item_code,
            "quantity": item.quantity,
            "threshold": item.threshold,
            "is_low_stock": item.is_low_stock,
            "cost_per_unit": item.cost_per_unit,
            "lead_time_days": item.lead_time_days,
        }
        for item in items
    ]


# Purchase Order Management
@router.post(
    "/{vendor_id}/purchase-orders",
    response_model=PurchaseOrder,
    status_code=status.HTTP_201_CREATED,
)
async def create_purchase_order(
    vendor_id: int,
    po_data: PurchaseOrderCreate,
    inventory_service: InventoryService = Depends(get_inventory_service),
    current_user: User = Depends(require_permission("inventory:create")),
):
    """Create purchase order for vendor"""
    # Verify vendor exists
    vendor = inventory_service.get_vendor_by_id(vendor_id)
    if not vendor:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Vendor not found"
        )

    po_dict = po_data.dict()
    po_dict["vendor_id"] = vendor_id

    return inventory_service.create_purchase_order(po_dict, current_user.id)


@router.get("/{vendor_id}/purchase-orders", response_model=List[PurchaseOrder])
async def get_vendor_purchase_orders(
    vendor_id: int,
    status_filter: Optional[str] = Query(None, description="Filter by PO status"),
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    inventory_service: InventoryService = Depends(get_inventory_service),
    current_user: User = Depends(require_permission("inventory:read")),
):
    """Get purchase orders for vendor"""
    from core.inventory_models import PurchaseOrder

    query = inventory_service.db.query(PurchaseOrder).filter(
        PurchaseOrder.vendor_id == vendor_id, PurchaseOrder.is_active == True
    )

    if status_filter:
        query = query.filter(PurchaseOrder.status == status_filter)

    return (
        query.order_by(PurchaseOrder.order_date.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )


@router.get(
    "/{vendor_id}/purchase-orders/{po_id}", response_model=PurchaseOrderWithItems
)
async def get_purchase_order(
    vendor_id: int,
    po_id: int,
    inventory_service: InventoryService = Depends(get_inventory_service),
    current_user: User = Depends(require_permission("inventory:read")),
):
    """Get specific purchase order with items"""
    from core.inventory_models import PurchaseOrder
    from sqlalchemy.orm import joinedload

    po = (
        inventory_service.db.query(PurchaseOrder)
        .options(joinedload(PurchaseOrder.vendor), joinedload(PurchaseOrder.items))
        .filter(
            PurchaseOrder.id == po_id,
            PurchaseOrder.vendor_id == vendor_id,
            PurchaseOrder.is_active == True,
        )
        .first()
    )

    if not po:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Purchase order not found"
        )

    return po


@router.put("/{vendor_id}/purchase-orders/{po_id}", response_model=PurchaseOrder)
async def update_purchase_order(
    vendor_id: int,
    po_id: int,
    po_data: PurchaseOrderUpdate,
    inventory_service: InventoryService = Depends(get_inventory_service),
    current_user: User = Depends(require_permission("inventory:update")),
):
    """Update purchase order"""
    from core.inventory_models import PurchaseOrder

    po = (
        inventory_service.db.query(PurchaseOrder)
        .filter(
            PurchaseOrder.id == po_id,
            PurchaseOrder.vendor_id == vendor_id,
            PurchaseOrder.is_active == True,
        )
        .first()
    )

    if not po:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Purchase order not found"
        )

    update_data = po_data.dict(exclude_unset=True)
    for key, value in update_data.items():
        setattr(po, key, value)

    inventory_service.db.commit()
    inventory_service.db.refresh(po)

    return po


@router.post(
    "/{vendor_id}/purchase-orders/{po_id}/items", response_model=PurchaseOrderItem
)
async def add_item_to_purchase_order(
    vendor_id: int,
    po_id: int,
    item_data: PurchaseOrderItemCreate,
    inventory_service: InventoryService = Depends(get_inventory_service),
    current_user: User = Depends(require_permission("inventory:update")),
):
    """Add item to purchase order"""
    from core.inventory_models import PurchaseOrder

    # Verify PO exists and belongs to vendor
    po = (
        inventory_service.db.query(PurchaseOrder)
        .filter(
            PurchaseOrder.id == po_id,
            PurchaseOrder.vendor_id == vendor_id,
            PurchaseOrder.is_active == True,
        )
        .first()
    )

    if not po:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Purchase order not found"
        )

    # Verify inventory item exists
    inventory_item = inventory_service.get_inventory_by_id(item_data.inventory_id)
    if not inventory_item:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Inventory item not found"
        )

    item_dict = item_data.dict()
    item_dict["total_cost"] = item_data.quantity_ordered * item_data.unit_cost
    item_dict["unit"] = inventory_item.unit

    return inventory_service.add_item_to_purchase_order(po_id, item_dict)


@router.post(
    "/{vendor_id}/purchase-orders/{po_id}/receive", response_model=PurchaseOrder
)
async def receive_purchase_order(
    vendor_id: int,
    po_id: int,
    received_items: List[
        dict
    ],  # List of {item_id, quantity_received, quality_rating, condition_notes}
    inventory_service: InventoryService = Depends(get_inventory_service),
    current_user: User = Depends(require_permission("inventory:update")),
):
    """Receive items from purchase order and update inventory"""
    from core.inventory_models import PurchaseOrder, PurchaseOrderItem
    from core.inventory_schemas import AdjustmentType
    from datetime import datetime

    # Get purchase order
    po = (
        inventory_service.db.query(PurchaseOrder)
        .filter(
            PurchaseOrder.id == po_id,
            PurchaseOrder.vendor_id == vendor_id,
            PurchaseOrder.is_active == True,
        )
        .first()
    )

    if not po:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Purchase order not found"
        )

    # Process received items
    for received_item in received_items:
        po_item = (
            inventory_service.db.query(PurchaseOrderItem)
            .filter(
                PurchaseOrderItem.purchase_order_id == po_id,
                PurchaseOrderItem.id == received_item["item_id"],
            )
            .first()
        )

        if po_item:
            # Update PO item
            po_item.quantity_received = received_item["quantity_received"]
            po_item.quality_rating = received_item.get("quality_rating")
            po_item.condition_notes = received_item.get("condition_notes")
            po_item.status = (
                "received"
                if po_item.quantity_received >= po_item.quantity_ordered
                else "partial"
            )

            # Update inventory
            if received_item["quantity_received"] > 0:
                inventory_service.adjust_inventory_quantity(
                    inventory_id=po_item.inventory_id,
                    adjustment_type=AdjustmentType.PURCHASE,
                    quantity=received_item["quantity_received"],
                    reason=f"Received from PO {po.po_number}",
                    user_id=current_user.id,
                    unit_cost=po_item.unit_cost,
                    reference_type="purchase_order",
                    reference_id=po.po_number,
                )

    # Update PO status
    all_items = (
        inventory_service.db.query(PurchaseOrderItem)
        .filter(PurchaseOrderItem.purchase_order_id == po_id)
        .all()
    )

    if all(item.quantity_received >= item.quantity_ordered for item in all_items):
        po.status = "received"
    elif any(item.quantity_received > 0 for item in all_items):
        po.status = "partial"

    po.actual_delivery_date = datetime.utcnow()

    inventory_service.db.commit()
    inventory_service.db.refresh(po)

    return po


# Vendor Analytics
@router.get("/{vendor_id}/analytics")
async def get_vendor_analytics(
    vendor_id: int,
    start_date: Optional[str] = Query(None, description="Start date (YYYY-MM-DD)"),
    end_date: Optional[str] = Query(None, description="End date (YYYY-MM-DD)"),
    inventory_service: InventoryService = Depends(get_inventory_service),
    current_user: User = Depends(require_permission("inventory:read")),
):
    """Get vendor performance analytics"""
    from core.inventory_models import PurchaseOrder, PurchaseOrderItem
    from sqlalchemy import func
    from datetime import datetime

    # Parse dates
    start_dt = datetime.strptime(start_date, "%Y-%m-%d") if start_date else None
    end_dt = datetime.strptime(end_date, "%Y-%m-%d") if end_date else None

    # Basic vendor info
    vendor = inventory_service.get_vendor_by_id(vendor_id)
    if not vendor:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Vendor not found"
        )

    # Purchase order statistics
    po_query = inventory_service.db.query(PurchaseOrder).filter(
        PurchaseOrder.vendor_id == vendor_id, PurchaseOrder.is_active == True
    )

    if start_dt:
        po_query = po_query.filter(PurchaseOrder.order_date >= start_dt)
    if end_dt:
        po_query = po_query.filter(PurchaseOrder.order_date <= end_dt)

    total_orders = po_query.count()
    total_amount = (
        po_query.with_entities(func.sum(PurchaseOrder.total_amount)).scalar() or 0
    )

    # On-time delivery rate
    completed_orders = po_query.filter(PurchaseOrder.status == "received").all()
    on_time_deliveries = len(
        [
            po
            for po in completed_orders
            if po.actual_delivery_date
            and po.expected_delivery_date
            and po.actual_delivery_date <= po.expected_delivery_date
        ]
    )

    on_time_rate = (
        (on_time_deliveries / len(completed_orders)) * 100 if completed_orders else 0
    )

    # Average order value
    avg_order_value = total_amount / total_orders if total_orders > 0 else 0

    # Item performance
    items_supplied = (
        inventory_service.db.query(
            func.count(
                func.distinct(
                    inventory_service.db.query(PurchaseOrderItem.inventory_id)
                    .join(PurchaseOrder)
                    .filter(PurchaseOrder.vendor_id == vendor_id)
                    .subquery()
                    .c.inventory_id
                )
            )
        ).scalar()
        or 0
    )

    # --- New supplier performance metrics ---
    # Average delivery time (days) between order date and actual delivery date for completed orders
    delivery_deltas = [
        (po.actual_delivery_date - po.order_date).days
        for po in completed_orders
        if po.actual_delivery_date
    ]
    avg_delivery_days = (
        sum(delivery_deltas) / len(delivery_deltas) if delivery_deltas else 0
    )

    # Average quality rating across all received PO items
    quality_query = (
        inventory_service.db.query(func.avg(PurchaseOrderItem.quality_rating))
        .join(PurchaseOrder)
        .filter(PurchaseOrder.vendor_id == vendor_id)
    )
    if start_dt:
        quality_query = quality_query.filter(PurchaseOrder.order_date >= start_dt)
    if end_dt:
        quality_query = quality_query.filter(PurchaseOrder.order_date <= end_dt)
    avg_quality_rating = quality_query.scalar() or 0

    # Count of quality issues (quality rating <= 2)
    quality_issue_query = (
        inventory_service.db.query(func.count(PurchaseOrderItem.id))
        .join(PurchaseOrder)
        .filter(
            PurchaseOrder.vendor_id == vendor_id, PurchaseOrderItem.quality_rating <= 2
        )
    )
    if start_dt:
        quality_issue_query = quality_issue_query.filter(
            PurchaseOrder.order_date >= start_dt
        )
    if end_dt:
        quality_issue_query = quality_issue_query.filter(
            PurchaseOrder.order_date <= end_dt
        )
    quality_issues_count = quality_issue_query.scalar() or 0

    # Average price change percentage across items (max vs. min unit cost)
    cost_subquery = (
        inventory_service.db.query(
            PurchaseOrderItem.inventory_id,
            func.min(PurchaseOrderItem.unit_cost).label("min_cost"),
            func.max(PurchaseOrderItem.unit_cost).label("max_cost"),
        )
        .join(PurchaseOrder)
        .filter(PurchaseOrder.vendor_id == vendor_id)
    )
    if start_dt:
        cost_subquery = cost_subquery.filter(PurchaseOrder.order_date >= start_dt)
    if end_dt:
        cost_subquery = cost_subquery.filter(PurchaseOrder.order_date <= end_dt)
    cost_subquery = cost_subquery.group_by(PurchaseOrderItem.inventory_id).subquery()

    avg_price_change_percent = (
        inventory_service.db.query(
            func.avg(
                (
                    (cost_subquery.c.max_cost - cost_subquery.c.min_cost)
                    / func.nullif(cost_subquery.c.min_cost, 0)
                )
                * 100
            )
        ).scalar()
        or 0
    )
    # --- End new metrics ---

    return {
        "vendor": {
            "id": vendor.id,
            "name": vendor.name,
            "rating": vendor.rating,
            "status": vendor.status,
        },
        "period": {"start_date": start_date, "end_date": end_date},
        "metrics": {
            "total_orders": total_orders,
            "total_amount": float(total_amount),
            "average_order_value": float(avg_order_value),
            "on_time_delivery_rate": round(on_time_rate, 2),
            "items_supplied": items_supplied,
            "active_inventory_items": (
                len(
                    [
                        item
                        for item in vendor.inventory_items
                        if item.is_active and not item.deleted_at
                    ]
                )
                if hasattr(vendor, "inventory_items")
                else 0
            ),
            # New metrics
            "average_delivery_days": round(avg_delivery_days, 2),
            "average_quality_rating": (
                round(avg_quality_rating, 2) if avg_quality_rating else 0
            ),
            "quality_issues": quality_issues_count,
            "average_price_change_percent": (
                round(avg_price_change_percent, 2) if avg_price_change_percent else 0
            ),
        },
    }


# Vendor Performance Rating
@router.post("/{vendor_id}/rate", response_model=Vendor)
async def rate_vendor(
    vendor_id: int,
    rating: float = Query(..., ge=1, le=5, description="Rating from 1 to 5"),
    notes: Optional[str] = Query(None, description="Rating notes"),
    inventory_service: InventoryService = Depends(get_inventory_service),
    current_user: User = Depends(require_permission("inventory:update")),
):
    """Rate vendor performance"""
    vendor = inventory_service.get_vendor_by_id(vendor_id)
    if not vendor:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Vendor not found"
        )

    # Update rating (could be enhanced to track rating history)
    vendor.rating = rating
    if notes:
        vendor.notes = (
            f"{vendor.notes}\n\nRating Update: {rating}/5 - {notes}"
            if vendor.notes
            else f"Rating: {rating}/5 - {notes}"
        )

    inventory_service.db.commit()
    inventory_service.db.refresh(vendor)

    return vendor
