# backend/modules/settings/routes/settings_routes.py

"""
Routes for comprehensive settings and configuration management.
"""

from fastapi import APIRouter, Depends, Query, status, Body, Request
from sqlalchemy.orm import Session
from typing import List, Optional, Dict, Any
from datetime import datetime

from core.database import get_db
from core.auth import get_current_user
from core.error_handling import handle_api_errors, NotFoundError, APIValidationError
from modules.auth.models import User
from modules.auth.permissions import Permission, check_permission

from ..services.settings_service import SettingsService
from ..schemas.settings_schemas import (
    SettingCreate, SettingUpdate, SettingResponse, SettingListResponse,
    SettingFilters, BulkSettingUpdate,
    SettingDefinitionResponse, SettingGroupResponse,
    ConfigurationTemplateCreate, ConfigurationTemplateResponse, ApplyTemplateRequest,
    FeatureFlagCreate, FeatureFlagUpdate, FeatureFlagResponse, FeatureFlagStatus,
    APIKeyCreate, APIKeyResponse, APIKeyCreateResponse,
    WebhookCreate, WebhookUpdate, WebhookResponse, WebhookTestRequest, WebhookTestResponse,
    SettingHistoryResponse
)
from ..models.settings_models import (
    SettingScope, SettingCategory, SettingDefinition, ConfigurationTemplate,
    FeatureFlag, APIKey, Webhook, SettingHistory
)
from sqlalchemy import or_
import secrets
from datetime import timedelta

router = APIRouter(prefix="/api/v1/settings", tags=["Settings"])


# ========== Settings Management ==========

