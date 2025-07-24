import asyncio
from sqlalchemy.orm import Session, joinedload
from typing import Dict, Any
from datetime import datetime
from ..models.pos_integration import POSIntegration
from ..models.pos_sync_log import POSSyncLog
from ..adapters.adapter_factory import AdapterFactory
from ..enums.pos_enums import POSVendor, POSSyncStatus, POSSyncType
from ..schemas.pos_schemas import SyncResponse
from ...orders.models.order_models import Order


class POSBridgeService:
    def __init__(self, db: Session):
        self.db = db
        self.max_retries = 3
        self.retry_delays = [1, 5, 15]

    async def sync_order_to_pos(
        self, order_id: int, integration_id: int
    ) -> SyncResponse:
        integration = self.db.query(POSIntegration).filter(
            POSIntegration.id == integration_id
        ).first()

        if not integration:
            return SyncResponse(success=False, message="Integration not found")

        order = self.db.query(Order).options(joinedload(Order.order_items)).filter(
            Order.id == order_id
        ).first()
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

    async def sync_all_active_integrations(self, order_id: int) -> Dict[str, Any]:
        active_integrations = self.db.query(POSIntegration).filter(
            POSIntegration.status == "active"
        ).all()

        results = []
        for integration in active_integrations:
            result = await self.sync_order_to_pos(order_id, integration.id)
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
