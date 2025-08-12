"""
Tests for order prioritization algorithms.
"""

import pytest
from datetime import datetime, timedelta
from decimal import Decimal
from sqlalchemy.orm import Session

from modules.orders.models.priority_models import (
    PriorityRule, PriorityProfile, PriorityProfileRule,
    QueuePriorityConfig, OrderPriorityScore,
    PriorityAlgorithmType, PriorityScoreType
)
from modules.orders.models.order_models import Order, OrderItem, OrderPriority
from modules.orders.models.queue_models import OrderQueue, QueueItem, QueueType, QueueItemStatus
from modules.customers.models.customer_models import Customer, CustomerTier
from modules.orders.services.priority_service import PriorityService
from modules.menu.models.menu_models import MenuItem


@pytest.fixture
def priority_service(db_session):
    """Create priority service instance"""
    return PriorityService(db_session)


@pytest.fixture
def sample_queue(db_session):
    """Create a sample queue"""
    queue = OrderQueue(
        name="Test Kitchen Queue",
        queue_type=QueueType.KITCHEN,
        status="active",
        priority=50,
        auto_sequence=True,
        default_prep_time=15
    )
    db_session.add(queue)
    db_session.commit()
    return queue


@pytest.fixture
def vip_customer(db_session):
    """Create a VIP customer"""
    customer = Customer(
        first_name="VIP",
        last_name="Customer",
        email="vip@example.com",
        tier=CustomerTier.VIP,
        lifetime_value=Decimal("5000.00")
    )
    db_session.add(customer)
    db_session.commit()
    return customer


@pytest.fixture
def regular_customer(db_session):
    """Create a regular customer"""
    customer = Customer(
        first_name="Regular",
        last_name="Customer",
        email="regular@example.com",
        tier=CustomerTier.BRONZE,
        lifetime_value=Decimal("100.00")
    )
    db_session.add(customer)
    db_session.commit()
    return customer


@pytest.fixture
def priority_rules(db_session):
    """Create sample priority rules"""
    rules = []
    
    # Preparation time rule
    prep_rule = PriorityRule(
        name="Preparation Time Priority",
        algorithm_type=PriorityAlgorithmType.PREPARATION_TIME,
        is_active=True,
        weight=2.0,
        min_score=0,
        max_score=100,
        parameters={
            "base_minutes": 15,
            "penalty_per_minute": 2
        },
        score_type=PriorityScoreType.LINEAR
    )
    db_session.add(prep_rule)
    rules.append(prep_rule)
    
    # Delivery window rule
    delivery_rule = PriorityRule(
        name="Delivery Window Priority",
        algorithm_type=PriorityAlgorithmType.DELIVERY_WINDOW,
        is_active=True,
        weight=3.0,
        min_score=0,
        max_score=100,
        parameters={
            "grace_minutes": 10,
            "critical_minutes": 30
        },
        score_type=PriorityScoreType.LINEAR
    )
    db_session.add(delivery_rule)
    rules.append(delivery_rule)
    
    # VIP status rule
    vip_rule = PriorityRule(
        name="VIP Status Priority",
        algorithm_type=PriorityAlgorithmType.VIP_STATUS,
        is_active=True,
        weight=1.5,
        min_score=0,
        max_score=100,
        parameters={
            "tier_scores": {
                "bronze": 10,
                "silver": 20,
                "gold": 30,
                "platinum": 50,
                "vip": 100
            }
        },
        score_type=PriorityScoreType.LINEAR
    )
    db_session.add(vip_rule)
    rules.append(vip_rule)
    
    # Order value rule
    value_rule = PriorityRule(
        name="Order Value Priority",
        algorithm_type=PriorityAlgorithmType.ORDER_VALUE,
        is_active=True,
        weight=1.0,
        min_score=0,
        max_score=100,
        parameters={
            "min_value": 0,
            "max_value": 200
        },
        score_type=PriorityScoreType.LINEAR
    )
    db_session.add(value_rule)
    rules.append(value_rule)
    
    db_session.commit()
    return rules


