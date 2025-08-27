# backend/tests/modules/insights/test_insights_routes.py

"""
Comprehensive tests for insights routes.
"""

import pytest
from fastapi.testclient import TestClient
from datetime import datetime, timedelta
from unittest.mock import Mock, patch, MagicMock

from main import app
from core.rbac_models import RBACUser as User
from modules.insights.models.insight_models import Insight, InsightRating
from core.database import get_db


@pytest.fixture
def client():
    """Test client for API requests"""
    return TestClient(app)


@pytest.fixture
def mock_db():
    """Mock database session"""
    db = Mock()
    return db


@pytest.fixture
def auth_headers():
    """Mock authentication headers"""
    return {"Authorization": "Bearer test-token"}


@pytest.fixture
def mock_current_user():
    """Mock authenticated user"""
    user = Mock(spec=User)
    user.id = 1
    user.email = "test@example.com"
    user.role = "admin"
    return user


@pytest.fixture
def sample_insight_response():
    """Sample insight response data"""
    return {
        "id": 1,
        "title": "Low Inventory Alert",
        "description": "Tomatoes are running low",
        "domain": "inventory",
        "severity": "high",
        "is_actionable": True,
        "impact_score": 8.5,
        "impact_value": 250.00,
        "is_active": True,
        "is_acknowledged": False,
        "is_resolved": False,
        "created_at": datetime.utcnow().isoformat(),
        "updated_at": datetime.utcnow().isoformat()
    }


class TestInsightRoutes:
    """Test insight CRUD routes"""
    
    @patch('modules.insights.routes.insights_routes.get_current_user')
    @patch('modules.insights.routes.insights_routes.get_db')
    @patch('modules.insights.routes.insights_routes.InsightsService')
    def test_create_insight(self, mock_service_class, mock_get_db, mock_get_user, client, mock_db, mock_current_user, sample_insight_response):
        """Test POST /api/v1/insights/"""
        # Setup mocks
        mock_get_db.return_value = mock_db
        mock_get_user.return_value = mock_current_user
        
        mock_service = Mock()
        mock_service.create_insight.return_value = Mock(**sample_insight_response)
        mock_service_class.return_value = mock_service
        
        # Request data
        insight_data = {
            "title": "Low Inventory Alert",
            "description": "Tomatoes are running low",
            "domain": "inventory",
            "severity": "high",
            "is_actionable": True,
            "impact_score": 8.5,
            "source": "inventory_monitor"
        }
        
        # Make request
        response = client.post(
            "/api/v1/insights/",
            json=insight_data,
            headers=auth_headers
        )
        
        # Verify response
        assert response.status_code == 201
        assert response.json()["title"] == "Low Inventory Alert"
        mock_service.create_insight.assert_called_once()
    
    @patch('modules.insights.routes.insights_routes.get_current_user')
    @patch('modules.insights.routes.insights_routes.get_db')
    def test_get_insights_list(self, mock_get_db, mock_get_user, client, mock_db, mock_current_user):
        """Test GET /api/v1/insights/"""
        # Setup mocks
        mock_get_db.return_value = mock_db
        mock_get_user.return_value = mock_current_user
        
        # Mock query chain
        mock_query = Mock()
        mock_query.filter.return_value = mock_query
        mock_query.order_by.return_value = mock_query
        mock_query.offset.return_value = mock_query
        mock_query.limit.return_value = mock_query
        mock_query.all.return_value = [
            Mock(id=1, title="Insight 1", domain="sales"),
            Mock(id=2, title="Insight 2", domain="inventory")
        ]
        mock_query.count.return_value = 2
        
        mock_db.query.return_value = mock_query
        
        # Make request
        response = client.get(
            "/api/v1/insights/?domain=sales&severity=high",
            headers=auth_headers
        )
        
        # Verify response
        assert response.status_code == 200
        data = response.json()
        assert "items" in data
        assert "total" in data
        assert data["total"] == 2
    
    @patch('modules.insights.routes.insights_routes.get_current_user')
    @patch('modules.insights.routes.insights_routes.get_db')
    @patch('modules.insights.routes.insights_routes.InsightsService')
    def test_update_insight(self, mock_service_class, mock_get_db, mock_get_user, client, mock_db, mock_current_user):
        """Test PUT /api/v1/insights/{insight_id}"""
        # Setup mocks
        mock_get_db.return_value = mock_db
        mock_get_user.return_value = mock_current_user
        
        mock_service = Mock()
        updated_insight = Mock(id=1, title="Updated Title", severity="critical")
        mock_service.update_insight.return_value = updated_insight
        mock_service_class.return_value = mock_service
        
        # Update data
        update_data = {
            "title": "Updated Title",
            "severity": "critical"
        }
        
        # Make request
        response = client.put(
            "/api/v1/insights/1",
            json=update_data,
            headers=auth_headers
        )
        
        # Verify response
        assert response.status_code == 200
        mock_service.update_insight.assert_called_once_with(1, Mock())
    
    @patch('modules.insights.routes.insights_routes.get_current_user')
    @patch('modules.insights.routes.insights_routes.get_db')
    def test_delete_insight(self, mock_get_db, mock_get_user, client, mock_db, mock_current_user):
        """Test DELETE /api/v1/insights/{insight_id}"""
        # Setup mocks
        mock_get_db.return_value = mock_db
        mock_get_user.return_value = mock_current_user
        
        mock_insight = Mock(id=1)
        mock_db.query.return_value.filter.return_value.first.return_value = mock_insight
        
        # Make request
        response = client.delete("/api/v1/insights/1", headers=auth_headers)
        
        # Verify response
        assert response.status_code == 204
        assert mock_insight.is_active == False
        mock_db.commit.assert_called_once()


