# backend/modules/settings/schemas/settings_schemas.py

"""
Schemas for settings and configuration management.
"""

from typing import List, Dict, Any, Optional, Union
from datetime import datetime
from pydantic import BaseModel, Field, field_validator, model_validator
import json

from ..models.settings_models import SettingCategory, SettingType, SettingScope


# ========== Setting Schemas ==========


class SettingBase(BaseModel, ConfigDict):
    """Base setting schema"""

    key: str = Field(..., max_length=100, pattern="^[a-z][a-z0-9_]*$")
    category: SettingCategory
    label: str = Field(..., max_length=200)
    description: Optional[str] = None
    is_sensitive: bool = False
    is_public: bool = False
    validation_rules: Optional[Dict[str, Any]] = {}
    allowed_values: Optional[List[Any]] = []
    ui_config: Optional[Dict[str, Any]] = {}


class SettingCreate(BaseModel):
    """Create setting request"""

    key: str = Field(..., max_length=100, pattern="^[a-z][a-z0-9_]*$")
    value: Union[str, int, float, bool, dict, list]
    scope: SettingScope
    restaurant_id: Optional[int] = None
    location_id: Optional[int] = None
    user_id: Optional[int] = None

    @model_validator(mode="after")
    def validate_scope_ids(self):
        scope = self.scope
        restaurant_id = self.restaurant_id
        location_id = self.location_id
        user_id = self.user_id

        if scope == SettingScope.RESTAURANT and not restaurant_id:
            raise ValueError("restaurant_id required for restaurant scope")
        elif scope == SettingScope.LOCATION and not location_id:
            raise ValueError("location_id required for location scope")
        elif scope == SettingScope.USER and not user_id:
            raise ValueError("user_id required for user scope")
        elif scope == SettingScope.SYSTEM and (restaurant_id or location_id or user_id):
            raise ValueError("No IDs should be provided for system scope")

        return self


class SettingUpdate(BaseModel):
    """Update setting request"""

    value: Union[str, int, float, bool, dict, list]
    description: Optional[str] = None
    validation_rules: Optional[Dict[str, Any]] = None
    ui_config: Optional[Dict[str, Any]] = None


class SettingResponse(BaseModel):
    """Setting response"""

    id: int
    key: str
    category: str
    scope: str
    value: Any  # Parsed from JSON string
    value_type: str
    label: str
    description: Optional[str]
    is_sensitive: bool
    is_public: bool
    validation_rules: Dict[str, Any]
    allowed_values: List[Any]
    ui_config: Dict[str, Any]
    restaurant_id: Optional[int]
    location_id: Optional[int]
    user_id: Optional[int]
    modified_by_id: Optional[int]
    modified_at: datetime
    created_at: datetime
    updated_at: datetime
    model_config = ConfigDict(from_attributes=True)

    # Custom JSON encoders need to be handled differently in v2
    # Consider using model_serializer if needed

    @field_validator("value", mode="before")
    def parse_value(cls, v, values):
        if isinstance(v, str):
            try:
                return json.loads(v)
            except:
                return v
        return v


class SettingListResponse(BaseModel):
    """Paginated setting list"""

    items: List[SettingResponse]
    total: int
    page: int
    size: int
    pages: int


class BulkSettingUpdate(BaseModel):
    """Bulk update settings"""

    settings: List[Dict[str, Any]] = Field(..., min_items=1, max_items=50)

    class Config:
        schema_extra = {
            "example": {
                "settings": [
                    {"key": "tax_rate", "value": 8.5},
                    {"key": "currency", "value": "USD"},
                ]
            }
        }


# ========== Setting Definition Schemas ==========


class SettingDefinitionCreate(BaseModel):
    """Create setting definition"""

    key: str = Field(..., max_length=100, pattern="^[a-z][a-z0-9_]*$")
    category: SettingCategory
    scope: SettingScope
    value_type: SettingType
    label: str = Field(..., max_length=200)
    description: Optional[str] = None
    help_text: Optional[str] = None
    default_value: Optional[Any] = None
    validation_rules: Optional[Dict[str, Any]] = {}
    allowed_values: Optional[List[Any]] = []
    is_required: bool = False
    is_sensitive: bool = False
    requires_restart: bool = False
    depends_on: Optional[List[str]] = []
    conflicts_with: Optional[List[str]] = []
    ui_config: Optional[Dict[str, Any]] = {}
    sort_order: int = 0


