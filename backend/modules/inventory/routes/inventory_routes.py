# backend/modules/inventory/routes/inventory_routes.py

from fastapi import APIRouter, Depends, HTTPException, status, Query, BackgroundTasks
from sqlalchemy.orm import Session
from typing import List, Optional
from math import ceil
from datetime import date, datetime

from backend.core.database import get_db
from backend.core.inventory_service import InventoryService
from backend.core.inventory_schemas import (
    Inventory, InventoryCreate, InventoryUpdate, InventoryWithDetails,
    InventoryAlert, InventoryAlertCreate, InventoryAlertWithItem,
    InventoryAdjustment, InventoryAdjustmentCreate, InventoryAdjustmentWithItem,
    InventoryUsageLog, InventoryUsageLogCreate,
    InventorySearchParams, AlertSearchParams, 
    InventoryResponse, AlertResponse, AdjustmentResponse,
    InventoryDashboardStats, InventoryAnalytics, UsageReportParams,
    BulkAdjustmentRequest, BulkInventoryUpdate,
    AdjustmentType, AlertPriority, AlertStatus
)
from backend.core.rbac_auth import require_permission
from backend.core.rbac_models import RBACUser


router = APIRouter(prefix="/inventory", tags=["Inventory Management"])


def get_inventory_service(db: Session = Depends(get_db)) -> InventoryService:
    """Dependency to get inventory service instance"""
    return InventoryService(db)


# Core Inventory Management
@router.post("/", response_model=Inventory, status_code=status.HTTP_201_CREATED)
async def create_inventory_item(
    item_data: InventoryCreate,
    inventory_service: InventoryService = Depends(get_inventory_service),
    current_user: RBACUser = Depends(require_permission("inventory:create"))
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
    sort_by: str = Query("item_name", regex=r'^(item_name|quantity|threshold|category|created_at)$'),
    sort_order: str = Query("asc", regex=r'^(asc|desc)$'),
    inventory_service: InventoryService = Depends(get_inventory_service),
    current_user: RBACUser = Depends(require_permission("inventory:read"))
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
    current_user: RBACUser = Depends(require_permission("inventory:read"))
):
    """Get items that are below their reorder threshold"""
    return inventory_service.get_low_stock_items()


@router.get("/dashboard", response_model=InventoryDashboardStats)
async def get_dashboard_stats(
    inventory_service: InventoryService = Depends(get_inventory_service),
    current_user: RBACUser = Depends(require_permission("inventory:read"))
):
    """Get inventory dashboard statistics"""
    return inventory_service.get_inventory_dashboard_stats()


@router.get("/{inventory_id}", response_model=InventoryWithDetails)
async def get_inventory_item(
    inventory_id: int,
    inventory_service: InventoryService = Depends(get_inventory_service),
    current_user: RBACUser = Depends(require_permission("inventory:read"))
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
    current_user: RBACUser = Depends(require_permission("inventory:update"))
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
    current_user: RBACUser = Depends(require_permission("inventory:delete"))
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
    current_user: RBACUser = Depends(require_permission("inventory:update"))
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
    current_user: RBACUser = Depends(require_permission("inventory:read"))
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
    current_user: RBACUser = Depends(require_permission("inventory:update"))
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
    current_user: RBACUser = Depends(require_permission("inventory:read"))
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
    current_user: RBACUser = Depends(require_permission("inventory:read"))
):
    """Get active inventory alerts"""
    return inventory_service.get_active_alerts(priority)


@router.post("/alerts/{alert_id}/acknowledge", response_model=InventoryAlert)
async def acknowledge_alert(
    alert_id: int,
    notes: Optional[str] = Query(None, description="Acknowledgment notes"),
    inventory_service: InventoryService = Depends(get_inventory_service),
    current_user: RBACUser = Depends(require_permission("inventory:update"))
):
    """Acknowledge an inventory alert"""
    return inventory_service.acknowledge_alert(alert_id, current_user.id, notes)


@router.post("/alerts/{alert_id}/resolve", response_model=InventoryAlert)
async def resolve_alert(
    alert_id: int,
    notes: Optional[str] = Query(None, description="Resolution notes"),
    inventory_service: InventoryService = Depends(get_inventory_service),
    current_user: RBACUser = Depends(require_permission("inventory:update"))
):
    """Resolve an inventory alert"""
    return inventory_service.resolve_alert(alert_id, current_user.id, notes)


@router.post("/alerts/check", status_code=status.HTTP_200_OK)
async def check_all_alerts(
    background_tasks: BackgroundTasks,
    inventory_service: InventoryService = Depends(get_inventory_service),
    current_user: RBACUser = Depends(require_permission("inventory:update"))
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
    current_user: RBACUser = Depends(require_permission("inventory:update"))
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
    current_user: RBACUser = Depends(require_permission("inventory:read"))
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
    current_user: RBACUser = Depends(require_permission("inventory:read"))
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
    current_user: RBACUser = Depends(require_permission("inventory:update"))
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
    current_user: RBACUser = Depends(require_permission("inventory:read"))
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
    current_user: RBACUser = Depends(require_permission("inventory:read"))
):
    """Get detailed low stock report"""
    items = inventory_service.get_low_stock_items()
    
    if category:
        items = [item for item in items if item.category == category]
    if vendor_id:
        items = [item for item in items if item.vendor_id == vendor_id]
    
    return items


@router.get("/reports/usage-summary")
async def get_usage_summary_report(
    start_date: Optional[date] = Query(None, description="Start date"),
    end_date: Optional[date] = Query(None, description="End date"),
    category: Optional[str] = Query(None, description="Filter by category"),
    inventory_service: InventoryService = Depends(get_inventory_service),
    current_user: RBACUser = Depends(require_permission("inventory:read"))
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
    current_user: RBACUser = Depends(require_permission("inventory:read"))
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