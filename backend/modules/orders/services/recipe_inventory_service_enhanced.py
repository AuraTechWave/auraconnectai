# backend/modules/orders/services/recipe_inventory_service_enhanced.py

from sqlalchemy.orm import Session
from sqlalchemy import and_
from fastapi import HTTPException
from typing import List, Dict, Optional, Set, Tuple
from datetime import datetime
from decimal import Decimal
import time

from core.inventory_models import Inventory, InventoryAdjustment, AdjustmentType
from core.notification_service import NotificationService
from ..models.order_models import OrderItem, OrderStatus
from ..models.manual_review_models import ReviewReason
from ...menu.models.recipe_models import Recipe, RecipeIngredient, RecipeSubRecipe
from ...menu.services.recipe_service import RecipeService
from ..exceptions.inventory_exceptions import (
    InsufficientInventoryError, MissingRecipeError, InventoryNotFoundError,
    RecipeLoopError, InventorySyncError, ConcurrentDeductionError,
    InventoryIssueDetail
)
from ..utils.inventory_logging import InventoryLogger, log_inventory_operation
from ..utils.database_retry import with_deadlock_retry
from ..services.manual_review_service import ManualReviewService


class RecipeInventoryServiceEnhanced:
    """Enhanced service for handling recipe-based inventory deductions with error handling and logging"""
    
    def __init__(self, db: Session):
        self.db = db
        self.recipe_service = RecipeService(db)
        self.logger = InventoryLogger()
        self.manual_review_service = ManualReviewService(db)
        self.notification_service = NotificationService(db)
    
    @log_inventory_operation("deduction")
    async def deduct_inventory_for_order(
        self,
        order_items: List[OrderItem],
        order_id: int,
        user_id: int,
        deduction_type: str = "order_completion",
        allow_partial: bool = False,
        create_review_on_failure: bool = True
    ) -> Dict:
        """
        Enhanced deduct inventory with comprehensive error handling and logging
        
        Args:
            order_items: List of order items to process
            order_id: Order ID for tracking
            user_id: User performing the deduction
            deduction_type: Type of deduction (order_completion, order_progress, etc.)
            allow_partial: Allow partial deduction if some items fail
            create_review_on_failure: Create manual review entry on failure
        
        Returns:
            Dict with success status, deducted items, warnings, and any errors
        """
        start_time = time.time()
        low_stock_items = []
        insufficient_stock_items = []
        deducted_items = []
        items_without_recipes = []
        inventory_not_found = []
        
        # Log operation start
        self.logger.log_deduction_start(
            order_id=order_id,
            user_id=user_id,
            order_items=order_items,
            deduction_type=deduction_type
        )
        
        try:
            # Check for concurrent deduction attempts
            existing_adjustments = self.db.query(InventoryAdjustment).filter(
                and_(
                    InventoryAdjustment.reference_type == "order",
                    InventoryAdjustment.reference_id == str(order_id),
                    InventoryAdjustment.adjustment_type == AdjustmentType.CONSUMPTION
                )
            ).all()
            
            if existing_adjustments:
                self.logger.log_concurrent_deduction(
                    order_id=order_id,
                    existing_adjustments=[adj.id for adj in existing_adjustments]
                )
                raise ConcurrentDeductionError(
                    order_id=order_id,
                    existing_adjustments=[adj.id for adj in existing_adjustments]
                )
            
            # Collect all required ingredients
            try:
                required_ingredients = await self._calculate_required_ingredients(order_items)
            except MissingRecipeError as e:
                self.logger.log_missing_recipe(order_id, e.menu_items)
                if create_review_on_failure:
                    await self.manual_review_service.create_review_request(
                        order_id=order_id,
                        reason=ReviewReason.MISSING_RECIPE,
                        error=e,
                        priority=5
                    )
                raise
            except RecipeLoopError as e:
                if create_review_on_failure:
                    await self.manual_review_service.create_review_request(
                        order_id=order_id,
                        reason=ReviewReason.RECIPE_CIRCULAR_DEPENDENCY,
                        error=e,
                        priority=7
                    )
                raise
            
            # Extract items without recipes from the result
            if 'items_without_recipes' in required_ingredients:
                items_without_recipes = required_ingredients.pop('items_without_recipes')
                if items_without_recipes and not allow_partial:
                    raise MissingRecipeError(
                        menu_items=items_without_recipes,
                        order_id=order_id
                    )
            
            # Check availability for all ingredients
            for inventory_id, required_data in required_ingredients.items():
                inventory_item = self.db.query(Inventory).filter(
                    Inventory.id == inventory_id,
                    Inventory.deleted_at.is_(None)
                ).first()
                
                if not inventory_item:
                    inventory_not_found.append(inventory_id)
                    continue
                
                # Check if sufficient stock
                if inventory_item.quantity < required_data["quantity"]:
                    issue = InventoryIssueDetail(
                        inventory_id=inventory_id,
                        item_name=inventory_item.item_name,
                        available_quantity=inventory_item.quantity,
                        required_quantity=required_data["quantity"],
                        unit=inventory_item.unit,
                        issue_type="insufficient_stock"
                    )
                    insufficient_stock_items.append(issue)
                    continue
            
            # Handle inventory not found
            if inventory_not_found:
                self.logger.log_inventory_not_found(order_id, inventory_not_found)
                if not allow_partial:
                    error = InventoryNotFoundError(
                        inventory_ids=inventory_not_found,
                        order_id=order_id
                    )
                    if create_review_on_failure:
                        await self.manual_review_service.create_review_request(
                            order_id=order_id,
                            reason=ReviewReason.INVENTORY_NOT_FOUND,
                            error=error,
                            priority=8
                        )
                    raise error
            
            # Handle insufficient stock
            if insufficient_stock_items:
                self.logger.log_insufficient_inventory(
                    order_id=order_id,
                    insufficient_items=[
                        {
                            "inventory_id": item.inventory_id,
                            "item_name": item.item_name,
                            "available": item.available_quantity,
                            "required": item.required_quantity,
                            "shortage": item.required_quantity - item.available_quantity
                        }
                        for item in insufficient_stock_items
                    ]
                )
                
                if not allow_partial:
                    self.db.rollback()
                    error = InsufficientInventoryError(
                        items=insufficient_stock_items,
                        order_id=order_id
                    )
                    if create_review_on_failure:
                        await self.manual_review_service.create_review_request(
                            order_id=order_id,
                            reason=ReviewReason.INSUFFICIENT_STOCK,
                            error=error,
                            priority=6
                        )
                    
                    # Send critical alert for high-value orders
                    order_total = sum(item.price * item.quantity for item in order_items)
                    if order_total > 500:  # High-value order threshold
                        await self.notification_service.send_critical_alert(
                            alert_type="insufficient_inventory_high_value_order",
                            message=f"Cannot fulfill high-value order #{order_id} (${order_total:.2f}) due to insufficient inventory",
                            affected_resources=[
                                {
                                    "type": "inventory",
                                    "id": item.inventory_id,
                                    "name": item.item_name,
                                    "shortage": item.required_quantity - item.available_quantity
                                }
                                for item in insufficient_stock_items
                            ]
                        )
                    
                    raise error
            
            # Perform the deduction
            for inventory_id, required_data in required_ingredients.items():
                # Skip if inventory not found and partial allowed
                if inventory_id in inventory_not_found:
                    continue
                
                # Skip if insufficient stock and partial allowed
                if any(item.inventory_id == inventory_id for item in insufficient_stock_items):
                    continue
                
                inventory_item = await self._get_inventory_with_lock(inventory_id)
                
                if not inventory_item:
                    continue
                
                # Deduct quantity
                old_quantity = inventory_item.quantity
                inventory_item.quantity -= required_data["quantity"]
                
                # Create inventory adjustment record
                adjustment = InventoryAdjustment(
                    inventory_id=inventory_id,
                    adjustment_type=AdjustmentType.CONSUMPTION,
                    quantity_before=old_quantity,
                    quantity_change=-required_data["quantity"],
                    quantity_after=inventory_item.quantity,
                    unit=inventory_item.unit,
                    reason=f"Order #{order_id} - {deduction_type}",
                    reference_type="order",
                    reference_id=str(order_id),
                    performed_by=user_id,
                    metadata={
                        "order_items": required_data["order_items"],
                        "recipes_used": required_data["recipes"],
                        "deduction_type": deduction_type
                    }
                )
                self.db.add(adjustment)
                
                # Track deducted items
                deducted_items.append({
                    "inventory_id": inventory_id,
                    "item_name": inventory_item.item_name,
                    "quantity_deducted": required_data["quantity"],
                    "unit": inventory_item.unit,
                    "new_quantity": inventory_item.quantity
                })
                
                # Check for low stock
                if inventory_item.threshold and inventory_item.quantity <= inventory_item.threshold:
                    low_stock_items.append({
                        "inventory_id": inventory_id,
                        "item_name": inventory_item.item_name,
                        "current_quantity": inventory_item.quantity,
                        "threshold": inventory_item.threshold,
                        "unit": inventory_item.unit
                    })
                    
                    # Log low stock notification
                    self.logger.log_low_stock_notification(
                        inventory_id=inventory_id,
                        item_name=inventory_item.item_name,
                        current_quantity=inventory_item.quantity,
                        threshold=inventory_item.threshold
                    )
                    
                    # Send low stock notification
                    await self.notification_service.send_role_notification(
                        role="inventory_manager",
                        subject=f"Low Stock Alert: {inventory_item.item_name}",
                        message=(
                            f"Item: {inventory_item.item_name}\n"
                            f"Current Quantity: {inventory_item.quantity} {inventory_item.unit}\n"
                            f"Threshold: {inventory_item.threshold} {inventory_item.unit}\n"
                            f"Triggered by Order #{order_id}"
                        ),
                        priority="high" if inventory_item.quantity < inventory_item.threshold * 0.5 else "normal"
                    )
            
            self.db.commit()
            
            # Calculate processing time
            processing_time_ms = (time.time() - start_time) * 1000
            
            # Log success
            self.logger.log_deduction_success(
                order_id=order_id,
                deducted_items=deducted_items,
                low_stock_alerts=low_stock_items,
                processing_time_ms=processing_time_ms
            )
            
            result = {
                "success": True,
                "deducted_items": deducted_items,
                "low_stock_alerts": low_stock_items,
                "items_without_recipes": items_without_recipes,
                "total_items_deducted": len(deducted_items),
                "processing_time_ms": processing_time_ms
            }
            
            # Add warnings if partial deduction
            if allow_partial and (insufficient_stock_items or inventory_not_found):
                result["partial_deduction"] = True
                result["skipped_due_to_insufficient_stock"] = [
                    {
                        "inventory_id": item.inventory_id,
                        "item_name": item.item_name,
                        "shortage": item.required_quantity - item.available_quantity
                    }
                    for item in insufficient_stock_items
                ]
                result["skipped_due_to_not_found"] = inventory_not_found
            
            return result
            
        except (InsufficientInventoryError, MissingRecipeError, 
                InventoryNotFoundError, RecipeLoopError, 
                InventorySyncError, ConcurrentDeductionError) as e:
            # Already logged and handled
            raise
        except HTTPException:
            # Re-raise HTTP exceptions
            raise
        except Exception as e:
            # Log unexpected errors
            self.logger.log_deduction_error(
                order_id=order_id,
                error=e,
                error_type="unexpected"
            )
            
            # Log the attempt
            await self.manual_review_service.log_deduction_attempt(
                order_id=order_id,
                user_id=user_id,
                error=e,
                attempted_deductions=[],
                menu_items_affected=[
                    {
                        "menu_item_id": item.menu_item_id,
                        "quantity": item.quantity
                    }
                    for item in order_items
                ]
            )
            
            # Create review request for unexpected errors
            if create_review_on_failure:
                await self.manual_review_service.create_review_request(
                    order_id=order_id,
                    reason=ReviewReason.OTHER,
                    error_details={
                        "error_type": e.__class__.__name__,
                        "error_message": str(e)
                    },
                    priority=5
                )
            
            self.db.rollback()
            raise HTTPException(
                status_code=500,
                detail=f"Error processing recipe-based inventory deduction: {str(e)}"
            )
    
    @log_inventory_operation("reversal")
    async def reverse_inventory_deduction(
        self,
        order_id: int,
        user_id: int,
        reason: str = "Order cancellation",
        force: bool = False
    ) -> Dict:
        """
        Enhanced reverse inventory deductions with logging
        
        Args:
            order_id: Order ID to reverse deductions for
            user_id: User performing the reversal
            reason: Reason for reversal
            force: Force reversal even if external systems are synced
        
        Returns:
            Dict with reversal results
        """
        self.logger.log_reversal_start(
            order_id=order_id,
            user_id=user_id,
            reason=reason
        )
        
        reversed_items = []
        
        try:
            # Check if adjustments have been synced to external systems
            if not force:
                synced_adjustments = self.db.query(InventoryAdjustment).filter(
                    and_(
                        InventoryAdjustment.reference_type == "order",
                        InventoryAdjustment.reference_id == str(order_id),
                        InventoryAdjustment.metadata.op("->")("synced_to_external").astext == "true"
                    )
                ).all()
                
                if synced_adjustments:
                    error = InventorySyncError(
                        order_id=order_id,
                        synced_adjustments=[adj.id for adj in synced_adjustments]
                    )
                    await self.manual_review_service.create_review_request(
                        order_id=order_id,
                        reason=ReviewReason.SYNC_CONFLICT,
                        error=error,
                        priority=8
                    )
                    raise error
            
            # Find all deductions for this order
            adjustments = self.db.query(InventoryAdjustment).filter(
                and_(
                    InventoryAdjustment.reference_type == "order",
                    InventoryAdjustment.reference_id == str(order_id),
                    InventoryAdjustment.adjustment_type == AdjustmentType.CONSUMPTION
                )
            ).all()
            
            if not adjustments:
                return {
                    "success": True,
                    "message": "No inventory deductions found for this order",
                    "reversed_items": []
                }
            
            # Reverse each adjustment
            for adjustment in adjustments:
                inventory_item = self.db.query(Inventory).filter(
                    Inventory.id == adjustment.inventory_id
                ).with_for_update().first()  # Lock row for update
                
                if not inventory_item:
                    continue
                
                # Restore quantity
                old_quantity = inventory_item.quantity
                restore_quantity = abs(adjustment.quantity_change)
                inventory_item.quantity += restore_quantity
                
                # Create reversal adjustment
                reversal = InventoryAdjustment(
                    inventory_id=adjustment.inventory_id,
                    adjustment_type=AdjustmentType.RETURN,
                    quantity_before=old_quantity,
                    quantity_change=restore_quantity,
                    quantity_after=inventory_item.quantity,
                    unit=inventory_item.unit,
                    reason=reason,
                    reference_type="order_reversal",
                    reference_id=str(order_id),
                    performed_by=user_id,
                    metadata={
                        "original_adjustment_id": adjustment.id,
                        "reversal_reason": reason,
                        "forced": force
                    }
                )
                self.db.add(reversal)
                
                reversed_items.append({
                    "inventory_id": adjustment.inventory_id,
                    "item_name": inventory_item.item_name,
                    "quantity_restored": restore_quantity,
                    "unit": inventory_item.unit,
                    "new_quantity": inventory_item.quantity
                })
            
            self.db.commit()
            
            # Log success
            self.logger.log_reversal_success(
                order_id=order_id,
                reversed_items=reversed_items
            )
            
            return {
                "success": True,
                "reversed_items": reversed_items,
                "total_items_reversed": len(reversed_items)
            }
            
        except Exception as e:
            self.db.rollback()
            self.logger.log_deduction_error(
                order_id=order_id,
                error=e,
                error_type="reversal_error"
            )
            raise HTTPException(
                status_code=500,
                detail=f"Error reversing inventory deduction: {str(e)}"
            )
    
    async def _calculate_required_ingredients(
        self,
        order_items: List[OrderItem]
    ) -> Dict[int, Dict]:
        """
        Calculate total required ingredients for all order items with enhanced error handling
        
        Returns:
            Dict mapping inventory_id to required quantity and metadata
        
        Raises:
            MissingRecipeError: If menu items don't have recipes
            RecipeLoopError: If circular dependencies are detected
        """
        from sqlalchemy.orm import joinedload, selectinload
        
        required_ingredients = {}
        items_without_recipes = []
        
        # Bulk fetch all menu item IDs
        menu_item_ids = [item.menu_item_id for item in order_items]
        
        # Prefetch all recipes with ingredients and sub-recipes in one query
        recipes = self.db.query(Recipe).options(
            selectinload(Recipe.ingredients).joinedload(RecipeIngredient.inventory_item),
            selectinload(Recipe.sub_recipes).joinedload(RecipeSubRecipe.sub_recipe)
        ).filter(
            Recipe.menu_item_id.in_(menu_item_ids),
            Recipe.deleted_at.is_(None)
        ).all()
        
        # Create a mapping for quick lookup
        recipe_map = {recipe.menu_item_id: recipe for recipe in recipes}
        
        for order_item in order_items:
            recipe = recipe_map.get(order_item.menu_item_id)
            
            if not recipe:
                items_without_recipes.append({
                    "menu_item_id": order_item.menu_item_id,
                    "menu_item_name": getattr(order_item.menu_item, 'name', 'Unknown')
                })
                continue
            
            # Process direct ingredients with loop detection
            try:
                await self._add_recipe_ingredients(
                    recipe_id=recipe.id,
                    quantity_multiplier=order_item.quantity,
                    required_ingredients=required_ingredients,
                    order_item_id=order_item.id
                )
            except RecipeLoopError:
                # Re-raise with additional context
                raise
        
        # Check if any items are missing recipes
        if items_without_recipes:
            # Instead of raising immediately, include in result
            required_ingredients['items_without_recipes'] = items_without_recipes
        
        return required_ingredients
    
    async def _add_recipe_ingredients(
        self,
        recipe_id: int,
        quantity_multiplier: float,
        required_ingredients: Dict,
        order_item_id: Optional[int] = None,
        visited_recipes: Optional[Set[int]] = None,
        recipe_chain: Optional[List[int]] = None
    ):
        """
        Recursively add recipe ingredients with loop detection
        
        Raises:
            RecipeLoopError: If circular dependency is detected
        """
        if visited_recipes is None:
            visited_recipes = set()
        if recipe_chain is None:
            recipe_chain = []
        
        # Detect circular dependency
        if recipe_id in visited_recipes:
            recipe_chain.append(recipe_id)
            raise RecipeLoopError(
                recipe_chain=recipe_chain,
                order_id=order_item_id if order_item_id else 0
            )
        
        visited_recipes.add(recipe_id)
        recipe_chain.append(recipe_id)
        
        # Get recipe with ingredients and sub-recipes
        recipe = self.db.query(Recipe).filter(
            Recipe.id == recipe_id
        ).first()
        
        if not recipe:
            return
        
        # Process direct ingredients
        ingredients = self.db.query(RecipeIngredient).filter(
            RecipeIngredient.recipe_id == recipe_id,
            RecipeIngredient.is_active == True
        ).all()
        
        for ingredient in ingredients:
            if ingredient.is_optional:
                continue
            
            required_quantity = ingredient.quantity * quantity_multiplier
            
            if ingredient.inventory_id not in required_ingredients:
                required_ingredients[ingredient.inventory_id] = {
                    "quantity": 0,
                    "unit": ingredient.unit,
                    "order_items": [],
                    "recipes": []
                }
            
            required_ingredients[ingredient.inventory_id]["quantity"] += required_quantity
            
            if order_item_id:
                required_ingredients[ingredient.inventory_id]["order_items"].append(order_item_id)
            
            required_ingredients[ingredient.inventory_id]["recipes"].append({
                "recipe_id": recipe_id,
                "recipe_name": recipe.name,
                "quantity_used": required_quantity
            })
        
        # Process sub-recipes
        sub_recipes = self.db.query(RecipeSubRecipe).filter(
            RecipeSubRecipe.parent_recipe_id == recipe_id,
            RecipeSubRecipe.is_active == True
        ).all()
        
        for sub_recipe_link in sub_recipes:
            await self._add_recipe_ingredients(
                recipe_id=sub_recipe_link.sub_recipe_id,
                quantity_multiplier=quantity_multiplier * sub_recipe_link.quantity,
                required_ingredients=required_ingredients,
                order_item_id=order_item_id,
                visited_recipes=visited_recipes.copy(),
                recipe_chain=recipe_chain.copy()
            )
    
    async def handle_partial_fulfillment(
        self,
        order_items: List[Dict],
        order_id: int,
        user_id: int
    ) -> Dict:
        """
        Handle inventory deduction for partially fulfilled orders
        
        Args:
            order_items: List of dicts with menu_item_id and fulfilled_quantity
            order_id: Order ID
            user_id: User performing the deduction
        
        Returns:
            Dict with deduction results
        """
        # Convert to OrderItem-like objects for processing
        partial_items = []
        for item_data in order_items:
            # Create a temporary OrderItem-like object
            class PartialOrderItem:
                def __init__(self, menu_item_id, quantity):
                    self.menu_item_id = menu_item_id
                    self.quantity = quantity
            
            partial_items.append(
                PartialOrderItem(
                    menu_item_id=item_data["menu_item_id"],
                    quantity=item_data["fulfilled_quantity"]
                )
            )
        
        # Use the main deduction method with partial quantities
        return await self.deduct_inventory_for_order(
            order_items=partial_items,
            order_id=order_id,
            user_id=user_id,
            deduction_type="partial_fulfillment",
            allow_partial=True  # Allow partial deduction for partial fulfillment
        )
    
    async def get_inventory_impact_preview(
        self,
        order_items: List[OrderItem]
    ) -> Dict:
        """
        Preview inventory impact without performing deduction
        
        Args:
            order_items: List of order items to preview
        
        Returns:
            Dict with preview of inventory changes
        """
        try:
            required_ingredients = await self._calculate_required_ingredients(order_items)
            impact_preview = []
            warnings = []
            
            # Extract items without recipes
            items_without_recipes = required_ingredients.pop('items_without_recipes', [])
            if items_without_recipes:
                warnings.append(f"{len(items_without_recipes)} menu items lack recipe configuration")
            
            for inventory_id, required_data in required_ingredients.items():
                inventory_item = self.db.query(Inventory).filter(
                    Inventory.id == inventory_id,
                    Inventory.deleted_at.is_(None)
                ).first()
                
                if not inventory_item:
                    warnings.append(f"Inventory item {inventory_id} not found")
                    continue
                
                new_quantity = inventory_item.quantity - required_data["quantity"]
                
                impact_preview.append({
                    "inventory_id": inventory_id,
                    "item_name": inventory_item.item_name,
                    "current_quantity": inventory_item.quantity,
                    "required_quantity": required_data["quantity"],
                    "new_quantity": new_quantity,
                    "unit": inventory_item.unit,
                    "sufficient_stock": new_quantity >= 0,
                    "will_be_low_stock": inventory_item.threshold and new_quantity <= inventory_item.threshold,
                    "recipes_using": required_data["recipes"]
                })
            
            return {
                "impact_preview": impact_preview,
                "warnings": warnings,
                "items_without_recipes": items_without_recipes,
                "can_fulfill": all(item["sufficient_stock"] for item in impact_preview) and not items_without_recipes
            }
            
        except Exception as e:
            raise HTTPException(
                status_code=500,
                detail=f"Error generating inventory impact preview: {str(e)}"
            )
    
    @with_deadlock_retry(max_retries=3)
    async def _get_inventory_with_lock(self, inventory_id: int) -> Optional[Inventory]:
        """
        Get inventory item with row-level lock for update
        
        This method includes retry logic for deadlock scenarios
        """
        return self.db.query(Inventory).filter(
            Inventory.id == inventory_id
        ).with_for_update().first()
    
    @with_deadlock_retry(max_retries=5, initial_delay=0.05)
    async def _perform_deduction_transaction(
        self,
        inventory_updates: List[Dict],
        order_id: int,
        user_id: int,
        deduction_type: str
    ) -> List[InventoryAdjustment]:
        """
        Perform the actual inventory deduction in a transaction with retry logic
        
        Args:
            inventory_updates: List of dicts with inventory_id, quantity_change, etc.
            order_id: Order ID for reference
            user_id: User performing the deduction
            deduction_type: Type of deduction
            
        Returns:
            List of created InventoryAdjustment records
        """
        adjustments = []
        
        try:
            # Sort inventory IDs to prevent deadlocks
            sorted_updates = sorted(inventory_updates, key=lambda x: x['inventory_id'])
            
            for update in sorted_updates:
                inventory = self.db.query(Inventory).filter(
                    Inventory.id == update['inventory_id']
                ).with_for_update().first()
                
                if not inventory:
                    continue
                
                # Perform deduction
                old_quantity = inventory.quantity
                inventory.quantity -= update['quantity_change']
                
                # Create adjustment record
                adjustment = InventoryAdjustment(
                    inventory_id=update['inventory_id'],
                    adjustment_type=AdjustmentType.CONSUMPTION,
                    quantity_before=old_quantity,
                    quantity_change=-update['quantity_change'],
                    quantity_after=inventory.quantity,
                    unit=inventory.unit,
                    reason=f"Order #{order_id} - {deduction_type}",
                    reference_type="order",
                    reference_id=str(order_id),
                    performed_by=user_id,
                    metadata=update.get('metadata', {})
                )
                self.db.add(adjustment)
                adjustments.append(adjustment)
            
            self.db.commit()
            return adjustments
            
        except Exception:
            self.db.rollback()
            raise