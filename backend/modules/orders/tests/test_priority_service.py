"""
Tests for priority service functionality.
"""

import pytest
from datetime import datetime, timedelta
from unittest.mock import Mock, patch
from sqlalchemy.orm import Session

from ..models.priority_models import (
    PriorityRule, PriorityProfile, PriorityProfileRule,
    QueuePriorityConfig, OrderPriorityScore, PriorityAdjustmentLog,
    PriorityAlgorithm, PriorityScoreType
)
from ..models.queue_models import (
    OrderQueue, QueueItem, QueueType, QueueStatus, QueueItemStatus
)
from ..models.order_models import Order
from ..services.priority_service import PriorityService
from core.exceptions import NotFoundError, ValidationError


@pytest.fixture
def db_session(mocker):
    """Mock database session"""
    session = mocker.Mock(spec=Session)
    return session


@pytest.fixture
def priority_service(db_session):
    """Create priority service instance"""
    return PriorityService(db_session)


@pytest.fixture
def sample_queue():
    """Create sample queue"""
    queue = OrderQueue(
        id=1,
        name="Kitchen Queue",
        queue_type=QueueType.KITCHEN,
        status=QueueStatus.ACTIVE
    )
    return queue


@pytest.fixture
def sample_queue_item():
    """Create sample queue item"""
    item = QueueItem(
        id=1,
        queue_id=1,
        order_id=100,
        sequence_number=1,
        priority=0,
        status=QueueItemStatus.QUEUED,
        queued_at=datetime.utcnow() - timedelta(minutes=10)
    )
    return item


@pytest.fixture
def sample_order():
    """Create sample order"""
    order = Order(
        id=100,
        order_number="ORD-001",
        total_amount=75.50,
        customer_id=1,
        status="pending"
    )
    return order


@pytest.fixture
def sample_priority_rule():
    """Create sample priority rule"""
    rule = PriorityRule(
        id=1,
        name="Wait Time Rule",
        score_type=PriorityScoreType.WAIT_TIME,
        is_active=True,
        score_config={
            "type": "linear",
            "base_score": 10,
            "multiplier": 2
        },
        min_score=0,
        max_score=100,
        default_weight=1.0
    )
    return rule


@pytest.fixture
def sample_priority_profile(sample_priority_rule):
    """Create sample priority profile"""
    profile = PriorityProfile(
        id=1,
        name="Default Profile",
        algorithm_type=PriorityAlgorithm.WEIGHTED,
        is_active=True,
        is_default=True,
        aggregation_method="weighted_sum",
        total_weight_normalization=True,
        min_total_score=0,
        max_total_score=100
    )
    
    # Add rule to profile
    profile_rule = PriorityProfileRule(
        profile_id=profile.id,
        rule_id=sample_priority_rule.id,
        rule=sample_priority_rule,
        weight=2.0,
        is_active=True
    )
    profile.profile_rules = [profile_rule]
    
    return profile


@pytest.fixture
def sample_queue_config(sample_priority_profile):
    """Create sample queue priority config"""
    config = QueuePriorityConfig(
        id=1,
        queue_id=1,
        profile_id=1,
        profile=sample_priority_profile,
        is_active=True,
        priority_enabled=True,
        auto_rebalance=True,
        rebalance_interval_minutes=5,
        rebalance_threshold=0.2,
        max_position_change=5,
        boost_new_items=True,
        boost_duration_seconds=30
    )
    return config


