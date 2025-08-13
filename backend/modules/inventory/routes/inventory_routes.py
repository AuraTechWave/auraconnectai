# backend/modules/inventory/routes/inventory_routes.py

from fastapi import APIRouter, Depends, HTTPException, status, Query, BackgroundTasks
from sqlalchemy.orm import Session
from typing import List, Optional
from math import ceil
from datetime import date, datetime

from core.database import get_db
from core.inventory_service import InventoryService
from core.inventory_schemas import (
    Inventory, InventoryCreate, InventoryUpdate, InventoryWithDetails,
    InventoryAlert, InventoryAlertCreate, InventoryAlertWithItem,
    InventoryAdjustment, InventoryAdjustmentCreate, InventoryAdjustmentWithItem,
    InventoryUsageLog, InventoryUsageLogCreate,
    InventorySearchParams, AlertSearchParams, 
    InventoryResponse, AlertResponse, AdjustmentResponse,
    InventoryDashboardStats, InventoryAnalytics, UsageReportParams,
    BulkAdjustmentRequest, BulkInventoryUpdate,
    AdjustmentType, AlertPriority, AlertStatus,
    WasteEventCreate, WasteEventResponse,
    PurchaseOrder
)
from core.inventory_models import WasteReason
from core.auth import require_permission, User


router = APIRouter(prefix="/inventory", tags=["Inventory Management"])


def get_inventory_service(db: Session = Depends(get_db)) -> InventoryService:
    """Dependency to get inventory service instance"""
    return InventoryService(db)


# Core Inventory Management
@router.post("/", response_model=Inventory, status_code=status.HTTP_201_CREATED)
async def create_inventory_item(
    item_data: InventoryCreate,
    inventory_service: InventoryService = Depends(get_inventory_service),
    current_user: User = Depends(require_permission("inventory:create"))
):
    """Create a new inventory item"""
    return inventory_service.create_inventory_item(item_data.dict(), current_user.id)


@router.get("/", response_model=InventoryResponse)
async def get_inventory_items(
    query: Optional[str] = Query(None, description="Search query"),
    category: Optional[str] = Query(None, description="Filter by category"),
    vendor_id: Optional[int] = Query(None, description="Filter by vendor"),
    low_stock_only: Optional[bool] = Query(None, description="Show only low stock items"),
    active_only: Optional[bool] = Query(True, description="Show only active items"),
    limit: int = Query(50, ge=1, le=500, description="Items per page"),
    offset: int = Query(0, ge=0, description="Items to skip"),
    sort_by: str = Query("item_name", pattern=r'^(item_name|quantity|threshold|category|created_at)$'),
    sort_order: str = Query("asc", pattern=r'^(asc|desc)$'),
    inventory_service: InventoryService = Depends(get_inventory_service),
    current_user: User = Depends(require_permission("inventory:read"))
):
    """Get inventory items with filtering and pagination"""
    items, total = inventory_service.get_inventory_items(
        active_only=active_only,
        low_stock_only=low_stock_only,
        category=category,
        vendor_id=vendor_id,
        search_query=query,
        limit=limit,
        offset=offset
    )
    
    pages = ceil(total / limit) if total > 0 else 0
    page = (offset // limit) + 1 if limit > 0 else 1
    
    return InventoryResponse(
        items=items,
        total=total,
        page=page,
        size=limit,
        pages=pages
    )


@router.get("/low-stock", response_model=List[Inventory])
async def get_low_stock_items(
    inventory_service: InventoryService = Depends(get_inventory_service),
    current_user: User = Depends(require_permission("inventory:read"))
):
    """Get items that are below their reorder threshold"""
    return inventory_service.get_low_stock_items()


@router.post("/auto-reorder", response_model=List[PurchaseOrder], status_code=status.HTTP_201_CREATED)
async def auto_reorder_low_stock_items(
    inventory_service: InventoryService = Depends(get_inventory_service),
    current_user: User = Depends(require_permission("inventory:create"))
):
    """Automatically create draft purchase orders for all low-stock items.

    The service groups low-stock inventory by vendor and generates a draft
    purchase order for each vendor.  The newly created purchase orders are
    returned so the caller can review and send them.
    """
    return inventory_service.auto_create_purchase_orders_for_low_stock(current_user.id)


@router.get("/dashboard", response_model=InventoryDashboardStats)
async def get_dashboard_stats(
    inventory_service: InventoryService = Depends(get_inventory_service),
    current_user: User = Depends(require_permission("inventory:read"))
):
    """Get inventory dashboard statistics"""
    return inventory_service.get_inventory_dashboard_stats()


@router.get("/{inventory_id}", response_model=InventoryWithDetails)
async def get_inventory_item(
    inventory_id: int,
    inventory_service: InventoryService = Depends(get_inventory_service),
    current_user: User = Depends(require_permission("inventory:read"))
):
    """Get inventory item by ID with details"""
    item = inventory_service.get_inventory_by_id(inventory_id)
    if not item:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Inventory item not found"
        )
    return item