class SettingDefinitionResponse(BaseModel):
    """Setting definition response"""

    id: int
    key: str
    category: str
    scope: str
    value_type: str
    label: str
    description: Optional[str]
    help_text: Optional[str]
    default_value: Optional[Any]
    validation_rules: Dict[str, Any]
    allowed_values: List[Any]
    is_required: bool
    is_sensitive: bool
    requires_restart: bool
    depends_on: List[str]
    conflicts_with: List[str]
    ui_config: Dict[str, Any]
    sort_order: int
    is_active: bool
    is_deprecated: bool
    deprecation_message: Optional[str]
    introduced_version: Optional[str]
    deprecated_version: Optional[str]
    removed_version: Optional[str]
    created_at: datetime
    updated_at: datetime
    model_config = ConfigDict(from_attributes=True)

    # Custom JSON encoders need to be handled differently in v2
    # Consider using model_serializer if needed


# ========== Setting Group Schemas ==========


class SettingGroupCreate(BaseModel):
    """Create setting group"""

    name: str = Field(..., max_length=100, pattern="^[a-z][a-z0-9_]*$")
    label: str = Field(..., max_length=200)
    description: Optional[str] = None
    category: SettingCategory
    settings: List[str] = Field(..., min_items=1)
    ui_config: Optional[Dict[str, Any]] = {}
    sort_order: int = 0
    required_permission: Optional[str] = None
    is_advanced: bool = False


class SettingGroupResponse(BaseModel):
    """Setting group response"""

    id: int
    name: str
    label: str
    description: Optional[str]
    category: str
    settings: List[str]
    ui_config: Dict[str, Any]
    sort_order: int
    required_permission: Optional[str]
    is_advanced: bool
    created_at: datetime
    updated_at: datetime
    model_config = ConfigDict(from_attributes=True)

    # Custom JSON encoders need to be handled differently in v2
    # Consider using model_serializer if needed


# ========== Configuration Template Schemas ==========


class ConfigurationTemplateCreate(BaseModel):
    """Create configuration template"""

    name: str = Field(..., max_length=100)
    label: str = Field(..., max_length=200)
    description: Optional[str] = None
    category: str = Field(..., max_length=50)
    settings: Dict[str, Any] = Field(..., description="Key-value pairs of settings")
    scope: SettingScope
    tags: Optional[List[str]] = []


class ConfigurationTemplateResponse(BaseModel):
    """Configuration template response"""

    id: int
    name: str
    label: str
    description: Optional[str]
    category: str
    settings: Dict[str, Any]
    scope: str
    is_active: bool
    is_default: bool
    usage_count: int
    created_by_id: Optional[int]
    tags: List[str]
    created_at: datetime
    updated_at: datetime
    model_config = ConfigDict(from_attributes=True)

    # Custom JSON encoders need to be handled differently in v2
    # Consider using model_serializer if needed


class ApplyTemplateRequest(BaseModel):
    """Apply configuration template request"""

    template_id: int
    override_existing: bool = False
    settings_override: Optional[Dict[str, Any]] = {}


# ========== Feature Flag Schemas ==========


class FeatureFlagCreate(BaseModel):
    """Create feature flag"""

    key: str = Field(..., max_length=100, pattern="^[A-Z][A-Z0-9_]*$")
    name: str = Field(..., max_length=200)
    description: Optional[str] = None
    is_enabled: bool = False
    rollout_percentage: int = Field(0, ge=0, le=100)
    enabled_restaurants: Optional[List[int]] = []
    enabled_users: Optional[List[int]] = []
    targeting_rules: Optional[Dict[str, Any]] = {}
    enabled_from: Optional[datetime] = None
    enabled_until: Optional[datetime] = None
    depends_on: Optional[List[str]] = []
    tags: Optional[List[str]] = []


class FeatureFlagUpdate(BaseModel):
    """Update feature flag"""

    name: Optional[str] = Field(None, max_length=200)
    description: Optional[str] = None
    is_enabled: Optional[bool] = None
    rollout_percentage: Optional[int] = Field(None, ge=0, le=100)
    enabled_restaurants: Optional[List[int]] = None
    enabled_users: Optional[List[int]] = None
    targeting_rules: Optional[Dict[str, Any]] = None
    enabled_from: Optional[datetime] = None
    enabled_until: Optional[datetime] = None
    depends_on: Optional[List[str]] = None
    tags: Optional[List[str]] = None


class FeatureFlagResponse(BaseModel):
    """Feature flag response"""

    id: int
    key: str
    name: str
    description: Optional[str]
    is_enabled: bool
    rollout_percentage: int
    enabled_restaurants: List[int]
    enabled_users: List[int]
    targeting_rules: Dict[str, Any]
    enabled_from: Optional[datetime]
    enabled_until: Optional[datetime]
    depends_on: List[str]
    created_by_id: Optional[int]
    tags: List[str]
    created_at: datetime
    updated_at: datetime
    model_config = ConfigDict(from_attributes=True)

    # Custom JSON encoders need to be handled differently in v2
    # Consider using model_serializer if needed


