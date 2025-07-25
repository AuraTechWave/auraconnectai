import asyncio
import logging
from sqlalchemy.orm import Session, joinedload
from typing import Dict, Any, Optional
from datetime import datetime
from ..models.pos_integration import POSIntegration
from ..models.pos_sync_log import POSSyncLog
from ..adapters.adapter_factory import AdapterFactory
from ..enums.pos_enums import POSVendor, POSSyncStatus, POSSyncType
from ..schemas.pos_schemas import SyncResponse, POSOrderTransformResult
from ...orders.models.order_models import Order, OrderItem
from backend.modules.settings.models.pos_sync_models import POSSyncSetting
from ...orders.enums.order_enums import OrderStatus
from ...orders.models.inventory_models import MenuItemInventory

logger = logging.getLogger(__name__)


class POSBridgeService:
    def __init__(self, db: Session):
        self.db = db
        self.max_retries = 3
        self.retry_delays = [1, 5, 15]

    def is_sync_enabled(
        self,
        tenant_id: Optional[int] = None,
        team_id: Optional[int] = None
    ) -> bool:
        if team_id:
            team_setting = self.db.query(POSSyncSetting).filter(
                POSSyncSetting.tenant_id == tenant_id,
                POSSyncSetting.team_id == team_id
            ).first()
            if team_setting:
                return team_setting.enabled

        global_setting = self.db.query(POSSyncSetting).filter(
            POSSyncSetting.tenant_id == tenant_id,
            POSSyncSetting.team_id.is_(None)
        ).first()

        if global_setting:
            return global_setting.enabled

        return True

    async def sync_order_to_pos(
        self,
        order_id: int,
        integration_id: int,
        tenant_id: Optional[int] = None,
        team_id: Optional[int] = None
    ) -> SyncResponse:
        if not self.is_sync_enabled(tenant_id, team_id):
            logger.info(
                f"POS order sync skipped for tenant {tenant_id}, "
                f"team {team_id} - sync disabled"
            )
            return SyncResponse(
                success=False, message="POS sync disabled for this tenant/team"
            )

        integration = self.db.query(POSIntegration).filter(
            POSIntegration.id == integration_id
        ).first()

        if not integration:
            return SyncResponse(success=False, message="Integration not found")

        order = self.db.query(Order).options(
            joinedload(Order.order_items)
        ).filter(Order.id == order_id).first()
        if not order:
            return SyncResponse(success=False, message="Order not found")

        adapter = AdapterFactory.create_adapter(
            POSVendor(integration.vendor),
            integration.credentials
        )

        order_data = self._transform_order_to_dict(order)

        for attempt in range(self.max_retries):
            try:
                result = await adapter.push_order(order_data)

                sync_log = POSSyncLog(
                    integration_id=integration_id,
                    type=POSSyncType.ORDER_PUSH.value,
                    status=(
                        POSSyncStatus.SUCCESS.value
                        if result.success
                        else POSSyncStatus.FAILURE.value
                    ),
                    message=result.message,
                    order_id=order_id,
                    attempt_count=attempt + 1,
                    synced_at=datetime.utcnow()
                )
                self.db.add(sync_log)
                self.db.commit()

                if result.success:
                    return SyncResponse(
                        success=True,
                        message="Order synced successfully",
                        sync_log_id=sync_log.id,
                    )

                if attempt < self.max_retries - 1:
                    await asyncio.sleep(self.retry_delays[attempt])

            except Exception as e:
                sync_log = POSSyncLog(
                    integration_id=integration_id,
                    type=POSSyncType.ORDER_PUSH.value,
                    status=(
                        POSSyncStatus.RETRY.value
                        if attempt < self.max_retries - 1
                        else POSSyncStatus.FAILURE.value
                    ),
                    message=f"Attempt {attempt + 1} failed: {str(e)}",
                    order_id=order_id,
                    attempt_count=attempt + 1,
                    synced_at=datetime.utcnow()
                )
                self.db.add(sync_log)
                self.db.commit()

                if attempt < self.max_retries - 1:
                    await asyncio.sleep(self.retry_delays[attempt])

        return SyncResponse(success=False, message="Max retries exceeded")

    async def sync_menu_to_vendor(
        self,
        vendor: str,
        tenant_id: Optional[int] = None,
        team_id: Optional[int] = None
    ):
        if not self.is_sync_enabled(tenant_id, team_id):
            logger.info(
                f"POS menu sync skipped for tenant {tenant_id}, "
                f"team {team_id} - sync disabled"
            )
            return False

        logger.info(
            f"Syncing menu to {vendor} for tenant {tenant_id}, team {team_id}"
        )
        return True

    async def sync_orders_from_vendor(
        self,
        integration_id: int,
        tenant_id: Optional[int] = None,
        team_id: Optional[int] = None,
        since_timestamp: Optional[datetime] = None
    ) -> Dict[str, Any]:
        if not self.is_sync_enabled(tenant_id, team_id):
            logger.info(
                f"POS order sync skipped for tenant {tenant_id}, "
                f"team {team_id} - sync disabled"
            )
            return {"success": False, "message": "POS sync disabled"}

        integration = self.db.query(POSIntegration).filter(
            POSIntegration.id == integration_id
        ).first()

        if not integration:
            return {"success": False, "message": "Integration not found"}

        adapter = AdapterFactory.create_adapter(
            POSVendor(integration.vendor),
            integration.credentials
        )

        for attempt in range(self.max_retries):
            try:
                vendor_orders = await adapter.get_vendor_orders(
                    since_timestamp
                )

                results = []
                for order_data in vendor_orders.get("orders", []):
                    result = await self._process_vendor_order(
                        order_data, integration, tenant_id, team_id
                    )
                    results.append(result)

                return {
                    "success": True,
                    "message": f"Processed {len(results)} orders",
                    "results": results
                }

            except Exception as e:
                sync_log = POSSyncLog(
                    integration_id=integration_id,
                    type=POSSyncType.ORDER_PULL.value,
                    status=(
                        POSSyncStatus.RETRY.value
                        if attempt < self.max_retries - 1
                        else POSSyncStatus.FAILURE.value
                    ),
                    message=f"Attempt {attempt + 1} failed: {str(e)}",
                    attempt_count=attempt + 1,
                    synced_at=datetime.utcnow()
                )
                self.db.add(sync_log)
                self.db.commit()

                if attempt < self.max_retries - 1:
                    await asyncio.sleep(self.retry_delays[attempt])

        return {"success": False, "message": "Max retries exceeded"}

    def _resolve_menu_item_id_sync(
        self, pos_item_data: Dict[str, Any], vendor: str
    ) -> int:
        external_id = (pos_item_data.get("id") or
                       pos_item_data.get("menuItemId"))
        item_name = pos_item_data.get("name") or pos_item_data.get("itemName")

        if external_id:
            try:
                external_id_int = int(external_id)
                existing_mapping = self.db.query(MenuItemInventory).filter(
                    MenuItemInventory.menu_item_id == external_id_int
                ).first()
                if existing_mapping:
                    return existing_mapping.menu_item_id
            except (ValueError, TypeError):
                pass

        if item_name:
            logger.info(f"Could not resolve menu item by external_id, "
                        f"using fallback for item: {item_name}")

        category_fallbacks = {
            "beverage": 100,
            "food": 200,
            "dessert": 300,
            "appetizer": 400,
            "drink": 100,
            "coffee": 100,
            "tea": 100,
            "burger": 200,
            "pizza": 200,
            "sandwich": 200,
            "salad": 200,
            "cake": 300,
            "ice cream": 300,
            "cookie": 300,
            "soup": 400,
            "wings": 400,
            "fries": 400
        }

        if item_name:
            item_name_lower = item_name.lower()
            for category, fallback_id in category_fallbacks.items():
                if category in item_name_lower:
                    return fallback_id

        return 1

    def _normalize_price(self, price_data: Any, vendor: str) -> float:
        try:
            if vendor == POSVendor.SQUARE.value:
                return float(price_data) / 100
            elif vendor in [POSVendor.TOAST.value, POSVendor.CLOVER.value]:
                return float(price_data)
            else:
                return float(price_data)
        except (ValueError, TypeError):
            logger.warning(f"Invalid price data: {price_data} for vendor: "
                           f"{vendor}")
            return 0.0

    def _validate_pos_order_sync(self, order_data: Dict[str, Any]) -> bool:
        required_fields = ["staff_id", "status", "order_items"]
        if not all(field in order_data for field in required_fields):
            return False

        if not isinstance(order_data["order_items"], list):
            return False

        for item in order_data["order_items"]:
            if not all(key in item for key in ["quantity", "price"]):
                return False

            if (not isinstance(item["quantity"], (int, float)) or
                    item["quantity"] <= 0):
                return False

            if (not isinstance(item["price"], (int, float)) or
                    item["price"] < 0):
                return False

        return True

    def _transform_order_to_dict(self, order: Order) -> Dict[str, Any]:
        return {
            "id": order.id,
            "staff_id": order.staff_id,
            "table_no": order.table_no,
            "status": order.status,
            "items": [
                {
                    "id": item.id,
                    "menu_item_id": item.menu_item_id,
                    "quantity": item.quantity,
                    "price": float(item.price),
                    "notes": item.notes
                }
                for item in order.order_items
            ]
        }

    async def test_integration(self, integration_id: int) -> bool:
        integration = self.db.query(POSIntegration).filter(
            POSIntegration.id == integration_id
        ).first()

        if not integration:
            return False

        try:
            adapter = AdapterFactory.create_adapter(
                POSVendor(integration.vendor),
                integration.credentials
            )

            return await adapter.test_connection()
        except Exception:
            return False

    async def sync_all_active_integrations(
        self,
        order_id: int,
        tenant_id: Optional[int] = None,
        team_id: Optional[int] = None
    ) -> Dict[str, Any]:
        if not self.is_sync_enabled(tenant_id, team_id):
            logger.info(
                f"POS sync skipped for all integrations - tenant {tenant_id}, "
                f"team {team_id} - sync disabled"
            )
            return {
                "order_id": order_id,
                "total_integrations": 0,
                "results": [],
                "message": "POS sync disabled for this tenant/team"
            }

        active_integrations = self.db.query(POSIntegration).filter(
            POSIntegration.status == "active"
        ).all()

        results = []
        for integration in active_integrations:
            result = await self.sync_order_to_pos(
                order_id, integration.id, tenant_id, team_id
            )
            results.append({
                "integration_id": integration.id,
                "vendor": integration.vendor,
                "success": result.success,
                "message": result.message
            })

        return {
            "order_id": order_id,
            "total_integrations": len(active_integrations),
            "results": results
        }

    async def _process_vendor_order(
        self,
        order_data: Dict[str, Any],
        integration: POSIntegration,
        tenant_id: Optional[int] = None,
        team_id: Optional[int] = None
    ) -> Dict[str, Any]:
        external_id = order_data.get("external_id") or order_data.get("id")
        existing_order = self.db.query(Order).filter(
            Order.external_id == external_id
        ).first()

        if existing_order:
            return {
                "external_id": external_id,
                "status": "skipped",
                "message": "Order already exists"
            }

        transform_result = await self._transform_pos_order_data(
            order_data, integration.vendor
        )

        if not transform_result.success:
            return {
                "external_id": external_id,
                "status": "failed",
                "message": transform_result.error_message
            }

        if not self._validate_pos_order_sync(transform_result.order_data):
            return {
                "external_id": external_id,
                "status": "failed",
                "message": "Order validation failed"
            }

        try:
            order = await self._create_order_from_pos_data(
                transform_result.order_data, external_id, tenant_id, team_id
            )

            sync_log = POSSyncLog(
                integration_id=integration.id,
                type=POSSyncType.ORDER_PULL.value,
                status=POSSyncStatus.SUCCESS.value,
                message="Order created successfully",
                order_id=order.id,
                attempt_count=1,
                synced_at=datetime.utcnow()
            )
            self.db.add(sync_log)
            self.db.commit()

            return {
                "external_id": external_id,
                "order_id": order.id,
                "status": "created",
                "message": "Order created successfully"
            }

        except Exception as e:
            return {
                "external_id": external_id,
                "status": "failed",
                "message": f"Failed to create order: {str(e)}"
            }

    async def _transform_pos_order_data(
        self,
        order_data: Dict[str, Any],
        vendor: str
    ) -> POSOrderTransformResult:
        try:
            if vendor == POSVendor.TOAST.value:
                return self._transform_toast_order(order_data)
            elif vendor == POSVendor.SQUARE.value:
                return self._transform_square_order(order_data)
            elif vendor == POSVendor.CLOVER.value:
                return self._transform_clover_order(order_data)
            else:
                return POSOrderTransformResult(
                    success=False,
                    error_message=f"Unsupported vendor: {vendor}"
                )
        except Exception as e:
            return POSOrderTransformResult(
                success=False,
                error_message=f"Transformation failed: {str(e)}"
            )

    def _transform_toast_order(
        self, order_data: Dict[str, Any]
    ) -> POSOrderTransformResult:
        order_items = []
        for item in order_data.get("selections", []):
            menu_item_id = self._resolve_menu_item_id_sync(
                item, POSVendor.TOAST.value
            )
            price = self._normalize_price(
                item.get("unitPrice", 0), POSVendor.TOAST.value
            )
            order_items.append({
                "menu_item_id": menu_item_id,
                "quantity": item.get("quantity", 1),
                "price": price,
                "notes": item.get("specialInstructions", "")
            })

        transformed = {
            "staff_id": 1,
            "table_no": order_data.get("metadata", {}).get("tableNumber"),
            "status": self._map_pos_status_to_aura_status(
                order_data.get("status", "pending")
            ),
            "order_items": order_items
        }

        return POSOrderTransformResult(success=True, order_data=transformed)

    def _transform_square_order(
        self, order_data: Dict[str, Any]
    ) -> POSOrderTransformResult:
        order = order_data.get("order", {})
        order_items = []
        for item in order.get("line_items", []):
            menu_item_id = self._resolve_menu_item_id_sync(
                item, POSVendor.SQUARE.value
            )
            price = self._normalize_price(
                item.get("base_price_money", {}).get("amount", 0),
                POSVendor.SQUARE.value
            )
            order_items.append({
                "menu_item_id": menu_item_id,
                "quantity": int(item.get("quantity", 1)),
                "price": price,
                "notes": item.get("note", "")
            })

        transformed = {
            "staff_id": 1,
            "table_no": order.get("metadata", {}).get("table_no"),
            "status": self._map_pos_status_to_aura_status(
                order.get("state", "pending")
            ),
            "order_items": order_items
        }

        return POSOrderTransformResult(success=True, order_data=transformed)

    def _transform_clover_order(
        self, order_data: Dict[str, Any]
    ) -> POSOrderTransformResult:
        order_items = []
        for item in order_data.get("lineItems", []):
            menu_item_id = self._resolve_menu_item_id_sync(
                item, POSVendor.CLOVER.value
            )
            price = self._normalize_price(
                item.get("price", 0), POSVendor.CLOVER.value
            )
            order_items.append({
                "menu_item_id": menu_item_id,
                "quantity": item.get("quantity", 1),
                "price": price,
                "notes": item.get("note", "")
            })

        transformed = {
            "staff_id": 1,
            "table_no": order_data.get("metadata", {}).get("table_number"),
            "status": self._map_pos_status_to_aura_status(
                order_data.get("state", "pending")
            ),
            "order_items": order_items
        }

        return POSOrderTransformResult(success=True, order_data=transformed)

    def _map_pos_status_to_aura_status(self, pos_status: str) -> str:
        status_mapping = {
            "pending": OrderStatus.PENDING.value,
            "confirmed": OrderStatus.IN_PROGRESS.value,
            "preparing": OrderStatus.IN_KITCHEN.value,
            "ready": OrderStatus.READY.value,
            "completed": OrderStatus.COMPLETED.value,
            "cancelled": OrderStatus.CANCELLED.value
        }
        return status_mapping.get(
            pos_status.lower(), OrderStatus.PENDING.value
        )

    async def _create_order_from_pos_data(
        self,
        order_data: Dict[str, Any],
        external_id: str,
        tenant_id: Optional[int] = None,
        team_id: Optional[int] = None
    ) -> Order:
        order = Order(
            staff_id=order_data["staff_id"],
            table_no=order_data.get("table_no"),
            status=order_data["status"],
            external_id=external_id
        )

        self.db.add(order)
        self.db.flush()

        for item_data in order_data["order_items"]:
            order_item = OrderItem(
                order_id=order.id,
                menu_item_id=item_data["menu_item_id"],
                quantity=item_data["quantity"],
                price=item_data["price"],
                notes=item_data.get("notes")
            )
            self.db.add(order_item)

        self.db.commit()
        self.db.refresh(order)
        return order
