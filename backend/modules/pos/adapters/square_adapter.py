import httpx
from typing import Dict, Any
from .base_adapter import BasePOSAdapter
from ..schemas.pos_schemas import SyncResponse


class SquareAdapter(BasePOSAdapter):
    def __init__(self, credentials: Dict[str, Any]):
        super().__init__(credentials)
        self.base_url = "https://connect.squareup.com/v2"
        self.headers = {
            "Authorization": f"Bearer {credentials.get('access_token')}",
            "Content-Type": "application/json"
        }

    async def push_order(self, order_data: Dict[str, Any]) -> SyncResponse:
        transformed_data = self.transform_order_data(order_data)

        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(
                    f"{self.base_url}/orders",
                    json=transformed_data,
                    headers=self.headers,
                    timeout=30.0,
                )
                response.raise_for_status()
                return SyncResponse(
                    success=True, message="Order pushed successfully to Square"
                )
            except httpx.HTTPError as e:
                return SyncResponse(
                    success=False, message=f"Square API error: {str(e)}"
                )

    async def test_connection(self) -> bool:
        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(
                    f"{self.base_url}/locations",
                    headers=self.headers,
                    timeout=10.0
                )
                return response.status_code == 200
            except Exception:
                return False

    def transform_order_data(self, order: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "order": {
                "location_id": self.credentials.get("location_id"),
                "line_items": [
                    {
                        "name": f"Menu Item {item['menu_item_id']}",
                        "quantity": str(item["quantity"]),
                        "base_price_money": {
                            "amount": int(item["price"] * 100),
                            "currency": "USD"
                        },
                        "note": item.get("notes", "")
                    }
                    for item in order.get("items", [])
                ],
                "metadata": {
                    "aura_order_id": str(order["id"]),
                    "table_no": str(order.get("table_no", "")),
                    "staff_id": str(order["staff_id"])
                }
            }
        }

    async def get_vendor_orders(self) -> Dict[str, Any]:
        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(
                    f"{self.base_url}/orders/search",
                    headers=self.headers,
                    timeout=30.0
                )
                response.raise_for_status()
                return response.json()
            except httpx.HTTPError:
                return {}
