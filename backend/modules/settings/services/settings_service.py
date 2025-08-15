# backend/modules/settings/services/settings_service.py

"""
Core service for settings and configuration management.
"""

from sqlalchemy.orm import Session, joinedload
from sqlalchemy import and_, or_
from typing import List, Optional, Dict, Any, Union, Tuple
from datetime import datetime
import json
import logging
import hashlib
import secrets
from cryptography.fernet import Fernet

from ..models.settings_models import (
    Setting,
    SettingDefinition,
    SettingGroup,
    ConfigurationTemplate,
    FeatureFlag,
    APIKey,
    Webhook,
    SettingHistory,
    SettingCategory,
    SettingType,
    SettingScope,
)
from ..schemas.settings_schemas import (
    SettingCreate,
    SettingUpdate,
    SettingFilters,
    FeatureFlagCreate,
    FeatureFlagUpdate,
    APIKeyCreate,
    WebhookCreate,
    WebhookUpdate,
    ConfigurationTemplateCreate,
)
from core.error_handling import NotFoundError, APIValidationError, ConflictError

logger = logging.getLogger(__name__)


class SettingsService:
    """Service for managing settings and configuration"""

    def __init__(self, db: Session):
        self.db = db
        # In production, this would come from environment
        self.encryption_key = Fernet.generate_key()
        self.fernet = Fernet(self.encryption_key)

    # ========== Settings CRUD ==========

    def create_setting(self, setting_data: SettingCreate, user_id: int) -> Setting:
        """Create a new setting"""
        # Get setting definition
        definition = self._get_setting_definition(setting_data.key)
        if not definition:
            raise NotFoundError("Setting definition", setting_data.key)

        # Validate value
        self._validate_setting_value(setting_data.value, definition)

        # Check if setting already exists
        existing = self._get_setting(
            setting_data.key,
            setting_data.scope,
            setting_data.restaurant_id,
            setting_data.location_id,
            setting_data.user_id,
        )

        if existing:
            raise ConflictError(
                "Setting already exists",
                {"key": setting_data.key, "scope": setting_data.scope},
            )

        # Serialize value
        value_str = self._serialize_value(setting_data.value, definition.value_type)

        # Encrypt if sensitive
        if definition.is_sensitive:
            value_str = self._encrypt_value(value_str)

        # Create setting
        setting = Setting(
            key=setting_data.key,
            category=definition.category,
            scope=setting_data.scope,
            restaurant_id=setting_data.restaurant_id,
            location_id=setting_data.location_id,
            user_id=setting_data.user_id,
            value=value_str,
            value_type=definition.value_type,
            label=definition.label,
            description=definition.description,
            is_sensitive=definition.is_sensitive,
            is_public=False,
            validation_rules=definition.validation_rules,
            allowed_values=definition.allowed_values,
            default_value=definition.default_value,
            ui_config=definition.ui_config,
            sort_order=definition.sort_order,
            modified_by_id=user_id,
        )

        self.db.add(setting)

        # Create history entry
        self._create_history_entry(setting, None, value_str, "create", user_id)

        self.db.commit()
        self.db.refresh(setting)

        return setting

    def get_setting(
        self,
        key: str,
        scope: SettingScope,
        restaurant_id: Optional[int] = None,
        location_id: Optional[int] = None,
        user_id: Optional[int] = None,
    ) -> Optional[Setting]:
        """Get a specific setting"""
        setting = self._get_setting(key, scope, restaurant_id, location_id, user_id)

        if setting and setting.is_sensitive:
            # Decrypt value for response
            setting.value = self._decrypt_value(setting.value)

        return setting

    def get_setting_value(
        self,
        key: str,
        scope: SettingScope,
        restaurant_id: Optional[int] = None,
        location_id: Optional[int] = None,
        user_id: Optional[int] = None,
        default: Any = None,
    ) -> Any:
        """Get setting value with fallback"""
        setting = self.get_setting(key, scope, restaurant_id, location_id, user_id)

        if not setting:
            # Try to get from higher scope
            if scope == SettingScope.USER and location_id:
                setting = self.get_setting(
                    key, SettingScope.LOCATION, restaurant_id, location_id
                )
            elif scope in [SettingScope.USER, SettingScope.LOCATION] and restaurant_id:
                setting = self.get_setting(key, SettingScope.RESTAURANT, restaurant_id)

            if not setting:
                setting = self.get_setting(key, SettingScope.SYSTEM)

        if setting:
            return self._deserialize_value(setting.value, setting.value_type)

        # Return default from definition or provided default
        definition = self._get_setting_definition(key)
        if definition and definition.default_value:
            return self._deserialize_value(
                definition.default_value, definition.value_type
            )

        return default

    def update_setting(
        self,
        key: str,
        scope: SettingScope,
        update_data: SettingUpdate,
        user_id: int,
        restaurant_id: Optional[int] = None,
        location_id: Optional[int] = None,
        setting_user_id: Optional[int] = None,
    ) -> Setting:
        """Update a setting"""
        setting = self._get_setting(
            key, scope, restaurant_id, location_id, setting_user_id
        )

        if not setting:
            raise NotFoundError("Setting", key)

        # Get definition for validation
        definition = self._get_setting_definition(key)

        # Store old value for history
        old_value = setting.value

        # Validate and serialize new value
        self._validate_setting_value(update_data.value, definition)
        new_value = self._serialize_value(update_data.value, setting.value_type)

        # Encrypt if sensitive
        if setting.is_sensitive:
            new_value = self._encrypt_value(new_value)

        # Update setting
        setting.value = new_value
        setting.modified_by_id = user_id
        setting.modified_at = datetime.utcnow()

        if update_data.description is not None:
            setting.description = update_data.description
        if update_data.validation_rules is not None:
            setting.validation_rules = update_data.validation_rules
        if update_data.ui_config is not None:
            setting.ui_config = update_data.ui_config

        # Create history entry
        self._create_history_entry(setting, old_value, new_value, "update", user_id)

        self.db.commit()
        self.db.refresh(setting)

        return setting

    def delete_setting(
        self,
        key: str,
        scope: SettingScope,
        user_id: int,
        restaurant_id: Optional[int] = None,
        location_id: Optional[int] = None,
        setting_user_id: Optional[int] = None,
    ) -> bool:
        """Delete a setting"""
        setting = self._get_setting(
            key, scope, restaurant_id, location_id, setting_user_id
        )

        if not setting:
            return False

        # Create history entry
        self._create_history_entry(setting, setting.value, None, "delete", user_id)

        self.db.delete(setting)
        self.db.commit()

        return True

    def list_settings(
        self, filters: SettingFilters, skip: int = 0, limit: int = 50
    ) -> Tuple[List[Setting], int]:
        """List settings with filters"""
        query = self.db.query(Setting)

        if filters.category:
            query = query.filter(Setting.category == filters.category)

        if filters.scope:
            query = query.filter(Setting.scope == filters.scope)

        if filters.restaurant_id is not None:
            query = query.filter(Setting.restaurant_id == filters.restaurant_id)

        if filters.location_id is not None:
            query = query.filter(Setting.location_id == filters.location_id)

        if filters.user_id is not None:
            query = query.filter(Setting.user_id == filters.user_id)

        if filters.is_sensitive is not None:
            query = query.filter(Setting.is_sensitive == filters.is_sensitive)

        if filters.search:
            search_term = f"%{filters.search}%"
            query = query.filter(
                or_(
                    Setting.key.ilike(search_term),
                    Setting.label.ilike(search_term),
                    Setting.description.ilike(search_term),
                )
            )

        # Get total count
        total = query.count()

        # Apply pagination
        settings = (
            query.order_by(Setting.category, Setting.sort_order, Setting.key)
            .offset(skip)
            .limit(limit)
            .all()
        )

        # Decrypt sensitive values
        for setting in settings:
            if setting.is_sensitive:
                setting.value = self._decrypt_value(setting.value)

        return settings, total

    def bulk_update_settings(
        self,
        updates: List[Dict[str, Any]],
        scope: SettingScope,
        user_id: int,
        restaurant_id: Optional[int] = None,
        location_id: Optional[int] = None,
    ) -> List[Setting]:
        """Update multiple settings at once"""
        updated_settings = []

        for update in updates:
            key = update.get("key")
            value = update.get("value")

            if not key or value is None:
                continue

            try:
                setting = self.update_setting(
                    key,
                    scope,
                    SettingUpdate(value=value),
                    user_id,
                    restaurant_id,
                    location_id,
                )
                updated_settings.append(setting)
            except NotFoundError:
                # Try to create if doesn't exist
                setting = self.create_setting(
                    SettingCreate(
                        key=key,
                        value=value,
                        scope=scope,
                        restaurant_id=restaurant_id,
                        location_id=location_id,
                    ),
                    user_id,
                )
                updated_settings.append(setting)
            except Exception as e:
                logger.error(f"Failed to update setting {key}: {e}")

        return updated_settings

    # ========== Configuration Templates ==========

    def create_template(
        self, template_data: ConfigurationTemplateCreate, user_id: int
    ) -> ConfigurationTemplate:
        """Create configuration template"""
        # Check for duplicate name
        existing = (
            self.db.query(ConfigurationTemplate)
            .filter(ConfigurationTemplate.name == template_data.name)
            .first()
        )

        if existing:
            raise ConflictError(
                "Template with this name already exists", {"name": template_data.name}
            )

        template = ConfigurationTemplate(
            name=template_data.name,
            label=template_data.label,
            description=template_data.description,
            category=template_data.category,
            settings=template_data.settings,
            scope=template_data.scope,
            created_by_id=user_id,
            tags=template_data.tags or [],
        )

        self.db.add(template)
        self.db.commit()
        self.db.refresh(template)

        return template

    def apply_template(
        self,
        template_id: int,
        scope: SettingScope,
        user_id: int,
        restaurant_id: Optional[int] = None,
        location_id: Optional[int] = None,
        override_existing: bool = False,
        settings_override: Optional[Dict[str, Any]] = None,
    ) -> List[Setting]:
        """Apply configuration template"""
        template = (
            self.db.query(ConfigurationTemplate)
            .filter(
                ConfigurationTemplate.id == template_id,
                ConfigurationTemplate.is_active == True,
            )
            .first()
        )

        if not template:
            raise NotFoundError("Configuration template", template_id)

        # Merge settings
        settings_to_apply = template.settings.copy()
        if settings_override:
            settings_to_apply.update(settings_override)

        applied_settings = []

        for key, value in settings_to_apply.items():
            existing = self._get_setting(key, scope, restaurant_id, location_id, None)

            if existing and not override_existing:
                continue

            try:
                if existing:
                    setting = self.update_setting(
                        key,
                        scope,
                        SettingUpdate(value=value),
                        user_id,
                        restaurant_id,
                        location_id,
                    )
                else:
                    setting = self.create_setting(
                        SettingCreate(
                            key=key,
                            value=value,
                            scope=scope,
                            restaurant_id=restaurant_id,
                            location_id=location_id,
                        ),
                        user_id,
                    )

                applied_settings.append(setting)
            except Exception as e:
                logger.error(f"Failed to apply setting {key} from template: {e}")

        # Update usage count
        template.usage_count += 1
        self.db.commit()

        return applied_settings

    # ========== Feature Flags ==========

    def create_feature_flag(
        self, flag_data: FeatureFlagCreate, user_id: int
    ) -> FeatureFlag:
        """Create feature flag"""
        # Check for duplicate key
        existing = (
            self.db.query(FeatureFlag).filter(FeatureFlag.key == flag_data.key).first()
        )

        if existing:
            raise ConflictError(
                "Feature flag with this key already exists", {"key": flag_data.key}
            )

        flag = FeatureFlag(
            key=flag_data.key,
            name=flag_data.name,
            description=flag_data.description,
            is_enabled=flag_data.is_enabled,
            rollout_percentage=flag_data.rollout_percentage,
            enabled_restaurants=flag_data.enabled_restaurants or [],
            enabled_users=flag_data.enabled_users or [],
            targeting_rules=flag_data.targeting_rules or {},
            enabled_from=flag_data.enabled_from,
            enabled_until=flag_data.enabled_until,
            depends_on=flag_data.depends_on or [],
            created_by_id=user_id,
            tags=flag_data.tags or [],
        )

        self.db.add(flag)
        self.db.commit()
        self.db.refresh(flag)

        return flag

    def is_feature_enabled(
        self,
        key: str,
        restaurant_id: Optional[int] = None,
        user_id: Optional[int] = None,
        context: Optional[Dict[str, Any]] = None,
    ) -> Tuple[bool, str]:
        """Check if feature is enabled for given context"""
        flag = self.db.query(FeatureFlag).filter(FeatureFlag.key == key).first()

        if not flag:
            return False, "Feature flag not found"

        # Check if globally disabled
        if not flag.is_enabled:
            return False, "Feature is globally disabled"

        # Check time constraints
        now = datetime.utcnow()
        if flag.enabled_from and now < flag.enabled_from:
            return False, "Feature not yet enabled"
        if flag.enabled_until and now > flag.enabled_until:
            return False, "Feature has expired"

        # Check dependencies
        for dep_key in flag.depends_on:
            dep_enabled, _ = self.is_feature_enabled(dep_key, restaurant_id, user_id)
            if not dep_enabled:
                return False, f"Dependency {dep_key} is not enabled"

        # Check explicit targeting
        if restaurant_id and restaurant_id in flag.enabled_restaurants:
            return True, "Restaurant is explicitly enabled"

        if user_id and user_id in flag.enabled_users:
            return True, "User is explicitly enabled"

        # Check rollout percentage
        if flag.rollout_percentage == 100:
            return True, "Feature is fully rolled out"
        elif flag.rollout_percentage == 0:
            return False, "Feature has 0% rollout"
        else:
            # Use consistent hashing for gradual rollout
            hash_input = f"{key}:{restaurant_id or 0}:{user_id or 0}"
            hash_value = int(hashlib.md5(hash_input.encode()).hexdigest(), 16)
            if (hash_value % 100) < flag.rollout_percentage:
                return True, f"Included in {flag.rollout_percentage}% rollout"
            else:
                return False, f"Not included in {flag.rollout_percentage}% rollout"

    # ========== API Keys ==========

    def create_api_key(
        self, key_data: APIKeyCreate, restaurant_id: int, user_id: int
    ) -> Tuple[APIKey, str]:
        """Create API key and return key model and actual key"""
        # Generate secure API key
        api_key = f"ak_{secrets.token_urlsafe(32)}"
        key_hash = hashlib.sha256(api_key.encode()).hexdigest()
        key_prefix = api_key[:10]

        key_model = APIKey(
            key_hash=key_hash,
            key_prefix=key_prefix,
            name=key_data.name,
            description=key_data.description,
            restaurant_id=restaurant_id,
            created_by_id=user_id,
            scopes=key_data.scopes,
            allowed_ips=key_data.allowed_ips or [],
            expires_at=key_data.expires_at,
            rate_limit_per_hour=key_data.rate_limit_per_hour,
            rate_limit_per_day=key_data.rate_limit_per_day,
        )

        self.db.add(key_model)
        self.db.commit()
        self.db.refresh(key_model)

        return key_model, api_key

    def validate_api_key(
        self,
        api_key: str,
        required_scope: Optional[str] = None,
        ip_address: Optional[str] = None,
    ) -> Optional[APIKey]:
        """Validate API key and check permissions"""
        # Hash the key
        key_hash = hashlib.sha256(api_key.encode()).hexdigest()

        # Find key by hash
        key_model = (
            self.db.query(APIKey)
            .filter(APIKey.key_hash == key_hash, APIKey.is_active == True)
            .first()
        )

        if not key_model:
            return None

        # Check expiration
        if key_model.expires_at and datetime.utcnow() > key_model.expires_at:
            return None

        # Check IP whitelist
        if key_model.allowed_ips and ip_address:
            if ip_address not in key_model.allowed_ips:
                return None

        # Check scope
        if required_scope and required_scope not in key_model.scopes:
            return None

        # Update usage stats
        key_model.last_used_at = datetime.utcnow()
        key_model.usage_count += 1
        self.db.commit()

        return key_model

    # ========== Helper Methods ==========

    def _get_setting(
        self,
        key: str,
        scope: SettingScope,
        restaurant_id: Optional[int],
        location_id: Optional[int],
        user_id: Optional[int],
    ) -> Optional[Setting]:
        """Get setting with exact scope match"""
        return (
            self.db.query(Setting)
            .filter(
                Setting.key == key,
                Setting.scope == scope,
                Setting.restaurant_id == restaurant_id,
                Setting.location_id == location_id,
                Setting.user_id == user_id,
            )
            .first()
        )

    def _get_setting_definition(self, key: str) -> Optional[SettingDefinition]:
        """Get setting definition"""
        return (
            self.db.query(SettingDefinition)
            .filter(SettingDefinition.key == key, SettingDefinition.is_active == True)
            .first()
        )

    def _validate_setting_value(self, value: Any, definition: SettingDefinition):
        """Validate setting value against definition"""
        # Type validation
        if definition.value_type == SettingType.INTEGER:
            if not isinstance(value, int):
                raise APIValidationError(f"Value must be an integer")
        elif definition.value_type == SettingType.FLOAT:
            if not isinstance(value, (int, float)):
                raise APIValidationError(f"Value must be a number")
        elif definition.value_type == SettingType.BOOLEAN:
            if not isinstance(value, bool):
                raise APIValidationError(f"Value must be a boolean")
        elif definition.value_type == SettingType.STRING:
            if not isinstance(value, str):
                raise APIValidationError(f"Value must be a string")

        # Allowed values validation
        if definition.allowed_values and value not in definition.allowed_values:
            raise APIValidationError(
                f"Value must be one of: {definition.allowed_values}"
            )

        # Custom validation rules
        if definition.validation_rules:
            # TODO: Implement custom validation logic
            pass

    def _serialize_value(self, value: Any, value_type: SettingType) -> str:
        """Serialize value to string for storage"""
        if value_type in [SettingType.JSON, SettingType.ENUM]:
            return json.dumps(value)
        else:
            return str(value)

    def _deserialize_value(self, value_str: str, value_type: SettingType) -> Any:
        """Deserialize value from storage"""
        if value_type == SettingType.INTEGER:
            return int(value_str)
        elif value_type == SettingType.FLOAT:
            return float(value_str)
        elif value_type == SettingType.BOOLEAN:
            return value_str.lower() in ["true", "1", "yes"]
        elif value_type == SettingType.JSON:
            return json.loads(value_str)
        elif value_type == SettingType.DATETIME:
            return datetime.fromisoformat(value_str)
        else:
            return value_str

    def _encrypt_value(self, value: str) -> str:
        """Encrypt sensitive value"""
        return self.fernet.encrypt(value.encode()).decode()

    def _decrypt_value(self, encrypted_value: str) -> str:
        """Decrypt sensitive value"""
        try:
            return self.fernet.decrypt(encrypted_value.encode()).decode()
        except:
            # Return as-is if decryption fails (might not be encrypted)
            return encrypted_value

    def _create_history_entry(
        self,
        setting: Setting,
        old_value: Optional[str],
        new_value: Optional[str],
        change_type: str,
        user_id: int,
    ):
        """Create setting history entry"""
        history = SettingHistory(
            setting_key=setting.key,
            scope=setting.scope,
            restaurant_id=setting.restaurant_id,
            location_id=setting.location_id,
            user_id=setting.user_id,
            old_value=old_value,
            new_value=new_value,
            change_type=change_type,
            changed_by_id=user_id,
        )

        self.db.add(history)
