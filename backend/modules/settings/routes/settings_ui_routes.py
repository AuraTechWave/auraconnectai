"""
Enhanced UI-focused routes for settings configuration interface.

This module provides endpoints specifically designed for the settings UI,
including grouped settings, validation, bulk operations, and UI metadata.
"""

from fastapi import APIRouter, Depends, Query, HTTPException, Body
from sqlalchemy.orm import Session
from typing import List, Optional, Dict, Any
from datetime import datetime

from core.database import get_db
from core.auth import get_current_user
from core.exceptions import NotFoundError, ValidationError, UnauthorizedException
from modules.auth.models import User
from modules.auth.permissions import Permission, check_permission

from ..services.settings_ui_service import SettingsUIService
from ..schemas.settings_ui_schemas import (
    SettingsUIResponse,
    SettingsSectionResponse,
    SettingsValidationResponse,
    SettingsBulkOperationRequest,
    SettingsBulkOperationResponse,
    SettingsResetRequest,
    SettingsExportRequest,
    SettingsImportRequest,
    SettingsSearchRequest,
    SettingsComparisonResponse,
    UIMetadataResponse,
)
from ..models.settings_models import SettingScope, SettingCategory

router = APIRouter(prefix="/api/v1/settings-ui", tags=["Settings UI"])


