# backend/modules/orders/tests/test_inventory_error_handling.py

import pytest
from unittest.mock import Mock, patch, AsyncMock
from sqlalchemy.orm import Session
from datetime import datetime

from core.database import get_test_db
from core.inventory_models import Inventory, InventoryAdjustment
from ..models.order_models import Order, OrderItem
from ..enums.order_enums import OrderStatus
from ..models.manual_review_models import ManualReviewQueue, ReviewReason, ReviewStatus
from ...menu.models.menu_models import MenuItem
from ...menu.models.recipe_models import Recipe, RecipeIngredient
from ..services.recipe_inventory_service_enhanced import RecipeInventoryServiceEnhanced
from ..exceptions.inventory_exceptions import (
    InsufficientInventoryError, MissingRecipeError, InventoryNotFoundError,
    RecipeLoopError, ConcurrentDeductionError
)
from tests.factories import (
    UserFactory, InventoryFactory, MenuItemFactory,
    RecipeFactory, RecipeIngredientFactory, OrderFactory, OrderItemFactory
)


@pytest.mark.unit
class TestInventoryErrorHandling:
    """Test error handling for inventory deduction failures"""
    
    @pytest.fixture
    def service(self, db: Session):
        """Create service instance with mocked dependencies"""
        service = RecipeInventoryServiceEnhanced(db)
        # Mock notification service
        service.notification_service.send_role_notification = AsyncMock(return_value=True)
        service.notification_service.send_critical_alert = AsyncMock(return_value=True)
        return service
    
    @pytest.mark.asyncio
    async def test_missing_recipe_error(self, db: Session, service):
        """Test handling of missing recipe configurations"""
        # Create test data
        user = UserFactory()
        menu_item = MenuItemFactory(name="Pizza Without Recipe")
        order = OrderFactory(created_by=user)
        order_item = OrderItemFactory(order=order, menu_item=menu_item, quantity=2)
        
        # No recipe created for the menu item
        
        # Attempt deduction
        with pytest.raises(MissingRecipeError) as exc_info:
            await service.deduct_inventory_for_order(
                order_items=[order_item],
                order_id=order.id,
                user_id=user.id
            )
        
        # Verify error details
        error = exc_info.value
        assert error.order_id == order.id
        assert len(error.menu_items) == 1
        assert error.menu_items[0]["menu_item_id"] == menu_item.id
        assert error.error_code == "MISSING_RECIPE_CONFIG"
        
        # Verify manual review was created
        review = db.query(ManualReviewQueue).filter(
            ManualReviewQueue.order_id == order.id
        ).first()
        assert review is not None
        assert review.reason == ReviewReason.MISSING_RECIPE
        assert review.status == ReviewStatus.PENDING
        assert review.priority == 5
        
        # Verify order was marked for review
        db.refresh(order)
        assert order.requires_manual_review is True
        assert order.review_reason == ReviewReason.MISSING_RECIPE.value
    
    @pytest.mark.asyncio
    async def test_insufficient_inventory_error(self, db: Session, service):
        """Test handling of insufficient inventory"""
        # Create test data
        user = UserFactory()
        inventory = InventoryFactory(item_name="Flour", quantity=5.0, unit="kg")
        menu_item = MenuItemFactory(name="Bread")
        recipe = RecipeFactory(menu_item=menu_item)
        ingredient = RecipeIngredientFactory(
            recipe=recipe,
            inventory_item=inventory,
            quantity=3.0,  # Need 3kg per bread
            unit="kg"
        )
        
        order = OrderFactory(created_by=user)
        order_item = OrderItemFactory(
            order=order,
            menu_item=menu_item,
            quantity=2,  # Need 6kg total, but only have 5kg
            price=10.0
        )
        
        # Attempt deduction
        with pytest.raises(InsufficientInventoryError) as exc_info:
            await service.deduct_inventory_for_order(
                order_items=[order_item],
                order_id=order.id,
                user_id=user.id
            )
        
        # Verify error details
        error = exc_info.value
        assert error.order_id == order.id
        assert len(error.items) == 1
        assert error.items[0].inventory_id == inventory.id
        assert error.items[0].available_quantity == 5.0
        assert error.items[0].required_quantity == 6.0
        assert error.error_code == "INSUFFICIENT_INVENTORY"
        
        # Verify manual review was created
        review = db.query(ManualReviewQueue).filter(
            ManualReviewQueue.order_id == order.id
        ).first()
        assert review is not None
        assert review.reason == ReviewReason.INSUFFICIENT_STOCK
        assert review.priority == 6
        
        # Verify no inventory was deducted
        db.refresh(inventory)
        assert inventory.quantity == 5.0  # Unchanged
        
        # Verify no adjustments were created
        adjustments = db.query(InventoryAdjustment).filter(
            InventoryAdjustment.reference_id == str(order.id)
        ).all()
        assert len(adjustments) == 0
    
    @pytest.mark.asyncio
    async def test_insufficient_inventory_high_value_order_alert(self, db: Session, service):
        """Test critical alert for high-value orders with insufficient inventory"""
        # Create high-value order
        user = UserFactory()
        inventory = InventoryFactory(item_name="Truffle Oil", quantity=1.0, unit="bottle")
        menu_item = MenuItemFactory(name="Truffle Pasta", price=150.0)  # High price
        recipe = RecipeFactory(menu_item=menu_item)
        ingredient = RecipeIngredientFactory(
            recipe=recipe,
            inventory_item=inventory,
            quantity=0.5,
            unit="bottle"
        )
        
        order = OrderFactory(created_by=user)
        order_item = OrderItemFactory(
            order=order,
            menu_item=menu_item,
            quantity=4,  # Total: $600, need 2 bottles but only have 1
            price=150.0
        )
        
        # Attempt deduction
        with pytest.raises(InsufficientInventoryError):
            await service.deduct_inventory_for_order(
                order_items=[order_item],
                order_id=order.id,
                user_id=user.id
            )
        
        # Verify critical alert was sent
        service.notification_service.send_critical_alert.assert_called_once()
        call_args = service.notification_service.send_critical_alert.call_args
        assert call_args[1]["alert_type"] == "insufficient_inventory_high_value_order"
        assert f"${600:.2f}" in call_args[1]["message"]
    
    @pytest.mark.asyncio
    async def test_inventory_not_found_error(self, db: Session, service):
        """Test handling of missing inventory items"""
        # Create test data with invalid inventory reference
        user = UserFactory()
        menu_item = MenuItemFactory(name="Ghost Dish")
        recipe = RecipeFactory(menu_item=menu_item)
        
        # Manually create ingredient with non-existent inventory ID
        ingredient = RecipeIngredient(
            recipe_id=recipe.id,
            inventory_id=99999,  # Non-existent
            quantity=1.0,
            unit="unit",
            created_by=user.id
        )
        db.add(ingredient)
        db.commit()
        
        order = OrderFactory(created_by=user)
        order_item = OrderItemFactory(order=order, menu_item=menu_item)
        
        # Attempt deduction
        with pytest.raises(InventoryNotFoundError) as exc_info:
            await service.deduct_inventory_for_order(
                order_items=[order_item],
                order_id=order.id,
                user_id=user.id
            )
        
        # Verify error details
        error = exc_info.value
        assert error.order_id == order.id
        assert 99999 in error.inventory_ids
        assert error.error_code == "INVENTORY_NOT_FOUND"
        
        # Verify manual review was created
        review = db.query(ManualReviewQueue).filter(
            ManualReviewQueue.order_id == order.id
        ).first()
        assert review is not None
        assert review.reason == ReviewReason.INVENTORY_NOT_FOUND
        assert review.priority == 8  # High priority
    
    @pytest.mark.asyncio
    async def test_recipe_circular_dependency_error(self, db: Session, service):
        """Test detection of circular recipe dependencies"""
        # Create circular dependency: Recipe A -> Recipe B -> Recipe A
        user = UserFactory()
        inventory = InventoryFactory(quantity=100.0)
        
        menu_item_a = MenuItemFactory(name="Product A")
        menu_item_b = MenuItemFactory(name="Product B")
        
        recipe_a = RecipeFactory(menu_item=menu_item_a)
        recipe_b = RecipeFactory(menu_item=menu_item_b)
        
        # A uses inventory
        RecipeIngredientFactory(
            recipe=recipe_a,
            inventory_item=inventory,
            quantity=1.0
        )
        
        # Create circular sub-recipes
        from ...menu.models.recipe_models import RecipeSubRecipe
        
        # A includes B as sub-recipe
        sub_a_to_b = RecipeSubRecipe(
            parent_recipe_id=recipe_a.id,
            sub_recipe_id=recipe_b.id,
            quantity=1.0,
            is_active=True
        )
        db.add(sub_a_to_b)
        
        # B includes A as sub-recipe (circular!)
        sub_b_to_a = RecipeSubRecipe(
            parent_recipe_id=recipe_b.id,
            sub_recipe_id=recipe_a.id,
            quantity=1.0,
            is_active=True
        )
        db.add(sub_b_to_a)
        db.commit()
        
        order = OrderFactory(created_by=user)
        order_item = OrderItemFactory(order=order, menu_item=menu_item_a)
        
        # Attempt deduction
        with pytest.raises(RecipeLoopError) as exc_info:
            await service.deduct_inventory_for_order(
                order_items=[order_item],
                order_id=order.id,
                user_id=user.id
            )
        
        # Verify error details
        error = exc_info.value
        assert recipe_a.id in error.recipe_chain
        assert recipe_b.id in error.recipe_chain
        assert error.error_code == "RECIPE_CIRCULAR_DEPENDENCY"
        
        # Verify manual review was created
        review = db.query(ManualReviewQueue).filter(
            ManualReviewQueue.order_id == order.id
        ).first()
        assert review is not None
        assert review.reason == ReviewReason.RECIPE_CIRCULAR_DEPENDENCY
        assert review.priority == 7
    
    @pytest.mark.asyncio
    async def test_concurrent_deduction_error(self, db: Session, service):
        """Test detection of concurrent deduction attempts"""
        # Create test data
        user = UserFactory()
        inventory = InventoryFactory(quantity=100.0)
        menu_item = MenuItemFactory()
        recipe = RecipeFactory(menu_item=menu_item)
        RecipeIngredientFactory(recipe=recipe, inventory_item=inventory, quantity=5.0)
        
        order = OrderFactory(created_by=user)
        order_item = OrderItemFactory(order=order, menu_item=menu_item)
        
        # Create existing adjustment (simulating previous deduction)
        existing_adjustment = InventoryAdjustment(
            inventory_id=inventory.id,
            adjustment_type="consumption",
            quantity_before=100.0,
            quantity_change=-5.0,
            quantity_after=95.0,
            unit=inventory.unit,
            reason=f"Order #{order.id} - order_completion",
            reference_type="order",
            reference_id=str(order.id),
            performed_by=user.id
        )
        db.add(existing_adjustment)
        db.commit()
        
        # Attempt duplicate deduction
        with pytest.raises(ConcurrentDeductionError) as exc_info:
            await service.deduct_inventory_for_order(
                order_items=[order_item],
                order_id=order.id,
                user_id=user.id
            )
        
        # Verify error details
        error = exc_info.value
        assert error.order_id == order.id
        assert existing_adjustment.id in error.existing_adjustments
        assert error.error_code == "CONCURRENT_DEDUCTION"
    
    @pytest.mark.asyncio
    async def test_partial_deduction_allowed(self, db: Session, service):
        """Test partial deduction when allow_partial=True"""
        # Create mixed scenario: some items can be fulfilled, others cannot
        user = UserFactory()
        
        # Sufficient inventory
        flour = InventoryFactory(item_name="Flour", quantity=10.0, unit="kg")
        # Insufficient inventory
        cheese = InventoryFactory(item_name="Cheese", quantity=1.0, unit="kg")
        
        # Menu item 1: Can be fulfilled
        bread = MenuItemFactory(name="Bread")
        bread_recipe = RecipeFactory(menu_item=bread)
        RecipeIngredientFactory(
            recipe=bread_recipe,
            inventory_item=flour,
            quantity=2.0,
            unit="kg"
        )
        
        # Menu item 2: Cannot be fulfilled
        pizza = MenuItemFactory(name="Pizza")
        pizza_recipe = RecipeFactory(menu_item=pizza)
        RecipeIngredientFactory(
            recipe=pizza_recipe,
            inventory_item=cheese,
            quantity=2.0,  # Need 2kg but only have 1kg
            unit="kg"
        )
        
        order = OrderFactory(created_by=user)
        order_items = [
            OrderItemFactory(order=order, menu_item=bread, quantity=1),
            OrderItemFactory(order=order, menu_item=pizza, quantity=1)
        ]
        
        # Attempt partial deduction
        result = await service.deduct_inventory_for_order(
            order_items=order_items,
            order_id=order.id,
            user_id=user.id,
            allow_partial=True,
            create_review_on_failure=False
        )
        
        # Verify partial success
        assert result["success"] is True
        assert result["partial_deduction"] is True
        assert len(result["deducted_items"]) == 1  # Only bread
        assert result["deducted_items"][0]["item_name"] == "Flour"
        assert result["deducted_items"][0]["quantity_deducted"] == 2.0
        
        # Verify skipped items
        assert len(result["skipped_due_to_insufficient_stock"]) == 1
        assert result["skipped_due_to_insufficient_stock"][0]["item_name"] == "Cheese"
        assert result["skipped_due_to_insufficient_stock"][0]["shortage"] == 1.0
        
        # Verify flour was deducted
        db.refresh(flour)
        assert flour.quantity == 8.0
        
        # Verify cheese was not deducted
        db.refresh(cheese)
        assert cheese.quantity == 1.0
    
    @pytest.mark.asyncio
    async def test_low_stock_notification(self, db: Session, service):
        """Test low stock notifications are triggered"""
        # Create inventory near threshold
        user = UserFactory()
        inventory = InventoryFactory(
            item_name="Sugar",
            quantity=15.0,
            threshold=10.0,
            unit="kg"
        )
        
        menu_item = MenuItemFactory()
        recipe = RecipeFactory(menu_item=menu_item)
        RecipeIngredientFactory(
            recipe=recipe,
            inventory_item=inventory,
            quantity=8.0,  # Will bring quantity to 7kg, below threshold
            unit="kg"
        )
        
        order = OrderFactory(created_by=user)
        order_item = OrderItemFactory(order=order, menu_item=menu_item)
        
        # Perform deduction
        result = await service.deduct_inventory_for_order(
            order_items=[order_item],
            order_id=order.id,
            user_id=user.id
        )
        
        # Verify low stock alert
        assert len(result["low_stock_alerts"]) == 1
        alert = result["low_stock_alerts"][0]
        assert alert["item_name"] == "Sugar"
        assert alert["current_quantity"] == 7.0
        assert alert["threshold"] == 10.0
        
        # Verify notification was sent
        service.notification_service.send_role_notification.assert_called()
        call_args = service.notification_service.send_role_notification.call_args
        assert call_args[1]["role"] == "inventory_manager"
        assert "Low Stock Alert: Sugar" in call_args[1]["subject"]
    
    @pytest.mark.asyncio
    async def test_error_logging(self, db: Session, service, caplog):
        """Test that errors are properly logged"""
        import logging
        caplog.set_level(logging.INFO)
        
        # Create scenario that will fail
        user = UserFactory()
        menu_item = MenuItemFactory(name="No Recipe Item")
        order = OrderFactory(created_by=user)
        order_item = OrderItemFactory(order=order, menu_item=menu_item)
        
        # Attempt deduction
        with pytest.raises(MissingRecipeError):
            await service.deduct_inventory_for_order(
                order_items=[order_item],
                order_id=order.id,
                user_id=user.id
            )
        
        # Verify logs contain expected information
        logs = caplog.text
        assert "Starting deduction operation" in logs
        assert f"order_id={order.id}" in logs
        assert "Missing recipe configuration" in logs
        assert "Manual review required" in logs