@router.post("/", response_model=SettingResponse, status_code=status.HTTP_201_CREATED)
@handle_api_errors
async def create_setting(
    setting_data: SettingCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Create a new setting.
    
    Returns:
        Created setting
        
    Raises:
        403: Insufficient permissions
        404: Setting definition not found
        409: Setting already exists
        422: Validation error
    """
    check_permission(current_user, Permission.SETTINGS_MANAGE)
    
    # Validate scope permissions
    if setting_data.scope == SettingScope.SYSTEM:
        check_permission(current_user, Permission.SYSTEM_ADMIN)
    elif setting_data.scope == SettingScope.RESTAURANT:
        if setting_data.restaurant_id != current_user.restaurant_id:
            raise APIValidationError("Cannot create settings for other restaurants")
    
    service = SettingsService(db)
    setting = service.create_setting(setting_data, current_user.id)
    
    return setting


@router.get("/", response_model=SettingListResponse)
@handle_api_errors
async def list_settings(
    category: Optional[SettingCategory] = Query(None),
    scope: Optional[SettingScope] = Query(None),
    is_sensitive: Optional[bool] = Query(None),
    search: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    size: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    List settings with filters.
    
    Returns:
        Paginated list of settings
        
    Raises:
        403: Insufficient permissions
    """
    check_permission(current_user, Permission.SETTINGS_VIEW)
    
    filters = SettingFilters(
        category=category,
        scope=scope,
        restaurant_id=current_user.restaurant_id if scope != SettingScope.SYSTEM else None,
        is_sensitive=is_sensitive,
        search=search
    )
    
    service = SettingsService(db)
    settings, total = service.list_settings(
        filters=filters,
        skip=(page - 1) * size,
        limit=size
    )
    
    return SettingListResponse(
        items=settings,
        total=total,
        page=page,
        size=size,
        pages=(total + size - 1) // size
    )


@router.get("/{key}", response_model=SettingResponse)
@handle_api_errors
async def get_setting(
    key: str,
    scope: SettingScope = Query(...),
    location_id: Optional[int] = Query(None),
    user_id: Optional[int] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Get a specific setting.
    
    Returns:
        Setting details
        
    Raises:
        403: Insufficient permissions
        404: Setting not found
    """
    check_permission(current_user, Permission.SETTINGS_VIEW)
    
    service = SettingsService(db)
    setting = service.get_setting(
        key=key,
        scope=scope,
        restaurant_id=current_user.restaurant_id if scope != SettingScope.SYSTEM else None,
        location_id=location_id,
        user_id=user_id if scope == SettingScope.USER else None
    )
    
    if not setting:
        raise NotFoundError("Setting", key)
    
    return setting


@router.put("/{key}", response_model=SettingResponse)
@handle_api_errors
async def update_setting(
    key: str,
    update_data: SettingUpdate,
    scope: SettingScope = Query(...),
    location_id: Optional[int] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Update a setting.
    
    Returns:
        Updated setting
        
    Raises:
        403: Insufficient permissions
        404: Setting not found
        422: Validation error
    """
    check_permission(current_user, Permission.SETTINGS_MANAGE)
    
    service = SettingsService(db)
    setting = service.update_setting(
        key=key,
        scope=scope,
        update_data=update_data,
        user_id=current_user.id,
        restaurant_id=current_user.restaurant_id if scope != SettingScope.SYSTEM else None,
        location_id=location_id,
        setting_user_id=current_user.id if scope == SettingScope.USER else None
    )
    
    return setting


@router.delete("/{key}", status_code=status.HTTP_204_NO_CONTENT)
@handle_api_errors
async def delete_setting(
    key: str,
    scope: SettingScope = Query(...),
    location_id: Optional[int] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Delete a setting.
    
    Returns:
        No content on success
        
    Raises:
        403: Insufficient permissions
        404: Setting not found
    """
    check_permission(current_user, Permission.SETTINGS_MANAGE)
    
    service = SettingsService(db)
    deleted = service.delete_setting(
        key=key,
        scope=scope,
        user_id=current_user.id,
        restaurant_id=current_user.restaurant_id if scope != SettingScope.SYSTEM else None,
        location_id=location_id,
        setting_user_id=current_user.id if scope == SettingScope.USER else None
    )
    
    if not deleted:
        raise NotFoundError("Setting", key)


@router.post("/bulk", response_model=List[SettingResponse])
@handle_api_errors
async def bulk_update_settings(
    bulk_data: BulkSettingUpdate,
    scope: SettingScope = Query(...),
    location_id: Optional[int] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Update multiple settings at once.
    
    Returns:
        List of updated settings
        
    Raises:
        403: Insufficient permissions
        422: Validation error
    """
    check_permission(current_user, Permission.SETTINGS_MANAGE)
    
    service = SettingsService(db)
    settings = service.bulk_update_settings(
        updates=bulk_data.settings,
        scope=scope,
        user_id=current_user.id,
        restaurant_id=current_user.restaurant_id if scope != SettingScope.SYSTEM else None,
        location_id=location_id
    )
    
    return settings


# ========== Setting Definitions ==========

@router.get("/definitions", response_model=List[SettingDefinitionResponse])
@handle_api_errors
async def list_setting_definitions(
    category: Optional[SettingCategory] = Query(None),
    scope: Optional[SettingScope] = Query(None),
    is_active: bool = Query(True),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    List available setting definitions.
    
    Returns:
        List of setting definitions
        
    Raises:
        403: Insufficient permissions
    """
    check_permission(current_user, Permission.SETTINGS_VIEW)
    
    service = SettingsService(db)
    
    query = db.query(service.db.query(SettingDefinition))
    
    if category:
        query = query.filter(SettingDefinition.category == category)
    if scope:
        query = query.filter(SettingDefinition.scope == scope)
    if is_active is not None:
        query = query.filter(SettingDefinition.is_active == is_active)
    
    definitions = query.order_by(
        SettingDefinition.category,
        SettingDefinition.sort_order,
        SettingDefinition.key
    ).all()
    
    return definitions


# ========== Configuration Templates ==========

@router.post("/templates", response_model=ConfigurationTemplateResponse, status_code=status.HTTP_201_CREATED)
@handle_api_errors
async def create_template(
    template_data: ConfigurationTemplateCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Create configuration template.
    
    Returns:
        Created template
        
    Raises:
        403: Insufficient permissions
        409: Template name already exists
    """
    check_permission(current_user, Permission.SETTINGS_MANAGE)
    
    service = SettingsService(db)
    template = service.create_template(template_data, current_user.id)
    
    return template


@router.get("/templates", response_model=List[ConfigurationTemplateResponse])
@handle_api_errors
async def list_templates(
    category: Optional[str] = Query(None),
    scope: Optional[SettingScope] = Query(None),
    is_active: bool = Query(True),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    List configuration templates.
    
    Returns:
        List of templates
        
    Raises:
        403: Insufficient permissions
    """
    check_permission(current_user, Permission.SETTINGS_VIEW)
    
    service = SettingsService(db)
    
    query = db.query(ConfigurationTemplate)
    
    if category:
        query = query.filter(ConfigurationTemplate.category == category)
    if scope:
        query = query.filter(ConfigurationTemplate.scope == scope)
    if is_active is not None:
        query = query.filter(ConfigurationTemplate.is_active == is_active)
    
    templates = query.order_by(ConfigurationTemplate.name).all()
    
    return templates


@router.post("/templates/{template_id}/apply", response_model=List[SettingResponse])
@handle_api_errors
async def apply_template(
    template_id: int,
    request: ApplyTemplateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Apply configuration template.
    
    Returns:
        List of applied settings
        
    Raises:
        403: Insufficient permissions
        404: Template not found
    """
    check_permission(current_user, Permission.SETTINGS_MANAGE)
    
    service = SettingsService(db)
    settings = service.apply_template(
        template_id=template_id,
        scope=SettingScope.RESTAURANT,  # Default to restaurant scope
        user_id=current_user.id,
        restaurant_id=current_user.restaurant_id,
        override_existing=request.override_existing,
        settings_override=request.settings_override
    )
    
    return settings


# ========== Feature Flags ==========

@router.post("/feature-flags", response_model=FeatureFlagResponse, status_code=status.HTTP_201_CREATED)
@handle_api_errors
async def create_feature_flag(
    flag_data: FeatureFlagCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Create feature flag.
    
    Returns:
        Created feature flag
        
    Raises:
        403: Insufficient permissions
        409: Flag key already exists
    """
    check_permission(current_user, Permission.SYSTEM_ADMIN)
    
    service = SettingsService(db)
    flag = service.create_feature_flag(flag_data, current_user.id)
    
    return flag


@router.get("/feature-flags", response_model=List[FeatureFlagResponse])
@handle_api_errors
async def list_feature_flags(
    is_enabled: Optional[bool] = Query(None),
    tags: Optional[List[str]] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    List feature flags.
    
    Returns:
        List of feature flags
        
    Raises:
        403: Insufficient permissions
    """
    check_permission(current_user, Permission.SETTINGS_VIEW)
    
    query = db.query(FeatureFlag)
    
    if is_enabled is not None:
        query = query.filter(FeatureFlag.is_enabled == is_enabled)
    
    flags = query.order_by(FeatureFlag.key).all()
    
    # Filter by tags if provided
    if tags:
        flags = [f for f in flags if any(tag in f.tags for tag in tags)]
    
    return flags


@router.get("/feature-flags/{key}/status", response_model=FeatureFlagStatus)
@handle_api_errors
async def check_feature_flag(
    key: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Check if feature is enabled for current context.
    
    Returns:
        Feature flag status
        
    Raises:
        403: Insufficient permissions
    """
    check_permission(current_user, Permission.SETTINGS_VIEW)
    
    service = SettingsService(db)
    is_enabled, reason = service.is_feature_enabled(
        key=key,
        restaurant_id=current_user.restaurant_id,
        user_id=current_user.id
    )
    
    return FeatureFlagStatus(
        key=key,
        is_enabled=is_enabled,
        reason=reason
    )


@router.put("/feature-flags/{key}", response_model=FeatureFlagResponse)
@handle_api_errors
async def update_feature_flag(
    key: str,
    update_data: FeatureFlagUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Update feature flag.
    
    Returns:
        Updated feature flag
        
    Raises:
        403: Insufficient permissions
        404: Flag not found
    """
    check_permission(current_user, Permission.SYSTEM_ADMIN)
    
    flag = db.query(FeatureFlag).filter(FeatureFlag.key == key).first()
    
    if not flag:
        raise NotFoundError("Feature flag", key)
    
    # Update fields
    update_dict = update_data.dict(exclude_unset=True)
    for field, value in update_dict.items():
        setattr(flag, field, value)
    
    db.commit()
    db.refresh(flag)
    
    return flag


# ========== API Keys ==========

@router.post("/api-keys", response_model=APIKeyCreateResponse, status_code=status.HTTP_201_CREATED)
@handle_api_errors
async def create_api_key(
    key_data: APIKeyCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Create API key.
    
    Returns:
        Created API key (with actual key - only shown once)
        
    Raises:
        403: Insufficient permissions
    """
    check_permission(current_user, Permission.API_KEYS_MANAGE)
    
    service = SettingsService(db)
    key_model, api_key = service.create_api_key(
        key_data,
        current_user.restaurant_id,
        current_user.id
    )
    
    response = APIKeyCreateResponse(
        **key_model.__dict__,
        api_key=api_key
    )
    
    return response


@router.get("/api-keys", response_model=List[APIKeyResponse])
@handle_api_errors
async def list_api_keys(
    is_active: Optional[bool] = Query(True),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    List API keys for restaurant.
    
    Returns:
        List of API keys (without actual keys)
        
    Raises:
        403: Insufficient permissions
    """
    check_permission(current_user, Permission.API_KEYS_VIEW)
    
    query = db.query(APIKey).filter(
        APIKey.restaurant_id == current_user.restaurant_id
    )
    
    if is_active is not None:
        query = query.filter(APIKey.is_active == is_active)
    
    keys = query.order_by(APIKey.created_at.desc()).all()
    
    return keys


@router.delete("/api-keys/{key_id}", status_code=status.HTTP_204_NO_CONTENT)
@handle_api_errors
async def revoke_api_key(
    key_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Revoke API key.
    
    Returns:
        No content on success
        
    Raises:
        403: Insufficient permissions
        404: Key not found
    """
    check_permission(current_user, Permission.API_KEYS_MANAGE)
    
    key = db.query(APIKey).filter(
        APIKey.id == key_id,
        APIKey.restaurant_id == current_user.restaurant_id
    ).first()
    
    if not key:
        raise NotFoundError("API key", key_id)
    
    key.is_active = False
    db.commit()


# ========== Webhooks ==========

@router.post("/webhooks", response_model=WebhookResponse, status_code=status.HTTP_201_CREATED)
@handle_api_errors
async def create_webhook(
    webhook_data: WebhookCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Create webhook.
    
    Returns:
        Created webhook
        
    Raises:
        403: Insufficient permissions
    """
    check_permission(current_user, Permission.WEBHOOKS_MANAGE)
    
    webhook = Webhook(
        name=webhook_data.name,
        url=webhook_data.url,
        description=webhook_data.description,
        restaurant_id=current_user.restaurant_id,
        created_by_id=current_user.id,
        events=webhook_data.events,
        secret=webhook_data.secret or secrets.token_urlsafe(32),
        headers=webhook_data.headers or {},
        max_retries=webhook_data.max_retries,
        retry_delay_seconds=webhook_data.retry_delay_seconds,
        timeout_seconds=webhook_data.timeout_seconds
    )
    
    db.add(webhook)
    db.commit()
    db.refresh(webhook)
    
    return webhook


@router.get("/webhooks", response_model=List[WebhookResponse])
@handle_api_errors
async def list_webhooks(
    is_active: Optional[bool] = Query(True),
    event: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    List webhooks.
    
    Returns:
        List of webhooks
        
    Raises:
        403: Insufficient permissions
    """
    check_permission(current_user, Permission.WEBHOOKS_VIEW)
    
    query = db.query(Webhook).filter(
        Webhook.restaurant_id == current_user.restaurant_id
    )
    
    if is_active is not None:
        query = query.filter(Webhook.is_active == is_active)
    
    webhooks = query.order_by(Webhook.name).all()
    
    # Filter by event if provided
    if event:
        webhooks = [w for w in webhooks if event in w.events]
    
    return webhooks


@router.post("/webhooks/{webhook_id}/test", response_model=WebhookTestResponse)
@handle_api_errors
async def test_webhook(
    webhook_id: int,
    test_data: WebhookTestRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Test webhook with sample payload.
    
    Returns:
        Test result
        
    Raises:
        403: Insufficient permissions
        404: Webhook not found
    """
    check_permission(current_user, Permission.WEBHOOKS_MANAGE)
    
    webhook = db.query(Webhook).filter(
        Webhook.id == webhook_id,
        Webhook.restaurant_id == current_user.restaurant_id
    ).first()
    
    if not webhook:
        raise NotFoundError("Webhook", webhook_id)
    
    # TODO: Implement actual webhook testing
    # For now, return mock response
    return WebhookTestResponse(
        success=True,
        status_code=200,
        response_time_ms=150.5,
        error=None,
        response_body='{"status": "ok"}'
    )


# ========== Setting History ==========

@router.get("/history", response_model=List[SettingHistoryResponse])
@handle_api_errors
async def get_setting_history(
    key: Optional[str] = Query(None),
    scope: Optional[SettingScope] = Query(None),
    days: int = Query(30, ge=1, le=365),
    page: int = Query(1, ge=1),
    size: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Get setting change history.
    
    Returns:
        List of history entries
        
    Raises:
        403: Insufficient permissions
    """
    check_permission(current_user, Permission.SETTINGS_VIEW)
    
    from_date = datetime.utcnow() - timedelta(days=days)
    
    query = db.query(SettingHistory).filter(
        SettingHistory.changed_at >= from_date
    )
    
    # Filter by restaurant for non-system admins
    if not current_user.is_system_admin:
        query = query.filter(
            or_(
                SettingHistory.restaurant_id == current_user.restaurant_id,
                SettingHistory.scope == SettingScope.SYSTEM
            )
        )
    
    if key:
        query = query.filter(SettingHistory.setting_key == key)
    if scope:
        query = query.filter(SettingHistory.scope == scope)
    
    # Order by most recent first
    query = query.order_by(SettingHistory.changed_at.desc())
    
    # Apply pagination
    history = query.offset((page - 1) * size).limit(size).all()
    
    return history