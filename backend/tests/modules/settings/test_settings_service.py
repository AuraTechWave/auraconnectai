# backend/tests/modules/settings/test_settings_service.py

"""
Comprehensive tests for settings service.
"""

import pytest
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from unittest.mock import Mock, patch, MagicMock
from cryptography.fernet import Fernet

from modules.settings.services.settings_service import SettingsService
from modules.settings.models.settings_models import (
    Setting, SettingDefinition, FeatureFlag, APIKey, Webhook
)
from modules.settings.schemas.settings_schemas import (
    SettingCreate, SettingUpdate, FeatureFlagCreate, APIKeyCreate,
    WebhookCreate, SettingsBulkUpdate
)
from core.error_handling import NotFoundError, APIValidationError, ConflictError


@pytest.fixture
def db_session():
    """Mock database session"""
    session = Mock(spec=Session)
    session.query = Mock()
    session.add = Mock()
    session.commit = Mock()
    session.refresh = Mock()
    session.flush = Mock()
    session.bulk_insert_mappings = Mock()
    return session


@pytest.fixture
def settings_service(db_session):
    """Create SettingsService instance"""
    return SettingsService(db_session)


@pytest.fixture
def sample_setting():
    """Sample setting for testing"""
    return Setting(
        id=1,
        key="restaurant.name",
        value="Test Restaurant",
        value_type="string",
        scope="restaurant",
        scope_id=1,
        is_sensitive=False,
        created_at=datetime.utcnow()
    )


@pytest.fixture
def sample_setting_definition():
    """Sample setting definition"""
    return SettingDefinition(
        id=1,
        key="restaurant.name",
        display_name="Restaurant Name",
        description="Name of the restaurant",
        value_type="string",
        default_value="My Restaurant",
        is_required=True,
        validation_rules={"min_length": 1, "max_length": 100}
    )


@pytest.fixture
def sample_feature_flag():
    """Sample feature flag"""
    return FeatureFlag(
        id=1,
        key="new_checkout",
        name="New Checkout Flow",
        description="Enable new checkout experience",
        is_enabled=True,
        rollout_percentage=50,
        target_users=[],
        target_groups=["beta_testers"]
    )


class TestSettingManagement:
    """Tests for setting CRUD operations"""
    
    def test_create_setting_success(self, settings_service, db_session, sample_setting_definition):
        """Test successful setting creation"""
        setting_data = SettingCreate(
            key="restaurant.name",
            value="My Restaurant",
            scope="restaurant",
            scope_id=1
        )
        
        # Mock definition lookup
        db_session.query.return_value.filter.return_value.first.return_value = sample_setting_definition
        
        # Create setting
        result = settings_service.create_setting(setting_data)
        
        # Verify
        db_session.add.assert_called_once()
        db_session.commit.assert_called_once()
        assert result.key == "restaurant.name"
        assert result.value == "My Restaurant"
    
    def test_create_setting_invalid_key(self, settings_service, db_session):
        """Test creating setting with invalid key"""
        setting_data = SettingCreate(
            key="invalid.key",
            value="test",
            scope="system"
        )
        
        # Mock no definition found
        db_session.query.return_value.filter.return_value.first.return_value = None
        
        with pytest.raises(APIValidationError) as exc_info:
            settings_service.create_setting(setting_data)
        
        assert "Invalid setting key" in str(exc_info.value)
    
    def test_create_sensitive_setting_encryption(self, settings_service, db_session, sample_setting_definition):
        """Test sensitive setting encryption"""
        # Mark definition as sensitive
        sample_setting_definition.is_sensitive = True
        
        setting_data = SettingCreate(
            key="smtp.password",
            value="secret123",
            scope="system"
        )
        
        # Mock definition lookup
        db_session.query.return_value.filter.return_value.first.return_value = sample_setting_definition
        
        # Create setting
        result = settings_service.create_setting(setting_data)
        
        # Verify encryption
        assert result.value != "secret123"  # Should be encrypted
        assert result.is_sensitive == True
        
        # Verify can decrypt
        decrypted = settings_service._decrypt_value(result.value)
        assert decrypted == "secret123"
    
    def test_get_setting_by_key(self, settings_service, db_session, sample_setting):
        """Test retrieving setting by key"""
        # Mock query
        db_session.query.return_value.filter.return_value.order_by.return_value.first.return_value = sample_setting
        
        result = settings_service.get_setting("restaurant.name", scope="restaurant", scope_id=1)
        
        assert result == sample_setting
    
    def test_get_setting_decrypt_sensitive(self, settings_service, db_session):
        """Test decrypting sensitive setting on retrieval"""
        # Create encrypted setting
        encrypted_value = settings_service._encrypt_value("secret123")
        sensitive_setting = Setting(
            key="api.key",
            value=encrypted_value,
            is_sensitive=True
        )
        
        # Mock query
        db_session.query.return_value.filter.return_value.order_by.return_value.first.return_value = sensitive_setting
        
        result = settings_service.get_setting("api.key", decrypt=True)
        
        # Should decrypt value
        assert result.value == "secret123"
    
    def test_update_setting(self, settings_service, db_session, sample_setting):
        """Test updating setting"""
        update_data = SettingUpdate(value="Updated Restaurant")
        
        # Mock query
        db_session.query.return_value.filter.return_value.first.return_value = sample_setting
        
        result = settings_service.update_setting(1, update_data)
        
        assert result.value == "Updated Restaurant"
        db_session.commit.assert_called_once()
    
    def test_bulk_update_settings(self, settings_service, db_session):
        """Test bulk settings update"""
        updates = SettingsBulkUpdate(
            updates=[
                {"key": "restaurant.name", "value": "New Name"},
                {"key": "restaurant.address", "value": "123 Main St"}
            ],
            scope="restaurant",
            scope_id=1
        )
        
        # Mock settings
        setting1 = Mock(key="restaurant.name")
        setting2 = Mock(key="restaurant.address")
        
        db_session.query.return_value.filter.return_value.all.return_value = [setting1, setting2]
        
        result = settings_service.bulk_update_settings(updates)
        
        assert result["updated"] == 2
        assert setting1.value == "New Name"
        assert setting2.value == "123 Main St"


