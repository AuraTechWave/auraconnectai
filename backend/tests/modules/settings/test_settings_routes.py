# backend/tests/modules/settings/test_settings_routes.py

"""
Comprehensive tests for settings routes.
"""

import pytest
from fastapi.testclient import TestClient
from datetime import datetime, timedelta
from unittest.mock import Mock, patch, MagicMock

from main import app
from modules.auth.models import User
from modules.settings.models.settings_models import Setting, FeatureFlag, APIKey, Webhook
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
    user.email = "admin@example.com"
    user.role = "admin"
    user.restaurant_id = 1
    return user


class TestSettingsRoutes:
    """Test settings CRUD routes"""
    
    @patch('modules.settings.routes.settings_routes.get_current_user')
    @patch('modules.settings.routes.settings_routes.get_db')
    @patch('modules.settings.routes.settings_routes.SettingsService')
    def test_create_setting(self, mock_service_class, mock_get_db, mock_get_user, client, mock_db, mock_current_user):
        """Test POST /api/v1/settings/"""
        # Setup mocks
        mock_get_db.return_value = mock_db
        mock_get_user.return_value = mock_current_user
        
        mock_service = Mock()
        mock_setting = Mock(
            id=1,
            key="restaurant.name",
            value="Test Restaurant",
            scope="restaurant",
            scope_id=1
        )
        mock_service.create_setting.return_value = mock_setting
        mock_service_class.return_value = mock_service
        
        # Request data
        setting_data = {
            "key": "restaurant.name",
            "value": "Test Restaurant",
            "scope": "restaurant",
            "scope_id": 1
        }
        
        # Make request
        response = client.post(
            "/api/v1/settings/",
            json=setting_data,
            headers=auth_headers
        )
        
        # Verify response
        assert response.status_code == 201
        assert response.json()["key"] == "restaurant.name"
        mock_service.create_setting.assert_called_once()
    
    @patch('modules.settings.routes.settings_routes.get_current_user')
    @patch('modules.settings.routes.settings_routes.get_db')
    @patch('modules.settings.routes.settings_routes.SettingsService')
    def test_get_setting(self, mock_service_class, mock_get_db, mock_get_user, client, mock_db, mock_current_user):
        """Test GET /api/v1/settings/{key}"""
        # Setup mocks
        mock_get_db.return_value = mock_db
        mock_get_user.return_value = mock_current_user
        
        mock_service = Mock()
        mock_setting = Mock(
            key="restaurant.name",
            value="Test Restaurant",
            value_type="string"
        )
        mock_service.get_setting.return_value = mock_setting
        mock_service_class.return_value = mock_service
        
        # Make request
        response = client.get(
            "/api/v1/settings/restaurant.name?scope=restaurant&scope_id=1",
            headers=auth_headers
        )
        
        # Verify response
        assert response.status_code == 200
        assert response.json()["key"] == "restaurant.name"
        assert response.json()["value"] == "Test Restaurant"
    
    @patch('modules.settings.routes.settings_routes.get_current_user')
    @patch('modules.settings.routes.settings_routes.get_db')
    @patch('modules.settings.routes.settings_routes.SettingsService')
    def test_get_effective_setting(self, mock_service_class, mock_get_db, mock_get_user, client, mock_db, mock_current_user):
        """Test GET /api/v1/settings/{key}/effective"""
        # Setup mocks
        mock_get_db.return_value = mock_db
        mock_get_user.return_value = mock_current_user
        
        mock_service = Mock()
        mock_setting = Mock(
            key="tax.rate",
            value="0.085",
            scope="restaurant"
        )
        mock_service.get_effective_setting.return_value = mock_setting
        mock_service_class.return_value = mock_service
        
        # Make request
        response = client.get(
            "/api/v1/settings/tax.rate/effective",
            headers=auth_headers
        )
        
        # Verify response
        assert response.status_code == 200
        assert response.json()["value"] == "0.085"
        assert response.json()["effective_scope"] == "restaurant"
    
    @patch('modules.settings.routes.settings_routes.get_current_user')
    @patch('modules.settings.routes.settings_routes.get_db')
    @patch('modules.settings.routes.settings_routes.SettingsService')
    def test_update_setting(self, mock_service_class, mock_get_db, mock_get_user, client, mock_db, mock_current_user):
        """Test PUT /api/v1/settings/{setting_id}"""
        # Setup mocks
        mock_get_db.return_value = mock_db
        mock_get_user.return_value = mock_current_user
        
        mock_service = Mock()
        mock_updated_setting = Mock(
            id=1,
            key="restaurant.name",
            value="Updated Restaurant"
        )
        mock_service.update_setting.return_value = mock_updated_setting
        mock_service_class.return_value = mock_service
        
        # Update data
        update_data = {"value": "Updated Restaurant"}
        
        # Make request
        response = client.put(
            "/api/v1/settings/1",
            json=update_data,
            headers=auth_headers
        )
        
        # Verify response
        assert response.status_code == 200
        assert response.json()["value"] == "Updated Restaurant"
    
    @patch('modules.settings.routes.settings_routes.get_current_user')
    @patch('modules.settings.routes.settings_routes.get_db')
    @patch('modules.settings.routes.settings_routes.SettingsService')
    def test_bulk_update_settings(self, mock_service_class, mock_get_db, mock_get_user, client, mock_db, mock_current_user):
        """Test POST /api/v1/settings/bulk"""
        # Setup mocks
        mock_get_db.return_value = mock_db
        mock_get_user.return_value = mock_current_user
        
        mock_service = Mock()
        mock_service.bulk_update_settings.return_value = {
            "updated": 2,
            "failed": 0
        }
        mock_service_class.return_value = mock_service
        
        # Bulk update data
        bulk_data = {
            "updates": [
                {"key": "restaurant.name", "value": "New Name"},
                {"key": "restaurant.address", "value": "123 Main St"}
            ],
            "scope": "restaurant",
            "scope_id": 1
        }
        
        # Make request
        response = client.post(
            "/api/v1/settings/bulk",
            json=bulk_data,
            headers=auth_headers
        )
        
        # Verify response
        assert response.status_code == 200
        assert response.json()["updated"] == 2