@router.put("/{inventory_id}", response_model=Inventory)
async def update_inventory_item(
    inventory_id: int,
    item_data: InventoryUpdate,
    inventory_service: InventoryService = Depends(get_inventory_service),
    current_user: User = Depends(require_permission("inventory:update"))
):
    """Update inventory item"""
    return inventory_service.update_inventory_item(
        inventory_id, 
        item_data.dict(exclude_unset=True), 
        current_user.id
    )


@router.delete("/{inventory_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_inventory_item(
    inventory_id: int,
    inventory_service: InventoryService = Depends(get_inventory_service),
    current_user: User = Depends(require_permission("inventory:delete"))
):
    """Soft delete inventory item"""
    item = inventory_service.get_inventory_by_id(inventory_id)
    if not item:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Inventory item not found"
        )
    
    item.deleted_at = datetime.utcnow()
    inventory_service.db.commit()


# Inventory Adjustments
@router.post("/{inventory_id}/adjust", response_model=InventoryAdjustment)
async def adjust_inventory_quantity(
    inventory_id: int,
    adjustment_data: InventoryAdjustmentCreate,
    inventory_service: InventoryService = Depends(get_inventory_service),
    current_user: User = Depends(require_permission("inventory:update"))
):
    """Adjust inventory quantity with audit trail"""
    return inventory_service.adjust_inventory_quantity(
        inventory_id=inventory_id,
        adjustment_type=adjustment_data.adjustment_type,
        quantity=adjustment_data.quantity_adjusted,
        reason=adjustment_data.reason,
        user_id=current_user.id,
        unit_cost=adjustment_data.unit_cost,
        reference_type=adjustment_data.reference_type,
        reference_id=adjustment_data.reference_id,
        notes=adjustment_data.notes
    )


@router.get("/{inventory_id}/adjustments", response_model=List[InventoryAdjustment])
async def get_inventory_adjustments(
    inventory_id: int,
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    inventory_service: InventoryService = Depends(get_inventory_service),
    current_user: User = Depends(require_permission("inventory:read"))
):
    """Get adjustment history for inventory item"""
    adjustments = inventory_service.db.query(inventory_service.db.query(
        InventoryAdjustment.__class__
    )).filter(
        InventoryAdjustment.inventory_id == inventory_id,
        InventoryAdjustment.is_active == True
    ).order_by(InventoryAdjustment.created_at.desc()).offset(offset).limit(limit).all()
    
    return adjustments


@router.post("/adjustments/bulk", response_model=List[InventoryAdjustment])
async def bulk_adjust_inventory(
    bulk_request: BulkAdjustmentRequest,
    inventory_service: InventoryService = Depends(get_inventory_service),
    current_user: User = Depends(require_permission("inventory:update"))
):
    """Perform bulk inventory adjustments"""
    adjustments = []
    
    for adjustment_data in bulk_request.adjustments:
        try:
            adjustment = inventory_service.adjust_inventory_quantity(
                inventory_id=adjustment_data.inventory_id,
                adjustment_type=adjustment_data.adjustment_type,
                quantity=adjustment_data.quantity_adjusted,
                reason=f"{bulk_request.reason}: {adjustment_data.reason}",
                user_id=current_user.id,
                unit_cost=adjustment_data.unit_cost,
                reference_type=adjustment_data.reference_type,
                reference_id=adjustment_data.reference_id,
                notes=f"{bulk_request.notes}\n{adjustment_data.notes}" if bulk_request.notes else adjustment_data.notes
            )
            adjustments.append(adjustment)
        except Exception as e:
            # Log error but continue with other adjustments
            continue
    
    return adjustments