class TestSettingScopes:
    """Tests for multi-scope settings"""
    
    def test_get_settings_by_scope(self, settings_service, db_session):
        """Test retrieving all settings for a scope"""
        # Mock settings
        settings = [
            Mock(key="setting1", value="value1"),
            Mock(key="setting2", value="value2")
        ]
        
        db_session.query.return_value.filter.return_value.all.return_value = settings
        
        result = settings_service.get_settings_by_scope("restaurant", 1)
        
        assert len(result) == 2
    
    def test_get_effective_setting_hierarchy(self, settings_service, db_session):
        """Test setting hierarchy resolution"""
        # Mock settings at different scopes
        system_setting = Mock(key="tax.rate", value="0.08", scope="system")
        restaurant_setting = Mock(key="tax.rate", value="0.085", scope="restaurant")
        
        def query_side_effect(*args):
            mock = Mock()
            mock.filter.return_value.order_by.return_value.first.side_effect = [
                None,  # No user-level setting
                None,  # No location-level setting
                restaurant_setting,  # Restaurant-level setting exists
                system_setting  # System-level setting
            ]
            return mock
        
        db_session.query.side_effect = query_side_effect
        
        # Get effective setting
        result = settings_service.get_effective_setting(
            "tax.rate",
            user_id=1,
            location_id=1,
            restaurant_id=1
        )
        
        # Should return restaurant-level setting (more specific)
        assert result == restaurant_setting


