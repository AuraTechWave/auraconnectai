# backend/modules/promotions/tests/test_discount_service.py

import pytest
from datetime import datetime, timedelta

from backend.modules.promotions.models.promotion_models import (
    PromotionType, DiscountType, PromotionStatus
)


class TestDiscountCalculationService:
    """Test cases for DiscountCalculationService"""
    
    def test_calculate_percentage_discount(self, discount_service, db_session, promotion_factory):
        """Test calculating percentage discount"""
        promotion = promotion_factory.create_percentage_promotion(
            db_session,
            discount_value=20.0,  # 20% discount
            status=PromotionStatus.ACTIVE
        )
        
        order_items = [
            {'product_id': 1, 'quantity': 2, 'unit_price': 50.0, 'subtotal': 100.0},
            {'product_id': 2, 'quantity': 1, 'unit_price': 30.0, 'subtotal': 30.0}
        ]
        
        discount_amount = discount_service.calculate_discount(
            promotion.id, order_items, customer_id=1
        )
        
        expected_discount = (100.0 + 30.0) * 0.20  # 20% of 130
        assert discount_amount == expected_discount
        assert discount_amount == 26.0
    
    def test_calculate_fixed_amount_discount(self, discount_service, db_session, promotion_factory):
        """Test calculating fixed amount discount"""
        promotion = promotion_factory.create_fixed_amount_promotion(
            db_session,
            discount_value=25.0,  # $25 off
            status=PromotionStatus.ACTIVE
        )
        
        order_items = [
            {'product_id': 1, 'quantity': 2, 'unit_price': 50.0, 'subtotal': 100.0}
        ]
        
        discount_amount = discount_service.calculate_discount(
            promotion.id, order_items, customer_id=1
        )
        
        assert discount_amount == 25.0
    
    def test_calculate_fixed_amount_discount_exceeds_total(self, discount_service, db_session, promotion_factory):
        """Test fixed amount discount when it exceeds order total"""
        promotion = promotion_factory.create_fixed_amount_promotion(
            db_session,
            discount_value=50.0,  # $50 off
            status=PromotionStatus.ACTIVE
        )
        
        order_items = [
            {'product_id': 1, 'quantity': 1, 'unit_price': 30.0, 'subtotal': 30.0}
        ]
        
        discount_amount = discount_service.calculate_discount(
            promotion.id, order_items, customer_id=1
        )
        
        # Discount should not exceed order total
        assert discount_amount == 30.0
    
    def test_calculate_bogo_discount(self, discount_service, db_session, promotion_factory):
        """Test calculating buy-one-get-one discount"""
        promotion = promotion_factory.create_bogo_promotion(
            db_session,
            status=PromotionStatus.ACTIVE
        )
        
        # BOGO typically applies to same products
        order_items = [
            {'product_id': 1, 'quantity': 3, 'unit_price': 20.0, 'subtotal': 60.0}
        ]
        
        discount_amount = discount_service.calculate_discount(
            promotion.id, order_items, customer_id=1
        )
        
        # With 3 items: customer pays for 2, gets 1 free
        # So discount = 1 * 20.0 = 20.0
        assert discount_amount == 20.0
    
    def test_calculate_discount_minimum_order_not_met(self, discount_service, db_session, promotion_factory):
        """Test discount calculation when minimum order amount is not met"""
        promotion = promotion_factory.create_percentage_promotion(
            db_session,
            discount_value=15.0,
            minimum_order_amount=100.0,
            status=PromotionStatus.ACTIVE
        )
        
        order_items = [
            {'product_id': 1, 'quantity': 1, 'unit_price': 50.0, 'subtotal': 50.0}
        ]
        
        discount_amount = discount_service.calculate_discount(
            promotion.id, order_items, customer_id=1
        )
        
        # Order total (50) is below minimum (100), so no discount
        assert discount_amount == 0.0
    
    def test_calculate_discount_minimum_order_met(self, discount_service, db_session, promotion_factory):
        """Test discount calculation when minimum order amount is met"""
        promotion = promotion_factory.create_percentage_promotion(
            db_session,
            discount_value=15.0,
            minimum_order_amount=100.0,
            status=PromotionStatus.ACTIVE
        )
        
        order_items = [
            {'product_id': 1, 'quantity': 2, 'unit_price': 60.0, 'subtotal': 120.0}
        ]
        
        discount_amount = discount_service.calculate_discount(
            promotion.id, order_items, customer_id=1
        )
        
        # Order total (120) meets minimum (100), so apply 15% discount
        expected_discount = 120.0 * 0.15
        assert discount_amount == expected_discount
        assert discount_amount == 18.0
    
    def test_calculate_discount_inactive_promotion(self, discount_service, db_session, promotion_factory):
        """Test discount calculation for inactive promotion"""
        promotion = promotion_factory.create_percentage_promotion(
            db_session,
            discount_value=20.0,
            status=PromotionStatus.DRAFT  # Not active
        )
        
        order_items = [
            {'product_id': 1, 'quantity': 1, 'unit_price': 100.0, 'subtotal': 100.0}
        ]
        
        with pytest.raises(ValueError, match="Promotion .* is not active"):
            discount_service.calculate_discount(
                promotion.id, order_items, customer_id=1
            )
    
    def test_calculate_discount_nonexistent_promotion(self, discount_service):
        """Test discount calculation for non-existent promotion"""
        order_items = [
            {'product_id': 1, 'quantity': 1, 'unit_price': 100.0, 'subtotal': 100.0}
        ]
        
        with pytest.raises(ValueError, match="Promotion .* not found"):
            discount_service.calculate_discount(
                99999, order_items, customer_id=1
            )
    
    def test_apply_discount_to_order(self, discount_service, db_session, promotion_factory, sample_customer, order_factory):
        """Test applying discount to an order"""
        promotion = promotion_factory.create_percentage_promotion(
            db_session,
            discount_value=10.0,
            status=PromotionStatus.ACTIVE
        )
        
        order = order_factory.create_order(
            db_session,
            sample_customer,
            subtotal=100.0,
            total_amount=100.0,
            final_amount=100.0
        )
        
        order_items = [
            {'product_id': 1, 'quantity': 2, 'unit_price': 50.0, 'subtotal': 100.0}
        ]
        
        updated_order = discount_service.apply_discount_to_order(
            order.id, promotion.id, order_items
        )
        
        assert updated_order.discount_amount == 10.0  # 10% of 100
        assert updated_order.final_amount == 90.0  # 100 - 10
    
    def test_calculate_multiple_promotions(self, discount_service, db_session, promotion_factory):
        """Test calculating discounts for multiple promotions"""
        promo1 = promotion_factory.create_percentage_promotion(
            db_session,
            name="Promo 1",
            discount_value=10.0,
            priority=1,
            status=PromotionStatus.ACTIVE
        )
        promo2 = promotion_factory.create_fixed_amount_promotion(
            db_session,
            name="Promo 2",
            discount_value=15.0,
            priority=2,
            status=PromotionStatus.ACTIVE
        )
        
        order_items = [
            {'product_id': 1, 'quantity': 2, 'unit_price': 50.0, 'subtotal': 100.0}
        ]
        
        result = discount_service.calculate_multiple_promotions(
            [promo1.id, promo2.id], order_items, customer_id=1
        )
        
        assert len(result['applied_promotions']) == 2
        assert result['total_discount'] > 0
        
        # Check individual promotion discounts
        promo1_discount = next(
            p['discount_amount'] for p in result['applied_promotions'] 
            if p['promotion_id'] == promo1.id
        )
        promo2_discount = next(
            p['discount_amount'] for p in result['applied_promotions'] 
            if p['promotion_id'] == promo2.id
        )
        
        assert promo1_discount == 10.0  # 10% of 100
        assert promo2_discount == 15.0  # $15 off
    
    def test_calculate_multiple_promotions_with_stacking_rules(self, discount_service, db_session, promotion_factory):
        """Test multiple promotion calculation with stacking rules"""
        # Create promotions that shouldn't stack (same type)
        promo1 = promotion_factory.create_percentage_promotion(
            db_session,
            name="Promo 1",
            discount_value=15.0,
            priority=1,
            can_stack=False,
            status=PromotionStatus.ACTIVE
        )
        promo2 = promotion_factory.create_percentage_promotion(
            db_session,
            name="Promo 2",
            discount_value=20.0,
            priority=2,
            can_stack=False,
            status=PromotionStatus.ACTIVE
        )
        
        order_items = [
            {'product_id': 1, 'quantity': 2, 'unit_price': 50.0, 'subtotal': 100.0}
        ]
        
        result = discount_service.calculate_multiple_promotions(
            [promo1.id, promo2.id], order_items, customer_id=1
        )
        
        # Should only apply the best promotion (highest discount)
        assert len(result['applied_promotions']) == 1
        applied_promo = result['applied_promotions'][0]
        assert applied_promo['promotion_id'] == promo2.id  # Higher discount
        assert applied_promo['discount_amount'] == 20.0
    
    def test_get_best_promotion_for_order(self, discount_service, db_session, promotion_factory):
        """Test finding the best promotion for an order"""
        promo1 = promotion_factory.create_percentage_promotion(
            db_session,
            name="10% Off",
            discount_value=10.0,
            status=PromotionStatus.ACTIVE
        )
        promo2 = promotion_factory.create_fixed_amount_promotion(
            db_session,
            name="$25 Off",
            discount_value=25.0,
            status=PromotionStatus.ACTIVE
        )
        promo3 = promotion_factory.create_percentage_promotion(
            db_session,
            name="15% Off",
            discount_value=15.0,
            status=PromotionStatus.ACTIVE
        )
        
        order_items = [
            {'product_id': 1, 'quantity': 3, 'unit_price': 50.0, 'subtotal': 150.0}
        ]
        
        best_promotion = discount_service.get_best_promotion_for_order(
            [promo1.id, promo2.id, promo3.id], order_items, customer_id=1
        )
        
        # For $150 order:
        # - 10% off = $15
        # - $25 off = $25
        # - 15% off = $22.50
        # Best should be $25 off (promo2)
        assert best_promotion['promotion_id'] == promo2.id
        assert best_promotion['discount_amount'] == 25.0
    
    def test_validate_discount_constraints(self, discount_service, db_session, promotion_factory):
        """Test validation of discount constraints"""
        promotion = promotion_factory.create_percentage_promotion(
            db_session,
            discount_value=20.0,
            max_discount_amount=30.0,  # Cap discount at $30
            status=PromotionStatus.ACTIVE
        )
        
        # Order that would normally get $40 discount (20% of $200)
        order_items = [
            {'product_id': 1, 'quantity': 4, 'unit_price': 50.0, 'subtotal': 200.0}
        ]
        
        discount_amount = discount_service.calculate_discount(
            promotion.id, order_items, customer_id=1
        )
        
        # Should be capped at max_discount_amount
        assert discount_amount == 30.0
    
    def test_calculate_tiered_discount(self, discount_service, db_session):
        """Test calculating tiered discount based on order amount"""
        from backend.modules.promotions.models.promotion_models import Promotion
        
        # Create a tiered promotion
        promotion = Promotion(
            name="Tiered Discount",
            description="Spend more, save more",
            promotion_type=PromotionType.TIERED_DISCOUNT,
            discount_type=DiscountType.PERCENTAGE,
            status=PromotionStatus.ACTIVE,
            start_date=datetime.utcnow() - timedelta(days=1),
            end_date=datetime.utcnow() + timedelta(days=30),
            max_uses=100,
            current_uses=0,
            # Tier rules: 5% for $50+, 10% for $100+, 15% for $200+
            tier_rules={
                'tiers': [
                    {'min_amount': 50, 'discount_percentage': 5},
                    {'min_amount': 100, 'discount_percentage': 10},
                    {'min_amount': 200, 'discount_percentage': 15}
                ]
            }
        )
        
        db_session.add(promotion)
        db_session.commit()
        db_session.refresh(promotion)
        
        # Test different order amounts
        test_cases = [
            (30.0, 0.0),    # Below minimum tier
            (75.0, 3.75),   # 5% tier: 75 * 0.05 = 3.75
            (150.0, 15.0),  # 10% tier: 150 * 0.10 = 15.0
            (250.0, 37.5),  # 15% tier: 250 * 0.15 = 37.5
        ]
        
        for order_amount, expected_discount in test_cases:
            order_items = [
                {'product_id': 1, 'quantity': 1, 'unit_price': order_amount, 'subtotal': order_amount}
            ]
            
            discount_amount = discount_service.calculate_discount(
                promotion.id, order_items, customer_id=1
            )
            
            assert discount_amount == expected_discount, f"Order amount {order_amount}: expected {expected_discount}, got {discount_amount}"