class TestBatchOperations:
    """Test batch operation routes"""
    
    @patch('modules.insights.routes.insights_routes.get_current_user')
    @patch('modules.insights.routes.insights_routes.get_db')
    @patch('modules.insights.routes.insights_routes.InsightsService')
    def test_batch_acknowledge(self, mock_service_class, mock_get_db, mock_get_user, client, mock_db, mock_current_user):
        """Test POST /api/v1/insights/batch/acknowledge"""
        # Setup mocks
        mock_get_db.return_value = mock_db
        mock_get_user.return_value = mock_current_user
        
        mock_service = Mock()
        mock_service.batch_update_insights.return_value = {"updated_count": 3}
        mock_service_class.return_value = mock_service
        
        # Request data
        batch_data = {"insight_ids": [1, 2, 3]}
        
        # Make request
        response = client.post(
            "/api/v1/insights/batch/acknowledge",
            json=batch_data,
            headers=auth_headers
        )
        
        # Verify response
        assert response.status_code == 200
        assert response.json()["updated_count"] == 3
    
    @patch('modules.insights.routes.insights_routes.get_current_user')
    @patch('modules.insights.routes.insights_routes.get_db')
    @patch('modules.insights.routes.insights_routes.InsightsService')
    def test_batch_dismiss(self, mock_service_class, mock_get_db, mock_get_user, client, mock_db, mock_current_user):
        """Test POST /api/v1/insights/batch/dismiss"""
        # Setup mocks
        mock_get_db.return_value = mock_db
        mock_get_user.return_value = mock_current_user
        
        mock_service = Mock()
        mock_service.batch_update_insights.return_value = {"updated_count": 2}
        mock_service_class.return_value = mock_service
        
        # Request data
        batch_data = {"insight_ids": [1, 2], "reason": "Not relevant"}
        
        # Make request
        response = client.post(
            "/api/v1/insights/batch/dismiss",
            json=batch_data,
            headers=auth_headers
        )
        
        # Verify response
        assert response.status_code == 200
        assert response.json()["updated_count"] == 2