class TestFeatureFlagRoutes:
    """Test feature flag routes"""
    
    @patch('modules.settings.routes.settings_routes.get_current_user')
    @patch('modules.settings.routes.settings_routes.get_db')
    @patch('modules.settings.routes.settings_routes.SettingsService')
    def test_create_feature_flag(self, mock_service_class, mock_get_db, mock_get_user, client, mock_db, mock_current_user):
        """Test POST /api/v1/settings/features/"""
        # Setup mocks
        mock_get_db.return_value = mock_db
        mock_get_user.return_value = mock_current_user
        
        mock_service = Mock()
        mock_flag = Mock(
            id=1,
            key="new_feature",
            name="New Feature",
            is_enabled=False
        )
        mock_service.create_feature_flag.return_value = mock_flag
        mock_service_class.return_value = mock_service
        
        # Request data
        flag_data = {
            "key": "new_feature",
            "name": "New Feature",
            "description": "Test feature",
            "is_enabled": False
        }
        
        # Make request
        response = client.post(
            "/api/v1/settings/features/",
            json=flag_data,
            headers=auth_headers
        )
        
        # Verify response
        assert response.status_code == 201
        assert response.json()["key"] == "new_feature"
    
    @patch('modules.settings.routes.settings_routes.get_current_user')
    @patch('modules.settings.routes.settings_routes.get_db')
    def test_list_feature_flags(self, mock_get_db, mock_get_user, client, mock_db, mock_current_user):
        """Test GET /api/v1/settings/features/"""
        # Setup mocks
        mock_get_db.return_value = mock_db
        mock_get_user.return_value = mock_current_user
        
        # Mock feature flags
        mock_flags = [
            Mock(id=1, key="feature1", name="Feature 1", is_enabled=True),
            Mock(id=2, key="feature2", name="Feature 2", is_enabled=False)
        ]
        
        mock_db.query.return_value.filter.return_value.all.return_value = mock_flags
        
        # Make request
        response = client.get("/api/v1/settings/features/", headers=auth_headers)
        
        # Verify response
        assert response.status_code == 200
        assert len(response.json()) == 2
    
    @patch('modules.settings.routes.settings_routes.get_current_user')
    @patch('modules.settings.routes.settings_routes.get_db')
    @patch('modules.settings.routes.settings_routes.SettingsService')
    def test_evaluate_feature_flag(self, mock_service_class, mock_get_db, mock_get_user, client, mock_db, mock_current_user):
        """Test GET /api/v1/settings/features/{key}/evaluate"""
        # Setup mocks
        mock_get_db.return_value = mock_db
        mock_get_user.return_value = mock_current_user
        
        mock_service = Mock()
        mock_service.evaluate_feature_flag.return_value = True
        mock_service_class.return_value = mock_service
        
        # Make request
        response = client.get(
            "/api/v1/settings/features/new_feature/evaluate",
            headers=auth_headers
        )
        
        # Verify response
        assert response.status_code == 200
        assert response.json()["enabled"] == True
    
    @patch('modules.settings.routes.settings_routes.get_current_user')
    @patch('modules.settings.routes.settings_routes.get_db')
    @patch('modules.settings.routes.settings_routes.SettingsService')
    def test_toggle_feature_flag(self, mock_service_class, mock_get_db, mock_get_user, client, mock_db, mock_current_user):
        """Test PUT /api/v1/settings/features/{key}/toggle"""
        # Setup mocks
        mock_get_db.return_value = mock_db
        mock_get_user.return_value = mock_current_user
        
        mock_service = Mock()
        mock_flag = Mock(key="feature1", is_enabled=True)
        mock_service.toggle_feature_flag.return_value = mock_flag
        mock_service_class.return_value = mock_service
        
        # Make request
        response = client.put(
            "/api/v1/settings/features/feature1/toggle",
            json={"enabled": True},
            headers=auth_headers
        )
        
        # Verify response
        assert response.status_code == 200
        assert response.json()["is_enabled"] == True


