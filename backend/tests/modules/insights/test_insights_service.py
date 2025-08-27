# backend/tests/modules/insights/test_insights_service.py

"""
Comprehensive tests for insights service.
"""

import pytest
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from unittest.mock import Mock, patch, MagicMock

from modules.insights.services.insights_service import InsightsService
from modules.insights.models.insight_models import (
    Insight, InsightRating, InsightAction, InsightThread
)
from modules.insights.schemas.insights_schemas import (
    InsightCreate, InsightUpdate, InsightBatchUpdate, RatingCreate
)
from core.rbac_models import RBACUser as User
from core.error_handling import NotFoundError, APIValidationError


@pytest.fixture
def db_session():
    """Mock database session"""
    session = Mock(spec=Session)
    session.query = Mock()
    session.add = Mock()
    session.commit = Mock()
    session.refresh = Mock()
    session.flush = Mock()
    return session


@pytest.fixture
def insights_service(db_session):
    """Create InsightsService instance with mocked dependencies"""
    return InsightsService(db_session)


@pytest.fixture
def sample_insight():
    """Sample insight for testing"""
    return Insight(
        id=1,
        title="Low Inventory Alert",
        description="Tomatoes are running low",
        domain="inventory",
        severity="high",
        is_actionable=True,
        impact_score=8.5,
        impact_value=250.00,
        estimated_savings=50.00,
        source="inventory_monitor",
        is_active=True,
        created_at=datetime.utcnow()
    )


@pytest.fixture
def sample_user():
    """Sample user for testing"""
    user = Mock(spec=User)
    user.id = 1
    user.email = "test@example.com"
    user.full_name = "Test User"
    return user


class TestInsightCreation:
    """Tests for insight creation"""
    
    def test_create_insight_success(self, insights_service, db_session):
        """Test successful insight creation"""
        insight_data = InsightCreate(
            title="Test Insight",
            description="Test description",
            domain="sales",
            severity="medium",
            is_actionable=True,
            impact_score=5.0,
            source="test"
        )
        
        # Mock the query for existing insights
        db_session.query.return_value.filter.return_value.first.return_value = None
        
        # Create insight
        result = insights_service.create_insight(insight_data)
        
        # Verify database operations
        db_session.add.assert_called_once()
        db_session.commit.assert_called_once()
        
        # Verify insight properties
        assert result.title == "Test Insight"
        assert result.domain == "sales"
        assert result.severity == "medium"
    
    def test_create_insight_with_duplicate_detection(self, insights_service, db_session, sample_insight):
        """Test duplicate insight detection"""
        insight_data = InsightCreate(
            title="Low Inventory Alert",
            description="Tomatoes are running low",
            domain="inventory",
            severity="high",
            source="test"
        )
        
        # Mock existing similar insight
        db_session.query.return_value.filter.return_value.first.return_value = sample_insight
        
        # Create should update existing instead
        result = insights_service.create_insight(insight_data)
        
        # Should not add new insight
        db_session.add.assert_not_called()
        
        # Should update existing
        assert sample_insight.is_active == True
        assert sample_insight.impact_score == 8.5
    
    def test_create_insight_with_auto_threading(self, insights_service, db_session):
        """Test automatic thread assignment"""
        insight_data = InsightCreate(
            title="Sales Drop",
            description="Sales decreased by 20%",
            domain="sales",
            severity="high",
            source="test"
        )
        
        # Mock no existing insight
        db_session.query.return_value.filter.return_value.first.return_value = None
        
        # Mock related thread search
        thread_mock = Mock(spec=InsightThread)
        thread_mock.id = 1
        
        # Configure thread query
        thread_query = Mock()
        thread_query.filter.return_value.first.return_value = thread_mock
        
        # Setup query routing
        def query_side_effect(model):
            if model == InsightThread:
                return thread_query
            return Mock()
        
        db_session.query.side_effect = query_side_effect
        
        result = insights_service.create_insight(insight_data)
        
        # Should assign to thread
        assert result.thread_id == 1


