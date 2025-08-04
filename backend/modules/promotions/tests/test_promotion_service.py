# backend/modules/promotions/tests/test_promotion_service.py

import pytest
from datetime import datetime, timedelta
from unittest.mock import patch

from modules.promotions.schemas.promotion_schemas import PromotionCreate, PromotionUpdate
from modules.promotions.models.promotion_models import (
    PromotionStatus, PromotionType, DiscountType
)


class TestPromotionService:
    """Test cases for PromotionService"""
    
    def test_create_promotion(self, promotion_service, db_session):
        """Test creating a new promotion"""
        promotion_data = PromotionCreate(
            name="Test Promotion",
            description="A test promotion",
            promotion_type=PromotionType.PERCENTAGE_DISCOUNT,
            discount_type=DiscountType.PERCENTAGE,
            discount_value=15.0,
            start_date=datetime.utcnow(),
            end_date=datetime.utcnow() + timedelta(days=30),
            max_uses=100
        )
        
        promotion = promotion_service.create_promotion(promotion_data)
        
        assert promotion.id is not None
        assert promotion.name == "Test Promotion"
        assert promotion.promotion_type == PromotionType.PERCENTAGE_DISCOUNT
        assert promotion.discount_value == 15.0
        assert promotion.status == PromotionStatus.DRAFT
        assert promotion.current_uses == 0
    
    def test_get_promotion_by_id(self, promotion_service, sample_promotion):
        """Test retrieving a promotion by ID"""
        promotion = promotion_service.get_promotion_by_id(sample_promotion.id)
        
        assert promotion is not None
        assert promotion.id == sample_promotion.id
        assert promotion.name == sample_promotion.name
    
    def test_get_promotion_by_id_not_found(self, promotion_service):
        """Test retrieving a non-existent promotion"""
        promotion = promotion_service.get_promotion_by_id(99999)
        assert promotion is None
    
    def test_update_promotion(self, promotion_service, sample_promotion):
        """Test updating a promotion"""
        update_data = PromotionUpdate(
            name="Updated Promotion",
            discount_value=20.0
        )
        
        updated_promotion = promotion_service.update_promotion(
            sample_promotion.id, update_data
        )
        
        assert updated_promotion.name == "Updated Promotion"
        assert updated_promotion.discount_value == 20.0
        assert updated_promotion.id == sample_promotion.id
    
    def test_activate_promotion(self, promotion_service, db_session, promotion_factory):
        """Test activating a draft promotion"""
        promotion = promotion_factory.create_percentage_promotion(
            db_session,
            status=PromotionStatus.DRAFT
        )
        
        activated = promotion_service.activate_promotion(promotion.id)
        
        assert activated.status == PromotionStatus.ACTIVE
    
    def test_activate_promotion_invalid_status(self, promotion_service, db_session, promotion_factory):
        """Test activating a promotion with invalid status"""
        promotion = promotion_factory.create_percentage_promotion(
            db_session,
            status=PromotionStatus.ENDED
        )
        
        with pytest.raises(ValueError, match="Cannot activate promotion"):
            promotion_service.activate_promotion(promotion.id)
    
    def test_pause_promotion(self, promotion_service, sample_promotion):
        """Test pausing an active promotion"""
        sample_promotion.status = PromotionStatus.ACTIVE
        
        paused = promotion_service.pause_promotion(sample_promotion.id)
        
        assert paused.status == PromotionStatus.PAUSED
    
    def test_cancel_promotion(self, promotion_service, sample_promotion):
        """Test cancelling a promotion"""
        cancelled = promotion_service.cancel_promotion(sample_promotion.id)
        
        assert cancelled.status == PromotionStatus.CANCELLED
    
    def test_delete_promotion(self, promotion_service, sample_promotion):
        """Test deleting a draft promotion"""
        sample_promotion.status = PromotionStatus.DRAFT
        
        success = promotion_service.delete_promotion(sample_promotion.id)
        
        assert success is True
        
        # Verify promotion is deleted
        deleted_promotion = promotion_service.get_promotion_by_id(sample_promotion.id)
        assert deleted_promotion is None
    
    def test_delete_active_promotion_fails(self, promotion_service, sample_promotion):
        """Test that deleting an active promotion fails"""
        sample_promotion.status = PromotionStatus.ACTIVE
        
        with pytest.raises(ValueError, match="Cannot delete active promotion"):
            promotion_service.delete_promotion(sample_promotion.id)
    
    def test_get_active_promotions(self, promotion_service, db_session, promotion_factory):
        """Test retrieving active promotions"""
        # Create multiple promotions with different statuses
        active_promo1 = promotion_factory.create_percentage_promotion(
            db_session,
            name="Active 1",
            status=PromotionStatus.ACTIVE
        )
        active_promo2 = promotion_factory.create_percentage_promotion(
            db_session,
            name="Active 2",
            status=PromotionStatus.ACTIVE
        )
        promotion_factory.create_percentage_promotion(
            db_session,
            name="Draft",
            status=PromotionStatus.DRAFT
        )
        promotion_factory.create_percentage_promotion(
            db_session,
            name="Paused",
            status=PromotionStatus.PAUSED
        )
        
        active_promotions = promotion_service.get_active_promotions()
        
        assert len(active_promotions) == 2
        active_names = [p.name for p in active_promotions]
        assert "Active 1" in active_names
        assert "Active 2" in active_names
    
    def test_get_promotions_by_type(self, promotion_service, db_session, promotion_factory):
        """Test retrieving promotions by type"""
        percentage_promo = promotion_factory.create_percentage_promotion(db_session)
        fixed_promo = promotion_factory.create_fixed_amount_promotion(db_session)
        bogo_promo = promotion_factory.create_bogo_promotion(db_session)
        
        percentage_promotions = promotion_service.get_promotions_by_type(
            PromotionType.PERCENTAGE_DISCOUNT
        )
        
        assert len(percentage_promotions) == 1
        assert percentage_promotions[0].id == percentage_promo.id
    
    def test_check_promotion_eligibility(self, promotion_service, sample_promotion, sample_customer):
        """Test checking promotion eligibility"""
        sample_promotion.status = PromotionStatus.ACTIVE
        sample_promotion.max_uses = 100
        sample_promotion.current_uses = 50
        
        is_eligible, reason = promotion_service.check_promotion_eligibility(
            sample_promotion.id, sample_customer.id
        )
        
        assert is_eligible is True
        assert reason == "Eligible"
    
    def test_check_promotion_eligibility_inactive(self, promotion_service, sample_promotion, sample_customer):
        """Test checking eligibility for inactive promotion"""
        sample_promotion.status = PromotionStatus.DRAFT
        
        is_eligible, reason = promotion_service.check_promotion_eligibility(
            sample_promotion.id, sample_customer.id
        )
        
        assert is_eligible is False
        assert "not active" in reason
    
    def test_check_promotion_eligibility_expired(self, promotion_service, sample_promotion, sample_customer):
        """Test checking eligibility for expired promotion"""
        sample_promotion.status = PromotionStatus.ACTIVE
        sample_promotion.end_date = datetime.utcnow() - timedelta(days=1)
        
        is_eligible, reason = promotion_service.check_promotion_eligibility(
            sample_promotion.id, sample_customer.id
        )
        
        assert is_eligible is False
        assert "expired" in reason
    
    def test_check_promotion_eligibility_max_uses_reached(self, promotion_service, sample_promotion, sample_customer):
        """Test checking eligibility when max uses reached"""
        sample_promotion.status = PromotionStatus.ACTIVE
        sample_promotion.max_uses = 10
        sample_promotion.current_uses = 10
        
        is_eligible, reason = promotion_service.check_promotion_eligibility(
            sample_promotion.id, sample_customer.id
        )
        
        assert is_eligible is False
        assert "maximum usage limit" in reason
    
    def test_increment_promotion_usage(self, promotion_service, sample_promotion):
        """Test incrementing promotion usage count"""
        initial_uses = sample_promotion.current_uses
        
        updated_promotion = promotion_service.increment_promotion_usage(sample_promotion.id)
        
        assert updated_promotion.current_uses == initial_uses + 1
    
    def test_get_promotion_statistics(self, promotion_service, sample_promotion, db_session):
        """Test getting promotion statistics"""
        # Add some usage data
        from modules.promotions.models.promotion_models import PromotionUsage
        
        usage1 = PromotionUsage(
            promotion_id=sample_promotion.id,
            customer_id=1,
            order_id=1,
            discount_amount=10.0,
            final_order_amount=90.0,
            created_at=datetime.utcnow()
        )
        usage2 = PromotionUsage(
            promotion_id=sample_promotion.id,
            customer_id=2,
            order_id=2,
            discount_amount=15.0,
            final_order_amount=135.0,
            created_at=datetime.utcnow()
        )
        
        db_session.add_all([usage1, usage2])
        db_session.commit()
        
        stats = promotion_service.get_promotion_statistics(sample_promotion.id)
        
        assert stats['total_usage'] == 2
        assert stats['total_discount_amount'] == 25.0
        assert stats['total_revenue'] == 225.0
        assert stats['unique_customers'] == 2
        assert stats['average_discount'] == 12.5
        assert stats['average_order_value'] == 112.5
    
    def test_search_promotions(self, promotion_service, db_session, promotion_factory):
        """Test searching promotions"""
        promo1 = promotion_factory.create_percentage_promotion(
            db_session,
            name="Summer Sale"
        )
        promo2 = promotion_factory.create_percentage_promotion(
            db_session,
            name="Winter Discount"
        )
        promo3 = promotion_factory.create_percentage_promotion(
            db_session,
            name="Holiday Special"
        )
        
        # Test search by name
        results = promotion_service.search_promotions(search_term="summer")
        assert len(results) == 1
        assert results[0].id == promo1.id
        
        # Test search by description (if it contains the term)
        results = promotion_service.search_promotions(search_term="discount")
        assert len(results) >= 1  # Should find at least the Winter Discount
    
    def test_bulk_update_promotion_status(self, promotion_service, db_session, promotion_factory):
        """Test bulk updating promotion status"""
        promo1 = promotion_factory.create_percentage_promotion(
            db_session,
            status=PromotionStatus.DRAFT
        )
        promo2 = promotion_factory.create_percentage_promotion(
            db_session,
            status=PromotionStatus.DRAFT
        )
        promo3 = promotion_factory.create_percentage_promotion(
            db_session,
            status=PromotionStatus.ACTIVE
        )
        
        promotion_ids = [promo1.id, promo2.id]
        updated_count = promotion_service.bulk_update_promotion_status(
            promotion_ids, PromotionStatus.ACTIVE
        )
        
        assert updated_count == 2
        
        # Verify updates
        db_session.refresh(promo1)
        db_session.refresh(promo2)
        db_session.refresh(promo3)
        
        assert promo1.status == PromotionStatus.ACTIVE
        assert promo2.status == PromotionStatus.ACTIVE
        assert promo3.status == PromotionStatus.ACTIVE  # Unchanged