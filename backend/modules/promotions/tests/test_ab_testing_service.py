# backend/modules/promotions/tests/test_ab_testing_service.py

import pytest
from datetime import datetime, timedelta

from modules.promotions.schemas.promotion_schemas import PromotionCreate
from modules.promotions.models.promotion_models import (
    PromotionType, DiscountType, PromotionStatus
)


class TestABTestingService:
    """Test cases for ABTestingService"""
    
    def test_create_ab_test(self, ab_testing_service, db_session):
        """Test creating an A/B test"""
        control_promotion = PromotionCreate(
            name="Control Promotion",
            description="Control promotion for A/B test",
            promotion_type=PromotionType.PERCENTAGE_DISCOUNT,
            discount_type=DiscountType.PERCENTAGE,
            discount_value=10.0,
            start_date=datetime.utcnow(),
            end_date=datetime.utcnow() + timedelta(days=30),
            max_uses=1000
        )
        
        variant_promotions = [
            PromotionCreate(
                name="Variant 1",
                description="First variant promotion",
                promotion_type=PromotionType.PERCENTAGE_DISCOUNT,
                discount_type=DiscountType.PERCENTAGE,
                discount_value=15.0,
                start_date=datetime.utcnow(),
                end_date=datetime.utcnow() + timedelta(days=30),
                max_uses=1000
            ),
            PromotionCreate(
                name="Variant 2", 
                description="Second variant promotion",
                promotion_type=PromotionType.FIXED_AMOUNT_DISCOUNT,
                discount_type=DiscountType.FIXED_AMOUNT,
                discount_value=20.0,
                start_date=datetime.utcnow(),
                end_date=datetime.utcnow() + timedelta(days=30),
                max_uses=1000
            )
        ]
        
        test_config = {
            'control_traffic_percentage': 40,
            'variant_traffic_percentages': [30, 30],
            'duration_days': 14,
            'minimum_sample_size': 100,
            'success_metric': 'conversion_rate'
        }
        
        result = ab_testing_service.create_ab_test(
            test_name="Discount Amount Test",
            control_promotion=control_promotion,
            variant_promotions=variant_promotions,
            test_config=test_config
        )
        
        assert result['test_name'] == "Discount Amount Test"
        assert result['total_promotions'] == 3  # 1 control + 2 variants
        assert result['control_promotion'].metadata['ab_test']['variant_type'] == 'control'
        assert len(result['variant_promotions']) == 2
        
        # Check traffic percentages
        assert result['control_promotion'].metadata['ab_test']['traffic_percentage'] == 40
        assert result['variant_promotions'][0].metadata['ab_test']['traffic_percentage'] == 30
        assert result['variant_promotions'][1].metadata['ab_test']['traffic_percentage'] == 30
    
    def test_create_ab_test_invalid_traffic_split(self, ab_testing_service):
        """Test creating A/B test with invalid traffic split"""
        control_promotion = PromotionCreate(
            name="Control",
            promotion_type=PromotionType.PERCENTAGE_DISCOUNT,
            discount_type=DiscountType.PERCENTAGE,
            discount_value=10.0,
            start_date=datetime.utcnow(),
            end_date=datetime.utcnow() + timedelta(days=30)
        )
        
        variant_promotions = [
            PromotionCreate(
                name="Variant 1",
                promotion_type=PromotionType.PERCENTAGE_DISCOUNT,
                discount_type=DiscountType.PERCENTAGE,
                discount_value=15.0,
                start_date=datetime.utcnow(),
                end_date=datetime.utcnow() + timedelta(days=30)
            )
        ]
        
        # Traffic percentages don't sum to 100
        test_config = {
            'control_traffic_percentage': 60,
            'variant_traffic_percentages': [50],  # 60 + 50 = 110%
        }
        
        with pytest.raises(ValueError, match="Traffic percentages must sum to 100"):
            ab_testing_service.create_ab_test(
                test_name="Invalid Test",
                control_promotion=control_promotion,
                variant_promotions=variant_promotions,
                test_config=test_config
            )
    
    def test_assign_user_to_variant(self, ab_testing_service, db_session):
        """Test assigning users to variants"""
        # First create an A/B test
        control_promotion = PromotionCreate(
            name="Control",
            promotion_type=PromotionType.PERCENTAGE_DISCOUNT,
            discount_type=DiscountType.PERCENTAGE,
            discount_value=10.0,
            start_date=datetime.utcnow(),
            end_date=datetime.utcnow() + timedelta(days=30)
        )
        
        variant_promotions = [
            PromotionCreate(
                name="Variant 1",
                promotion_type=PromotionType.PERCENTAGE_DISCOUNT,
                discount_type=DiscountType.PERCENTAGE,
                discount_value=15.0,
                start_date=datetime.utcnow(),
                end_date=datetime.utcnow() + timedelta(days=30)
            )
        ]
        
        test_config = {
            'control_traffic_percentage': 50,
            'variant_traffic_percentages': [50]
        }
        
        result = ab_testing_service.create_ab_test(
            test_name="Assignment Test",
            control_promotion=control_promotion,
            variant_promotions=variant_promotions,
            test_config=test_config
        )
        
        test_id = result['test_id']
        
        # Start the test
        ab_testing_service.start_ab_test(test_id)
        
        # Test assignment for different users
        assignments = []
        for customer_id in range(1, 101):  # Test 100 users
            assignment = ab_testing_service.assign_user_to_variant(
                test_id=test_id,
                customer_id=customer_id
            )
            assignments.append(assignment)
            
            assert assignment['test_id'] == test_id
            assert assignment['customer_id'] == customer_id
            assert assignment['assigned_variant'] in ['control', 'variant_1']
        
        # Check that assignment is deterministic (same user gets same variant)
        assignment1 = ab_testing_service.assign_user_to_variant(
            test_id=test_id,
            customer_id=1
        )
        assignment2 = ab_testing_service.assign_user_to_variant(
            test_id=test_id,
            customer_id=1
        )
        
        assert assignment1['assigned_variant'] == assignment2['assigned_variant']
        
        # Check traffic split is approximately correct (within reasonable margin)
        control_count = sum(1 for a in assignments if a['assigned_variant'] == 'control')
        variant_count = sum(1 for a in assignments if a['assigned_variant'] == 'variant_1')
        
        control_percentage = control_count / len(assignments) * 100
        variant_percentage = variant_count / len(assignments) * 100
        
        # Allow 10% margin of error for randomness
        assert 40 <= control_percentage <= 60
        assert 40 <= variant_percentage <= 60
    
    def test_assign_user_to_variant_inactive_test(self, ab_testing_service, db_session):
        """Test assigning user to variant when test is inactive"""
        # Create test but don't start it
        control_promotion = PromotionCreate(
            name="Control",
            promotion_type=PromotionType.PERCENTAGE_DISCOUNT,
            discount_type=DiscountType.PERCENTAGE,
            discount_value=10.0,
            start_date=datetime.utcnow(),
            end_date=datetime.utcnow() + timedelta(days=30)
        )
        
        variant_promotions = [
            PromotionCreate(
                name="Variant 1",
                promotion_type=PromotionType.PERCENTAGE_DISCOUNT,
                discount_type=DiscountType.PERCENTAGE,
                discount_value=15.0,
                start_date=datetime.utcnow(),
                end_date=datetime.utcnow() + timedelta(days=30)
            )
        ]
        
        result = ab_testing_service.create_ab_test(
            test_name="Inactive Test",
            control_promotion=control_promotion,
            variant_promotions=variant_promotions,
            test_config={'control_traffic_percentage': 50, 'variant_traffic_percentages': [50]}
        )
        
        test_id = result['test_id']
        
        # Try to assign user without starting test
        with pytest.raises(ValueError, match="A/B test .* is not active"):
            ab_testing_service.assign_user_to_variant(
                test_id=test_id,
                customer_id=1
            )
    
    def test_start_ab_test(self, ab_testing_service, db_session):
        """Test starting an A/B test"""
        # Create test
        control_promotion = PromotionCreate(
            name="Control",
            promotion_type=PromotionType.PERCENTAGE_DISCOUNT,
            discount_type=DiscountType.PERCENTAGE,
            discount_value=10.0,
            start_date=datetime.utcnow(),
            end_date=datetime.utcnow() + timedelta(days=30)
        )
        
        variant_promotions = [
            PromotionCreate(
                name="Variant 1",
                promotion_type=PromotionType.PERCENTAGE_DISCOUNT,
                discount_type=DiscountType.PERCENTAGE,
                discount_value=15.0,
                start_date=datetime.utcnow(),
                end_date=datetime.utcnow() + timedelta(days=30)
            )
        ]
        
        result = ab_testing_service.create_ab_test(
            test_name="Start Test",
            control_promotion=control_promotion,
            variant_promotions=variant_promotions,
            test_config={'control_traffic_percentage': 50, 'variant_traffic_percentages': [50]}
        )
        
        test_id = result['test_id']
        
        # Start the test
        start_result = ab_testing_service.start_ab_test(test_id)
        
        assert start_result['test_id'] == test_id
        assert start_result['status'] == 'active'
        assert start_result['promotions_activated'] == 2
        
        # Verify promotions are active
        from modules.promotions.models.promotion_models import Promotion
        test_promotions = db_session.query(Promotion).filter(
            Promotion.metadata['ab_test']['test_id'].astext == test_id
        ).all()
        
        for promotion in test_promotions:
            assert promotion.status == PromotionStatus.ACTIVE
            assert promotion.metadata['ab_test']['test_status'] == 'active'
    
    def test_stop_ab_test(self, ab_testing_service, db_session):
        """Test stopping an A/B test"""
        # Create and start test
        control_promotion = PromotionCreate(
            name="Control",
            promotion_type=PromotionType.PERCENTAGE_DISCOUNT,
            discount_type=DiscountType.PERCENTAGE,
            discount_value=10.0,
            start_date=datetime.utcnow(),
            end_date=datetime.utcnow() + timedelta(days=30)
        )
        
        variant_promotions = [
            PromotionCreate(
                name="Variant 1",
                promotion_type=PromotionType.PERCENTAGE_DISCOUNT,
                discount_type=DiscountType.PERCENTAGE,
                discount_value=15.0,
                start_date=datetime.utcnow(),
                end_date=datetime.utcnow() + timedelta(days=30)
            )
        ]
        
        result = ab_testing_service.create_ab_test(
            test_name="Stop Test",
            control_promotion=control_promotion,
            variant_promotions=variant_promotions,
            test_config={'control_traffic_percentage': 50, 'variant_traffic_percentages': [50]}
        )
        
        test_id = result['test_id']
        ab_testing_service.start_ab_test(test_id)
        
        # Stop the test with variant_1 as winner
        stop_result = ab_testing_service.stop_ab_test(test_id, winning_variant='variant_1')
        
        assert stop_result['test_id'] == test_id
        assert stop_result['status'] == 'stopped'
        assert stop_result['winning_variant'] == 'variant_1'
        
        # Verify promotion statuses
        from modules.promotions.models.promotion_models import Promotion
        test_promotions = db_session.query(Promotion).filter(
            Promotion.metadata['ab_test']['test_id'].astext == test_id
        ).all()
        
        for promotion in test_promotions:
            ab_test_data = promotion.metadata['ab_test']
            if ab_test_data['variant_id'] == 'variant_1':
                # Winner should still be active
                assert promotion.status == PromotionStatus.ACTIVE
                assert ab_test_data['test_status'] == 'winner'
            else:
                # Loser should be paused
                assert promotion.status == PromotionStatus.PAUSED
                assert ab_test_data['test_status'] == 'loser'
    
    def test_get_ab_test_results(self, ab_testing_service, db_session, sample_customer):
        """Test getting A/B test results"""
        # Create and start test
        control_promotion = PromotionCreate(
            name="Control",
            promotion_type=PromotionType.PERCENTAGE_DISCOUNT,
            discount_type=DiscountType.PERCENTAGE,
            discount_value=10.0,
            start_date=datetime.utcnow(),
            end_date=datetime.utcnow() + timedelta(days=30)
        )
        
        variant_promotions = [
            PromotionCreate(
                name="Variant 1",
                promotion_type=PromotionType.PERCENTAGE_DISCOUNT,
                discount_type=DiscountType.PERCENTAGE,
                discount_value=15.0,
                start_date=datetime.utcnow(),
                end_date=datetime.utcnow() + timedelta(days=30)
            )
        ]
        
        result = ab_testing_service.create_ab_test(
            test_name="Results Test",
            control_promotion=control_promotion,
            variant_promotions=variant_promotions,
            test_config={'control_traffic_percentage': 50, 'variant_traffic_percentages': [50]}
        )
        
        test_id = result['test_id']
        ab_testing_service.start_ab_test(test_id)
        
        # Add some usage data
        from modules.promotions.models.promotion_models import PromotionUsage
        
        control_promotion_obj = result['control_promotion']
        variant_promotion_obj = result['variant_promotions'][0]
        
        # Add usage for control
        control_usage = PromotionUsage(
            promotion_id=control_promotion_obj.id,
            customer_id=sample_customer.id,
            order_id=1,
            discount_amount=10.0,
            final_order_amount=90.0,
            created_at=datetime.utcnow()
        )
        
        # Add usage for variant
        variant_usage = PromotionUsage(
            promotion_id=variant_promotion_obj.id,
            customer_id=sample_customer.id,
            order_id=2,
            discount_amount=15.0,
            final_order_amount=135.0,
            created_at=datetime.utcnow()
        )
        
        db_session.add_all([control_usage, variant_usage])
        db_session.commit()
        
        # Get results
        results = ab_testing_service.get_ab_test_results(test_id)
        
        assert results['test_id'] == test_id
        assert results['test_name'] == "Results Test"
        assert len(results['variant_results']) == 2
        
        # Check variant results structure
        for variant_result in results['variant_results']:
            assert 'variant_id' in variant_result
            assert 'variant_type' in variant_result
            assert 'metrics' in variant_result
            assert 'conversions' in variant_result['metrics']
            assert 'total_revenue' in variant_result['metrics']
    
    def test_get_active_ab_tests(self, ab_testing_service, db_session):
        """Test getting active A/B tests"""
        # Create multiple tests
        for i in range(3):
            control_promotion = PromotionCreate(
                name=f"Control {i}",
                promotion_type=PromotionType.PERCENTAGE_DISCOUNT,
                discount_type=DiscountType.PERCENTAGE,
                discount_value=10.0,
                start_date=datetime.utcnow(),
                end_date=datetime.utcnow() + timedelta(days=30)
            )
            
            variant_promotions = [
                PromotionCreate(
                    name=f"Variant {i}",
                    promotion_type=PromotionType.PERCENTAGE_DISCOUNT,
                    discount_type=DiscountType.PERCENTAGE,
                    discount_value=15.0,
                    start_date=datetime.utcnow(),
                    end_date=datetime.utcnow() + timedelta(days=30)
                )
            ]
            
            result = ab_testing_service.create_ab_test(
                test_name=f"Test {i}",
                control_promotion=control_promotion,
                variant_promotions=variant_promotions,
                test_config={'control_traffic_percentage': 50, 'variant_traffic_percentages': [50]}
            )
            
            # Start only the first two tests
            if i < 2:
                ab_testing_service.start_ab_test(result['test_id'])
        
        active_tests = ab_testing_service.get_active_ab_tests()
        
        assert len(active_tests) == 2
        for test in active_tests:
            assert 'test_id' in test
            assert 'test_name' in test
            assert 'promotions' in test
            assert len(test['promotions']) == 2  # 1 control + 1 variant
    
    def test_validate_ab_test_config(self, ab_testing_service):
        """Test A/B test configuration validation"""
        # Valid config
        valid_config = {
            'control_traffic_percentage': 50,
            'variant_traffic_percentages': [30, 20],
            'duration_days': 14,
            'minimum_sample_size': 100
        }
        
        # Should not raise exception
        ab_testing_service._validate_ab_test_config(valid_config, 2)
        
        # Invalid config - wrong number of variant percentages
        invalid_config1 = {
            'control_traffic_percentage': 50,
            'variant_traffic_percentages': [50],  # Only 1 percentage for 2 variants
        }
        
        with pytest.raises(ValueError, match="Number of variant traffic percentages"):
            ab_testing_service._validate_ab_test_config(invalid_config1, 2)
        
        # Invalid config - percentages don't sum to 100
        invalid_config2 = {
            'control_traffic_percentage': 60,
            'variant_traffic_percentages': [50, 50],  # 60 + 50 + 50 = 160
        }
        
        with pytest.raises(ValueError, match="Traffic percentages must sum to 100"):
            ab_testing_service._validate_ab_test_config(invalid_config2, 2)
        
        # Invalid config - duration too short
        invalid_config3 = {
            'control_traffic_percentage': 50,
            'variant_traffic_percentages': [50],
            'duration_days': 0
        }
        
        with pytest.raises(ValueError, match="Test duration must be at least 1 day"):
            ab_testing_service._validate_ab_test_config(invalid_config3, 1)