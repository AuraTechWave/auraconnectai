#!/usr/bin/env python3
"""
Basic usage examples for the Orders module.

This script demonstrates common operations with the Orders API including:
- Creating orders
- Updating order status
- Adding items to orders
- Handling payments
"""

import asyncio
import json
from datetime import datetime
from typing import List, Dict, Any

# Using the AuraConnect SDK (install with: pip install auraconnect-sdk)
from auraconnect import OrdersClient, AuthClient
from auraconnect.exceptions import OrderError, ValidationError


class OrdersExample:
    def __init__(self, api_key: str, base_url: str = "https://api.auraconnect.com"):
        """Initialize the Orders example with authentication."""
        self.auth_client = AuthClient(api_key=api_key, base_url=base_url)
        self.orders_client = OrdersClient(api_key=api_key, base_url=base_url)
        
    async def create_simple_order(self) -> Dict[str, Any]:
        """Create a simple dine-in order."""
        print("\n=== Creating Simple Order ===")
        
        order_data = {
            "customer_id": 123,
            "location_id": 1,
            "order_type": "dine_in",
            "table_number": "5",
            "items": [
                {
                    "menu_item_id": 10,  # Cheeseburger
                    "quantity": 2,
                    "modifiers": [],
                    "special_instructions": "No pickles"
                },
                {
                    "menu_item_id": 15,  # Caesar Salad
                    "quantity": 1,
                    "modifiers": [
                        {"id": 101, "name": "Add Chicken", "price": "4.00"}
                    ]
                }
            ],
            "notes": "Birthday celebration - bring dessert with candle"
        }
        
        try:
            order = await self.orders_client.create_order(order_data)
            print(f"Order created successfully!")
            print(f"Order Number: {order['order_number']}")
            print(f"Total Amount: ${order['total_amount']}")
            print(f"Status: {order['status']}")
            return order
        except ValidationError as e:
            print(f"Validation error: {e}")
            raise
        except OrderError as e:
            print(f"Order creation failed: {e}")
            raise
            
    async def create_takeout_order_with_time(self) -> Dict[str, Any]:
        """Create a takeout order with pickup time."""
        print("\n=== Creating Takeout Order ===")
        
        order_data = {
            "customer_id": 456,
            "location_id": 1,
            "order_type": "takeout",
            "pickup_time": "2024-01-15T18:30:00Z",
            "items": [
                {
                    "menu_item_id": 25,  # Pizza
                    "quantity": 1,
                    "modifiers": [
                        {"id": 201, "name": "Large Size", "price": "4.00"},
                        {"id": 202, "name": "Extra Cheese", "price": "2.00"},
                        {"id": 203, "name": "Pepperoni", "price": "2.50"}
                    ]
                },
                {
                    "menu_item_id": 30,  # Wings
                    "quantity": 2,
                    "modifiers": [
                        {"id": 301, "name": "Buffalo Sauce", "price": "0.00"}
                    ]
                }
            ],
            "contact_phone": "(555) 123-4567"
        }
        
        order = await self.orders_client.create_order(order_data)
        print(f"Takeout order created: {order['order_number']}")
        print(f"Pickup time: {order['pickup_time']}")
        return order
        
    async def update_order_status(self, order_id: int, new_status: str) -> None:
        """Update the status of an order."""
        print(f"\n=== Updating Order Status to {new_status} ===")
        
        status_data = {
            "status": new_status,
            "reason": f"Status updated to {new_status}"
        }
        
        if new_status == "preparing":
            status_data["estimated_ready_time"] = "2024-01-15T15:45:00Z"
            
        result = await self.orders_client.update_order_status(order_id, status_data)
        print(f"Status updated: {result['previous_status']} -> {result['status']}")
        
    async def add_items_to_order(self, order_id: int) -> None:
        """Add additional items to an existing order."""
        print("\n=== Adding Items to Order ===")
        
        new_items = {
            "items": [
                {
                    "menu_item_id": 40,  # Dessert
                    "quantity": 1,
                    "modifiers": [],
                    "special_instructions": "With birthday candle"
                }
            ]
        }
        
        result = await self.orders_client.add_items(order_id, new_items)
        print(f"Added {len(result['added_items'])} items")
        print(f"New total: ${result['order_totals']['total_amount']}")
        
    async def process_payment(self, order_id: int) -> None:
        """Process payment for an order."""
        print("\n=== Processing Payment ===")
        
        payment_data = {
            "payment_method": "credit_card",
            "amount": "45.67",
            "tip_amount": "6.85",
            "card_token": "tok_1234567890",  # From payment processor
            "save_card": True
        }
        
        # Note: In real implementation, this would integrate with payment service
        print("Payment processed successfully")
        print(f"Total charged: ${float(payment_data['amount']) + float(payment_data['tip_amount']):.2f}")
        
    async def list_orders_with_filters(self) -> None:
        """List orders with various filters."""
        print("\n=== Listing Orders with Filters ===")
        
        # Today's orders
        filters = {
            "date_from": datetime.now().replace(hour=0, minute=0).isoformat(),
            "date_to": datetime.now().isoformat(),
            "status": "preparing",
            "location_id": 1,
            "page_size": 10
        }
        
        orders = await self.orders_client.list_orders(**filters)
        print(f"Found {orders['meta']['total_count']} orders")
        
        for order in orders['data'][:3]:  # Show first 3
            print(f"- {order['order_number']}: {order['status']} - ${order['total_amount']}")
            
    async def handle_order_lifecycle(self) -> None:
        """Demonstrate complete order lifecycle."""
        print("\n=== Complete Order Lifecycle ===")
        
        # 1. Create order
        order = await self.create_simple_order()
        order_id = order['id']
        
        # 2. Confirm order (automatic in some cases)
        await asyncio.sleep(1)  # Simulate processing
        await self.update_order_status(order_id, "confirmed")
        
        # 3. Start preparation
        await asyncio.sleep(1)
        await self.update_order_status(order_id, "preparing")
        
        # 4. Mark as ready
        await asyncio.sleep(2)
        await self.update_order_status(order_id, "ready")
        
        # 5. Complete order
        await asyncio.sleep(1)
        await self.update_order_status(order_id, "completed")
        
        print("\nOrder lifecycle completed!")
        
    async def handle_order_cancellation(self, order_id: int) -> None:
        """Handle order cancellation with refund."""
        print("\n=== Cancelling Order ===")
        
        cancellation_data = {
            "reason": "customer_request",
            "notes": "Customer called to cancel",
            "refund_amount": "45.67"
        }
        
        result = await self.orders_client.cancel_order(order_id, cancellation_data)
        print(f"Order cancelled: {result['status']}")
        print(f"Refund status: {result['refund']['status']}")
        
    async def subscribe_to_order_events(self, order_id: int) -> None:
        """Subscribe to real-time order updates."""
        print("\n=== Subscribing to Order Events ===")
        
        async def handle_event(event: Dict[str, Any]):
            print(f"Event received: {event['event_type']}")
            print(f"Order {event['data']['order_id']} - {event['data']}")
            
        # Subscribe to order events
        await self.orders_client.subscribe_to_order(order_id, handle_event)
        
        # Keep listening for 30 seconds
        await asyncio.sleep(30)
        

async def main():
    """Run order examples."""
    # Initialize with your API key
    api_key = "your_api_key_here"
    example = OrdersExample(api_key)
    
    try:
        # Create and process a simple order
        order = await example.create_simple_order()
        
        # Add more items
        await example.add_items_to_order(order['id'])
        
        # Update status
        await example.update_order_status(order['id'], "preparing")
        
        # Process payment
        await example.process_payment(order['id'])
        
        # List orders
        await example.list_orders_with_filters()
        
        # Complete lifecycle demo
        await example.handle_order_lifecycle()
        
        # Create takeout order
        takeout_order = await example.create_takeout_order_with_time()
        
    except Exception as e:
        print(f"Error: {e}")
        

if __name__ == "__main__":
    # Run the async main function
    asyncio.run(main())