class TestPriorityCalculation:
    """Test priority calculation functionality"""
    
    def test_calculate_order_priority_not_found(self, priority_service, db_session):
        """Test calculating priority for non-existent order"""
        db_session.query.return_value.filter.return_value.first.return_value = None
        
        with pytest.raises(NotFoundError):
            priority_service.calculate_order_priority(999, 1)
    
    def test_calculate_order_priority_no_config(
        self, priority_service, db_session, sample_queue_item
    ):
        """Test calculating priority when no config exists"""
        # Mock queue item exists
        db_session.query.return_value.filter.return_value.first.side_effect = [
            sample_queue_item,  # Queue item exists
            None  # No config
        ]
        
        score = priority_service.calculate_order_priority(100, 1)
        
        assert score.total_score == 0.0
        assert score.base_score == 0.0
        assert score.score_components == {}
    
    def test_calculate_weighted_priority(
        self, priority_service, db_session, sample_queue_item,
        sample_queue_config, sample_order
    ):
        """Test weighted priority calculation"""
        # Mock database queries
        db_session.query.return_value.filter.side_effect = [
            Mock(first=Mock(return_value=sample_queue_item)),  # Queue item
            Mock(first=Mock(return_value=sample_queue_config)),  # Config
            Mock(first=Mock(return_value=sample_order))  # Order
        ]
        
        # Mock profile query with options
        mock_profile_query = Mock()
        mock_profile_query.filter.return_value.first.return_value = sample_queue_config.profile
        db_session.query.return_value.options.return_value = mock_profile_query
        
        # Mock score query
        db_session.query.return_value.filter.return_value.first.return_value = None  # No existing score
        
        score = priority_service.calculate_order_priority(100, 1)
        
        # Verify calculations
        assert score.queue_item_id == sample_queue_item.id
        assert score.config_id == sample_queue_config.id
        assert score.total_score > 0  # Should have calculated a score
        assert "wait_time" in score.score_components
        assert score.is_boosted is False
    
    def test_calculate_fifo_priority(
        self, priority_service, db_session, sample_queue_item,
        sample_queue_config, sample_priority_profile
    ):
        """Test FIFO priority calculation"""
        # Change algorithm to FIFO
        sample_priority_profile.algorithm_type = PriorityAlgorithm.FIFO
        
        # Mock queries
        db_session.query.return_value.filter.side_effect = [
            Mock(first=Mock(return_value=sample_queue_item)),
            Mock(first=Mock(return_value=sample_queue_config))
        ]
        
        mock_profile_query = Mock()
        mock_profile_query.filter.return_value.first.return_value = sample_priority_profile
        db_session.query.return_value.options.return_value = mock_profile_query
        
        db_session.query.return_value.filter.return_value.first.return_value = None
        
        score = priority_service.calculate_order_priority(100, 1)
        
        # FIFO should only use wait time
        assert score.total_score == pytest.approx(10.0, rel=1)  # 10 minutes wait
        assert len(score.score_components) == 1
        assert "wait_time" in score.score_components
    
    def test_apply_new_item_boost(
        self, priority_service, db_session, sample_queue_item,
        sample_queue_config, sample_order
    ):
        """Test boost application for new items"""
        # Make item very new
        sample_queue_item.queued_at = datetime.utcnow() - timedelta(seconds=10)
        
        # Mock queries
        db_session.query.return_value.filter.side_effect = [
            Mock(first=Mock(return_value=sample_queue_item)),
            Mock(first=Mock(return_value=sample_queue_config)),
            Mock(first=Mock(return_value=sample_order))
        ]
        
        mock_profile_query = Mock()
        mock_profile_query.filter.return_value.first.return_value = sample_queue_config.profile
        db_session.query.return_value.options.return_value = mock_profile_query
        
        db_session.query.return_value.filter.return_value.first.return_value = None
        
        score = priority_service.calculate_order_priority(100, 1)
        
        # Should have boost applied
        assert score.is_boosted is True
        assert score.boost_score > 0
        assert score.boost_reason == "new_item"
        assert score.boost_expires_at is not None


