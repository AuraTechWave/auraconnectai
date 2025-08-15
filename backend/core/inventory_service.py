# backend/core/inventory_service.py

from typing import List, Optional, Dict, Any, Tuple
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import and_, or_, desc, asc, func, text
from fastapi import HTTPException, status
from datetime import datetime, timedelta, date
import uuid

from .inventory_models import (
    Inventory,
    InventoryAlert,
    InventoryAdjustment,
    Vendor,
    PurchaseOrder,
    PurchaseOrderItem,
    InventoryUsageLog,
    InventoryCount,
    InventoryCountItem,
    AlertStatus,
    AlertPriority,
    AdjustmentType,
    VendorStatus,
)


class InventoryService:
    """Comprehensive inventory management service with alerts and tracking"""

    def __init__(self, db: Session):
        self.db = db

    # Core Inventory Management
    def get_inventory_items(
        self,
        active_only: bool = True,
        low_stock_only: bool = False,
        category: Optional[str] = None,
        vendor_id: Optional[int] = None,
        search_query: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> Tuple[List[Inventory], int]:
        """Get inventory items with filtering and pagination"""
        query = self.db.query(Inventory).filter(Inventory.deleted_at.is_(None))

        if active_only:
            query = query.filter(Inventory.is_active == True)

        if category:
            query = query.filter(Inventory.category == category)

        if vendor_id:
            query = query.filter(Inventory.vendor_id == vendor_id)

        if search_query:
            search_term = f"%{search_query}%"
            query = query.filter(
                or_(
                    Inventory.item_name.ilike(search_term),
                    Inventory.description.ilike(search_term),
                    Inventory.sku.ilike(search_term),
                )
            )

        if low_stock_only:
            query = query.filter(Inventory.quantity <= Inventory.threshold)

        total = query.count()
        items = query.offset(offset).limit(limit).all()

        return items, total

    def get_inventory_by_id(self, inventory_id: int) -> Optional[Inventory]:
        """Get inventory item by ID with all relationships"""
        return (
            self.db.query(Inventory)
            .options(
                joinedload(Inventory.vendor),
                joinedload(Inventory.alerts),
                joinedload(Inventory.adjustments),
            )
            .filter(Inventory.id == inventory_id, Inventory.deleted_at.is_(None))
            .first()
        )

    def create_inventory_item(
        self, item_data: Dict[str, Any], user_id: int
    ) -> Inventory:
        """Create new inventory item"""
        # Check SKU uniqueness if provided
        if item_data.get("sku"):
            existing = (
                self.db.query(Inventory)
                .filter(
                    Inventory.sku == item_data["sku"], Inventory.deleted_at.is_(None)
                )
                .first()
            )
            if existing:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST, detail="SKU already exists"
                )

        inventory_item = Inventory(**item_data, created_by=user_id)

        self.db.add(inventory_item)
        self.db.commit()
        self.db.refresh(inventory_item)

        # Create initial adjustment record
        if inventory_item.quantity > 0:
            self.create_adjustment(
                inventory_id=inventory_item.id,
                adjustment_type=AdjustmentType.PURCHASE,
                quantity_adjusted=inventory_item.quantity,
                reason="Initial stock",
                user_id=user_id,
            )

        return inventory_item

    def update_inventory_item(
        self, inventory_id: int, update_data: Dict[str, Any], user_id: int
    ) -> Inventory:
        """Update inventory item"""
        item = self.get_inventory_by_id(inventory_id)
        if not item:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Inventory item not found"
            )

        # Check SKU uniqueness if being updated
        if "sku" in update_data and update_data["sku"] != item.sku:
            existing = (
                self.db.query(Inventory)
                .filter(
                    Inventory.sku == update_data["sku"],
                    Inventory.id != inventory_id,
                    Inventory.deleted_at.is_(None),
                )
                .first()
            )
            if existing:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST, detail="SKU already exists"
                )

        # Track quantity changes
        old_quantity = item.quantity

        for key, value in update_data.items():
            setattr(item, key, value)

        self.db.commit()
        self.db.refresh(item)

        # Create adjustment record if quantity changed
        if "quantity" in update_data and update_data["quantity"] != old_quantity:
            quantity_diff = update_data["quantity"] - old_quantity
            self.create_adjustment(
                inventory_id=inventory_id,
                adjustment_type=AdjustmentType.CORRECTION,
                quantity_adjusted=quantity_diff,
                reason="Manual quantity update",
                user_id=user_id,
            )

        # Check if alerts need to be created
        self.check_and_create_alerts(item)

        return item

    def adjust_inventory_quantity(
        self,
        inventory_id: int,
        adjustment_type: AdjustmentType,
        quantity: float,
        reason: str,
        user_id: int,
        unit_cost: Optional[float] = None,
        reference_type: Optional[str] = None,
        reference_id: Optional[str] = None,
        batch_number: Optional[str] = None,
        expiration_date: Optional[datetime] = None,
        location: Optional[str] = None,
        notes: Optional[str] = None,
    ) -> InventoryAdjustment:
        """Adjust inventory quantity with full audit trail"""
        item = self.get_inventory_by_id(inventory_id)
        if not item:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Inventory item not found"
            )

        old_quantity = item.quantity
        new_quantity = old_quantity + quantity

        if new_quantity < 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Adjustment would result in negative quantity",
            )

        # Create adjustment record
        adjustment = self.create_adjustment(
            inventory_id=inventory_id,
            adjustment_type=adjustment_type,
            quantity_adjusted=quantity,
            reason=reason,
            user_id=user_id,
            unit_cost=unit_cost,
            reference_type=reference_type,
            reference_id=reference_id,
            batch_number=batch_number,
            expiration_date=expiration_date,
            location=location,
            notes=notes,
            quantity_before=old_quantity,
            quantity_after=new_quantity,
        )

        # Update inventory quantity
        item.quantity = new_quantity
        item.last_adjusted_at = datetime.utcnow()

        self.db.commit()

        # Check alerts after adjustment
        self.check_and_create_alerts(item)

        return adjustment

    # Alert Management
    def check_and_create_alerts(
        self, inventory_item: Inventory
    ) -> List[InventoryAlert]:
        """Check inventory item and create alerts as needed"""
        alerts_created = []

        # Low stock alert
        if inventory_item.enable_low_stock_alerts and inventory_item.is_low_stock:
            existing_alert = (
                self.db.query(InventoryAlert)
                .filter(
                    InventoryAlert.inventory_id == inventory_item.id,
                    InventoryAlert.alert_type == "low_stock",
                    InventoryAlert.status.in_(
                        [AlertStatus.PENDING, AlertStatus.ACKNOWLEDGED]
                    ),
                )
                .first()
            )

            if not existing_alert:
                alert = self.create_alert(
                    inventory_id=inventory_item.id,
                    alert_type="low_stock",
                    priority=(
                        AlertPriority.HIGH
                        if inventory_item.quantity == 0
                        else AlertPriority.MEDIUM
                    ),
                    title=f"Low Stock: {inventory_item.item_name}",
                    message=f"Current stock ({inventory_item.quantity} {inventory_item.unit}) is below threshold ({inventory_item.threshold} {inventory_item.unit})",
                    threshold_value=inventory_item.threshold,
                    current_value=inventory_item.quantity,
                )
                alerts_created.append(alert)

        # Expiration alerts (if applicable)
        if inventory_item.track_expiration and inventory_item.shelf_life_days:
            # This would require batch tracking - placeholder for future implementation
            pass

        return alerts_created

    def create_alert(
        self,
        inventory_id: int,
        alert_type: str,
        priority: AlertPriority,
        title: str,
        message: str,
        threshold_value: Optional[float] = None,
        current_value: Optional[float] = None,
        auto_resolve: bool = False,
        expires_at: Optional[datetime] = None,
    ) -> InventoryAlert:
        """Create new inventory alert"""
        alert = InventoryAlert(
            inventory_id=inventory_id,
            alert_type=alert_type,
            priority=priority,
            status=AlertStatus.PENDING,
            title=title,
            message=message,
            threshold_value=threshold_value,
            current_value=current_value,
            auto_resolve=auto_resolve,
            expires_at=expires_at,
        )

        self.db.add(alert)
        self.db.commit()
        self.db.refresh(alert)

        return alert

    def get_active_alerts(
        self, priority: Optional[AlertPriority] = None
    ) -> List[InventoryAlert]:
        """Get active inventory alerts"""
        query = (
            self.db.query(InventoryAlert)
            .options(joinedload(InventoryAlert.inventory_item))
            .filter(
                InventoryAlert.is_active == True,
                InventoryAlert.status.in_(
                    [AlertStatus.PENDING, AlertStatus.ACKNOWLEDGED]
                ),
            )
        )

        if priority:
            query = query.filter(InventoryAlert.priority == priority)

        return query.order_by(
            InventoryAlert.priority.desc(), InventoryAlert.created_at.asc()
        ).all()

    def acknowledge_alert(
        self, alert_id: int, user_id: int, notes: Optional[str] = None
    ) -> InventoryAlert:
        """Acknowledge an alert"""
        alert = (
            self.db.query(InventoryAlert).filter(InventoryAlert.id == alert_id).first()
        )
        if not alert:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Alert not found"
            )

        alert.status = AlertStatus.ACKNOWLEDGED
        alert.acknowledged_by = user_id
        alert.acknowledged_at = datetime.utcnow()
        if notes:
            alert.resolution_notes = notes

        self.db.commit()
        self.db.refresh(alert)

        return alert

    def resolve_alert(
        self, alert_id: int, user_id: int, notes: Optional[str] = None
    ) -> InventoryAlert:
        """Resolve an alert"""
        alert = (
            self.db.query(InventoryAlert).filter(InventoryAlert.id == alert_id).first()
        )
        if not alert:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Alert not found"
            )

        alert.status = AlertStatus.RESOLVED
        alert.resolved_by = user_id
        alert.resolved_at = datetime.utcnow()
        if notes:
            alert.resolution_notes = notes

        self.db.commit()
        self.db.refresh(alert)

        return alert

    # Usage Tracking
    def record_usage(
        self,
        inventory_id: int,
        quantity_used: float,
        menu_item_id: Optional[int] = None,
        order_id: Optional[int] = None,
        order_item_id: Optional[int] = None,
        location: Optional[str] = None,
        station: Optional[str] = None,
        user_id: Optional[int] = None,
    ) -> InventoryUsageLog:
        """Record inventory usage from orders or other consumption"""
        inventory_item = self.get_inventory_by_id(inventory_id)
        if not inventory_item:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Inventory item not found"
            )

        # Create usage log
        usage_log = InventoryUsageLog(
            inventory_id=inventory_id,
            menu_item_id=menu_item_id,
            quantity_used=quantity_used,
            unit=inventory_item.unit,
            order_id=order_id,
            order_item_id=order_item_id,
            order_date=datetime.utcnow(),
            unit_cost=inventory_item.cost_per_unit,
            total_cost=(
                quantity_used * inventory_item.cost_per_unit
                if inventory_item.cost_per_unit
                else None
            ),
            location=location,
            station=station,
            created_by=user_id,
        )

        self.db.add(usage_log)

        # Adjust inventory quantity
        self.adjust_inventory_quantity(
            inventory_id=inventory_id,
            adjustment_type=AdjustmentType.SALE,
            quantity=-quantity_used,
            reason=f"Usage for order {order_id}" if order_id else "Manual usage",
            user_id=user_id or 0,
            reference_type="order" if order_id else "manual",
            reference_id=str(order_id) if order_id else None,
        )

        return usage_log

    def get_usage_analytics(
        self,
        inventory_id: Optional[int] = None,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
    ) -> Dict[str, Any]:
        """Get usage analytics for inventory items"""
        query = self.db.query(InventoryUsageLog)

        if inventory_id:
            query = query.filter(InventoryUsageLog.inventory_id == inventory_id)

        if start_date:
            query = query.filter(InventoryUsageLog.order_date >= start_date)

        if end_date:
            query = query.filter(InventoryUsageLog.order_date <= end_date)

        usage_logs = query.all()

        # Calculate analytics
        total_usage = sum(log.quantity_used for log in usage_logs)
        total_cost = sum(log.total_cost or 0 for log in usage_logs)
        average_daily_usage = (
            total_usage / max(1, (end_date - start_date).days)
            if start_date and end_date
            else 0
        )

        return {
            "total_usage": total_usage,
            "total_cost": total_cost,
            "average_daily_usage": average_daily_usage,
            "usage_count": len(usage_logs),
        }

    # Vendor Management
    def create_vendor(self, vendor_data: Dict[str, Any], user_id: int) -> Vendor:
        """Create new vendor"""
        vendor = Vendor(**vendor_data, created_by=user_id)
        self.db.add(vendor)
        self.db.commit()
        self.db.refresh(vendor)
        return vendor

    def get_vendors(self, active_only: bool = True) -> List[Vendor]:
        """Get vendors"""
        query = self.db.query(Vendor).filter(Vendor.deleted_at.is_(None))
        if active_only:
            query = query.filter(Vendor.is_active == True)
        return query.order_by(Vendor.name).all()

    def get_vendor_by_id(self, vendor_id: int) -> Optional[Vendor]:
        """Get vendor by ID"""
        return (
            self.db.query(Vendor)
            .filter(Vendor.id == vendor_id, Vendor.deleted_at.is_(None))
            .first()
        )

    # Purchase Orders
    def create_purchase_order(
        self, po_data: Dict[str, Any], user_id: int
    ) -> PurchaseOrder:
        """Create new purchase order"""
        # Generate PO number if not provided
        if "po_number" not in po_data:
            po_data["po_number"] = (
                f"PO-{datetime.now().strftime('%Y%m%d')}-{uuid.uuid4().hex[:6].upper()}"
            )

        purchase_order = PurchaseOrder(
            **po_data, created_by=user_id, order_date=datetime.utcnow()
        )

        self.db.add(purchase_order)
        self.db.commit()
        self.db.refresh(purchase_order)

        return purchase_order

    def add_item_to_purchase_order(
        self, po_id: int, item_data: Dict[str, Any]
    ) -> PurchaseOrderItem:
        """Add item to purchase order"""
        po_item = PurchaseOrderItem(purchase_order_id=po_id, **item_data)
        self.db.add(po_item)
        self.db.commit()
        self.db.refresh(po_item)

        # Update PO totals
        self.update_purchase_order_totals(po_id)

        return po_item

    def update_purchase_order_totals(self, po_id: int):
        """Update purchase order totals"""
        po = self.db.query(PurchaseOrder).filter(PurchaseOrder.id == po_id).first()
        if not po:
            return

        total = (
            self.db.query(func.sum(PurchaseOrderItem.total_cost))
            .filter(PurchaseOrderItem.purchase_order_id == po_id)
            .scalar()
            or 0
        )

        po.subtotal = total
        # Handle None values for tax_amount and shipping_cost
        tax_amount = po.tax_amount if po.tax_amount is not None else 0.0
        shipping_cost = po.shipping_cost if po.shipping_cost is not None else 0.0
        po.total_amount = total + tax_amount + shipping_cost
        self.db.commit()

    # Inventory Counting
    def create_inventory_count(
        self, count_data: Dict[str, Any], user_id: int
    ) -> InventoryCount:
        """Create new inventory count"""
        if "count_number" not in count_data:
            count_data["count_number"] = (
                f"COUNT-{datetime.now().strftime('%Y%m%d')}-{uuid.uuid4().hex[:6].upper()}"
            )

        count = InventoryCount(
            **count_data,
            created_by=user_id,
            counted_by=user_id,
            count_date=datetime.utcnow(),
        )

        self.db.add(count)
        self.db.commit()
        self.db.refresh(count)

        return count

    def add_count_item(
        self, count_id: int, item_data: Dict[str, Any], user_id: int
    ) -> InventoryCountItem:
        """Add item to inventory count"""
        inventory_item = self.get_inventory_by_id(item_data["inventory_id"])
        if not inventory_item:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Inventory item not found"
            )

        count_item = InventoryCountItem(
            inventory_count_id=count_id,
            system_quantity=inventory_item.quantity,
            variance=item_data["counted_quantity"] - inventory_item.quantity,
            counted_by=user_id,
            count_timestamp=datetime.utcnow(),
            **item_data,
        )

        self.db.add(count_item)
        self.db.commit()
        self.db.refresh(count_item)

        return count_item

    # ------------------------------------------------------------
    # Automated Re-order (Re-stock) Logic
    # ------------------------------------------------------------
    def auto_create_purchase_orders_for_low_stock(self, user_id: int = 0):
        """Automatically generate purchase orders for any inventory items
        that are currently below their reorder threshold.

        The algorithm performs the following steps:

        1. Fetch all low-stock items (using the helper already available).
        2. Group the items by their upstream vendor (``vendor_id``).
           • Items without a vendor are skipped – the business can manually
             review those.
        3. For every vendor group, create a *draft* purchase order using the
           existing :py:meth:`create_purchase_order` helper.
        4. Populate the newly created PO with :py:meth:`add_item_to_purchase_order`.
           • ``quantity_ordered`` is derived from the item’s ``reorder_quantity``
             field when provided; otherwise it defaults to the difference
             between the current quantity and the threshold (minimum 1).
           • ``unit_cost`` falls back to ``cost_per_unit`` if present, or 0.
        5. Return the list of created purchase orders so the caller (route,
           background task, etc.) can present them to the user.

        NOTE: This helper purposefully does *not* check for pre-existing open
        purchase orders.  That behaviour can be layered on later if required.
        """

        created_purchase_orders: List[PurchaseOrder] = []

        low_stock_items = self.get_low_stock_items()

        # Group items by vendor
        vendor_map: Dict[int, List[Inventory]] = {}
        for item in low_stock_items:
            if not item.vendor_id:
                # Cannot auto-reorder items without a vendor association
                continue
            vendor_map.setdefault(item.vendor_id, []).append(item)

        for vendor_id, items in vendor_map.items():
            po_data = {
                "vendor_id": vendor_id,
                "tax_amount": 0.0,
                "shipping_cost": 0.0,
                "subtotal": 0.0,
                "total_amount": 0.0,
            }

            # Create draft PO (status defaults to "draft")
            po = self.create_purchase_order(po_data, user_id=user_id)

            for inv_item in items:
                # Determine quantity to order
                if inv_item.reorder_quantity and inv_item.reorder_quantity > 0:
                    qty_to_order = inv_item.reorder_quantity
                else:
                    # Order enough to reach the threshold again at minimum
                    qty_to_order = max(inv_item.threshold - inv_item.quantity, 1)

                unit_cost = inv_item.cost_per_unit or 0.0

                po_item_data = {
                    "inventory_id": inv_item.id,
                    "quantity_ordered": qty_to_order,
                    "unit_cost": unit_cost,
                    "unit": inv_item.unit,
                    "total_cost": unit_cost * qty_to_order,
                }

                # Utilise existing helper to attach item and recalc totals
                self.add_item_to_purchase_order(po.id, po_item_data)

            # Refresh PO totals and state
            self.db.refresh(po)
            created_purchase_orders.append(po)

        return created_purchase_orders

    # Helper Methods
    def create_adjustment(
        self,
        inventory_id: int,
        adjustment_type: AdjustmentType,
        quantity_adjusted: float,
        reason: str,
        user_id: int,
        quantity_before: Optional[float] = None,
        quantity_after: Optional[float] = None,
        unit_cost: Optional[float] = None,
        reference_type: Optional[str] = None,
        reference_id: Optional[str] = None,
        batch_number: Optional[str] = None,
        expiration_date: Optional[datetime] = None,
        location: Optional[str] = None,
        notes: Optional[str] = None,
    ) -> InventoryAdjustment:
        """Create inventory adjustment record"""
        inventory_item = self.get_inventory_by_id(inventory_id)
        if not inventory_item:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Inventory item not found"
            )

        if quantity_before is None:
            quantity_before = inventory_item.quantity
        if quantity_after is None:
            quantity_after = quantity_before + quantity_adjusted

        adjustment = InventoryAdjustment(
            inventory_id=inventory_id,
            adjustment_type=adjustment_type,
            quantity_before=quantity_before,
            quantity_adjusted=quantity_adjusted,
            quantity_after=quantity_after,
            unit=inventory_item.unit,
            unit_cost=unit_cost or inventory_item.cost_per_unit,
            total_cost=(unit_cost or inventory_item.cost_per_unit or 0)
            * abs(quantity_adjusted),
            reference_type=reference_type,
            reference_id=reference_id,
            batch_number=batch_number,
            expiration_date=expiration_date,
            location=location,
            reason=reason,
            notes=notes,
            created_by=user_id,
        )

        self.db.add(adjustment)
        self.db.commit()
        self.db.refresh(adjustment)

        return adjustment

    def get_low_stock_items(self) -> List[Inventory]:
        """Get all items currently below their reorder threshold"""
        return (
            self.db.query(Inventory)
            .filter(
                Inventory.is_active == True,
                Inventory.deleted_at.is_(None),
                Inventory.quantity <= Inventory.threshold,
            )
            .order_by(Inventory.item_name)
            .all()
        )

    def get_inventory_dashboard_stats(self) -> Dict[str, Any]:
        """Get dashboard statistics"""
        total_items = (
            self.db.query(Inventory)
            .filter(Inventory.is_active == True, Inventory.deleted_at.is_(None))
            .count()
        )

        low_stock_items = len(self.get_low_stock_items())

        pending_alerts = (
            self.db.query(InventoryAlert)
            .filter(
                InventoryAlert.status == AlertStatus.PENDING,
                InventoryAlert.is_active == True,
            )
            .count()
        )

        total_value = (
            self.db.query(func.sum(Inventory.quantity * Inventory.cost_per_unit))
            .filter(
                Inventory.is_active == True,
                Inventory.deleted_at.is_(None),
                Inventory.cost_per_unit.isnot(None),
            )
            .scalar()
            or 0
        )

        return {
            "total_items": total_items,
            "low_stock_items": low_stock_items,
            "pending_alerts": pending_alerts,
            "total_inventory_value": float(total_value),
            "stock_percentage": ((total_items - low_stock_items) / max(1, total_items))
            * 100,
        }
