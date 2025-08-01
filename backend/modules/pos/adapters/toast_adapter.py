import httpx
from typing import Dict, Any, Optional, List
from datetime import datetime
from .base_adapter import BasePOSAdapter
from ..schemas.pos_schemas import SyncResponse


class ToastAdapter(BasePOSAdapter):
    def __init__(self, credentials: Dict[str, Any]):
        super().__init__(credentials)
        self.base_url = "https://ws-api.toasttab.com"
        self.headers = {
            "Authorization": f"Bearer {credentials.get('access_token')}",
            "Content-Type": "application/json",
            "Toast-Restaurant-External-ID": credentials.get(
                "restaurant_id", ""
            )
        }

    async def push_order(self, order_data: Dict[str, Any]) -> SyncResponse:
        transformed_data = self.transform_order_data(order_data)

        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(
                    f"{self.base_url}/orders/v2/orders",
                    json=transformed_data,
                    headers=self.headers,
                    timeout=30.0
                )
                response.raise_for_status()
                return SyncResponse(
                    success=True, message="Order pushed successfully to Toast"
                )
            except httpx.HTTPError as e:
                return SyncResponse(
                    success=False, message=f"Toast API error: {str(e)}"
                )

    async def test_connection(self) -> bool:
        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(
                    f"{self.base_url}/config/v1/restaurants",
                    headers=self.headers,
                    timeout=10.0
                )
                return response.status_code == 200
            except Exception:
                return False

    def transform_order_data(self, order: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "externalId": f"aura-{order['id']}",
            "orderType": "DINE_IN",
            "selections": [
                {
                    "externalId": f"item-{item['id']}",
                    "menuItemId": item["menu_item_id"],
                    "quantity": item["quantity"],
                    "unitPrice": float(item["price"]),
                    "specialInstructions": item.get("notes", "")
                }
                for item in order.get("items", [])
            ],
            "metadata": {
                "tableNumber": order.get("table_no"),
                "staffId": order["staff_id"],
                "auraOrderId": order["id"]
            }
        }

    async def get_vendor_orders(
        self, since_timestamp: Optional[datetime] = None
    ) -> Dict[str, Any]:
        async with httpx.AsyncClient() as client:
            try:
                params = {}
                if since_timestamp:
                    params["modifiedAfter"] = since_timestamp.isoformat()

                response = await client.get(
                    f"{self.base_url}/orders/v2/orders",
                    headers=self.headers,
                    params=params,
                    timeout=30.0
                )
                response.raise_for_status()
                return response.json()
            except httpx.HTTPError:
                return {"orders": []}

    # Menu synchronization method stubs - Toast integration not fully implemented
    async def get_menu_categories(self, since_timestamp: Optional[datetime] = None) -> List[Dict[str, Any]]:
        return []

    async def get_menu_items(self, since_timestamp: Optional[datetime] = None) -> List[Dict[str, Any]]:
        return []

    async def get_modifier_groups(self, since_timestamp: Optional[datetime] = None) -> List[Dict[str, Any]]:
        return []

    async def get_modifiers(self, modifier_group_id: str) -> List[Dict[str, Any]]:
        return []

    async def create_menu_category(self, category_data: Dict[str, Any]) -> Dict[str, Any]:
        raise NotImplementedError("Toast menu sync not implemented")

    async def update_menu_category(self, category_id: str, category_data: Dict[str, Any]) -> Dict[str, Any]:
        raise NotImplementedError("Toast menu sync not implemented")

    async def delete_menu_category(self, category_id: str) -> bool:
        raise NotImplementedError("Toast menu sync not implemented")

    async def create_menu_item(self, item_data: Dict[str, Any]) -> Dict[str, Any]:
        raise NotImplementedError("Toast menu sync not implemented")

    async def update_menu_item(self, item_id: str, item_data: Dict[str, Any]) -> Dict[str, Any]:
        raise NotImplementedError("Toast menu sync not implemented")

    async def delete_menu_item(self, item_id: str) -> bool:
        raise NotImplementedError("Toast menu sync not implemented")

    async def create_modifier_group(self, modifier_group_data: Dict[str, Any]) -> Dict[str, Any]:
        raise NotImplementedError("Toast menu sync not implemented")

    async def update_modifier_group(self, modifier_group_id: str, modifier_group_data: Dict[str, Any]) -> Dict[str, Any]:
        raise NotImplementedError("Toast menu sync not implemented")

    async def delete_modifier_group(self, modifier_group_id: str) -> bool:
        raise NotImplementedError("Toast menu sync not implemented")

    async def create_modifier(self, modifier_group_id: str, modifier_data: Dict[str, Any]) -> Dict[str, Any]:
        raise NotImplementedError("Toast menu sync not implemented")

    async def update_modifier(self, modifier_id: str, modifier_data: Dict[str, Any]) -> Dict[str, Any]:
        raise NotImplementedError("Toast menu sync not implemented")

    async def delete_modifier(self, modifier_id: str) -> bool:
        raise NotImplementedError("Toast menu sync not implemented")