@pytest.fixture
def priority_profile(db_session, priority_rules):
    """Create a priority profile with rules"""
    profile = PriorityProfile(
        name="Standard Priority Profile",
        is_active=True,
        is_default=True,
        normalize_scores=True,
        normalization_method="min_max"
    )
    db_session.add(profile)
    db_session.flush()
    
    # Add all rules to profile
    for rule in priority_rules:
        profile_rule = PriorityProfileRule(
            profile_id=profile.id,
            rule_id=rule.id,
            weight_override=None,
            is_required=False,
            fallback_score=0
        )
        db_session.add(profile_rule)
    
    db_session.commit()
    return profile


@pytest.fixture
def queue_priority_config(db_session, sample_queue, priority_profile):
    """Create queue priority configuration"""
    config = QueuePriorityConfig(
        queue_id=sample_queue.id,
        priority_profile_id=priority_profile.id,
        priority_boost_vip=20.0,
        priority_boost_delayed=15.0,
        priority_boost_large_party=10.0,
        rebalance_enabled=True,
        rebalance_interval=300,
        max_position_change=5,
        peak_hours=[{
            "days": [0, 1, 2, 3, 4],  # Monday to Friday
            "start_hour": 11,
            "end_hour": 14
        }],
        peak_multiplier=1.5
    )
    db_session.add(config)
    db_session.commit()
    return config


class TestPriorityAlgorithms:
    """Test individual priority algorithms"""
    
    def test_preparation_time_priority(self, db_session, priority_service, priority_rules):
        """Test preparation time-based priority calculation"""
        prep_rule = next(r for r in priority_rules if r.algorithm_type == PriorityAlgorithmType.PREPARATION_TIME)
        
        # Create order with items
        order = Order(
            staff_id=1,
            status="pending",
            total_amount=Decimal("50.00")
        )
        db_session.add(order)
        
        # Add items with different prep times
        item1 = OrderItem(order=order, menu_item_id=1, quantity=2, price=Decimal("10.00"))
        item2 = OrderItem(order=order, menu_item_id=2, quantity=1, price=Decimal("30.00"))
        db_session.add_all([item1, item2])
        
        queue = OrderQueue(id=1, name="Test", queue_type=QueueType.KITCHEN)
        db_session.add(queue)
        db_session.commit()
        
        # Calculate priority
        score = priority_service._calculate_prep_time_priority(prep_rule, order, queue)
        
        # Should get max score for quick prep time (no menu items with prep time defined)
        assert score == prep_rule.max_score
    
    def test_delivery_window_priority(self, db_session, priority_service, priority_rules):
        """Test delivery window-based priority calculation"""
        delivery_rule = next(r for r in priority_rules if r.algorithm_type == PriorityAlgorithmType.DELIVERY_WINDOW)
        
        # Test various delivery windows
        now = datetime.utcnow()
        queue = OrderQueue(id=1, name="Test", queue_type=QueueType.DELIVERY)
        
        # Order due in 5 minutes (within grace period)
        order1 = Order(
            staff_id=1,
            status="pending",
            scheduled_fulfillment_time=now + timedelta(minutes=5)
        )
        score1 = priority_service._calculate_delivery_window_priority(delivery_rule, order1, queue)
        assert score1 > 85  # Should be high priority
        
        # Order due in 25 minutes (within critical period)
        order2 = Order(
            staff_id=1,
            status="pending",
            scheduled_fulfillment_time=now + timedelta(minutes=25)
        )
        score2 = priority_service._calculate_delivery_window_priority(delivery_rule, order2, queue)
        assert 30 < score2 < 70  # Should be medium priority
        
        # Order already late
        order3 = Order(
            staff_id=1,
            status="pending",
            scheduled_fulfillment_time=now - timedelta(minutes=10)
        )
        score3 = priority_service._calculate_delivery_window_priority(delivery_rule, order3, queue)
        assert score3 == delivery_rule.max_score  # Should be maximum priority
    
    def test_vip_status_priority(self, db_session, priority_service, priority_rules, vip_customer, regular_customer):
        """Test VIP status-based priority calculation"""
        vip_rule = next(r for r in priority_rules if r.algorithm_type == PriorityAlgorithmType.VIP_STATUS)
        queue = OrderQueue(id=1, name="Test", queue_type=QueueType.KITCHEN)
        
        # VIP customer order
        vip_order = Order(
            staff_id=1,
            customer_id=vip_customer.id,
            status="pending"
        )
        vip_score = priority_service._calculate_vip_priority(vip_rule, vip_order, queue)
        assert vip_score > 95  # VIP should get near maximum score
        
        # Regular customer order
        regular_order = Order(
            staff_id=1,
            customer_id=regular_customer.id,
            status="pending"
        )
        regular_score = priority_service._calculate_vip_priority(vip_rule, regular_order, queue)
        assert regular_score < 20  # Bronze tier should get low score
        
        # No customer order
        no_customer_order = Order(
            staff_id=1,
            customer_id=None,
            status="pending"
        )
        no_customer_score = priority_service._calculate_vip_priority(vip_rule, no_customer_order, queue)
        assert no_customer_score == vip_rule.min_score
    
    def test_order_value_priority(self, db_session, priority_service, priority_rules):
        """Test order value-based priority calculation"""
        value_rule = next(r for r in priority_rules if r.algorithm_type == PriorityAlgorithmType.ORDER_VALUE)
        queue = OrderQueue(id=1, name="Test", queue_type=QueueType.KITCHEN)
        
        # Low value order
        low_order = Order(
            staff_id=1,
            status="pending",
            total_amount=Decimal("20.00")
        )
        low_score = priority_service._calculate_order_value_priority(value_rule, low_order, queue)
        assert low_score < 20
        
        # Medium value order
        medium_order = Order(
            staff_id=1,
            status="pending",
            total_amount=Decimal("100.00")
        )
        medium_score = priority_service._calculate_order_value_priority(value_rule, medium_order, queue)
        assert 45 < medium_score < 55
        
        # High value order
        high_order = Order(
            staff_id=1,
            status="pending",
            total_amount=Decimal("250.00")
        )
        high_score = priority_service._calculate_order_value_priority(value_rule, high_order, queue)
        assert high_score == value_rule.max_score