class TestFeatureFlags:
    """Tests for feature flag management"""
    
    def test_create_feature_flag(self, settings_service, db_session):
        """Test creating feature flag"""
        flag_data = FeatureFlagCreate(
            key="new_feature",
            name="New Feature",
            description="Test feature",
            is_enabled=False
        )
        
        # Mock no existing flag
        db_session.query.return_value.filter.return_value.first.return_value = None
        
        result = settings_service.create_feature_flag(flag_data)
        
        db_session.add.assert_called_once()
        assert result.key == "new_feature"
        assert result.is_enabled == False
    
    def test_evaluate_feature_flag_enabled(self, settings_service, db_session, sample_feature_flag):
        """Test feature flag evaluation - enabled"""
        # Mock flag lookup
        db_session.query.return_value.filter.return_value.first.return_value = sample_feature_flag
        
        # Test basic evaluation
        assert settings_service.evaluate_feature_flag("new_checkout") == True
    
    def test_evaluate_feature_flag_rollout_percentage(self, settings_service, db_session):
        """Test feature flag with rollout percentage"""
        flag = FeatureFlag(
            key="gradual_rollout",
            is_enabled=True,
            rollout_percentage=50
        )
        
        db_session.query.return_value.filter.return_value.first.return_value = flag
        
        # Test multiple evaluations
        results = []
        for i in range(100):
            result = settings_service.evaluate_feature_flag("gradual_rollout", user_id=i)
            results.append(result)
        
        # Should be roughly 50% true
        true_count = sum(results)
        assert 30 <= true_count <= 70  # Allow some variance
    
    def test_evaluate_feature_flag_target_users(self, settings_service, db_session):
        """Test feature flag with target users"""
        flag = FeatureFlag(
            key="beta_feature",
            is_enabled=True,
            rollout_percentage=0,  # Only for target users
            target_users=[1, 2, 3]
        )
        
        db_session.query.return_value.filter.return_value.first.return_value = flag
        
        # Target user should get access
        assert settings_service.evaluate_feature_flag("beta_feature", user_id=1) == True
        
        # Non-target user should not
        assert settings_service.evaluate_feature_flag("beta_feature", user_id=99) == False
    
    def test_toggle_feature_flag(self, settings_service, db_session, sample_feature_flag):
        """Test toggling feature flag"""
        # Mock flag lookup
        db_session.query.return_value.filter.return_value.first.return_value = sample_feature_flag
        
        # Initially enabled
        assert sample_feature_flag.is_enabled == True
        
        # Toggle off
        result = settings_service.toggle_feature_flag("new_checkout", False)
        
        assert result.is_enabled == False
        db_session.commit.assert_called_once()


class TestAPIKeyManagement:
    """Tests for API key management"""
    
    def test_generate_api_key(self, settings_service, db_session):
        """Test API key generation"""
        key_data = APIKeyCreate(
            name="Test API Key",
            description="For testing",
            scopes=["read:insights", "write:insights"]
        )
        
        result = settings_service.generate_api_key(key_data, user_id=1)
        
        # Verify key format
        assert result["key"].startswith("ak_")
        assert len(result["key"]) > 20
        
        # Verify database operations
        db_session.add.assert_called_once()
        
        # Verify hashing
        api_key_obj = db_session.add.call_args[0][0]
        assert api_key_obj.key_hash != result["key"]
    
    def test_validate_api_key_valid(self, settings_service, db_session):
        """Test validating valid API key"""
        # Generate a key first
        raw_key = "ak_test123456"
        key_hash = settings_service._hash_api_key(raw_key)
        
        api_key = APIKey(
            id=1,
            key_hash=key_hash,
            is_active=True,
            expires_at=datetime.utcnow() + timedelta(days=30),
            scopes=["read:all"]
        )
        
        # Mock lookup
        db_session.query.return_value.filter.return_value.first.return_value = api_key
        
        result = settings_service.validate_api_key(raw_key)
        
        assert result == api_key
        assert api_key.last_used_at is not None
    
    def test_validate_api_key_expired(self, settings_service, db_session):
        """Test validating expired API key"""
        raw_key = "ak_expired123"
        key_hash = settings_service._hash_api_key(raw_key)
        
        api_key = APIKey(
            key_hash=key_hash,
            is_active=True,
            expires_at=datetime.utcnow() - timedelta(days=1)  # Expired
        )
        
        db_session.query.return_value.filter.return_value.first.return_value = api_key
        
        result = settings_service.validate_api_key(raw_key)
        
        assert result is None
    
    def test_revoke_api_key(self, settings_service, db_session):
        """Test revoking API key"""
        api_key = APIKey(id=1, is_active=True)
        
        db_session.query.return_value.filter.return_value.first.return_value = api_key
        
        result = settings_service.revoke_api_key(1)
        
        assert result.is_active == False
        assert result.revoked_at is not None
        db_session.commit.assert_called_once()


