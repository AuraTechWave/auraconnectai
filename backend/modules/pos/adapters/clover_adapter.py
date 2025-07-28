import httpx
from typing import Dict, Any, Optional, List
from datetime import datetime
from .base_adapter import BasePOSAdapter
from ..schemas.pos_schemas import SyncResponse


class CloverAdapter(BasePOSAdapter):
    def __init__(self, credentials: Dict[str, Any]):
        super().__init__(credentials)
        self.base_url = "https://api.clover.com/v3"
        self.merchant_id = credentials.get("merchant_id")
        self.headers = {
            "Authorization": f"Bearer {credentials.get('access_token')}",
            "Content-Type": "application/json"
        }

    async def push_order(self, order_data: Dict[str, Any]) -> SyncResponse:
        transformed_data = self.transform_order_data(order_data)

        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(
                    f"{self.base_url}/merchants/{self.merchant_id}/orders",
                    json=transformed_data,
                    headers=self.headers,
                    timeout=30.0
                )
                response.raise_for_status()
                return SyncResponse(
                    success=True, message="Order pushed successfully to Clover"
                )
            except httpx.HTTPError as e:
                return SyncResponse(
                    success=False, message=f"Clover API error: {str(e)}"
                )

    async def test_connection(self) -> bool:
        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(
                    f"{self.base_url}/merchants/{self.merchant_id}",
                    headers=self.headers,
                    timeout=10.0
                )
                return response.status_code == 200
            except Exception:
                return False

    def transform_order_data(self, order: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "state": "open",
            "orderType": {
                "id": "dine_in"
            },
            "lineItems": [
                {
                    "name": f"Menu Item {item['menu_item_id']}",
                    "price": int(item["price"] * 100),
                    "unitQty": item["quantity"],
                    "note": item.get("notes", "")
                }
                for item in order.get("items", [])
            ],
            "note": (
                f"Aura Order #{order['id']} - "
                f"Table {order.get('table_no', 'N/A')} - "
                f"Staff {order['staff_id']}"
            )
        }

    async def get_vendor_orders(
        self, since_timestamp: Optional[datetime] = None
    ) -> Dict[str, Any]:
        async with httpx.AsyncClient() as client:
            try:
                params = {}
                if since_timestamp:
                    timestamp_ms = int(since_timestamp.timestamp() * 1000)
                    params["filter"] = f"modifiedTime>={timestamp_ms}"

                response = await client.get(
                    f"{self.base_url}/merchants/{self.merchant_id}/orders",
                    headers=self.headers,
                    params=params,
                    timeout=30.0
                )
                response.raise_for_status()
                return response.json()
            except httpx.HTTPError:
                return {"orders": []}

    # Menu synchronization method stubs - Clover integration not fully implemented
    async def get_menu_categories(self, since_timestamp: Optional[datetime] = None) -> List[Dict[str, Any]]:
        return []

    async def get_menu_items(self, since_timestamp: Optional[datetime] = None) -> List[Dict[str, Any]]:
        return []

    async def get_modifier_groups(self, since_timestamp: Optional[datetime] = None) -> List[Dict[str, Any]]:
        return []

    async def get_modifiers(self, modifier_group_id: str) -> List[Dict[str, Any]]:
        return []

    async def create_menu_category(self, category_data: Dict[str, Any]) -> Dict[str, Any]:
        raise NotImplementedError("Clover menu sync not implemented")

    async def update_menu_category(self, category_id: str, category_data: Dict[str, Any]) -> Dict[str, Any]:
        raise NotImplementedError("Clover menu sync not implemented")

    async def delete_menu_category(self, category_id: str) -> bool:
        raise NotImplementedError("Clover menu sync not implemented")

    async def create_menu_item(self, item_data: Dict[str, Any]) -> Dict[str, Any]:
        raise NotImplementedError("Clover menu sync not implemented")

    async def update_menu_item(self, item_id: str, item_data: Dict[str, Any]) -> Dict[str, Any]:
        raise NotImplementedError("Clover menu sync not implemented")

    async def delete_menu_item(self, item_id: str) -> bool:
        raise NotImplementedError("Clover menu sync not implemented")

    async def create_modifier_group(self, modifier_group_data: Dict[str, Any]) -> Dict[str, Any]:
        raise NotImplementedError("Clover menu sync not implemented")

    async def update_modifier_group(self, modifier_group_id: str, modifier_group_data: Dict[str, Any]) -> Dict[str, Any]:
        raise NotImplementedError("Clover menu sync not implemented")

    async def delete_modifier_group(self, modifier_group_id: str) -> bool:
        raise NotImplementedError("Clover menu sync not implemented")

    async def create_modifier(self, modifier_group_id: str, modifier_data: Dict[str, Any]) -> Dict[str, Any]:
        raise NotImplementedError("Clover menu sync not implemented")

    async def update_modifier(self, modifier_id: str, modifier_data: Dict[str, Any]) -> Dict[str, Any]:
        raise NotImplementedError("Clover menu sync not implemented")

    async def delete_modifier(self, modifier_id: str) -> bool:
        raise NotImplementedError("Clover menu sync not implemented")
