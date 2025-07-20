from backend.modules.order.schemas.order_schemas import OrderCreate


async def create_order_service(order_data: OrderCreate):
    return {
        "message": "Order created successfully",
        "data": {
            "id": 1,
            "table_no": order_data.table_no,
            "customer_id": order_data.customer_id,
            "status": "pending",
            "created_at": "2025-07-20T00:41:14Z",
            "order_items": [
                {
                    "id": i + 1,
                    "order_id": 1,
                    "item_name": item.item_name,
                    "station": item.station,
                    "status": "pending",
                    "started_at": None,
                    "completed_at": None
                }
                for i, item in enumerate(order_data.order_items)
            ]
        }
    }
