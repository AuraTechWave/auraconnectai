from sqlalchemy.orm import Session
from fastapi import HTTPException
from typing import List, Dict
from ..models.inventory_models import Inventory, MenuItemInventory
from ..models.order_models import OrderItem
from ..schemas.inventory_schemas import InventoryOut, InventoryUpdate


async def get_inventory_by_id(db: Session, inventory_id: int):
    inventory = db.query(Inventory).filter(
        Inventory.id == inventory_id, Inventory.deleted_at.is_(None)
    ).first()

    if not inventory:
        raise HTTPException(
            status_code=404,
            detail=f"Inventory item with id {inventory_id} not found"
        )

    return inventory


async def deduct_inventory(db: Session, order_items: List[OrderItem]) -> Dict:
    low_stock_items = []
    insufficient_stock_items = []

    try:
        for order_item in order_items:
            mappings = db.query(MenuItemInventory).filter(
                MenuItemInventory.menu_item_id == order_item.menu_item_id
            ).all()

            for mapping in mappings:
                inventory_item = db.query(Inventory).filter(
                    Inventory.id == mapping.inventory_id,
                    Inventory.deleted_at.is_(None)
                ).first()

                if not inventory_item:
                    continue

                required_quantity = (mapping.quantity_needed *
                                     order_item.quantity)

                if inventory_item.quantity < required_quantity:
                    insufficient_stock_items.append({
                        "item_name": inventory_item.item_name,
                        "available": inventory_item.quantity,
                        "required": required_quantity
                    })
                    continue

                inventory_item.quantity -= required_quantity

                if inventory_item.quantity <= inventory_item.threshold:
                    low_stock_items.append({
                        "item_name": inventory_item.item_name,
                        "current_quantity": inventory_item.quantity,
                        "threshold": inventory_item.threshold
                    })

        if insufficient_stock_items:
            db.rollback()
            raise HTTPException(
                status_code=400,
                detail={
                    "message": "Insufficient inventory",
                    "items": insufficient_stock_items
                }
            )

        db.commit()
        return {
            "success": True,
            "low_stock_alerts": low_stock_items
        }

    except Exception as e:
        db.rollback()
        if isinstance(e, HTTPException):
            raise e
        raise HTTPException(
            status_code=500,
            detail="Error processing inventory deduction"
        )


async def check_low_stock(db: Session) -> List[Dict]:
    low_stock = db.query(Inventory).filter(
        Inventory.quantity <= Inventory.threshold,
        Inventory.deleted_at.is_(None)
    ).all()

    return [
        {
            "id": item.id,
            "item_name": item.item_name,
            "current_quantity": item.quantity,
            "threshold": item.threshold,
            "unit": item.unit
        }
        for item in low_stock
    ]


async def get_inventory_service(
    db: Session,
    limit: int = 100,
    offset: int = 0
) -> List[Inventory]:
    query = db.query(Inventory).filter(Inventory.deleted_at.is_(None))
    query = query.offset(offset).limit(limit)
    return query.all()


async def update_inventory_service(inventory_id: int,
                                   inventory_update: InventoryUpdate,
                                   db: Session):
    inventory = db.query(Inventory).filter(Inventory.id == inventory_id).first()
    if not inventory:
        raise HTTPException(status_code=404, detail="Inventory item not found")

    if inventory_update.item_name is not None:
        inventory.item_name = inventory_update.item_name
    if inventory_update.quantity is not None:
        inventory.quantity = inventory_update.quantity
    if inventory_update.unit is not None:
        inventory.unit = inventory_update.unit
    if inventory_update.threshold is not None:
        inventory.threshold = inventory_update.threshold
    if inventory_update.vendor_id is not None:
        inventory.vendor_id = inventory_update.vendor_id

    db.commit()
    db.refresh(inventory)

    return {
        "message": "Inventory updated successfully",
        "data": InventoryOut.model_validate(inventory)
    }
