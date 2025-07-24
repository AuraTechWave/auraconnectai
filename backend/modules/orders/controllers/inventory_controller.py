from sqlalchemy.orm import Session
from typing import List, Optional
from ..services.inventory_service import (
    get_inventory_by_id as get_inventory_service,
    check_low_stock as check_low_stock_service,
    deduct_inventory as deduct_inventory_service,
    get_inventory_service as list_inventory_service,
    update_inventory_service
)
from ..schemas.inventory_schemas import InventoryOut, InventoryUpdate


async def get_inventory_by_id(db: Session, inventory_id: int):
    return await get_inventory_service(db, inventory_id)


async def check_low_stock(db: Session) -> List[dict]:
    return await check_low_stock_service(db)


async def deduct_inventory_for_order(db: Session, order_items):
    return await deduct_inventory_service(db, order_items)


async def list_inventory(
    db: Session,
    limit: int = 100,
    offset: int = 0
) -> List[InventoryOut]:
    inventory_items = await list_inventory_service(db, limit, offset)
    return [InventoryOut.model_validate(item) for item in inventory_items]


async def update_inventory(inventory_id: int, inventory_data: InventoryUpdate, db: Session):
    return await update_inventory_service(inventory_id, inventory_data, db)