@pytest.mark.integration
class TestManualReviewIntegration:
    """Test manual review service integration"""
    
    @pytest.mark.asyncio
    async def test_manual_review_workflow(self, db: Session):
        """Test complete manual review workflow"""
        # Create service
        from ..services.manual_review_service import ManualReviewService
        review_service = ManualReviewService(db)
        review_service.notification_service.send_role_notification = AsyncMock(return_value=True)
        
        # Create test data
        user = UserFactory()
        manager = UserFactory()
        order = OrderFactory()
        
        # Create review request
        review = await review_service.create_review_request(
            order_id=order.id,
            reason=ReviewReason.MISSING_RECIPE,
            error_details={"test": "data"},
            priority=7
        )
        
        assert review.status == ReviewStatus.PENDING
        assert review.priority == 7
        
        # Get pending reviews
        result = await review_service.get_pending_reviews()
        assert result["total"] == 1
        assert result["high_priority_count"] == 1
        
        # Assign review
        review = await review_service.assign_review(
            review_id=review.id,
            assignee_id=manager.id
        )
        assert review.status == ReviewStatus.IN_REVIEW
        assert review.assigned_to == manager.id
        
        # Resolve review
        review = await review_service.resolve_review(
            review_id=review.id,
            reviewer_id=manager.id,
            resolution_action="manually_adjusted_inventory",
            notes="Added missing recipe configuration",
            mark_order_completed=True
        )
        
        assert review.status == ReviewStatus.RESOLVED
        assert review.reviewed_by == manager.id
        assert review.resolution_action == "manually_adjusted_inventory"
        
        # Verify order was updated
        db.refresh(order)
        assert order.requires_manual_review is False
    
    @pytest.mark.asyncio
    async def test_review_statistics(self, db: Session):
        """Test review statistics generation"""
        from ..services.manual_review_service import ManualReviewService
        review_service = ManualReviewService(db)
        review_service.notification_service.send_role_notification = AsyncMock(return_value=True)
        
        # Create various reviews
        user = UserFactory()
        
        # Create reviews with different statuses and reasons
        for i in range(5):
            order = OrderFactory()
            review = await review_service.create_review_request(
                order_id=order.id,
                reason=ReviewReason.MISSING_RECIPE if i < 3 else ReviewReason.INSUFFICIENT_STOCK,
                priority=i
            )
            
            # Resolve some reviews
            if i < 2:
                review.status = ReviewStatus.RESOLVED
                review.resolved_at = datetime.utcnow()
                db.commit()
        
        # Get statistics
        stats = await review_service.get_review_statistics()
        
        assert stats["total_reviews"] == 5
        assert stats["status_breakdown"][ReviewStatus.RESOLVED.value] == 2
        assert stats["status_breakdown"][ReviewStatus.PENDING.value] == 3
        assert stats["reason_breakdown"][ReviewReason.MISSING_RECIPE.value] == 3
        assert stats["reason_breakdown"][ReviewReason.INSUFFICIENT_STOCK.value] == 2