class TestAPIKeyRoutes:
    """Test API key routes"""
    
    @patch('modules.settings.routes.settings_routes.get_current_user')
    @patch('modules.settings.routes.settings_routes.get_db')
    @patch('modules.settings.routes.settings_routes.SettingsService')
    def test_generate_api_key(self, mock_service_class, mock_get_db, mock_get_user, client, mock_db, mock_current_user):
        """Test POST /api/v1/settings/api-keys/"""
        # Setup mocks
        mock_get_db.return_value = mock_db
        mock_get_user.return_value = mock_current_user
        
        mock_service = Mock()
        mock_service.generate_api_key.return_value = {
            "id": 1,
            "key": "ak_test123456",
            "name": "Test Key"
        }
        mock_service_class.return_value = mock_service
        
        # Request data
        key_data = {
            "name": "Test Key",
            "description": "For testing",
            "scopes": ["read:all"],
            "expires_in_days": 90
        }
        
        # Make request
        response = client.post(
            "/api/v1/settings/api-keys/",
            json=key_data,
            headers=auth_headers
        )
        
        # Verify response
        assert response.status_code == 201
        assert response.json()["key"].startswith("ak_")
    
    @patch('modules.settings.routes.settings_routes.get_current_user')
    @patch('modules.settings.routes.settings_routes.get_db')
    def test_list_api_keys(self, mock_get_db, mock_get_user, client, mock_db, mock_current_user):
        """Test GET /api/v1/settings/api-keys/"""
        # Setup mocks
        mock_get_db.return_value = mock_db
        mock_get_user.return_value = mock_current_user
        
        # Mock API keys
        mock_keys = [
            Mock(
                id=1,
                name="Key 1",
                is_active=True,
                created_at=datetime.utcnow(),
                last_used_at=None
            ),
            Mock(
                id=2,
                name="Key 2",
                is_active=False,
                created_at=datetime.utcnow(),
                last_used_at=datetime.utcnow()
            )
        ]
        
        mock_db.query.return_value.filter.return_value.order_by.return_value.all.return_value = mock_keys
        
        # Make request
        response = client.get("/api/v1/settings/api-keys/", headers=auth_headers)
        
        # Verify response
        assert response.status_code == 200
        assert len(response.json()) == 2
    
    @patch('modules.settings.routes.settings_routes.get_current_user')
    @patch('modules.settings.routes.settings_routes.get_db')
    @patch('modules.settings.routes.settings_routes.SettingsService')
    def test_revoke_api_key(self, mock_service_class, mock_get_db, mock_get_user, client, mock_db, mock_current_user):
        """Test DELETE /api/v1/settings/api-keys/{key_id}"""
        # Setup mocks
        mock_get_db.return_value = mock_db
        mock_get_user.return_value = mock_current_user
        
        mock_service = Mock()
        mock_key = Mock(id=1, is_active=False)
        mock_service.revoke_api_key.return_value = mock_key
        mock_service_class.return_value = mock_service
        
        # Make request
        response = client.delete("/api/v1/settings/api-keys/1", headers=auth_headers)
        
        # Verify response
        assert response.status_code == 200
        assert response.json()["message"] == "API key revoked successfully"