@router.get("/dashboard", response_model=SettingsUIResponse)
async def get_settings_dashboard(
    scope: SettingScope = Query(SettingScope.RESTAURANT),
    restaurant_id: Optional[int] = Query(None),
    location_id: Optional[int] = Query(None),
    user_id: Optional[int] = Query(None),
    include_definitions: bool = Query(True),
    include_history: bool = Query(False),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Get complete settings dashboard data for UI.
    
    Returns organized settings by category with UI metadata.
    """
    # Validate permissions
    if scope == SettingScope.SYSTEM:
        check_permission(current_user, Permission.SYSTEM_ADMIN)
    elif scope == SettingScope.RESTAURANT and restaurant_id != current_user.restaurant_id:
        check_permission(current_user, Permission.SETTINGS_MANAGE_ALL)
    
    service = SettingsUIService(db)
    return service.get_settings_dashboard(
        scope=scope,
        restaurant_id=restaurant_id or current_user.restaurant_id,
        location_id=location_id,
        user_id=user_id or (current_user.id if scope == SettingScope.USER else None),
        include_definitions=include_definitions,
        include_history=include_history,
    )


@router.get("/sections", response_model=List[SettingsSectionResponse])
async def get_settings_sections(
    category: Optional[SettingCategory] = Query(None),
    scope: SettingScope = Query(SettingScope.RESTAURANT),
    show_advanced: bool = Query(False),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Get settings organized by sections/groups for UI display.
    """
    check_permission(current_user, Permission.SETTINGS_VIEW)
    
    service = SettingsUIService(db)
    return service.get_settings_sections(
        category=category,
        scope=scope,
        show_advanced=show_advanced,
        user=current_user,
    )


@router.post("/validate", response_model=SettingsValidationResponse)
async def validate_settings(
    settings: Dict[str, Any] = Body(...),
    scope: SettingScope = Query(SettingScope.RESTAURANT),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Validate settings before saving.
    
    Checks value types, constraints, dependencies, and conflicts.
    """
    check_permission(current_user, Permission.SETTINGS_VIEW)
    
    service = SettingsUIService(db)
    return service.validate_settings(settings, scope)


@router.post("/bulk-update", response_model=SettingsBulkOperationResponse)
async def bulk_update_settings(
    request: SettingsBulkOperationRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Update multiple settings in a single transaction.
    
    All updates must succeed or all will be rolled back.
    """
    check_permission(current_user, Permission.SETTINGS_MANAGE)
    
    service = SettingsUIService(db)
    return service.bulk_update_settings(
        settings=request.settings,
        scope=request.scope,
        restaurant_id=request.restaurant_id or current_user.restaurant_id,
        location_id=request.location_id,
        user_id=request.user_id,
        user=current_user,
        validate_only=request.validate_only,
    )


@router.post("/reset", response_model=SettingsBulkOperationResponse)
async def reset_settings(
    request: SettingsResetRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Reset settings to defaults.
    
    Can reset individual settings, categories, or all settings.
    """
    check_permission(current_user, Permission.SETTINGS_MANAGE)
    
    # System-wide reset requires admin
    if request.scope == SettingScope.SYSTEM:
        check_permission(current_user, Permission.SYSTEM_ADMIN)
    
    service = SettingsUIService(db)
    return service.reset_settings(
        scope=request.scope,
        category=request.category,
        setting_keys=request.setting_keys,
        restaurant_id=request.restaurant_id or current_user.restaurant_id,
        location_id=request.location_id,
        user_id=request.user_id or (current_user.id if request.scope == SettingScope.USER else None),
        user=current_user,
    )


@router.post("/export")
async def export_settings(
    request: SettingsExportRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Export settings to JSON file.
    
    Includes metadata and can optionally include sensitive settings.
    """
    check_permission(current_user, Permission.SETTINGS_MANAGE)
    
    service = SettingsUIService(db)
    export_data = service.export_settings(
        scope=request.scope,
        categories=request.categories,
        include_sensitive=request.include_sensitive,
        include_metadata=request.include_metadata,
        restaurant_id=request.restaurant_id or current_user.restaurant_id,
        user=current_user,
    )
    
    return {
        "filename": f"settings_export_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.json",
        "data": export_data,
    }


@router.post("/import", response_model=SettingsBulkOperationResponse)
async def import_settings(
    request: SettingsImportRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Import settings from JSON.
    
    Validates all settings before importing.
    """
    check_permission(current_user, Permission.SETTINGS_MANAGE)
    
    service = SettingsUIService(db)
    return service.import_settings(
        data=request.data,
        scope=request.scope,
        merge_strategy=request.merge_strategy,
        validate_only=request.validate_only,
        restaurant_id=request.restaurant_id or current_user.restaurant_id,
        user=current_user,
    )


@router.post("/search")
async def search_settings(
    request: SettingsSearchRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Search settings by key, label, or description.
    
    Supports fuzzy matching and filtering.
    """
    check_permission(current_user, Permission.SETTINGS_VIEW)
    
    service = SettingsUIService(db)
    return service.search_settings(
        query=request.query,
        scope=request.scope,
        categories=request.categories,
        include_advanced=request.include_advanced,
        user=current_user,
    )


@router.get("/compare/{template_id}", response_model=SettingsComparisonResponse)
async def compare_with_template(
    template_id: int,
    scope: SettingScope = Query(SettingScope.RESTAURANT),
    restaurant_id: Optional[int] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Compare current settings with a configuration template.
    
    Shows differences and allows selective application.
    """
    check_permission(current_user, Permission.SETTINGS_VIEW)
    
    service = SettingsUIService(db)
    return service.compare_with_template(
        template_id=template_id,
        scope=scope,
        restaurant_id=restaurant_id or current_user.restaurant_id,
        user=current_user,
    )


@router.get("/metadata", response_model=UIMetadataResponse)
async def get_ui_metadata(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Get UI metadata for settings interface.
    
    Includes available categories, scopes, types, and UI configuration.
    """
    check_permission(current_user, Permission.SETTINGS_VIEW)
    
    service = SettingsUIService(db)
    return service.get_ui_metadata(user=current_user)


@router.get("/pending-changes")
async def get_pending_changes(
    scope: SettingScope = Query(SettingScope.RESTAURANT),
    restaurant_id: Optional[int] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Get settings that require restart or have pending changes.
    """
    check_permission(current_user, Permission.SETTINGS_VIEW)
    
    service = SettingsUIService(db)
    return service.get_pending_changes(
        scope=scope,
        restaurant_id=restaurant_id or current_user.restaurant_id,
        user=current_user,
    )


@router.post("/apply-preset/{preset_name}", response_model=SettingsBulkOperationResponse)
async def apply_preset(
    preset_name: str,
    scope: SettingScope = Query(SettingScope.RESTAURANT),
    restaurant_id: Optional[int] = Query(None),
    override_existing: bool = Query(False),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Apply a predefined settings preset.
    
    Available presets:
    - quick_service: Optimized for fast food/quick service
    - fine_dining: Optimized for fine dining experience
    - casual_dining: Balanced for casual restaurants
    - takeout_focused: Optimized for takeout/delivery
    - bar_lounge: Optimized for bars and lounges
    """
    check_permission(current_user, Permission.SETTINGS_MANAGE)
    
    service = SettingsUIService(db)
    return service.apply_preset(
        preset_name=preset_name,
        scope=scope,
        restaurant_id=restaurant_id or current_user.restaurant_id,
        override_existing=override_existing,
        user=current_user,
    )