class TestRatingRoutes:
    """Test rating-related routes"""
    
    @patch('modules.insights.routes.insights_routes.get_current_user')
    @patch('modules.insights.routes.insights_routes.get_db')
    @patch('modules.insights.routes.insights_routes.RatingService')
    def test_rate_insight(self, mock_rating_service_class, mock_get_db, mock_get_user, client, mock_db, mock_current_user):
        """Test POST /api/v1/insights/{insight_id}/rate"""
        # Setup mocks
        mock_get_db.return_value = mock_db
        mock_get_user.return_value = mock_current_user
        
        mock_service = Mock()
        mock_rating = Mock(id=1, rating=4, feedback="Helpful")
        mock_service.rate_insight.return_value = mock_rating
        mock_rating_service_class.return_value = mock_service
        
        # Rating data
        rating_data = {
            "rating": 4,
            "feedback": "Very helpful insight",
            "is_helpful": True
        }
        
        # Make request
        response = client.post(
            "/api/v1/insights/1/rate",
            json=rating_data,
            headers=auth_headers
        )
        
        # Verify response
        assert response.status_code == 200
        assert response.json()["rating"] == 4
    
    @patch('modules.insights.routes.insights_routes.get_current_user')
    @patch('modules.insights.routes.insights_routes.get_db')
    def test_get_insight_ratings(self, mock_get_db, mock_get_user, client, mock_db, mock_current_user):
        """Test GET /api/v1/insights/{insight_id}/ratings"""
        # Setup mocks
        mock_get_db.return_value = mock_db
        mock_get_user.return_value = mock_current_user
        
        # Mock ratings
        mock_ratings = [
            Mock(id=1, rating=5, user_id=1, created_at=datetime.utcnow()),
            Mock(id=2, rating=4, user_id=2, created_at=datetime.utcnow())
        ]
        
        mock_db.query.return_value.filter.return_value.order_by.return_value.all.return_value = mock_ratings
        
        # Make request
        response = client.get("/api/v1/insights/1/ratings", headers=auth_headers)
        
        # Verify response
        assert response.status_code == 200
        assert len(response.json()) == 2


class TestActionRoutes:
    """Test action-related routes"""
    
    @patch('modules.insights.routes.insights_routes.get_current_user')
    @patch('modules.insights.routes.insights_routes.get_db')
    @patch('modules.insights.routes.insights_routes.InsightsService')
    def test_mark_actioned(self, mock_service_class, mock_get_db, mock_get_user, client, mock_db, mock_current_user):
        """Test POST /api/v1/insights/{insight_id}/action"""
        # Setup mocks
        mock_get_db.return_value = mock_db
        mock_get_user.return_value = mock_current_user
        
        mock_service = Mock()
        mock_action = Mock(id=1, action_description="Fixed issue")
        mock_service.mark_insight_actioned.return_value = mock_action
        mock_service_class.return_value = mock_service
        
        # Action data
        action_data = {
            "action_description": "Created purchase order for tomatoes",
            "outcome": "success"
        }
        
        # Make request
        response = client.post(
            "/api/v1/insights/1/action",
            json=action_data,
            headers=auth_headers
        )
        
        # Verify response
        assert response.status_code == 200
        assert "action_id" in response.json()


class TestNotificationRoutes:
    """Test notification-related routes"""
    
    @patch('modules.insights.routes.insights_routes.get_current_user')
    @patch('modules.insights.routes.insights_routes.get_db')
    def test_create_notification_rule(self, mock_get_db, mock_get_user, client, mock_db, mock_current_user):
        """Test POST /api/v1/insights/notifications/rules"""
        # Setup mocks
        mock_get_db.return_value = mock_db
        mock_get_user.return_value = mock_current_user
        
        # Rule data
        rule_data = {
            "name": "Critical Alerts",
            "description": "Send email for critical insights",
            "conditions": {
                "severity": ["critical", "high"],
                "domains": ["inventory", "sales"]
            },
            "channels": ["email"],
            "recipients": ["manager@example.com"],
            "is_active": True
        }
        
        # Make request
        response = client.post(
            "/api/v1/insights/notifications/rules",
            json=rule_data,
            headers=auth_headers
        )
        
        # Verify response
        assert response.status_code == 201
        mock_db.add.assert_called_once()
        mock_db.commit.assert_called_once()