class TestWebhookRoutes:
    """Test webhook routes"""
    
    @patch('modules.settings.routes.settings_routes.get_current_user')
    @patch('modules.settings.routes.settings_routes.get_db')
    @patch('modules.settings.routes.settings_routes.SettingsService')
    def test_create_webhook(self, mock_service_class, mock_get_db, mock_get_user, client, mock_db, mock_current_user):
        """Test POST /api/v1/settings/webhooks/"""
        # Setup mocks
        mock_get_db.return_value = mock_db
        mock_get_user.return_value = mock_current_user
        
        mock_service = Mock()
        mock_webhook = Mock(
            id=1,
            name="Order Webhook",
            url="https://example.com/webhook",
            events=["order.created"]
        )
        mock_service.create_webhook.return_value = mock_webhook
        mock_service_class.return_value = mock_service
        
        # Request data
        webhook_data = {
            "name": "Order Webhook",
            "url": "https://example.com/webhook",
            "events": ["order.created", "order.updated"],
            "is_active": True
        }
        
        # Make request
        response = client.post(
            "/api/v1/settings/webhooks/",
            json=webhook_data,
            headers=auth_headers
        )
        
        # Verify response
        assert response.status_code == 201
        assert response.json()["name"] == "Order Webhook"
    
    @patch('modules.settings.routes.settings_routes.get_current_user')
    @patch('modules.settings.routes.settings_routes.get_db')
    @patch('modules.settings.routes.settings_routes.SettingsService')
    def test_test_webhook(self, mock_service_class, mock_get_db, mock_get_user, client, mock_db, mock_current_user):
        """Test POST /api/v1/settings/webhooks/{webhook_id}/test"""
        # Setup mocks
        mock_get_db.return_value = mock_db
        mock_get_user.return_value = mock_current_user
        
        mock_service = Mock()
        mock_service.test_webhook.return_value = {
            "success": True,
            "status_code": 200,
            "response_time": 0.5,
            "error": None
        }
        mock_service_class.return_value = mock_service
        
        # Make request
        response = client.post(
            "/api/v1/settings/webhooks/1/test",
            headers=auth_headers
        )
        
        # Verify response
        assert response.status_code == 200
        assert response.json()["success"] == True
        assert response.json()["status_code"] == 200
    
    @patch('modules.settings.routes.settings_routes.get_current_user')
    @patch('modules.settings.routes.settings_routes.get_db')
    @patch('modules.settings.routes.settings_routes.SettingsService')
    def test_rotate_webhook_secret(self, mock_service_class, mock_get_db, mock_get_user, client, mock_db, mock_current_user):
        """Test POST /api/v1/settings/webhooks/{webhook_id}/rotate-secret"""
        # Setup mocks
        mock_get_db.return_value = mock_db
        mock_get_user.return_value = mock_current_user
        
        mock_service = Mock()
        mock_webhook = Mock(id=1, secret="new_secret_123")
        mock_service.rotate_webhook_secret.return_value = mock_webhook
        mock_service_class.return_value = mock_service
        
        # Make request
        response = client.post(
            "/api/v1/settings/webhooks/1/rotate-secret",
            headers=auth_headers
        )
        
        # Verify response
        assert response.status_code == 200
        assert response.json()["message"] == "Webhook secret rotated successfully"
        assert "new_secret" in response.json()