class TestCompositePriority:
    """Test composite priority scoring"""
    
    def test_calculate_order_priority(self, db_session, priority_service, sample_queue, 
                                    priority_profile, queue_priority_config, vip_customer):
        """Test full priority calculation with multiple factors"""
        # Create a VIP order with delivery window
        order = Order(
            staff_id=1,
            customer_id=vip_customer.id,
            status="pending",
            total_amount=Decimal("150.00"),
            scheduled_fulfillment_time=datetime.utcnow() + timedelta(minutes=20)
        )
        db_session.add(order)
        db_session.commit()
        
        # Calculate priority
        priority_score = priority_service.calculate_order_priority(
            order_id=order.id,
            queue_id=sample_queue.id
        )
        
        assert priority_score is not None
        assert priority_score.order_id == order.id
        assert priority_score.queue_id == sample_queue.id
        assert priority_score.total_score > 0
        assert priority_score.normalized_score > 0
        assert len(priority_score.score_components) > 0
        assert priority_score.profile_used == priority_profile.name
        assert priority_score.priority_tier in ["low", "medium", "high", "critical"]
    
    def test_priority_with_boosts(self, db_session, priority_service, sample_queue,
                                 queue_priority_config, vip_customer):
        """Test priority calculation with VIP and delay boosts"""
        # Create a delayed VIP order
        order = Order(
            staff_id=1,
            customer_id=vip_customer.id,
            status="pending",
            total_amount=Decimal("100.00"),
            scheduled_fulfillment_time=datetime.utcnow() - timedelta(minutes=10)  # Already late
        )
        db_session.add(order)
        db_session.commit()
        
        # Calculate priority
        priority_score = priority_service.calculate_order_priority(
            order_id=order.id,
            queue_id=sample_queue.id
        )
        
        # Should have high score due to VIP + delay boosts
        assert priority_score.normalized_score > 100  # Base + boosts
        assert priority_score.priority_tier == "critical"


