# backend/modules/settings/__init__.py

"""
Comprehensive settings and configuration management module.
"""

from .routes.settings_routes import router as settings_router
# POS sync router exists separately
from .models.settings_models import (
    Setting, SettingDefinition, SettingGroup,
    ConfigurationTemplate, FeatureFlag, APIKey, Webhook,
    SettingCategory, SettingType, SettingScope
)
from .services.settings_service import SettingsService
# POSSyncService is in separate file

# Export main router
router = settings_router

__all__ = [
    "router",
    "Setting",
    "SettingDefinition",
    "SettingGroup",
    "ConfigurationTemplate",
    "FeatureFlag",
    "APIKey",
    "Webhook",
    "SettingCategory",
    "SettingType",
    "SettingScope",
    "SettingsService"
]