class TestAnalyticsRoutes:
    """Test analytics routes"""
    
    @patch('modules.insights.routes.insights_routes.get_current_user')
    @patch('modules.insights.routes.insights_routes.get_db')
    @patch('modules.insights.routes.insights_routes.InsightsService')
    def test_get_analytics(self, mock_service_class, mock_get_db, mock_get_user, client, mock_db, mock_current_user):
        """Test GET /api/v1/insights/analytics"""
        # Setup mocks
        mock_get_db.return_value = mock_db
        mock_get_user.return_value = mock_current_user
        
        mock_service = Mock()
        mock_analytics = {
            "summary": {
                "total_insights": 100,
                "active_insights": 80,
                "resolved_insights": 20
            },
            "insights_by_domain": {
                "sales": 30,
                "inventory": 25
            }
        }
        mock_service.get_analytics_summary.return_value = mock_analytics
        mock_service_class.return_value = mock_service
        
        # Make request
        response = client.get(
            "/api/v1/insights/analytics?days=30",
            headers=auth_headers
        )
        
        # Verify response
        assert response.status_code == 200
        data = response.json()
        assert data["summary"]["total_insights"] == 100
        assert "insights_by_domain" in data


class TestExportRoutes:
    """Test export routes"""
    
    @patch('modules.insights.routes.insights_routes.get_current_user')
    @patch('modules.insights.routes.insights_routes.get_db')
    @patch('modules.insights.routes.insights_routes.InsightsService')
    def test_export_csv(self, mock_service_class, mock_get_db, mock_get_user, client, mock_db, mock_current_user):
        """Test GET /api/v1/insights/export?format=csv"""
        # Setup mocks
        mock_get_db.return_value = mock_db
        mock_get_user.return_value = mock_current_user
        
        mock_service = Mock()
        csv_content = "id,title,domain,severity\n1,Test,sales,high"
        mock_service.export_insights.return_value = csv_content
        mock_service_class.return_value = mock_service
        
        # Make request
        response = client.get(
            "/api/v1/insights/export?format=csv",
            headers=auth_headers
        )
        
        # Verify response
        assert response.status_code == 200
        assert response.headers["content-type"] == "text/csv; charset=utf-8"
        assert "attachment" in response.headers["content-disposition"]
    
    @patch('modules.insights.routes.insights_routes.get_current_user')
    @patch('modules.insights.routes.insights_routes.get_db')
    @patch('modules.insights.routes.insights_routes.InsightsService')
    def test_export_json(self, mock_service_class, mock_get_db, mock_get_user, client, mock_db, mock_current_user):
        """Test GET /api/v1/insights/export?format=json"""
        # Setup mocks
        mock_get_db.return_value = mock_db
        mock_get_user.return_value = mock_current_user
        
        mock_service = Mock()
        json_content = '[{"id": 1, "title": "Test", "domain": "sales"}]'
        mock_service.export_insights.return_value = json_content
        mock_service_class.return_value = mock_service
        
        # Make request
        response = client.get(
            "/api/v1/insights/export?format=json",
            headers=auth_headers
        )
        
        # Verify response
        assert response.status_code == 200
        assert response.headers["content-type"] == "application/json"


class TestThreadRoutes:
    """Test thread-related routes"""
    
    @patch('modules.insights.routes.insights_routes.get_current_user')
    @patch('modules.insights.routes.insights_routes.get_db')
    @patch('modules.insights.routes.insights_routes.ThreadService')
    def test_create_thread(self, mock_thread_service_class, mock_get_db, mock_get_user, client, mock_db, mock_current_user):
        """Test POST /api/v1/insights/threads"""
        # Setup mocks
        mock_get_db.return_value = mock_db
        mock_get_user.return_value = mock_current_user
        
        mock_service = Mock()
        mock_thread = Mock(id=1, title="Sales Issues")
        mock_service.create_thread.return_value = mock_thread
        mock_thread_service_class.return_value = mock_service
        
        # Thread data
        thread_data = {
            "title": "Sales Issues",
            "description": "Thread for sales-related insights",
            "domain": "sales"
        }
        
        # Make request
        response = client.post(
            "/api/v1/insights/threads",
            json=thread_data,
            headers=auth_headers
        )
        
        # Verify response
        assert response.status_code == 201
        mock_service.create_thread.assert_called_once()


def test_insight_permissions():
    """Test that routes require proper permissions"""
    client = TestClient(app)
    
    # Test without auth header
    response = client.get("/api/v1/insights/")
    assert response.status_code == 401
    
    response = client.post("/api/v1/insights/", json={})
    assert response.status_code == 401
    
    response = client.delete("/api/v1/insights/1")
    assert response.status_code == 401


if __name__ == "__main__":
    pytest.main([__file__])