class FeatureFlagStatus(BaseModel):
    """Feature flag status for a specific context"""

    key: str
    is_enabled: bool
    reason: str  # Why it's enabled/disabled
    metadata: Optional[Dict[str, Any]] = {}


# ========== API Key Schemas ==========


class APIKeyCreate(BaseModel):
    """Create API key request"""

    name: str = Field(..., max_length=100)
    description: Optional[str] = None
    scopes: List[str] = Field(..., min_items=1)
    allowed_ips: Optional[List[str]] = []
    expires_at: Optional[datetime] = None
    rate_limit_per_hour: Optional[int] = Field(None, gt=0)
    rate_limit_per_day: Optional[int] = Field(None, gt=0)


class APIKeyResponse(BaseModel):
    """API key response (without actual key)"""

    id: int
    key_prefix: str
    name: str
    description: Optional[str]
    restaurant_id: int
    created_by_id: int
    scopes: List[str]
    allowed_ips: List[str]
    is_active: bool
    last_used_at: Optional[datetime]
    usage_count: int
    expires_at: Optional[datetime]
    rate_limit_per_hour: Optional[int]
    rate_limit_per_day: Optional[int]
    created_at: datetime
    updated_at: datetime
    model_config = ConfigDict(from_attributes=True)

    # Custom JSON encoders need to be handled differently in v2
    # Consider using model_serializer if needed


class APIKeyCreateResponse(APIKeyResponse):
    """API key creation response (includes actual key)"""

    api_key: str  # Only returned on creation


# ========== Webhook Schemas ==========


class WebhookCreate(BaseModel):
    """Create webhook"""

    name: str = Field(..., max_length=100)
    url: str = Field(..., max_length=500, pattern="^https?://")
    description: Optional[str] = None
    events: List[str] = Field(..., min_items=1)
    secret: Optional[str] = Field(None, min_length=32)
    headers: Optional[Dict[str, str]] = {}
    max_retries: int = Field(3, ge=0, le=10)
    retry_delay_seconds: int = Field(60, ge=1, le=3600)
    timeout_seconds: int = Field(30, ge=1, le=300)


class WebhookUpdate(BaseModel):
    """Update webhook"""

    name: Optional[str] = Field(None, max_length=100)
    url: Optional[str] = Field(None, max_length=500, pattern="^https?://")
    description: Optional[str] = None
    events: Optional[List[str]] = Field(None, min_items=1)
    secret: Optional[str] = Field(None, min_length=32)
    headers: Optional[Dict[str, str]] = None
    is_active: Optional[bool] = None
    max_retries: Optional[int] = Field(None, ge=0, le=10)
    retry_delay_seconds: Optional[int] = Field(None, ge=1, le=3600)
    timeout_seconds: Optional[int] = Field(None, ge=1, le=300)


class WebhookResponse(BaseModel):
    """Webhook response"""

    id: int
    name: str
    url: str
    description: Optional[str]
    restaurant_id: int
    created_by_id: int
    events: List[str]
    headers: Dict[str, str]
    max_retries: int
    retry_delay_seconds: int
    timeout_seconds: int
    is_active: bool
    last_triggered_at: Optional[datetime]
    last_success_at: Optional[datetime]
    last_failure_at: Optional[datetime]
    failure_count: int
    created_at: datetime
    updated_at: datetime
    model_config = ConfigDict(from_attributes=True)

    # Custom JSON encoders need to be handled differently in v2
    # Consider using model_serializer if needed


class WebhookTestRequest(BaseModel):
    """Test webhook request"""

    event_type: str
    payload: Dict[str, Any]


class WebhookTestResponse(BaseModel):
    """Webhook test response"""

    success: bool
    status_code: Optional[int]
    response_time_ms: float
    error: Optional[str]
    response_body: Optional[str]


# ========== Setting History Schemas ==========


class SettingHistoryResponse(BaseModel):
    """Setting history entry"""

    id: int
    setting_key: str
    scope: str
    restaurant_id: Optional[int]
    location_id: Optional[int]
    user_id: Optional[int]
    old_value: Optional[Any]
    new_value: Optional[Any]
    change_type: str
    changed_by_id: int
    changed_at: datetime
    change_reason: Optional[str]
    ip_address: Optional[str]
    user_agent: Optional[str]
    model_config = ConfigDict(from_attributes=True)

    # Custom JSON encoders need to be handled differently in v2
    # Consider using model_serializer if needed


# ========== Filters and Search ==========


class SettingFilters(BaseModel):
    """Setting filter criteria"""

    category: Optional[SettingCategory] = None
    scope: Optional[SettingScope] = None
    restaurant_id: Optional[int] = None
    location_id: Optional[int] = None
    user_id: Optional[int] = None
    is_sensitive: Optional[bool] = None
    search: Optional[str] = Field(None, max_length=100)
