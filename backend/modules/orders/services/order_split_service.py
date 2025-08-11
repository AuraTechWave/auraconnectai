"""
Order splitting service for managing order splits and payment distribution.
"""

import logging
from typing import List, Dict, Any, Optional, Tuple
from decimal import Decimal
from datetime import datetime
from sqlalchemy.orm import Session, joinedload
from sqlalchemy.exc import SQLAlchemyError
from fastapi import HTTPException, status

from ..models.order_models import Order, OrderItem, OrderSplit, SplitPayment
from ..schemas.order_split_schemas import (
    OrderSplitRequest, OrderSplitResponse, SplitType, PaymentStatus,
    OrderItemSplitRequest, PaymentSplitRequest, SplitOrderSummary,
    OrderSplitDetail, SplitPaymentDetail, BulkSplitRequest,
    SplitValidationResponse, MergeSplitRequest
)
from ..enums.order_enums import OrderStatus
from ...customers.models import Customer
from ...staff.models import StaffMember
from .order_service import create_order_with_items
from .webhook_service import WebhookService
from ..enums.webhook_enums import WebhookEventType

logger = logging.getLogger(__name__)


class OrderSplitService:
    """Service for handling order splitting operations"""
    
    def __init__(self, db: Session):
        self.db = db
        self.webhook_service = WebhookService(db)
    
    def validate_split_request(
        self,
        order_id: int,
        split_request: OrderSplitRequest
    ) -> SplitValidationResponse:
        """
        Validate if an order can be split as requested.
        
        Args:
            order_id: ID of the order to split
            split_request: Split request details
            
        Returns:
            SplitValidationResponse with validation details
        """
        # Get the order with items
        order = self.db.query(Order).options(
            joinedload(Order.order_items)
        ).filter(Order.id == order_id).first()
        
        if not order:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Order {order_id} not found"
            )
        
        # Check order status
        if order.status in [OrderStatus.COMPLETED, OrderStatus.CANCELLED]:
            return SplitValidationResponse(
                can_split=False,
                reason=f"Cannot split order with status {order.status}",
                splittable_items=[],
                estimated_totals={}
            )
        
        # Validate requested items
        warnings = []
        splittable_items = []
        item_map = {item.id: item for item in order.order_items}
        
        for split_item in split_request.items:
            if split_item.item_id not in item_map:
                warnings.append(f"Item {split_item.item_id} not found in order")
                continue
            
            order_item = item_map[split_item.item_id]
            
            # Check if already split
            existing_splits = self._get_item_split_count(order_id, split_item.item_id)
            available_qty = order_item.quantity - existing_splits
            
            if split_item.quantity > available_qty:
                warnings.append(
                    f"Item {split_item.item_id}: requested {split_item.quantity} "
                    f"but only {available_qty} available"
                )
                continue
            
            splittable_items.append({
                "item_id": split_item.item_id,
                "menu_item_id": order_item.menu_item_id,
                "quantity": split_item.quantity,
                "unit_price": float(order_item.price),
                "total_price": float(order_item.price * split_item.quantity)
            })
        
        # Calculate estimated totals
        subtotal = sum(item["total_price"] for item in splittable_items)
        tax_rate = float(order.tax_amount / order.subtotal) if order.subtotal else 0
        tax_amount = subtotal * tax_rate
        total = subtotal + tax_amount
        
        estimated_totals = {
            "subtotal": Decimal(str(subtotal)),
            "tax_amount": Decimal(str(tax_amount)),
            "total_amount": Decimal(str(total))
        }
        
        return SplitValidationResponse(
            can_split=len(splittable_items) > 0,
            reason=None if splittable_items else "No valid items to split",
            splittable_items=splittable_items,
            warnings=warnings,
            estimated_totals=estimated_totals
        )
    
    def split_order(
        self,
        order_id: int,
        split_request: OrderSplitRequest,
        current_user_id: int
    ) -> OrderSplitResponse:
        """
        Split an order into multiple orders.
        
        Args:
            order_id: ID of the order to split
            split_request: Split request details
            current_user_id: ID of the user performing the split
            
        Returns:
            OrderSplitResponse with split details
        """
        try:
            # Validate the split request
            validation = self.validate_split_request(order_id, split_request)
            if not validation.can_split:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=validation.reason or "Cannot split order"
                )
            
            # Get the parent order with lock to prevent concurrent splits
            parent_order = self.db.query(Order).filter(
                Order.id == order_id
            ).with_for_update().first()
            
            # Create split orders based on type
            if split_request.split_type == SplitType.TICKET:
                split_results = self._split_by_ticket(
                    parent_order, split_request, current_user_id
                )
            elif split_request.split_type == SplitType.DELIVERY:
                split_results = self._split_by_delivery(
                    parent_order, split_request, current_user_id
                )
            elif split_request.split_type == SplitType.PAYMENT:
                split_results = self._split_by_payment(
                    parent_order, split_request, current_user_id
                )
            else:
                raise ValueError(f"Unknown split type: {split_request.split_type}")
            
            self.db.commit()
            
            # Send webhook notifications
            for split_order_id in split_results["split_order_ids"]:
                self.webhook_service.trigger_webhook(
                    WebhookEventType.ORDER_SPLIT,
                    {
                        "parent_order_id": order_id,
                        "split_order_id": split_order_id,
                        "split_type": split_request.split_type.value
                    }
                )
            
            return OrderSplitResponse(
                success=True,
                message=f"Order split successfully into {len(split_results['split_order_ids'])} orders",
                parent_order_id=order_id,
                split_order_ids=split_results["split_order_ids"],
                split_details=split_results["details"]
            )
            
        except SQLAlchemyError as e:
            self.db.rollback()
            logger.error(f"Database error during order split: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to split order"
            )
    
    def _split_by_ticket(
        self,
        parent_order: Order,
        split_request: OrderSplitRequest,
        user_id: int
    ) -> Dict[str, Any]:
        """Split order for different kitchen tickets"""
        split_order_ids = []
        split_details = []
        
        # Group items by station or custom logic
        item_groups = self._group_items_for_ticket_split(
            parent_order, split_request.items
        )
        
        for group_name, items in item_groups.items():
            # Create new order for this ticket
            new_order = Order(
                staff_id=parent_order.staff_id,
                customer_id=parent_order.customer_id,
                table_no=parent_order.table_no,
                status=OrderStatus.PENDING,
                category_id=parent_order.category_id,
                customer_notes=f"Split from order #{parent_order.id} - {group_name}",
                external_id=f"{parent_order.external_id}_split_{len(split_order_ids) + 1}" if parent_order.external_id else None
            )
            self.db.add(new_order)
            self.db.flush()
            
            # Create order items
            subtotal = Decimal('0')
            for item_data in items:
                order_item = OrderItem(
                    order_id=new_order.id,
                    menu_item_id=item_data["menu_item_id"],
                    quantity=item_data["quantity"],
                    price=item_data["price"],
                    notes=item_data.get("notes")
                )
                self.db.add(order_item)
                subtotal += order_item.price * order_item.quantity
            
            # Calculate totals
            tax_rate = float(parent_order.tax_amount / parent_order.subtotal) if parent_order.subtotal else 0
            tax_amount = subtotal * Decimal(str(tax_rate))
            total_amount = subtotal + tax_amount
            
            new_order.subtotal = subtotal
            new_order.tax_amount = tax_amount
            new_order.total_amount = total_amount
            new_order.final_amount = total_amount
            
            # Create split record
            order_split = OrderSplit(
                parent_order_id=parent_order.id,
                split_order_id=new_order.id,
                split_type=SplitType.TICKET.value,
                split_reason=split_request.split_reason or f"Kitchen ticket split - {group_name}",
                split_by=user_id,
                split_metadata={
                    "group_name": group_name,
                    "item_count": len(items)
                }
            )
            self.db.add(order_split)
            
            split_order_ids.append(new_order.id)
            split_details.append({
                "split_order_id": new_order.id,
                "group_name": group_name,
                "items": items,
                "total_amount": float(total_amount)
            })
        
        return {
            "split_order_ids": split_order_ids,
            "details": split_details
        }
    
    def _split_by_delivery(
        self,
        parent_order: Order,
        split_request: OrderSplitRequest,
        user_id: int
    ) -> Dict[str, Any]:
        """Split order for separate deliveries"""
        # Create a new order for the split items
        new_order = Order(
            staff_id=parent_order.staff_id,
            customer_id=split_request.customer_id or parent_order.customer_id,
            table_no=split_request.table_no,
            status=OrderStatus.PENDING,
            category_id=parent_order.category_id,
            customer_notes=f"Delivery split from order #{parent_order.id}",
            scheduled_fulfillment_time=split_request.scheduled_time,
            external_id=f"{parent_order.external_id}_delivery" if parent_order.external_id else None
        )
        self.db.add(new_order)
        self.db.flush()
        
        # Get parent order items
        parent_items = {item.id: item for item in parent_order.order_items}
        
        # Create split order items
        subtotal = Decimal('0')
        for split_item in split_request.items:
            parent_item = parent_items[split_item.item_id]
            
            order_item = OrderItem(
                order_id=new_order.id,
                menu_item_id=parent_item.menu_item_id,
                quantity=split_item.quantity,
                price=parent_item.price,
                notes=split_item.notes or parent_item.notes
            )
            self.db.add(order_item)
            subtotal += order_item.price * order_item.quantity
        
        # Calculate totals
        tax_rate = float(parent_order.tax_amount / parent_order.subtotal) if parent_order.subtotal else 0
        tax_amount = subtotal * Decimal(str(tax_rate))
        total_amount = subtotal + tax_amount
        
        new_order.subtotal = subtotal
        new_order.tax_amount = tax_amount
        new_order.total_amount = total_amount
        new_order.final_amount = total_amount
        
        # Create split record
        order_split = OrderSplit(
            parent_order_id=parent_order.id,
            split_order_id=new_order.id,
            split_type=SplitType.DELIVERY.value,
            split_reason=split_request.split_reason or "Separate delivery requested",
            split_by=user_id,
            split_metadata={
                "delivery_address": split_request.delivery_address,
                "scheduled_time": split_request.scheduled_time.isoformat() if split_request.scheduled_time else None
            }
        )
        self.db.add(order_split)
        
        return {
            "split_order_ids": [new_order.id],
            "details": [{
                "split_order_id": new_order.id,
                "delivery_type": "separate",
                "scheduled_time": split_request.scheduled_time,
                "total_amount": float(total_amount)
            }]
        }
    
    def _split_by_payment(
        self,
        parent_order: Order,
        split_request: OrderSplitRequest,
        user_id: int
    ) -> Dict[str, Any]:
        """Split order for payment purposes"""
        # For payment splits, we typically create multiple orders
        # each representing a portion of the payment
        split_order_ids = []
        split_details = []
        
        # Group items by customer or payment method
        customer_groups = self._group_items_by_customer(
            parent_order, split_request.items
        )
        
        for customer_id, items in customer_groups.items():
            # Create order for this payment split
            new_order = Order(
                staff_id=parent_order.staff_id,
                customer_id=customer_id,
                table_no=parent_order.table_no,
                status=parent_order.status,
                category_id=parent_order.category_id,
                customer_notes=f"Payment split from order #{parent_order.id}"
            )
            self.db.add(new_order)
            self.db.flush()
            
            # Create order items and calculate totals
            subtotal = Decimal('0')
            for item_data in items:
                order_item = OrderItem(
                    order_id=new_order.id,
                    menu_item_id=item_data["menu_item_id"],
                    quantity=item_data["quantity"],
                    price=item_data["price"],
                    notes=item_data.get("notes")
                )
                self.db.add(order_item)
                subtotal += order_item.price * order_item.quantity
            
            # Calculate totals
            tax_rate = float(parent_order.tax_amount / parent_order.subtotal) if parent_order.subtotal else 0
            tax_amount = subtotal * Decimal(str(tax_rate))
            total_amount = subtotal + tax_amount
            
            new_order.subtotal = subtotal
            new_order.tax_amount = tax_amount
            new_order.total_amount = total_amount
            new_order.final_amount = total_amount
            
            # Create split record
            order_split = OrderSplit(
                parent_order_id=parent_order.id,
                split_order_id=new_order.id,
                split_type=SplitType.PAYMENT.value,
                split_reason=split_request.split_reason or "Payment split requested",
                split_by=user_id,
                split_metadata={
                    "customer_id": customer_id,
                    "item_count": len(items)
                }
            )
            self.db.add(order_split)
            
            # Create split payment record
            split_payment = SplitPayment(
                parent_order_id=parent_order.id,
                split_order_id=new_order.id,
                amount=total_amount,
                payment_status=PaymentStatus.PENDING.value,
                paid_by_customer_id=customer_id
            )
            self.db.add(split_payment)
            
            split_order_ids.append(new_order.id)
            split_details.append({
                "split_order_id": new_order.id,
                "customer_id": customer_id,
                "total_amount": float(total_amount),
                "payment_status": PaymentStatus.PENDING.value
            })
        
        return {
            "split_order_ids": split_order_ids,
            "details": split_details
        }
    
    def get_split_summary(self, order_id: int) -> SplitOrderSummary:
        """
        Get summary of all splits for an order.
        
        Args:
            order_id: Parent order ID
            
        Returns:
            SplitOrderSummary with all split details
        """
        # Get all splits for this order
        splits = self.db.query(OrderSplit).filter(
            OrderSplit.parent_order_id == order_id
        ).all()
        
        # Get payment splits
        payment_splits = self.db.query(SplitPayment).filter(
            SplitPayment.parent_order_id == order_id
        ).all()
        
        # Convert to response models
        split_details = [
            OrderSplitDetail.model_validate(split) for split in splits
        ]
        
        payment_details = [
            SplitPaymentDetail.model_validate(payment) for payment in payment_splits
        ]
        
        # Calculate totals
        total_amount = sum(p.amount for p in payment_splits)
        paid_amount = sum(
            p.amount for p in payment_splits 
            if p.payment_status == PaymentStatus.PAID.value
        )
        pending_amount = total_amount - paid_amount
        
        return SplitOrderSummary(
            parent_order_id=order_id,
            total_splits=len(splits),
            split_orders=split_details,
            payment_splits=payment_details,
            total_amount=total_amount,
            paid_amount=paid_amount,
            pending_amount=pending_amount
        )
    
    def update_split_payment(
        self,
        payment_id: int,
        payment_status: PaymentStatus,
        payment_reference: Optional[str] = None,
        payment_method: Optional[str] = None
    ) -> SplitPaymentDetail:
        """
        Update payment status for a split order.
        
        Args:
            payment_id: Split payment ID
            payment_status: New payment status
            payment_reference: Payment reference number
            payment_method: Payment method used
            
        Returns:
            Updated SplitPaymentDetail
        """
        payment = self.db.query(SplitPayment).filter(
            SplitPayment.id == payment_id
        ).first()
        
        if not payment:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Split payment {payment_id} not found"
            )
        
        payment.payment_status = payment_status.value
        if payment_reference:
            payment.payment_reference = payment_reference
        if payment_method:
            payment.payment_method = payment_method
        
        self.db.commit()
        
        # Send webhook notification
        self.webhook_service.trigger_webhook(
            WebhookEventType.PAYMENT_UPDATED,
            {
                "split_payment_id": payment_id,
                "parent_order_id": payment.parent_order_id,
                "split_order_id": payment.split_order_id,
                "payment_status": payment_status.value,
                "amount": float(payment.amount)
            }
        )
        
        return SplitPaymentDetail.model_validate(payment)
    
    def merge_split_orders(
        self,
        merge_request: MergeSplitRequest,
        current_user_id: int
    ) -> OrderSplitResponse:
        """
        Merge split orders back together.
        
        Args:
            merge_request: Merge request details
            current_user_id: ID of the user performing the merge
            
        Returns:
            OrderSplitResponse with merge results
        """
        try:
            # Validate all split orders exist and belong to same parent
            splits = self.db.query(OrderSplit).filter(
                OrderSplit.split_order_id.in_(merge_request.split_order_ids)
            ).all()
            
            if len(splits) != len(merge_request.split_order_ids):
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="One or more split orders not found"
                )
            
            # Check all belong to same parent
            parent_ids = {split.parent_order_id for split in splits}
            if len(parent_ids) > 1:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Split orders belong to different parent orders"
                )
            
            parent_order_id = parent_ids.pop()
            
            # Get split orders
            split_orders = self.db.query(Order).filter(
                Order.id.in_(merge_request.split_order_ids)
            ).all()
            
            # Check if any are already completed/cancelled
            for order in split_orders:
                if order.status in [OrderStatus.COMPLETED, OrderStatus.CANCELLED]:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=f"Cannot merge order {order.id} with status {order.status}"
                    )
            
            if merge_request.keep_original:
                # Merge back to parent order
                target_order = self.db.query(Order).filter(
                    Order.id == parent_order_id
                ).first()
                
                # Move all items back to parent
                for split_order in split_orders:
                    for item in split_order.order_items:
                        item.order_id = parent_order_id
                    
                    # Mark split order as cancelled
                    split_order.status = OrderStatus.CANCELLED
                    split_order.customer_notes = f"Merged back to order #{parent_order_id}"
                
                # Update parent order totals
                self._recalculate_order_totals(target_order)
                
            else:
                # Create new merged order
                first_order = split_orders[0]
                merged_order = Order(
                    staff_id=first_order.staff_id,
                    customer_id=first_order.customer_id,
                    table_no=first_order.table_no,
                    status=OrderStatus.PENDING,
                    category_id=first_order.category_id,
                    customer_notes=f"Merged from orders: {', '.join(str(o.id) for o in split_orders)}"
                )
                self.db.add(merged_order)
                self.db.flush()
                
                # Move all items to new order
                for split_order in split_orders:
                    for item in split_order.order_items:
                        item.order_id = merged_order.id
                    
                    # Mark split order as cancelled
                    split_order.status = OrderStatus.CANCELLED
                    split_order.customer_notes = f"Merged into order #{merged_order.id}"
                
                # Calculate totals for new order
                self._recalculate_order_totals(merged_order)
                target_order = merged_order
            
            # Update split records
            for split in splits:
                split.split_metadata = split.split_metadata or {}
                split.split_metadata["merged"] = True
                split.split_metadata["merged_at"] = datetime.utcnow().isoformat()
                split.split_metadata["merged_by"] = current_user_id
            
            self.db.commit()
            
            return OrderSplitResponse(
                success=True,
                message=f"Successfully merged {len(split_orders)} orders",
                parent_order_id=parent_order_id,
                split_order_ids=[target_order.id],
                split_details=[{
                    "merged_order_id": target_order.id,
                    "merged_from": merge_request.split_order_ids,
                    "total_amount": float(target_order.total_amount)
                }]
            )
            
        except SQLAlchemyError as e:
            self.db.rollback()
            logger.error(f"Database error during order merge: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to merge orders"
            )
    
    def _get_item_split_count(self, order_id: int, item_id: int) -> int:
        """Get count of already split quantities for an item"""
        # This would need to track split quantities per item
        # For now, return 0 as placeholder
        return 0
    
    def _group_items_for_ticket_split(
        self,
        parent_order: Order,
        split_items: List[OrderItemSplitRequest]
    ) -> Dict[str, List[Dict[str, Any]]]:
        """Group items for ticket splitting (by station, course, etc.)"""
        # For now, simple grouping - in real implementation would use
        # menu item categories, preparation stations, etc.
        groups = {}
        
        parent_items = {item.id: item for item in parent_order.order_items}
        
        for i, split_item in enumerate(split_items):
            group_name = f"Ticket {i + 1}"
            parent_item = parent_items[split_item.item_id]
            
            if group_name not in groups:
                groups[group_name] = []
            
            groups[group_name].append({
                "menu_item_id": parent_item.menu_item_id,
                "quantity": split_item.quantity,
                "price": parent_item.price,
                "notes": split_item.notes or parent_item.notes
            })
        
        return groups
    
    def _group_items_by_customer(
        self,
        parent_order: Order,
        split_items: List[OrderItemSplitRequest]
    ) -> Dict[int, List[Dict[str, Any]]]:
        """Group items by customer for payment splitting"""
        # For now, assign to parent order customer
        # In real implementation, would use customer assignments from request
        groups = {parent_order.customer_id: []}
        
        parent_items = {item.id: item for item in parent_order.order_items}
        
        for split_item in split_items:
            parent_item = parent_items[split_item.item_id]
            
            groups[parent_order.customer_id].append({
                "menu_item_id": parent_item.menu_item_id,
                "quantity": split_item.quantity,
                "price": parent_item.price,
                "notes": split_item.notes or parent_item.notes
            })
        
        return groups
    
    def _recalculate_order_totals(self, order: Order) -> None:
        """Recalculate order totals based on current items"""
        subtotal = Decimal('0')
        
        for item in order.order_items:
            subtotal += item.price * item.quantity
        
        # Maintain same tax rate
        tax_rate = float(order.tax_amount / order.subtotal) if order.subtotal else 0
        tax_amount = subtotal * Decimal(str(tax_rate))
        
        order.subtotal = subtotal
        order.tax_amount = tax_amount
        order.total_amount = subtotal + tax_amount
        order.final_amount = order.total_amount - (order.discount_amount or 0)
    
    def split_order_for_payment(
        self,
        order_id: int,
        payment_request: PaymentSplitRequest,
        current_user_id: int
    ) -> OrderSplitResponse:
        """
        Split an order specifically for payment purposes.
        
        This creates separate payment records without creating new orders,
        allowing flexible payment collection.
        """
        try:
            # Get the parent order with lock to prevent concurrent splits
            parent_order = self.db.query(Order).filter(
                Order.id == order_id
            ).with_for_update().first()
            
            if not parent_order:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Order {order_id} not found"
                )
            
            # Validate total amounts match
            total_split_amount = sum(Decimal(str(split.get('amount', 0))) for split in payment_request.splits)
            if abs(parent_order.final_amount - total_split_amount) > Decimal('0.01'):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Split amounts ({total_split_amount}) do not match order total ({parent_order.final_amount})"
                )
            
            split_order_ids = []
            split_details = []
            
            for i, split_config in enumerate(payment_request.splits):
                # Create a payment-only split order
                split_order = Order(
                    staff_id=parent_order.staff_id,
                    customer_id=split_config.get('customer_id', parent_order.customer_id),
                    table_no=parent_order.table_no,
                    status=parent_order.status,
                    category_id=parent_order.category_id,
                    customer_notes=f"Payment split #{i+1} from order #{parent_order.id}",
                    subtotal=Decimal('0'),  # Will be calculated based on split
                    tax_amount=Decimal('0'),
                    total_amount=Decimal(str(split_config['amount'])),
                    final_amount=Decimal(str(split_config['amount']))
                )
                self.db.add(split_order)
                self.db.flush()
                
                # Create split record
                order_split = OrderSplit(
                    parent_order_id=parent_order.id,
                    split_order_id=split_order.id,
                    split_type=SplitType.PAYMENT.value,
                    split_reason=f"Payment split {i+1} of {len(payment_request.splits)}",
                    split_by=current_user_id,
                    split_metadata={
                        "split_index": i + 1,
                        "total_splits": len(payment_request.splits),
                        "payment_method": split_config.get('payment_method'),
                        "split_by_name": split_config.get('split_by_name')
                    }
                )
                self.db.add(order_split)
                
                # Create split payment record
                split_payment = SplitPayment(
                    parent_order_id=parent_order.id,
                    split_order_id=split_order.id,
                    amount=Decimal(str(split_config['amount'])),
                    payment_method=split_config.get('payment_method'),
                    payment_status=PaymentStatus.PENDING.value,
                    paid_by_customer_id=split_config.get('customer_id')
                )
                self.db.add(split_payment)
                
                split_order_ids.append(split_order.id)
                split_details.append({
                    "split_order_id": split_order.id,
                    "amount": float(split_config['amount']),
                    "customer_id": split_config.get('customer_id'),
                    "payment_method": split_config.get('payment_method'),
                    "split_by_name": split_config.get('split_by_name')
                })
            
            self.db.commit()
            
            # Send webhook notifications
            for split_order_id in split_order_ids:
                self.webhook_service.trigger_webhook(
                    WebhookEventType.ORDER_SPLIT,
                    {
                        "parent_order_id": order_id,
                        "split_order_id": split_order_id,
                        "split_type": "payment"
                    }
                )
            
            return OrderSplitResponse(
                success=True,
                message=f"Payment split into {len(split_order_ids)} parts",
                parent_order_id=order_id,
                split_order_ids=split_order_ids,
                split_details=split_details
            )
            
        except SQLAlchemyError as e:
            self.db.rollback()
            logger.error(f"Database error during payment split: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to split payment"
            )
    
    def get_split_tracking(self, order_id: int) -> Dict[str, Any]:
        """
        Get comprehensive tracking information for split orders.
        
        Args:
            order_id: Parent order ID
            
        Returns:
            Dictionary with tracking details including status, timing, and progress
        """
        # Get parent order
        parent_order = self.db.query(Order).filter(Order.id == order_id).first()
        if not parent_order:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Order {order_id} not found"
            )
        
        # Get all splits
        splits = self.db.query(OrderSplit).options(
            joinedload(OrderSplit.split_order)
        ).filter(OrderSplit.parent_order_id == order_id).all()
        
        # Track different split types and their statuses
        split_tracking = {
            "parent_order": {
                "id": parent_order.id,
                "status": parent_order.status.value,
                "created_at": parent_order.created_at.isoformat(),
                "total_amount": float(parent_order.final_amount)
            },
            "splits_by_type": {
                SplitType.TICKET.value: [],
                SplitType.DELIVERY.value: [],
                SplitType.PAYMENT.value: []
            },
            "status_summary": {
                "total_splits": len(splits),
                "pending": 0,
                "in_progress": 0,
                "completed": 0,
                "cancelled": 0
            },
            "payment_summary": {
                "total_amount": float(parent_order.final_amount),
                "paid_amount": Decimal('0'),
                "pending_amount": Decimal('0')
            }
        }
        
        # Process each split
        for split in splits:
            split_info = {
                "split_id": split.id,
                "order_id": split.split_order_id,
                "status": split.split_order.status.value,
                "created_at": split.created_at.isoformat(),
                "split_by": split.split_by,
                "reason": split.split_reason,
                "metadata": split.split_metadata
            }
            
            # Add to appropriate type list
            split_tracking["splits_by_type"][split.split_type].append(split_info)
            
            # Update status counts
            status = split.split_order.status.value.lower()
            if status in split_tracking["status_summary"]:
                split_tracking["status_summary"][status] += 1
            
            # Get payment info if exists
            payment = self.db.query(SplitPayment).filter(
                SplitPayment.split_order_id == split.split_order_id
            ).first()
            
            if payment:
                split_info["payment"] = {
                    "amount": float(payment.amount),
                    "status": payment.payment_status,
                    "method": payment.payment_method,
                    "reference": payment.payment_reference
                }
                
                if payment.payment_status == PaymentStatus.PAID.value:
                    split_tracking["payment_summary"]["paid_amount"] += payment.amount
                else:
                    split_tracking["payment_summary"]["pending_amount"] += payment.amount
        
        # Convert decimals to floats for JSON serialization
        split_tracking["payment_summary"]["paid_amount"] = float(
            split_tracking["payment_summary"]["paid_amount"]
        )
        split_tracking["payment_summary"]["pending_amount"] = float(
            split_tracking["payment_summary"]["pending_amount"]
        )
        
        return split_tracking
    
    def update_split_status(
        self,
        split_order_id: int,
        new_status: OrderStatus,
        current_user_id: int,
        notes: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Update the status of a split order.
        
        Args:
            split_order_id: ID of the split order
            new_status: New order status
            current_user_id: User making the update
            notes: Optional notes about the status change
            
        Returns:
            Updated split order information
        """
        # Get the split order
        split_order = self.db.query(Order).filter(Order.id == split_order_id).first()
        if not split_order:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Split order {split_order_id} not found"
            )
        
        # Get the split record
        split_record = self.db.query(OrderSplit).filter(
            OrderSplit.split_order_id == split_order_id
        ).first()
        
        if not split_record:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Order {split_order_id} is not a split order"
            )
        
        # Update status
        old_status = split_order.status
        split_order.status = new_status
        
        # Add to metadata
        if not split_record.split_metadata:
            split_record.split_metadata = {}
        
        split_record.split_metadata["status_updates"] = split_record.split_metadata.get(
            "status_updates", []
        )
        split_record.split_metadata["status_updates"].append({
            "from": old_status.value,
            "to": new_status.value,
            "updated_by": current_user_id,
            "updated_at": datetime.utcnow().isoformat(),
            "notes": notes
        })
        
        self.db.commit()
        
        # Send webhook notification
        self.webhook_service.trigger_webhook(
            WebhookEventType.ORDER_UPDATED,
            {
                "order_id": split_order_id,
                "parent_order_id": split_record.parent_order_id,
                "old_status": old_status.value,
                "new_status": new_status.value,
                "is_split_order": True
            }
        )
        
        return {
            "split_order_id": split_order_id,
            "parent_order_id": split_record.parent_order_id,
            "old_status": old_status.value,
            "new_status": new_status.value,
            "updated_at": datetime.utcnow().isoformat()
        }