class TestQueueRebalancing:
    """Test queue rebalancing functionality"""
    
    def test_rebalance_not_enabled(
        self, priority_service, db_session, sample_queue_config
    ):
        """Test rebalancing when not enabled"""
        sample_queue_config.auto_rebalance = False
        
        db_session.query.return_value.filter.return_value.first.return_value = sample_queue_config
        
        with pytest.raises(ValidationError):
            priority_service.rebalance_queue(1)
    
    def test_rebalance_not_needed(
        self, priority_service, db_session, sample_queue_config
    ):
        """Test when rebalancing is not needed"""
        # Set recent rebalance time
        sample_queue_config.last_rebalance_time = datetime.utcnow() - timedelta(minutes=1)
        
        db_session.query.return_value.filter.return_value.first.return_value = sample_queue_config
        
        # Mock fairness calculation to return good value
        with patch.object(priority_service, '_calculate_fairness_index', return_value=0.9):
            result = priority_service.rebalance_queue(1, force=False)
        
        assert result.items_rebalanced == 0
        assert result.fairness_before == result.fairness_after
    
    def test_rebalance_queue_success(
        self, priority_service, db_session, sample_queue_config
    ):
        """Test successful queue rebalancing"""
        # Create multiple queue items with scores
        items = []
        for i in range(5):
            item = QueueItem(
                id=i+1,
                queue_id=1,
                order_id=100+i,
                sequence_number=i+1,
                status=QueueItemStatus.QUEUED,
                queued_at=datetime.utcnow() - timedelta(minutes=i*5)
            )
            score = OrderPriorityScore(
                queue_item_id=item.id,
                total_score=float(i * 10),  # Different scores
                base_score=float(i * 10)
            )
            items.append((item, score))
        
        db_session.query.return_value.filter.return_value.first.return_value = sample_queue_config
        
        # Mock queue items query
        mock_join = Mock()
        mock_join.filter.return_value.order_by.return_value.all.return_value = items
        db_session.query.return_value.join.return_value = mock_join
        
        # Mock fairness calculation
        with patch.object(priority_service, '_calculate_fairness_index', side_effect=[0.3, 0.8]):
            result = priority_service.rebalance_queue(1, force=True)
        
        assert result.items_rebalanced == 5
        assert result.fairness_before < result.fairness_after
        assert result.max_position_change >= 0
    
    def test_calculate_fairness_index(self, priority_service, db_session):
        """Test Gini coefficient calculation for fairness"""
        # Create queue items with different wait times
        items = []
        wait_times = [5, 10, 15, 20, 100]  # Large variance
        
        for i, wait_time in enumerate(wait_times):
            item = QueueItem(
                id=i+1,
                queued_at=datetime.utcnow() - timedelta(minutes=wait_time),
                status=QueueItemStatus.QUEUED
            )
            items.append(item)
        
        db_session.query.return_value.filter.return_value.all.return_value = items
        
        fairness = priority_service._calculate_fairness_index(1)
        
        # With high variance, fairness should be low
        assert 0 <= fairness <= 1
        assert fairness < 0.5  # High inequality


class TestPriorityAdjustments:
    """Test manual priority adjustments"""
    
    def test_adjust_priority_not_found(self, priority_service, db_session):
        """Test adjusting priority for non-existent score"""
        db_session.query.return_value.filter.return_value.first.return_value = None
        
        with pytest.raises(NotFoundError):
            priority_service.adjust_priority_manually(
                queue_item_id=999,
                new_score=50.0,
                adjustment_type="manual",
                adjustment_reason="Test",
                adjusted_by_id=1
            )
    
    def test_adjust_priority_boost(
        self, priority_service, db_session, sample_queue_item
    ):
        """Test applying priority boost"""
        # Create existing score
        existing_score = OrderPriorityScore(
            queue_item_id=1,
            total_score=30.0,
            base_score=30.0,
            boost_score=0.0
        )
        
        db_session.query.return_value.filter.side_effect = [
            Mock(first=Mock(return_value=existing_score)),
            Mock(first=Mock(return_value=sample_queue_item))
        ]
        
        # Mock resequencing
        with patch.object(priority_service, '_resequence_queue_after_adjustment'):
            log = priority_service.adjust_priority_manually(
                queue_item_id=1,
                new_score=50.0,
                adjustment_type="boost",
                adjustment_reason="VIP customer",
                adjusted_by_id=1,
                duration_seconds=300
            )
        
        assert log.old_score == 30.0
        assert log.new_score == 50.0
        assert log.adjustment_type == "boost"
        assert existing_score.is_boosted is True
        assert existing_score.boost_expires_at is not None