class TestQueueRebalancing:
    """Test queue rebalancing functionality"""
    
    def test_rebalance_queue(self, db_session, priority_service, sample_queue, 
                            queue_priority_config, vip_customer, regular_customer):
        """Test rebalancing queue based on priorities"""
        # Create multiple orders with different priorities
        orders = []
        
        # Regular order added first
        regular_order = Order(
            staff_id=1,
            customer_id=regular_customer.id,
            status="pending",
            total_amount=Decimal("30.00")
        )
        orders.append(regular_order)
        
        # VIP order added second
        vip_order = Order(
            staff_id=1,
            customer_id=vip_customer.id,
            status="pending",
            total_amount=Decimal("150.00")
        )
        orders.append(vip_order)
        
        # Urgent delivery order added third
        urgent_order = Order(
            staff_id=1,
            status="pending",
            total_amount=Decimal("50.00"),
            scheduled_fulfillment_time=datetime.utcnow() + timedelta(minutes=5)
        )
        orders.append(urgent_order)
        
        db_session.add_all(orders)
        db_session.commit()
        
        # Add orders to queue in arrival order
        queue_items = []
        for i, order in enumerate(orders):
            item = QueueItem(
                queue_id=sample_queue.id,
                order_id=order.id,
                sequence_number=i + 1,
                priority=50,  # Default priority
                status=QueueItemStatus.QUEUED
            )
            queue_items.append(item)
        
        db_session.add_all(queue_items)
        db_session.commit()
        
        # Calculate priorities for all orders
        for order in orders:
            priority_service.calculate_order_priority(order.id, sample_queue.id)
        
        # Rebalance queue
        result = priority_service.rebalance_queue(sample_queue.id)
        
        assert result["rebalanced"] is True
        assert result["items_reordered"] > 0
        
        # Verify new order: urgent should be first, VIP second, regular last
        db_session.expire_all()
        reordered_items = db_session.query(QueueItem).filter(
            QueueItem.queue_id == sample_queue.id
        ).order_by(QueueItem.sequence_number).all()
        
        # The exact order depends on calculated priorities, but VIP and urgent should be ahead of regular
        regular_position = next(i for i, item in enumerate(reordered_items) if item.order_id == regular_order.id)
        vip_position = next(i for i, item in enumerate(reordered_items) if item.order_id == vip_order.id)
        urgent_position = next(i for i, item in enumerate(reordered_items) if item.order_id == urgent_order.id)
        
        assert vip_position < regular_position  # VIP should be ahead of regular
        assert urgent_position < regular_position  # Urgent should be ahead of regular


class TestPriorityMetrics:
    """Test priority metrics and analytics"""
    
    def test_fairness_index_calculation(self, priority_service):
        """Test fairness index calculation"""
        # Perfect fairness - all wait times equal
        equal_times = [10, 10, 10, 10, 10]
        fairness = priority_service._calculate_fairness_index(equal_times)
        assert fairness > 0.99  # Should be close to 1
        
        # Poor fairness - very unequal wait times
        unequal_times = [5, 5, 5, 50, 50]
        unfairness = priority_service._calculate_fairness_index(unequal_times)
        assert unfairness < 0.7  # Should be lower
        
        # No data
        no_times = []
        no_fairness = priority_service._calculate_fairness_index(no_times)
        assert no_fairness == 1.0  # Default to perfect fairness


class TestEdgeCases:
    """Test edge cases and error handling"""
    
    def test_missing_order(self, db_session, priority_service, sample_queue):
        """Test priority calculation for non-existent order"""
        with pytest.raises(ValueError, match="Order .* not found"):
            priority_service.calculate_order_priority(
                order_id=99999,
                queue_id=sample_queue.id
            )
    
    def test_missing_queue(self, db_session, priority_service):
        """Test priority calculation for non-existent queue"""
        order = Order(staff_id=1, status="pending")
        db_session.add(order)
        db_session.commit()
        
        with pytest.raises(ValueError, match="Queue .* not found"):
            priority_service.calculate_order_priority(
                order_id=order.id,
                queue_id=99999
            )
    
    def test_no_priority_profile(self, db_session, priority_service, sample_queue):
        """Test priority calculation without configured profile"""
        # Create order without any priority configuration
        order = Order(
            staff_id=1,
            status="pending",
            priority=OrderPriority.HIGH
        )
        db_session.add(order)
        db_session.commit()
        
        # Should use default scoring
        priority_score = priority_service.calculate_order_priority(
            order_id=order.id,
            queue_id=sample_queue.id
        )
        
        assert priority_score is not None
        assert priority_score.profile_used == "default"
        assert priority_score.total_score > 50  # High priority order should get bonus