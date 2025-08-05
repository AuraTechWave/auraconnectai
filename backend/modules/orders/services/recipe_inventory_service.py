# backend/modules/orders/services/recipe_inventory_service.py

from sqlalchemy.orm import Session
from sqlalchemy import and_
from fastapi import HTTPException
from typing import List, Dict, Optional, Set, Tuple
from datetime import datetime
from decimal import Decimal

from core.inventory_models import Inventory, InventoryAdjustment, AdjustmentType
from ..models.order_models import OrderItem
from ..enums.order_enums import OrderStatus
from ...menu.models.recipe_models import Recipe, RecipeIngredient, RecipeSubRecipe
from ...menu.services.recipe_service import RecipeService


class RecipeInventoryService:
    """Service for handling recipe-based inventory deductions"""
    
    def __init__(self, db: Session):
        self.db = db
        self.recipe_service = RecipeService(db)
    
    async def deduct_inventory_for_order(
        self,
        order_items: List[OrderItem],
        order_id: int,
        user_id: int,
        deduction_type: str = "order_completion"
    ) -> Dict:
        """
        Deduct inventory based on recipe ingredients for order items
        
        Args:
            order_items: List of order items to process
            order_id: Order ID for tracking
            user_id: User performing the deduction
            deduction_type: Type of deduction (order_completion, order_progress, etc.)
        
        Returns:
            Dict with success status, deducted items, and any warnings
        """
        low_stock_items = []
        insufficient_stock_items = []
        deducted_items = []
        items_without_recipes = []
        
        try:
            # First, collect all required ingredients
            required_ingredients = await self._calculate_required_ingredients(order_items)
            
            # Check availability for all ingredients
            for inventory_id, required_data in required_ingredients.items():
                inventory_item = self.db.query(Inventory).filter(
                    Inventory.id == inventory_id,
                    Inventory.deleted_at.is_(None)
                ).first()
                
                if not inventory_item:
                    insufficient_stock_items.append({
                        "inventory_id": inventory_id,
                        "item_name": f"Unknown (ID: {inventory_id})",
                        "available": 0,
                        "required": required_data["quantity"],
                        "unit": required_data["unit"]
                    })
                    continue
                
                # Check if sufficient stock
                if inventory_item.quantity < required_data["quantity"]:
                    insufficient_stock_items.append({
                        "inventory_id": inventory_id,
                        "item_name": inventory_item.item_name,
                        "available": inventory_item.quantity,
                        "required": required_data["quantity"],
                        "unit": inventory_item.unit
                    })
                    continue
            
            # If any items have insufficient stock, rollback
            if insufficient_stock_items:
                self.db.rollback()
                raise HTTPException(
                    status_code=400,
                    detail={
                        "message": "Insufficient inventory for recipe ingredients",
                        "items": insufficient_stock_items,
                        "items_without_recipes": items_without_recipes
                    }
                )
            
            # Perform the deduction
            for inventory_id, required_data in required_ingredients.items():
                inventory_item = self.db.query(Inventory).filter(
                    Inventory.id == inventory_id
                ).first()
                
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
                    reference_id=order_id,
                    performed_by=user_id,
                    metadata={
                        "order_items": required_data["order_items"],
                        "recipes_used": required_data["recipes"]
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
                    
                    # Send low stock notification if configured
                    from ..config.inventory_config import get_inventory_config
                    config = get_inventory_config()
                    if config.SEND_LOW_STOCK_NOTIFICATIONS:
                        # TODO: Integrate with notification service
                        # await send_low_stock_notification(
                        #     inventory_item=inventory_item,
                        #     current_quantity=inventory_item.quantity,
                        #     threshold=inventory_item.threshold
                        # )
                        pass
            
            self.db.commit()
            
            return {
                "success": True,
                "deducted_items": deducted_items,
                "low_stock_alerts": low_stock_items,
                "items_without_recipes": items_without_recipes,
                "total_items_deducted": len(deducted_items)
            }
            
        except HTTPException:
            raise
        except Exception as e:
            self.db.rollback()
            raise HTTPException(
                status_code=500,
                detail=f"Error processing recipe-based inventory deduction: {str(e)}"
            )
    
    async def reverse_inventory_deduction(
        self,
        order_id: int,
        user_id: int,
        reason: str = "Order cancellation",
        force: bool = False
    ) -> Dict:
        """
        Reverse inventory deductions for a cancelled order
        
        Args:
            order_id: Order ID to reverse deductions for
            user_id: User performing the reversal
            reason: Reason for reversal
            force: Force reversal even if external systems are synced
        
        Returns:
            Dict with reversal results
        """
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
                ).first()
                
                if synced_adjustments:
                    raise HTTPException(
                        status_code=400,
                        detail="Cannot reverse inventory deductions that have been synced to external systems. Contact administrator."
                    )
            # Find all deductions for this order
            adjustments = self.db.query(InventoryAdjustment).filter(
                and_(
                    InventoryAdjustment.reference_type == "order",
                    InventoryAdjustment.reference_id == order_id,
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
                ).first()
                
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
                    reference_id=order_id,
                    performed_by=user_id,
                    metadata={
                        "original_adjustment_id": adjustment.id,
                        "reversal_reason": reason
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
            
            return {
                "success": True,
                "reversed_items": reversed_items,
                "total_items_reversed": len(reversed_items)
            }
            
        except Exception as e:
            self.db.rollback()
            raise HTTPException(
                status_code=500,
                detail=f"Error reversing inventory deduction: {str(e)}"
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
            deduction_type="partial_fulfillment"
        )
    
    async def _calculate_required_ingredients(
        self,
        order_items: List[OrderItem]
    ) -> Dict[int, Dict]:
        """
        Calculate total required ingredients for all order items
        
        Returns:
            Dict mapping inventory_id to required quantity and metadata
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
            
            # Process direct ingredients
            await self._add_recipe_ingredients(
                recipe_id=recipe.id,
                quantity_multiplier=order_item.quantity,
                required_ingredients=required_ingredients,
                order_item_id=order_item.id
            )
        
        return required_ingredients
    
    async def _add_recipe_ingredients(
        self,
        recipe_id: int,
        quantity_multiplier: float,
        required_ingredients: Dict,
        order_item_id: Optional[int] = None,
        visited_recipes: Optional[Set[int]] = None
    ):
        """
        Recursively add recipe ingredients including sub-recipes
        
        Args:
            recipe_id: Recipe to process
            quantity_multiplier: Multiplier for ingredient quantities
            required_ingredients: Dict to accumulate ingredients
            order_item_id: Associated order item ID
            visited_recipes: Set of visited recipe IDs to prevent cycles
        """
        if visited_recipes is None:
            visited_recipes = set()
        
        # Prevent infinite recursion
        if recipe_id in visited_recipes:
            return
        
        visited_recipes.add(recipe_id)
        
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
                visited_recipes=visited_recipes.copy()
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
                "can_fulfill": all(item["sufficient_stock"] for item in impact_preview)
            }
            
        except Exception as e:
            raise HTTPException(
                status_code=500,
                detail=f"Error generating inventory impact preview: {str(e)}"
            )