class TestWebhookManagement:
    """Tests for webhook management"""
    
    def test_create_webhook(self, settings_service, db_session):
        """Test creating webhook"""
        webhook_data = WebhookCreate(
            name="Order Webhook",
            url="https://example.com/webhook",
            events=["order.created", "order.updated"],
            is_active=True
        )
        
        result = settings_service.create_webhook(webhook_data)
        
        db_session.add.assert_called_once()
        assert result.name == "Order Webhook"
        assert len(result.secret) > 0  # Should generate secret
    
    @patch('requests.post')
    def test_test_webhook(self, mock_post, settings_service, db_session):
        """Test webhook testing"""
        webhook = Webhook(
            id=1,
            url="https://example.com/webhook",
            secret="test_secret"
        )
        
        db_session.query.return_value.filter.return_value.first.return_value = webhook
        
        # Mock successful response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.elapsed.total_seconds.return_value = 0.5
        mock_post.return_value = mock_response
        
        result = settings_service.test_webhook(1)
        
        assert result["success"] == True
        assert result["status_code"] == 200
        assert result["response_time"] == 0.5
    
    def test_rotate_webhook_secret(self, settings_service, db_session):
        """Test rotating webhook secret"""
        webhook = Webhook(
            id=1,
            secret="old_secret"
        )
        
        db_session.query.return_value.filter.return_value.first.return_value = webhook
        
        old_secret = webhook.secret
        result = settings_service.rotate_webhook_secret(1)
        
        assert result.secret != old_secret
        assert len(result.secret) > 0
        db_session.commit.assert_called_once()


class TestConfigurationTemplates:
    """Tests for configuration templates"""
    
    def test_apply_configuration_template(self, settings_service, db_session):
        """Test applying configuration template"""
        template = Mock(
            settings={
                "restaurant.timezone": "America/New_York",
                "restaurant.currency": "USD",
                "pos.integration": "square"
            }
        )
        
        db_session.query.return_value.filter.return_value.first.return_value = template
        
        # Mock existing settings check
        db_session.query.return_value.filter.return_value.all.return_value = []
        
        result = settings_service.apply_configuration_template(
            1,
            scope="restaurant",
            scope_id=1
        )
        
        assert result["applied_settings"] == 3
        assert db_session.bulk_insert_mappings.called


class TestSettingValidation:
    """Tests for setting validation"""
    
    def test_validate_setting_type_string(self, settings_service):
        """Test string type validation"""
        definition = SettingDefinition(
            value_type="string",
            validation_rules={"min_length": 3, "max_length": 10}
        )
        
        # Valid
        assert settings_service._validate_setting_value("hello", definition) == True
        
        # Too short
        with pytest.raises(APIValidationError):
            settings_service._validate_setting_value("hi", definition)
        
        # Too long
        with pytest.raises(APIValidationError):
            settings_service._validate_setting_value("this is too long", definition)
    
    def test_validate_setting_type_integer(self, settings_service):
        """Test integer type validation"""
        definition = SettingDefinition(
            value_type="integer",
            validation_rules={"min": 0, "max": 100}
        )
        
        # Valid
        assert settings_service._validate_setting_value("50", definition) == True
        
        # Out of range
        with pytest.raises(APIValidationError):
            settings_service._validate_setting_value("150", definition)
        
        # Not a number
        with pytest.raises(APIValidationError):
            settings_service._validate_setting_value("abc", definition)
    
    def test_validate_setting_type_boolean(self, settings_service):
        """Test boolean type validation"""
        definition = SettingDefinition(value_type="boolean")
        
        # Valid values
        assert settings_service._validate_setting_value("true", definition) == True
        assert settings_service._validate_setting_value("false", definition) == True
        assert settings_service._validate_setting_value("1", definition) == True
        assert settings_service._validate_setting_value("0", definition) == True
        
        # Invalid
        with pytest.raises(APIValidationError):
            settings_service._validate_setting_value("maybe", definition)
    
    def test_validate_setting_type_json(self, settings_service):
        """Test JSON type validation"""
        definition = SettingDefinition(
            value_type="json",
            validation_rules={"required_fields": ["host", "port"]}
        )
        
        # Valid
        valid_json = '{"host": "localhost", "port": 5432}'
        assert settings_service._validate_setting_value(valid_json, definition) == True
        
        # Missing required field
        with pytest.raises(APIValidationError):
            settings_service._validate_setting_value('{"host": "localhost"}', definition)
        
        # Invalid JSON
        with pytest.raises(APIValidationError):
            settings_service._validate_setting_value('not json', definition)


if __name__ == "__main__":
    pytest.main([__file__])