# Waste Tracking Endpoints
@router.post("/{inventory_id}/waste", response_model=WasteEventResponse, status_code=status.HTTP_201_CREATED)
async def record_waste_event(
    inventory_id: int,
    waste_data: WasteEventCreate,
    inventory_service: InventoryService = Depends(get_inventory_service),
    current_user: User = Depends(require_permission("inventory:update"))
):
    """
    Record a waste event for an inventory item
    
    - Validates that the inventory item exists
    - Ensures waste quantity doesn't exceed available stock
    - Creates proper audit trail
    - Triggers low stock alerts if necessary
    """
    # Check if inventory item exists
    item = inventory_service.get_inventory_by_id(inventory_id)
    if not item:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Inventory item with ID {inventory_id} not found"
        )
    
    # Validate waste_data.inventory_id matches the path parameter
    if waste_data.inventory_id != inventory_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Inventory ID in request body doesn't match path parameter"
        )
    
    # Check if there's enough quantity to waste
    if waste_data.quantity > item.quantity:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot waste {waste_data.quantity} {item.unit}. Only {item.quantity} {item.unit} available"
        )
    
    # Prepare the reason string
    reason = f"Waste - {waste_data.waste_reason.value}"
    if waste_data.waste_reason == WasteReason.OTHER and waste_data.custom_reason:
        reason = f"Waste - {waste_data.custom_reason}"
    
    # Create notes with additional metadata
    notes_parts = []
    if waste_data.witnessed_by:
        notes_parts.append(f"Witnessed by: {waste_data.witnessed_by}")
    if waste_data.temperature_at_waste:
        notes_parts.append(f"Temperature: {waste_data.temperature_at_waste}°F")
    if waste_data.batch_number:
        notes_parts.append(f"Batch: {waste_data.batch_number}")
    if waste_data.custom_reason and waste_data.waste_reason != WasteReason.OTHER:
        notes_parts.append(f"Additional notes: {waste_data.custom_reason}")
    
    notes = "\n".join(notes_parts) if notes_parts else None
    
    # Record the waste adjustment
    adjustment = inventory_service.adjust_inventory_quantity(
        inventory_id=inventory_id,
        adjustment_type=AdjustmentType.WASTE,
        quantity=-waste_data.quantity,  # Negative because we're removing from inventory
        reason=reason,
        user_id=current_user.id,
        unit_cost=item.cost_per_unit,
        reference_type="waste_event",
        reference_id=f"WASTE-{datetime.utcnow().strftime('%Y%m%d%H%M%S')}",
        batch_number=waste_data.batch_number,
        expiration_date=waste_data.expiration_date,
        location=waste_data.location,
        notes=notes
    )
    
    # Check and create alerts for low stock after waste
    updated_item = inventory_service.get_inventory_by_id(inventory_id)
    inventory_service.check_and_create_alerts(updated_item)
    
    # Prepare response
    # Note: In a real implementation, you'd want to get the user's name from the database
    return WasteEventResponse(
        id=adjustment.id,
        inventory_id=inventory_id,
        inventory_name=item.item_name,
        quantity_wasted=waste_data.quantity,
        unit=item.unit,
        waste_reason=waste_data.waste_reason,
        custom_reason=waste_data.custom_reason,
        total_cost=waste_data.quantity * (item.cost_per_unit or 0),
        created_by=current_user.id,
        created_by_name=f"User {current_user.id}",  # TODO: Get actual user name
        created_at=adjustment.created_at,
        location=waste_data.location,
        witnessed_by=waste_data.witnessed_by
    )