class TestConfigurationTemplateRoutes:
    """Test configuration template routes"""
    
    @patch('modules.settings.routes.settings_routes.get_current_user')
    @patch('modules.settings.routes.settings_routes.get_db')
    def test_list_configuration_templates(self, mock_get_db, mock_get_user, client, mock_db, mock_current_user):
        """Test GET /api/v1/settings/templates/"""
        # Setup mocks
        mock_get_db.return_value = mock_db
        mock_get_user.return_value = mock_current_user
        
        # Mock templates
        mock_templates = [
            Mock(id=1, name="Restaurant Defaults", category="restaurant"),
            Mock(id=2, name="POS Settings", category="integration")
        ]
        
        mock_db.query.return_value.filter.return_value.all.return_value = mock_templates
        
        # Make request
        response = client.get("/api/v1/settings/templates/", headers=auth_headers)
        
        # Verify response
        assert response.status_code == 200
        assert len(response.json()) == 2
    
    @patch('modules.settings.routes.settings_routes.get_current_user')
    @patch('modules.settings.routes.settings_routes.get_db')
    @patch('modules.settings.routes.settings_routes.SettingsService')
    def test_apply_configuration_template(self, mock_service_class, mock_get_db, mock_get_user, client, mock_db, mock_current_user):
        """Test POST /api/v1/settings/templates/{template_id}/apply"""
        # Setup mocks
        mock_get_db.return_value = mock_db
        mock_get_user.return_value = mock_current_user
        
        mock_service = Mock()
        mock_service.apply_configuration_template.return_value = {
            "applied_settings": 5,
            "failed_settings": 0
        }
        mock_service_class.return_value = mock_service
        
        # Apply data
        apply_data = {
            "scope": "restaurant",
            "scope_id": 1,
            "override_existing": False
        }
        
        # Make request
        response = client.post(
            "/api/v1/settings/templates/1/apply",
            json=apply_data,
            headers=auth_headers
        )
        
        # Verify response
        assert response.status_code == 200
        assert response.json()["applied_settings"] == 5


class TestSettingHistoryRoutes:
    """Test setting history routes"""
    
    @patch('modules.settings.routes.settings_routes.get_current_user')
    @patch('modules.settings.routes.settings_routes.get_db')
    def test_get_setting_history(self, mock_get_db, mock_get_user, client, mock_db, mock_current_user):
        """Test GET /api/v1/settings/{setting_id}/history"""
        # Setup mocks
        mock_get_db.return_value = mock_db
        mock_get_user.return_value = mock_current_user
        
        # Mock history entries
        mock_history = [
            Mock(
                id=1,
                old_value="Old Value",
                new_value="New Value",
                changed_at=datetime.utcnow(),
                changed_by=1
            ),
            Mock(
                id=2,
                old_value="Original Value",
                new_value="Old Value",
                changed_at=datetime.utcnow() - timedelta(days=1),
                changed_by=1
            )
        ]
        
        mock_db.query.return_value.filter.return_value.order_by.return_value.limit.return_value.all.return_value = mock_history
        
        # Make request
        response = client.get("/api/v1/settings/1/history", headers=auth_headers)
        
        # Verify response
        assert response.status_code == 200
        assert len(response.json()) == 2


def test_settings_permissions():
    """Test that routes require proper permissions"""
    client = TestClient(app)
    
    # Test without auth header
    response = client.get("/api/v1/settings/test.key")
    assert response.status_code == 401
    
    response = client.post("/api/v1/settings/", json={})
    assert response.status_code == 401
    
    response = client.delete("/api/v1/settings/api-keys/1")
    assert response.status_code == 401


if __name__ == "__main__":
    pytest.main([__file__])