class TestInsightUpdate:
    """Tests for insight updates"""
    
    def test_update_insight_success(self, insights_service, db_session, sample_insight):
        """Test successful insight update"""
        update_data = InsightUpdate(
            title="Updated Title",
            severity="critical",
            is_resolved=True
        )
        
        # Mock query
        db_session.query.return_value.filter.return_value.first.return_value = sample_insight
        
        result = insights_service.update_insight(1, update_data)
        
        # Verify updates
        assert result.title == "Updated Title"
        assert result.severity == "critical"
        assert result.is_resolved == True
        db_session.commit.assert_called_once()
    
    def test_update_insight_not_found(self, insights_service, db_session):
        """Test update non-existent insight"""
        update_data = InsightUpdate(title="Updated")
        
        # Mock query returns None
        db_session.query.return_value.filter.return_value.first.return_value = None
        
        with pytest.raises(NotFoundError):
            insights_service.update_insight(999, update_data)
    
    def test_batch_update_insights(self, insights_service, db_session, sample_insight):
        """Test batch update operations"""
        batch_update = InsightBatchUpdate(
            insight_ids=[1, 2, 3],
            is_acknowledged=True,
            acknowledged_by=1
        )
        
        # Mock insights
        insights = [sample_insight, Mock(spec=Insight), Mock(spec=Insight)]
        db_session.query.return_value.filter.return_value.all.return_value = insights
        
        result = insights_service.batch_update_insights(batch_update)
        
        # Verify all insights updated
        assert result["updated_count"] == 3
        for insight in insights:
            assert insight.is_acknowledged == True


class TestInsightRating:
    """Tests for insight rating functionality"""
    
    def test_rate_insight_success(self, insights_service, db_session, sample_insight, sample_user):
        """Test successful insight rating"""
        rating_data = RatingCreate(
            rating=4,
            feedback="Very helpful",
            is_helpful=True
        )
        
        # Mock queries
        db_session.query.return_value.filter.return_value.first.side_effect = [
            sample_insight,  # First call for insight
            None  # Second call for existing rating
        ]
        
        result = insights_service.rate_insight(1, rating_data, sample_user)
        
        # Verify rating created
        db_session.add.assert_called_once()
        assert isinstance(result, InsightRating)
        assert result.rating == 4
    
    def test_rate_insight_update_existing(self, insights_service, db_session, sample_insight, sample_user):
        """Test updating existing rating"""
        rating_data = RatingCreate(rating=5, is_helpful=True)
        
        existing_rating = Mock(spec=InsightRating)
        existing_rating.rating = 3
        
        # Mock queries
        db_session.query.return_value.filter.return_value.first.side_effect = [
            sample_insight,  # First call for insight
            existing_rating  # Second call for existing rating
        ]
        
        result = insights_service.rate_insight(1, rating_data, sample_user)
        
        # Should update existing
        assert existing_rating.rating == 5
        db_session.add.assert_not_called()


class TestInsightActions:
    """Tests for insight actions"""
    
    def test_mark_insight_actioned(self, insights_service, db_session, sample_insight, sample_user):
        """Test marking insight as actioned"""
        db_session.query.return_value.filter.return_value.first.return_value = sample_insight
        
        result = insights_service.mark_insight_actioned(
            1, "Created purchase order", sample_user
        )
        
        # Verify action created
        db_session.add.assert_called_once()
        assert sample_insight.action_taken_at is not None
        
        # Verify action object
        action_call = db_session.add.call_args[0][0]
        assert isinstance(action_call, InsightAction)
        assert action_call.action_description == "Created purchase order"


class TestInsightAnalytics:
    """Tests for insight analytics"""
    
    def test_get_analytics_summary(self, insights_service, db_session):
        """Test analytics summary generation"""
        # Mock various counts
        mock_counts = {
            'total': 100,
            'active': 80,
            'acknowledged': 60,
            'resolved': 40,
            'actioned': 30
        }
        
        # Configure query mocks
        query_mock = Mock()
        query_mock.count.side_effect = list(mock_counts.values())
        query_mock.filter.return_value = query_mock
        
        db_session.query.return_value = query_mock
        
        # Mock domain distribution
        domain_data = [
            ('sales', 30),
            ('inventory', 25),
            ('staff', 20),
            ('customer', 15),
            ('operations', 10)
        ]
        query_mock.group_by.return_value.all.return_value = domain_data
        
        result = insights_service.get_analytics_summary()
        
        # Verify summary
        assert result['summary']['total_insights'] == 100
        assert result['summary']['active_insights'] == 80
        assert len(result['insights_by_domain']) == 5
    
    def test_get_insights_export_csv(self, insights_service, db_session):
        """Test CSV export functionality"""
        # Mock insights
        insights = [
            Mock(
                id=1,
                title="Test 1",
                domain="sales",
                severity="high",
                created_at=datetime.utcnow(),
                is_acknowledged=False,
                is_resolved=False
            ),
            Mock(
                id=2,
                title="Test 2",
                domain="inventory",
                severity="medium",
                created_at=datetime.utcnow(),
                is_acknowledged=True,
                is_resolved=False
            )
        ]
        
        db_session.query.return_value.filter.return_value.all.return_value = insights
        
        result = insights_service.export_insights("csv", days=30)
        
        # Verify CSV content
        assert "id,title,domain,severity" in result
        assert "Test 1" in result
        assert "Test 2" in result