@router.get("/{inventory_id}/waste", response_model=List[WasteEventResponse])
async def get_waste_history(
    inventory_id: int,
    start_date: Optional[date] = Query(None, description="Start date for waste history"),
    end_date: Optional[date] = Query(None, description="End date for waste history"),
    waste_reason: Optional[WasteReason] = Query(None, description="Filter by waste reason"),
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    inventory_service: InventoryService = Depends(get_inventory_service),
    current_user: User = Depends(require_permission("inventory:read"))
):
    """
    Get waste history for a specific inventory item
    
    Returns all waste events with filtering options
    """
    # Check if inventory item exists
    item = inventory_service.get_inventory_by_id(inventory_id)
    if not item:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Inventory item with ID {inventory_id} not found"
        )
    
    # Query waste adjustments
    from core.inventory_models import InventoryAdjustment
    query = inventory_service.db.query(InventoryAdjustment).filter(
        InventoryAdjustment.inventory_id == inventory_id,
        InventoryAdjustment.adjustment_type == AdjustmentType.WASTE,
        InventoryAdjustment.is_active == True
    )
    
    if start_date:
        query = query.filter(InventoryAdjustment.created_at >= start_date)
    if end_date:
        query = query.filter(InventoryAdjustment.created_at <= end_date)
    if waste_reason:
        # Filter by reason containing the waste reason value
        query = query.filter(InventoryAdjustment.reason.like(f"%{waste_reason.value}%"))
    
    adjustments = query.order_by(InventoryAdjustment.created_at.desc()).offset(offset).limit(limit).all()
    
    # Convert to response format
    waste_events = []
    for adj in adjustments:
        # Parse waste reason from the reason field
        waste_reason_value = WasteReason.OTHER
        for wr in WasteReason:
            if wr.value in adj.reason.lower():
                waste_reason_value = wr
                break
        
        # Extract custom reason if it's OTHER
        custom_reason = None
        if waste_reason_value == WasteReason.OTHER:
            custom_reason = adj.reason.replace("Waste - ", "")
        
        # Extract witnessed_by from notes if present
        witnessed_by = None
        if adj.notes and "Witnessed by:" in adj.notes:
            for line in adj.notes.split("\n"):
                if line.startswith("Witnessed by:"):
                    witnessed_by = line.replace("Witnessed by:", "").strip()
                    break
        
        waste_events.append(WasteEventResponse(
            id=adj.id,
            inventory_id=inventory_id,
            inventory_name=item.item_name,
            quantity_wasted=abs(adj.quantity_change),  # Convert back to positive
            unit=adj.unit,
            waste_reason=waste_reason_value,
            custom_reason=custom_reason,
            total_cost=adj.total_cost or 0,
            created_by=adj.created_by,
            created_by_name=f"User {adj.created_by}",  # TODO: Get actual user name
            created_at=adj.created_at,
            location=adj.location,
            witnessed_by=witnessed_by
        ))
    
    return waste_events


