# backend/modules/orders/services/order_inventory_integration.py

"""
Order Inventory Integration Service

This module handles the automatic inventory deduction when orders are completed,
including support for partial fulfillment, cancellations, and rollbacks.
"""

import logging
from typing import Dict, List, Optional, Any
from datetime import datetime
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from fastapi import HTTPException, status

from ..models.order_models import Order, OrderItem
from ..enums.order_enums import OrderStatus
from .recipe_inventory_service import RecipeInventoryService
from ...menu.services.recipe_service import RecipeService
from core.inventory_models import Inventory, InventoryAdjustment, AdjustmentType

logger = logging.getLogger(__name__)


class OrderInventoryIntegrationService:
    """
    Service for integrating order operations with inventory management.
    Handles automatic deduction, rollback, and audit logging.
    """
    
    def __init__(self, db: Session):
        self.db = db
        self.recipe_inventory_service = RecipeInventoryService(db)
        self.recipe_service = RecipeService(db)
    
    async def complete_order_with_inventory(
        self,
        order_id: int,
        user_id: int,
        force_deduction: bool = False,
        skip_inventory: bool = False
    ) -> Dict[str, Any]:
        """
        Complete an order and automatically deduct inventory based on recipes.
        
        Args:
            order_id: Order to complete
            user_id: User performing the action
            force_deduction: Force deduction even if inventory is insufficient
            skip_inventory: Skip inventory deduction (for special cases)
        
        Returns:
            Dict with completion status and inventory deduction results
        """
        try:
            # Get order with items
            order = self.db.query(Order).filter(
                Order.id == order_id,
                Order.deleted_at.is_(None)
            ).first()
            
            if not order:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Order {order_id} not found"
                )
            
            # Validate order status
            if order.status == OrderStatus.COMPLETED:
                return {
                    "success": True,
                    "message": "Order is already completed",
                    "inventory_deducted": False
                }
            
            if order.status == OrderStatus.CANCELLED:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Cannot complete a cancelled order"
                )
            
            # Start transaction
            self.db.begin_nested()
            
            try:
                # Update order status
                old_status = order.status
                order.status = OrderStatus.COMPLETED
                order.completed_at = datetime.utcnow()
                order.completed_by = user_id
                
                inventory_result = None
                
                # Deduct inventory if not skipped
                if not skip_inventory:
                    # Get order items
                    order_items = self.db.query(OrderItem).filter(
                        OrderItem.order_id == order_id,
                        OrderItem.is_cancelled == False
                    ).all()
                    
                    if order_items:
                        # Perform inventory deduction
                        inventory_result = await self.recipe_inventory_service.deduct_inventory_for_order(
                            order_items=order_items,
                            order_id=order_id,
                            user_id=user_id,
                            deduction_type="order_completion"
                        )
                        
                        # Log the deduction
                        self.log_deduction_audit(
                            order_id=order_id,
                            user_id=user_id,
                            deduction_result=inventory_result,
                            metadata={
                                "previous_status": old_status.value,
                                "completion_time": order.completed_at.isoformat()
                            }
                        )
                
                # Commit the transaction
                self.db.commit()
                
                logger.info(
                    f"Order {order_id} completed successfully. "
                    f"Inventory deducted: {not skip_inventory}"
                )
                
                return {
                    "success": True,
                    "order_id": order_id,
                    "status": OrderStatus.COMPLETED.value,
                    "completed_at": order.completed_at,
                    "inventory_deducted": not skip_inventory,
                    "inventory_result": inventory_result
                }
                
            except HTTPException as e:
                # Rollback on HTTP exceptions (like insufficient inventory)
                self.db.rollback()
                logger.error(f"Failed to complete order {order_id}: {str(e)}")
                raise
            
            except Exception as e:
                # Rollback on any other error
                self.db.rollback()
                logger.error(f"Unexpected error completing order {order_id}: {str(e)}")
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail=f"Failed to complete order: {str(e)}"
                )
                
        except Exception as e:
            self.db.rollback()
            raise
    
    async def handle_order_cancellation(
        self,
        order_id: int,
        user_id: int,
        reason: str = "Order cancelled",
        reverse_inventory: bool = True
    ) -> Dict[str, Any]:
        """
        Handle order cancellation with optional inventory reversal.
        
        Args:
            order_id: Order to cancel
            user_id: User performing the cancellation
            reason: Cancellation reason
            reverse_inventory: Whether to reverse inventory deductions
        
        Returns:
            Dict with cancellation results
        """
        try:
            # Get order
            order = self.db.query(Order).filter(
                Order.id == order_id,
                Order.deleted_at.is_(None)
            ).first()
            
            if not order:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Order {order_id} not found"
                )
            
            # Check if order can be cancelled
            if order.status == OrderStatus.CANCELLED:
                return {
                    "success": True,
                    "message": "Order is already cancelled",
                    "inventory_reversed": False
                }
            
            # Start transaction
            self.db.begin_nested()
            
            try:
                # Update order status
                old_status = order.status
                order.status = OrderStatus.CANCELLED
                order.cancelled_at = datetime.utcnow()
                order.cancelled_by = user_id
                order.cancellation_reason = reason
                
                reversal_result = None
                
                # Reverse inventory if order was completed and reversal requested
                if reverse_inventory and old_status == OrderStatus.COMPLETED:
                    reversal_result = await self.recipe_inventory_service.reverse_inventory_deduction(
                        order_id=order_id,
                        user_id=user_id,
                        reason=reason
                    )
                    
                    # Log the reversal
                    self.log_reversal_audit(
                        order_id=order_id,
                        user_id=user_id,
                        reversal_result=reversal_result,
                        metadata={
                            "previous_status": old_status.value,
                            "cancellation_reason": reason
                        }
                    )
                
                # Commit the transaction
                self.db.commit()
                
                logger.info(
                    f"Order {order_id} cancelled successfully. "
                    f"Inventory reversed: {reverse_inventory and old_status == OrderStatus.COMPLETED}"
                )
                
                return {
                    "success": True,
                    "order_id": order_id,
                    "status": OrderStatus.CANCELLED.value,
                    "cancelled_at": order.cancelled_at,
                    "inventory_reversed": reverse_inventory and old_status == OrderStatus.COMPLETED,
                    "reversal_result": reversal_result
                }
                
            except Exception as e:
                self.db.rollback()
                logger.error(f"Failed to cancel order {order_id}: {str(e)}")
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail=f"Failed to cancel order: {str(e)}"
                )
                
        except Exception as e:
            self.db.rollback()
            raise
    
    async def handle_partial_fulfillment(
        self,
        order_id: int,
        fulfilled_items: List[Dict[str, Any]],
        user_id: int
    ) -> Dict[str, Any]:
        """
        Handle partial order fulfillment with proportional inventory deduction.
        
        Args:
            order_id: Order being partially fulfilled
            fulfilled_items: List of dicts with menu_item_id and fulfilled_quantity
            user_id: User performing the action
        
        Returns:
            Dict with partial fulfillment results
        """
        try:
            # Validate order exists and is in progress
            order = self.db.query(Order).filter(
                Order.id == order_id,
                Order.deleted_at.is_(None)
            ).first()
            
            if not order:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Order {order_id} not found"
                )
            
            if order.status not in [OrderStatus.PREPARING, OrderStatus.READY]:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Cannot partially fulfill order with status {order.status.value}"
                )
            
            # Perform partial deduction
            deduction_result = await self.recipe_inventory_service.handle_partial_fulfillment(
                order_items=fulfilled_items,
                order_id=order_id,
                user_id=user_id
            )
            
            # Update order metadata
            if not order.metadata:
                order.metadata = {}
            
            if "partial_fulfillments" not in order.metadata:
                order.metadata["partial_fulfillments"] = []
            
            order.metadata["partial_fulfillments"].append({
                "timestamp": datetime.utcnow().isoformat(),
                "user_id": user_id,
                "items": fulfilled_items,
                "deduction_result": deduction_result
            })
            
            self.db.commit()
            
            logger.info(f"Partial fulfillment completed for order {order_id}")
            
            return {
                "success": True,
                "order_id": order_id,
                "fulfilled_items": fulfilled_items,
                "inventory_result": deduction_result
            }
            
        except Exception as e:
            self.db.rollback()
            logger.error(f"Failed to handle partial fulfillment for order {order_id}: {str(e)}")
            raise
    
    async def validate_inventory_availability(
        self,
        order_id: int
    ) -> Dict[str, Any]:
        """
        Check if order can be fulfilled with current inventory levels.
        
        Args:
            order_id: Order to validate
        
        Returns:
            Dict with availability status and details
        """
        try:
            # Get order items
            order_items = self.db.query(OrderItem).filter(
                OrderItem.order_id == order_id,
                OrderItem.is_cancelled == False
            ).all()
            
            if not order_items:
                return {
                    "can_fulfill": True,
                    "message": "No items in order",
                    "insufficient_items": []
                }
            
            # Get inventory impact preview
            impact_preview = await self.recipe_inventory_service.get_inventory_impact_preview(
                order_items=order_items
            )
            
            return impact_preview
            
        except Exception as e:
            logger.error(f"Failed to validate inventory for order {order_id}: {str(e)}")
            raise
    
    def log_deduction_audit(
        self,
        order_id: int,
        user_id: int,
        deduction_result: Dict[str, Any],
        metadata: Optional[Dict[str, Any]] = None
    ):
        """
        Create detailed audit log for inventory deduction.
        """
        try:
            from ...insights.models.insight_models import AuditLog
            
            audit_log = AuditLog(
                action="inventory_deduction",
                entity_type="order",
                entity_id=order_id,
                user_id=user_id,
                details={
                    "deduction_result": deduction_result,
                    "metadata": metadata or {}
                },
                timestamp=datetime.utcnow()
            )
            
            self.db.add(audit_log)
            self.db.commit()
            
        except Exception as e:
            logger.error(f"Failed to create audit log for order {order_id}: {str(e)}")
            # Don't fail the main operation if audit logging fails
    
    def log_reversal_audit(
        self,
        order_id: int,
        user_id: int,
        reversal_result: Dict[str, Any],
        metadata: Optional[Dict[str, Any]] = None
    ):
        """
        Create detailed audit log for inventory reversal.
        """
        try:
            from ...insights.models.insight_models import AuditLog
            
            audit_log = AuditLog(
                action="inventory_reversal",
                entity_type="order",
                entity_id=order_id,
                user_id=user_id,
                details={
                    "reversal_result": reversal_result,
                    "metadata": metadata or {}
                },
                timestamp=datetime.utcnow()
            )
            
            self.db.add(audit_log)
            self.db.commit()
            
        except Exception as e:
            logger.error(f"Failed to create audit log for order {order_id}: {str(e)}")
            # Don't fail the main operation if audit logging fails