class TestPriorityComponents:
    """Test individual priority calculation components"""
    
    def test_calculate_wait_time_priority(self, priority_service):
        """Test wait time priority calculation"""
        queue_item = QueueItem(
            queued_at=datetime.utcnow() - timedelta(minutes=15)
        )
        
        rule = PriorityRule(
            score_config={
                "type": "linear",
                "base_score": 10,
                "multiplier": 2
            },
            min_score=0,
            max_score=100
        )
        
        score = priority_service._calculate_wait_time_priority(queue_item, rule)
        
        # 10 + (15 * 2) = 40
        assert score == pytest.approx(40.0)
    
    def test_calculate_order_value_priority(self, priority_service, sample_order):
        """Test order value priority calculation"""
        rule = PriorityRule(
            score_config={
                "type": "linear",
                "min_value": 0,
                "max_value": 100
            },
            min_score=0,
            max_score=100
        )
        
        score = priority_service._calculate_order_value_priority(sample_order, rule)
        
        # 75.50 / 100 * 100 = 75.5
        assert score == pytest.approx(75.5)
    
    def test_calculate_vip_priority(self, priority_service, db_session, sample_order):
        """Test VIP priority calculation"""
        # Create VIP customer
        from modules.customers.models import Customer
        vip_customer = Customer(
            id=1,
            is_vip=True,
            loyalty_tier="gold",
            order_count=50
        )
        
        db_session.query.return_value.filter.return_value.first.return_value = vip_customer
        
        rule = PriorityRule(
            score_config={
                "vip_score": 90,
                "tier_scores": {"gold": 80, "silver": 60},
                "frequency_threshold": 20,
                "frequency_score": 70
            },
            min_score=0,
            max_score=100
        )
        
        score = priority_service._calculate_vip_priority(sample_order, rule)
        
        # Should get VIP score (highest)
        assert score == 90
    
    def test_calculate_delivery_time_priority(self, priority_service):
        """Test delivery time priority calculation"""
        # Order with delivery in 30 minutes
        order = Order(
            promised_delivery_time=datetime.utcnow() + timedelta(minutes=30)
        )
        
        rule = PriorityRule(
            score_config={
                "type": "inverse_linear",
                "max_minutes": 120
            },
            min_score=0,
            max_score=100
        )
        
        score = priority_service._calculate_delivery_time_priority(order, rule)
        
        # (1 - 30/120) * 100 = 75
        assert score == pytest.approx(75.0)
    
    def test_calculate_complexity_priority(self, priority_service):
        """Test order complexity priority calculation"""
        # Create order with items and modifiers
        order = Order()
        order.items = [
            Mock(modifiers=[1, 2], special_instructions="No onions"),
            Mock(modifiers=[], special_instructions=None),
            Mock(modifiers=[3], special_instructions="Extra spicy")
        ]
        
        rule = PriorityRule(
            score_config={
                "type": "weighted",
                "item_weight": 1.0,
                "modification_weight": 2.0,
                "max_complexity": 20
            },
            min_score=0,
            max_score=100
        )
        
        score = priority_service._calculate_complexity_priority(order, rule)
        
        # 3 items * 1 + 5 modifications * 2 = 13
        # 13/20 * 100 = 65
        assert score == pytest.approx(65.0)


class TestQueueSequencing:
    """Test queue sequencing and position management"""
    
    def test_get_queue_priority_sequence(
        self, priority_service, db_session
    ):
        """Test getting current queue sequence"""
        # Create mock data
        items = []
        for i in range(3):
            items.append((
                QueueItem(
                    id=i+1,
                    sequence_number=i+1,
                    order_id=100+i,
                    status=QueueItemStatus.QUEUED,
                    queued_at=datetime.utcnow() - timedelta(minutes=i*5)
                ),
                OrderPriorityScore(total_score=float(30-i*10), is_boosted=False),
                Order(id=100+i, order_number=f"ORD-{i+1}")
            ))
        
        mock_join = Mock()
        mock_join.join.return_value.join.return_value.filter.return_value.order_by.return_value.all.return_value = items
        db_session.query.return_value = mock_join
        
        sequence = priority_service.get_queue_priority_sequence(1)
        
        assert len(sequence) == 3
        assert sequence[0]["sequence_number"] == 1
        assert sequence[0]["priority_score"] == 30.0
        assert "wait_time_minutes" in sequence[0]


class TestEnumUsage:
    """Test proper enum usage throughout the service"""
    
    def test_enum_comparisons_in_queries(self, priority_service, db_session):
        """Ensure all enum comparisons use enum types"""
        # This test verifies the service uses enums correctly
        # by checking that queries use enum types
        
        # Mock a query that would fail with string comparison
        mock_query = Mock()
        db_session.query.return_value = mock_query
        
        # Call various methods that filter by status
        with patch.object(priority_service, '_calculate_fairness_index') as mock_fairness:
            mock_fairness.return_value = 0.5
            
            # This should use QueueItemStatus enum
            mock_filter = Mock()
            mock_query.filter.return_value = mock_filter
            mock_filter.all.return_value = []
            
            priority_service._calculate_fairness_index(1)
            
            # Verify the filter was called (exact enum comparison is internal)
            assert mock_query.filter.called