# Inventory Alerts
@router.get("/alerts/", response_model=AlertResponse)
async def get_inventory_alerts(
    status: Optional[AlertStatus] = Query(None, description="Filter by status"),
    priority: Optional[AlertPriority] = Query(None, description="Filter by priority"),
    alert_type: Optional[str] = Query(None, description="Filter by alert type"),
    inventory_id: Optional[int] = Query(None, description="Filter by inventory item"),
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    inventory_service: InventoryService = Depends(get_inventory_service),
    current_user: User = Depends(require_permission("inventory:read"))
):
    """Get inventory alerts with filtering"""
    query = inventory_service.db.query(InventoryAlert).filter(
        InventoryAlert.is_active == True
    )
    
    if status:
        query = query.filter(InventoryAlert.status == status)
    if priority:
        query = query.filter(InventoryAlert.priority == priority)
    if alert_type:
        query = query.filter(InventoryAlert.alert_type == alert_type)
    if inventory_id:
        query = query.filter(InventoryAlert.inventory_id == inventory_id)
    
    total = query.count()
    alerts = query.order_by(
        InventoryAlert.priority.desc(),
        InventoryAlert.created_at.asc()
    ).offset(offset).limit(limit).all()
    
    pages = ceil(total / limit) if total > 0 else 0
    page = (offset // limit) + 1 if limit > 0 else 1
    
    return AlertResponse(
        items=alerts,
        total=total,
        page=page,
        size=limit,
        pages=pages
    )


@router.get("/alerts/active", response_model=List[InventoryAlertWithItem])
async def get_active_alerts(
    priority: Optional[AlertPriority] = Query(None, description="Filter by priority"),
    inventory_service: InventoryService = Depends(get_inventory_service),
    current_user: User = Depends(require_permission("inventory:read"))
):
    """Get active inventory alerts"""
    return inventory_service.get_active_alerts(priority)


@router.post("/alerts/{alert_id}/acknowledge", response_model=InventoryAlert)
async def acknowledge_alert(
    alert_id: int,
    notes: Optional[str] = Query(None, description="Acknowledgment notes"),
    inventory_service: InventoryService = Depends(get_inventory_service),
    current_user: User = Depends(require_permission("inventory:update"))
):
    """Acknowledge an inventory alert"""
    return inventory_service.acknowledge_alert(alert_id, current_user.id, notes)


@router.post("/alerts/{alert_id}/resolve", response_model=InventoryAlert)
async def resolve_alert(
    alert_id: int,
    notes: Optional[str] = Query(None, description="Resolution notes"),
    inventory_service: InventoryService = Depends(get_inventory_service),
    current_user: User = Depends(require_permission("inventory:update"))
):
    """Resolve an inventory alert"""
    return inventory_service.resolve_alert(alert_id, current_user.id, notes)


@router.post("/alerts/check", status_code=status.HTTP_200_OK)
async def check_all_alerts(
    background_tasks: BackgroundTasks,
    inventory_service: InventoryService = Depends(get_inventory_service),
    current_user: User = Depends(require_permission("inventory:update"))
):
    """Manually trigger alert checking for all inventory items"""
    def check_alerts_task():
        items = inventory_service.get_inventory_items(active_only=True)[0]
        for item in items:
            inventory_service.check_and_create_alerts(item)
    
    background_tasks.add_task(check_alerts_task)
    return {"message": "Alert checking initiated"}


# Usage Tracking
@router.post("/{inventory_id}/usage", response_model=InventoryUsageLog)
async def record_inventory_usage(
    inventory_id: int,
    usage_data: InventoryUsageLogCreate,
    inventory_service: InventoryService = Depends(get_inventory_service),
    current_user: User = Depends(require_permission("inventory:update"))
):
    """Record inventory usage"""
    return inventory_service.record_usage(
        inventory_id=inventory_id,
        quantity_used=usage_data.quantity_used,
        menu_item_id=usage_data.menu_item_id,
        order_id=usage_data.order_id,
        order_item_id=usage_data.order_item_id,
        location=usage_data.location,
        station=usage_data.station,
        user_id=current_user.id
    )


@router.get("/{inventory_id}/usage", response_model=List[InventoryUsageLog])
async def get_inventory_usage(
    inventory_id: int,
    start_date: Optional[date] = Query(None, description="Start date (YYYY-MM-DD)"),
    end_date: Optional[date] = Query(None, description="End date (YYYY-MM-DD)"),
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    inventory_service: InventoryService = Depends(get_inventory_service),
    current_user: User = Depends(require_permission("inventory:read"))
):
    """Get usage history for inventory item"""
    query = inventory_service.db.query(InventoryUsageLog).filter(
        InventoryUsageLog.inventory_id == inventory_id
    )
    
    if start_date:
        query = query.filter(InventoryUsageLog.order_date >= start_date)
    if end_date:
        query = query.filter(InventoryUsageLog.order_date <= end_date)
    
    return query.order_by(InventoryUsageLog.order_date.desc()).offset(offset).limit(limit).all()


@router.get("/{inventory_id}/analytics", response_model=InventoryAnalytics)
async def get_inventory_analytics(
    inventory_id: int,
    start_date: Optional[date] = Query(None, description="Start date (YYYY-MM-DD)"),
    end_date: Optional[date] = Query(None, description="End date (YYYY-MM-DD)"),
    inventory_service: InventoryService = Depends(get_inventory_service),
    current_user: User = Depends(require_permission("inventory:read"))
):
    """Get analytics for inventory item"""
    return inventory_service.get_usage_analytics(
        inventory_id=inventory_id,
        start_date=start_date,
        end_date=end_date
    )


# Bulk Operations
@router.put("/bulk", response_model=List[Inventory])
async def bulk_update_inventory(
    bulk_data: BulkInventoryUpdate,
    inventory_service: InventoryService = Depends(get_inventory_service),
    current_user: User = Depends(require_permission("inventory:update"))
):
    """Bulk update inventory items"""
    updated_items = []
    update_dict = bulk_data.updates.dict(exclude_unset=True)
    
    for inventory_id in bulk_data.inventory_ids:
        try:
            item = inventory_service.update_inventory_item(
                inventory_id, 
                update_dict, 
                current_user.id
            )
            updated_items.append(item)
        except Exception:
            continue  # Skip items that fail to update
    
    return updated_items


# Categories and Organization
@router.get("/categories/", response_model=List[str])
async def get_inventory_categories(
    inventory_service: InventoryService = Depends(get_inventory_service),
    current_user: User = Depends(require_permission("inventory:read"))
):
    """Get list of inventory categories"""
    categories = inventory_service.db.query(
        inventory_service.db.query.distinct(Inventory.category)
    ).filter(
        Inventory.category.isnot(None),
        Inventory.is_active == True,
        Inventory.deleted_at.is_(None)
    ).all()
    
    return [cat[0] for cat in categories if cat[0]]


# Reporting
@router.get("/reports/low-stock", response_model=List[Inventory])
async def get_low_stock_report(
    category: Optional[str] = Query(None, description="Filter by category"),
    vendor_id: Optional[int] = Query(None, description="Filter by vendor"),
    inventory_service: InventoryService = Depends(get_inventory_service),
    current_user: User = Depends(require_permission("inventory:read"))
):
    """Get detailed low stock report"""
    items = inventory_service.get_low_stock_items()
    
    if category:
        items = [item for item in items if item.category == category]
    if vendor_id:
        items = [item for item in items if item.vendor_id == vendor_id]
    
    return items


@router.get("/reports/waste-summary")
async def get_waste_summary_report(
    start_date: Optional[date] = Query(None, description="Start date"),
    end_date: Optional[date] = Query(None, description="End date"),
    category: Optional[str] = Query(None, description="Filter by category"),
    waste_reason: Optional[WasteReason] = Query(None, description="Filter by waste reason"),
    inventory_service: InventoryService = Depends(get_inventory_service),
    current_user: User = Depends(require_permission("inventory:read"))
):
    """Get waste summary report with cost analysis"""
    from core.inventory_models import InventoryAdjustment
    
    query = inventory_service.db.query(InventoryAdjustment).filter(
        InventoryAdjustment.adjustment_type == AdjustmentType.WASTE,
        InventoryAdjustment.is_active == True
    )
    
    if start_date:
        query = query.filter(InventoryAdjustment.created_at >= start_date)
    if end_date:
        query = query.filter(InventoryAdjustment.created_at <= end_date)
    if waste_reason:
        query = query.filter(InventoryAdjustment.reason.like(f"%{waste_reason.value}%"))
    
    adjustments = query.all()
    
    # Group by inventory item and waste reason
    waste_summary = {}
    reason_summary = {}
    total_waste_cost = 0
    
    for adj in adjustments:
        # Skip if no inventory relationship
        if not hasattr(adj, 'inventory_item') or not adj.inventory_item:
            continue
            
        item = adj.inventory_item
        if category and item.category != category:
            continue
        
        # Parse waste reason
        waste_reason_value = WasteReason.OTHER
        for wr in WasteReason:
            if wr.value in adj.reason.lower():
                waste_reason_value = wr
                break
        
        # Update item summary
        if item.id not in waste_summary:
            waste_summary[item.id] = {
                "inventory_id": item.id,
                "item_name": item.item_name,
                "category": item.category,
                "total_quantity_wasted": 0,
                "unit": item.unit,
                "total_cost": 0,
                "waste_count": 0,
                "reasons": {}
            }
        
        quantity_wasted = abs(adj.quantity_change)
        cost = adj.total_cost or (quantity_wasted * (item.cost_per_unit or 0))
        
        waste_summary[item.id]["total_quantity_wasted"] += quantity_wasted
        waste_summary[item.id]["total_cost"] += cost
        waste_summary[item.id]["waste_count"] += 1
        
        # Track reasons per item
        reason_key = waste_reason_value.value
        if reason_key not in waste_summary[item.id]["reasons"]:
            waste_summary[item.id]["reasons"][reason_key] = {
                "count": 0,
                "quantity": 0,
                "cost": 0
            }
        waste_summary[item.id]["reasons"][reason_key]["count"] += 1
        waste_summary[item.id]["reasons"][reason_key]["quantity"] += quantity_wasted
        waste_summary[item.id]["reasons"][reason_key]["cost"] += cost
        
        # Update reason summary
        if reason_key not in reason_summary:
            reason_summary[reason_key] = {
                "reason": reason_key,
                "total_incidents": 0,
                "total_cost": 0,
                "items_affected": set()
            }
        reason_summary[reason_key]["total_incidents"] += 1
        reason_summary[reason_key]["total_cost"] += cost
        reason_summary[reason_key]["items_affected"].add(item.item_name)
        
        total_waste_cost += cost
    
    # Convert sets to lists for JSON serialization
    for reason in reason_summary.values():
        reason["items_affected"] = list(reason["items_affected"])
    
    # Sort by cost
    sorted_items = sorted(waste_summary.values(), key=lambda x: x["total_cost"], reverse=True)
    
    return {
        "period": {
            "start_date": start_date,
            "end_date": end_date
        },
        "summary": {
            "total_waste_cost": total_waste_cost,
            "total_items_wasted": len(waste_summary),
            "total_waste_incidents": sum(item["waste_count"] for item in waste_summary.values())
        },
        "by_item": sorted_items[:20],  # Top 20 items by cost
        "by_reason": list(reason_summary.values()),
        "recommendations": _generate_waste_recommendations(sorted_items, reason_summary)
    }


def _generate_waste_recommendations(items_summary: list, reasons_summary: dict) -> list:
    """Generate actionable recommendations based on waste patterns"""
    recommendations = []
    
    # Check for high-cost items
    if items_summary and items_summary[0]["total_cost"] > 500:
        recommendations.append({
            "priority": "high",
            "category": "cost_reduction",
            "message": f"Item '{items_summary[0]['item_name']}' has the highest waste cost. Consider reviewing portion sizes or storage procedures."
        })
    
    # Check for expiration issues
    if "expired" in reasons_summary and reasons_summary["expired"]["total_incidents"] > 10:
        recommendations.append({
            "priority": "high",
            "category": "inventory_management",
            "message": "High number of expiration incidents. Consider implementing FIFO rotation system or reducing order quantities."
        })
    
    # Check for temperature issues
    if "temperature_abuse" in reasons_summary:
        recommendations.append({
            "priority": "high",
            "category": "equipment",
            "message": "Temperature abuse detected. Check refrigeration equipment and staff training on temperature monitoring."
        })
    
    # Check for spillage/preparation loss
    total_prep_loss = sum(
        reasons_summary.get(reason, {}).get("total_incidents", 0)
        for reason in ["spillage", "preparation_loss", "overcooking"]
    )
    if total_prep_loss > 20:
        recommendations.append({
            "priority": "medium",
            "category": "training",
            "message": "High preparation losses detected. Consider additional staff training on food handling procedures."
        })
    
    return recommendations


@router.get("/reports/usage-summary")
async def get_usage_summary_report(
    start_date: Optional[date] = Query(None, description="Start date"),
    end_date: Optional[date] = Query(None, description="End date"),
    category: Optional[str] = Query(None, description="Filter by category"),
    inventory_service: InventoryService = Depends(get_inventory_service),
    current_user: User = Depends(require_permission("inventory:read"))
):
    """Get usage summary report"""
    query = inventory_service.db.query(InventoryUsageLog)
    
    if start_date:
        query = query.filter(InventoryUsageLog.order_date >= start_date)
    if end_date:
        query = query.filter(InventoryUsageLog.order_date <= end_date)
    
    usage_logs = query.all()
    
    # Group by inventory item
    usage_summary = {}
    for log in usage_logs:
        if log.inventory_id not in usage_summary:
            usage_summary[log.inventory_id] = {
                "inventory_item": log.inventory_item.item_name if hasattr(log, 'inventory_item') else f"Item {log.inventory_id}",
                "total_usage": 0,
                "total_cost": 0,
                "usage_count": 0
            }
        
        usage_summary[log.inventory_id]["total_usage"] += log.quantity_used
        usage_summary[log.inventory_id]["total_cost"] += log.total_cost or 0
        usage_summary[log.inventory_id]["usage_count"] += 1
    
    return {
        "summary": list(usage_summary.values()),
        "period": {
            "start_date": start_date,
            "end_date": end_date
        }
    }


# Health Check
@router.get("/health")
async def inventory_health_check(
    inventory_service: InventoryService = Depends(get_inventory_service),
    current_user: User = Depends(require_permission("inventory:read"))
):
    """Get inventory system health status"""
    stats = inventory_service.get_inventory_dashboard_stats()
    alerts = inventory_service.get_active_alerts()
    
    health_status = "healthy"
    if stats["pending_alerts"] > 10:
        health_status = "warning"
    if stats["low_stock_items"] > stats["total_items"] * 0.2:  # More than 20% low stock
        health_status = "critical"
    
    return {
        "status": health_status,
        "total_items": stats["total_items"],
        "low_stock_items": stats["low_stock_items"],
        "pending_alerts": stats["pending_alerts"],
        "critical_alerts": len([a for a in alerts if a.priority == AlertPriority.CRITICAL]),
        "timestamp": datetime.utcnow()
    }