class TestNotificationService:
    """Tests for notification service"""
    
    @patch('modules.insights.services.notification_service.smtplib.SMTP')
    def test_send_email_notification(self, mock_smtp, db_session):
        """Test email notification sending"""
        from modules.insights.services.notification_service import NotificationService
        
        service = NotificationService(db_session)
        
        # Configure SMTP mock
        smtp_instance = MagicMock()
        mock_smtp.return_value.__enter__.return_value = smtp_instance
        
        result = service.send_email(
            "test@example.com",
            "Test Subject",
            "Test Body"
        )
        
        # Verify email sent
        assert result == True
        smtp_instance.send_message.assert_called_once()
    
    @patch('modules.insights.services.notification_service.requests.post')
    def test_send_slack_notification(self, mock_post, db_session):
        """Test Slack notification sending"""
        from modules.insights.services.notification_service import NotificationService
        
        service = NotificationService(db_session)
        
        # Configure response
        mock_response = Mock()
        mock_response.ok = True
        mock_post.return_value = mock_response
        
        result = service.send_slack(
            "https://hooks.slack.com/test",
            "Test notification"
        )
        
        # Verify request made
        assert result == True
        mock_post.assert_called_once()


class TestThreadService:
    """Tests for thread management service"""
    
    def test_create_thread(self, db_session):
        """Test thread creation"""
        from modules.insights.services.thread_service import ThreadService
        
        service = ThreadService(db_session)
        
        result = service.create_thread(
            "Sales Issues",
            "Thread for sales-related insights",
            "sales"
        )
        
        # Verify thread created
        db_session.add.assert_called_once()
        assert result.title == "Sales Issues"
        assert result.domain == "sales"
    
    def test_add_insight_to_thread(self, db_session, sample_insight):
        """Test adding insight to thread"""
        from modules.insights.services.thread_service import ThreadService
        
        service = ThreadService(db_session)
        
        # Mock thread
        thread = Mock(spec=InsightThread)
        thread.id = 1
        thread.insights = []
        
        db_session.query.return_value.filter.return_value.first.return_value = thread
        
        service.add_insight_to_thread(1, sample_insight)
        
        # Verify insight added
        assert sample_insight.thread_id == 1
        db_session.commit.assert_called_once()


@pytest.fixture
def mock_settings():
    """Mock settings for testing"""
    return {
        "SMTP_HOST": "smtp.test.com",
        "SMTP_PORT": 587,
        "SMTP_USER": "test@example.com",
        "SMTP_PASSWORD": "password",
        "SLACK_WEBHOOK_URL": "https://hooks.slack.com/test"
    }


def test_insight_severity_validation():
    """Test insight severity validation"""
    # Valid severities
    for severity in ["critical", "high", "medium", "low", "info"]:
        insight = InsightCreate(
            title="Test",
            description="Test",
            domain="sales",
            severity=severity,
            source="test"
        )
        assert insight.severity == severity
    
    # Invalid severity should raise validation error
    with pytest.raises(ValueError):
        InsightCreate(
            title="Test",
            description="Test",
            domain="sales",
            severity="invalid",
            source="test"
        )


def test_insight_domain_validation():
    """Test insight domain validation"""
    # Valid domains
    valid_domains = ["sales", "inventory", "staff", "customer", "operations", "finance", "marketing"]
    
    for domain in valid_domains:
        insight = InsightCreate(
            title="Test",
            description="Test",
            domain=domain,
            severity="medium",
            source="test"
        )
        assert insight.domain == domain


if __name__ == "__main__":
    pytest.main([__file__])