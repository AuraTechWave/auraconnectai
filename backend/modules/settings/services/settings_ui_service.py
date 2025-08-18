"""
UI-specific service for settings configuration interface.

This service provides methods optimized for UI interactions,
including grouped settings, validation, and bulk operations.
"""

from sqlalchemy.orm import Session
from sqlalchemy import and_, or_, func
from typing import List, Optional, Dict, Any, Tuple
from datetime import datetime
import json
import logging
from collections import defaultdict

from ..models.settings_models import (
    Setting,
    SettingDefinition,
    SettingGroup,
    ConfigurationTemplate,
    SettingHistory,
    SettingCategory,
    SettingType,
    SettingScope,
)
from ..schemas.settings_ui_schemas import (
    SettingUIField,
    SettingsSection,
    SettingsSectionResponse,
    SettingsUIResponse,
    SettingsValidationResponse,
    ValidationError,
    SettingChange,
    SettingsBulkOperationResponse,
    SettingDifference,
    SettingsComparisonResponse,
    UIFieldType,
    UIMetadataResponse,
    PendingChange,
)
from modules.auth.models import User
from core.exceptions import NotFoundError, ValidationError as CoreValidationError

logger = logging.getLogger(__name__)


class SettingsUIService:
    """Service for UI-focused settings operations"""
    
    def __init__(self, db: Session):
        self.db = db
        self.presets = self._load_presets()
    
    def get_settings_dashboard(
        self,
        scope: SettingScope,
        restaurant_id: Optional[int] = None,
        location_id: Optional[int] = None,
        user_id: Optional[int] = None,
        include_definitions: bool = True,
        include_history: bool = False,
    ) -> SettingsUIResponse:
        """Get complete settings dashboard data"""
        
        # Get all settings for scope
        settings_query = self.db.query(Setting).filter(Setting.scope == scope)
        
        if scope == SettingScope.RESTAURANT and restaurant_id:
            settings_query = settings_query.filter(Setting.restaurant_id == restaurant_id)
        elif scope == SettingScope.LOCATION and location_id:
            settings_query = settings_query.filter(Setting.location_id == location_id)
        elif scope == SettingScope.USER and user_id:
            settings_query = settings_query.filter(Setting.user_id == user_id)
        
        settings = settings_query.all()
        
        # Get definitions
        definitions = {}
        if include_definitions:
            defs = self.db.query(SettingDefinition).filter(
                SettingDefinition.is_active == True
            ).all()
            definitions = {d.key: d for d in defs}
        
        # Get groups
        groups = self.db.query(SettingGroup).order_by(
            SettingGroup.sort_order
        ).all()
        
        # Organize by category and group
        categories_data = defaultdict(lambda: {
            "sections": [],
            "total_settings": 0,
            "modified_count": 0,
        })
        
        # Build sections
        sections = []
        for group in groups:
            section_settings = []
            
            for setting_key in group.settings:
                setting = next((s for s in settings if s.key == setting_key), None)
                definition = definitions.get(setting_key)
                
                if definition and (setting or definition.default_value is not None):
                    ui_field = self._create_ui_field(setting, definition)
                    section_settings.append(ui_field)
            
            if section_settings:
                section = SettingsSection(
                    id=group.name,
                    name=group.name,
                    label=group.label,
                    description=group.description,
                    category=group.category,
                    settings=section_settings,
                    is_advanced=group.is_advanced,
                    required_permission=group.required_permission,
                    sort_order=group.sort_order,
                )
                sections.append(section)
                
                # Update category data
                cat_data = categories_data[group.category.value]
                cat_data["sections"].append(section)
                cat_data["total_settings"] += len(section_settings)
                cat_data["modified_count"] += sum(
                    1 for s in section_settings if s.is_modified
                )
        
        # Build categories list
        categories = []
        for cat in SettingCategory:
            if cat.value in categories_data:
                categories.append({
                    "key": cat.value,
                    "label": cat.value.replace("_", " ").title(),
                    "icon": self._get_category_icon(cat),
                    **categories_data[cat.value]
                })
        
        # Check for unsaved changes and restart requirements
        has_unsaved_changes = any(
            s.is_modified for section in sections for s in section.settings
        )
        
        requires_restart = [
            s.key for section in sections for s in section.settings
            if s.requires_restart and s.is_modified
        ]
        
        return SettingsUIResponse(
            categories=categories,
            sections=sections,
            metadata={
                "scope": scope.value,
                "total_settings": sum(len(s.settings) for s in sections),
                "total_sections": len(sections),
            },
            has_unsaved_changes=has_unsaved_changes,
            requires_restart=requires_restart,
            last_saved=None,  # TODO: Track last save time
            can_edit=True,  # TODO: Check permissions
            can_reset=True,  # TODO: Check permissions
        )
    
    def get_settings_sections(
        self,
        category: Optional[SettingCategory],
        scope: SettingScope,
        show_advanced: bool,
        user: User,
    ) -> List[SettingsSectionResponse]:
        """Get settings organized by sections"""
        
        groups_query = self.db.query(SettingGroup)
        
        if category:
            groups_query = groups_query.filter(SettingGroup.category == category)
        
        if not show_advanced:
            groups_query = groups_query.filter(SettingGroup.is_advanced == False)
        
        groups = groups_query.order_by(SettingGroup.sort_order).all()
        
        # Get all settings for the scope
        settings_query = self.db.query(Setting).filter(Setting.scope == scope)
        settings = settings_query.all()
        settings_map = {s.key: s for s in settings}
        
        # Get all definitions
        definitions = self.db.query(SettingDefinition).filter(
            SettingDefinition.is_active == True
        ).all()
        definitions_map = {d.key: d for d in definitions}
        
        sections = []
        total_settings = 0
        modified_count = 0
        has_errors = False
        
        for group in groups:
            # Check permissions
            if group.required_permission and not user.has_permission(group.required_permission):
                continue
            
            section_settings = []
            
            # Build section settings from group's setting keys
            for setting_key in group.settings:
                definition = definitions_map.get(setting_key)
                if definition:
                    setting = settings_map.get(setting_key)
                    ui_field = self._create_ui_field(setting, definition)
                    section_settings.append(ui_field)
                    
                    if ui_field.is_modified:
                        modified_count += 1
                    if ui_field.has_error:
                        has_errors = True
            
            if section_settings:
                section = SettingsSection(
                    id=group.name,
                    name=group.name,
                    label=group.label,
                    description=group.description,
                    category=group.category,
                    settings=section_settings,
                    is_advanced=group.is_advanced,
                    sort_order=group.sort_order,
                )
                sections.append(section)
                total_settings += len(section_settings)
        
        return SettingsSectionResponse(
            sections=sections,
            total_settings=total_settings,
            modified_count=modified_count,
            has_errors=has_errors,
        )
    
    def validate_settings(
        self,
        settings: Dict[str, Any],
        scope: SettingScope,
    ) -> SettingsValidationResponse:
        """Validate settings values"""
        
        errors = []
        warnings = []
        conflicts = []
        
        # Get definitions for all settings
        setting_keys = list(settings.keys())
        definitions = self.db.query(SettingDefinition).filter(
            SettingDefinition.key.in_(setting_keys)
        ).all()
        
        def_map = {d.key: d for d in definitions}
        
        # Validate each setting
        for key, value in settings.items():
            definition = def_map.get(key)
            
            if not definition:
                errors.append(ValidationError(
                    field=key,
                    message=f"Unknown setting: {key}",
                    code="unknown_setting",
                ))
                continue
            
            # Type validation
            try:
                self._validate_type(value, definition.value_type)
            except Exception as e:
                errors.append(ValidationError(
                    field=key,
                    message=str(e),
                    code="invalid_type",
                ))
            
            # Custom validation rules
            if definition.validation_rules:
                validation_errors = self._apply_validation_rules(
                    value, definition.validation_rules
                )
                errors.extend(validation_errors)
            
            # Check allowed values
            if definition.allowed_values and value not in definition.allowed_values:
                errors.append(ValidationError(
                    field=key,
                    message=f"Value must be one of: {definition.allowed_values}",
                    code="invalid_value",
                ))
        
        # Check dependencies
        dependencies_met = self._check_dependencies(settings, def_map)
        
        # Check conflicts
        conflicts_detected = self._check_conflicts(settings, def_map)
        
        return SettingsValidationResponse(
            is_valid=len(errors) == 0,
            errors=errors,
            warnings=warnings,
            dependencies_met=dependencies_met,
            conflicts_detected=conflicts_detected,
        )
    
    def bulk_update_settings(
        self,
        settings: List[SettingChange],
        scope: SettingScope,
        restaurant_id: Optional[int],
        location_id: Optional[int],
        user_id: Optional[int],
        user: User,
        validate_only: bool = False,
    ) -> SettingsBulkOperationResponse:
        """Update multiple settings in a transaction"""
        
        processed = 0
        failed = 0
        errors = []
        changes = []
        requires_restart = []
        
        # Convert to dict for validation
        settings_dict = {s.key: s.value for s in settings}
        
        # Validate all settings first
        validation = self.validate_settings(settings_dict, scope)
        
        if not validation.is_valid:
            return SettingsBulkOperationResponse(
                success=False,
                processed=0,
                failed=len(settings),
                errors=validation.errors,
                changes=[],
                requires_restart=[],
                rollback_performed=False,
            )
        
        if validate_only:
            return SettingsBulkOperationResponse(
                success=True,
                processed=len(settings),
                failed=0,
                errors=[],
                changes=settings,
                requires_restart=[],
                rollback_performed=False,
            )
        
        # Perform updates in transaction
        try:
            for setting_change in settings:
                # Get or create setting
                setting = self._get_or_create_setting(
                    key=setting_change.key,
                    scope=scope,
                    restaurant_id=restaurant_id,
                    location_id=location_id,
                    user_id=user_id,
                )
                
                # Store old value
                old_value = setting.value if setting.id else None
                setting_change.previous_value = old_value
                
                # Update value
                setting.value = json.dumps(setting_change.value)
                setting.modified_by_id = user.id
                setting.modified_at = datetime.utcnow()
                
                # Add to session
                if not setting.id:
                    self.db.add(setting)
                
                # Check if restart required
                definition = self.db.query(SettingDefinition).filter(
                    SettingDefinition.key == setting_change.key
                ).first()
                
                if definition and definition.requires_restart:
                    requires_restart.append(setting_change.key)
                
                # Log change
                self._log_setting_change(
                    setting=setting,
                    old_value=old_value,
                    new_value=setting.value,
                    user=user,
                    reason=f"Bulk update",
                )
                
                changes.append(setting_change)
                processed += 1
            
            self.db.commit()
            
        except Exception as e:
            self.db.rollback()
            logger.error(f"Bulk update failed: {e}")
            return SettingsBulkOperationResponse(
                success=False,
                processed=processed,
                failed=len(settings) - processed,
                errors=[ValidationError(
                    field="general",
                    message=str(e),
                    code="update_failed",
                )],
                changes=changes,
                requires_restart=requires_restart,
                rollback_performed=True,
            )
        
        return SettingsBulkOperationResponse(
            success=True,
            processed=processed,
            failed=failed,
            errors=errors,
            changes=changes,
            requires_restart=requires_restart,
            rollback_performed=False,
        )
    
    def reset_settings(
        self,
        scope: SettingScope,
        category: Optional[SettingCategory],
        setting_keys: Optional[List[str]],
        restaurant_id: Optional[int],
        location_id: Optional[int],
        user_id: Optional[int],
        user: User,
    ) -> SettingsBulkOperationResponse:
        """Reset settings to defaults"""
        
        # Get definitions for settings to reset
        definitions_query = self.db.query(SettingDefinition).filter(
            SettingDefinition.scope == scope
        )
        
        if category:
            definitions_query = definitions_query.filter(
                SettingDefinition.category == category
            )
        
        if setting_keys:
            definitions_query = definitions_query.filter(
                SettingDefinition.key.in_(setting_keys)
            )
        
        definitions = definitions_query.all()
        
        # Reset each setting
        changes = []
        for definition in definitions:
            if definition.default_value is not None:
                change = SettingChange(
                    key=definition.key,
                    value=json.loads(definition.default_value),
                    scope=scope,
                    category=definition.category,
                )
                changes.append(change)
        
        # Apply changes
        return self.bulk_update_settings(
            settings=changes,
            scope=scope,
            restaurant_id=restaurant_id,
            location_id=location_id,
            user_id=user_id,
            user=user,
            validate_only=False,
        )
    
    def apply_preset(
        self,
        preset_name: str,
        scope: SettingScope,
        restaurant_id: int,
        override_existing: bool,
        user: User,
    ) -> SettingsBulkOperationResponse:
        """Apply a predefined settings preset"""
        
        preset = self.presets.get(preset_name)
        if not preset:
            raise NotFoundError("Preset", preset_name)
        
        # Convert preset to changes
        changes = []
        for key, value in preset["settings"].items():
            change = SettingChange(
                key=key,
                value=value,
                scope=scope,
            )
            changes.append(change)
        
        # Apply changes
        return self.bulk_update_settings(
            settings=changes,
            scope=scope,
            restaurant_id=restaurant_id,
            location_id=None,
            user_id=None,
            user=user,
            validate_only=False,
        )
    
    def import_settings(
        self,
        data: Dict[str, Any],
        scope: SettingScope,
        merge_strategy: str,
        validate_only: bool,
        restaurant_id: Optional[int],
        user: User,
    ) -> SettingsBulkOperationResponse:
        """Import settings from JSON data"""
        
        # Extract settings from data
        settings_data = data.get("settings", {})
        if not settings_data:
            raise CoreValidationError("No settings found in import data")
        
        # Convert to setting changes
        changes = []
        for key, value in settings_data.items():
            # Skip if merge_strategy is skip_existing and setting exists
            if merge_strategy == "skip_existing":
                existing = self.db.query(Setting).filter(
                    and_(
                        Setting.key == key,
                        Setting.scope == scope,
                        Setting.restaurant_id == restaurant_id,
                    )
                ).first()
                
                if existing:
                    continue
            
            change = SettingChange(
                key=key,
                value=value,
                scope=scope,
            )
            changes.append(change)
        
        # Apply changes
        return self.bulk_update_settings(
            settings=changes,
            scope=scope,
            restaurant_id=restaurant_id,
            location_id=None,
            user_id=None,
            user=user,
            validate_only=validate_only,
        )
    
    def export_settings(
        self,
        scope: SettingScope,
        categories: Optional[List[SettingCategory]],
        include_sensitive: bool,
        include_metadata: bool,
        restaurant_id: Optional[int],
        user: User,
    ) -> Dict[str, Any]:
        """Export settings to JSON format"""
        
        # Query settings
        settings_query = self.db.query(Setting).filter(Setting.scope == scope)
        
        if restaurant_id:
            settings_query = settings_query.filter(Setting.restaurant_id == restaurant_id)
        
        if categories:
            settings_query = settings_query.filter(Setting.category.in_(categories))
        
        if not include_sensitive:
            settings_query = settings_query.filter(Setting.is_sensitive == False)
        
        settings = settings_query.all()
        
        # Build export data
        export_data = {
            "version": "1.0",
            "exported_at": datetime.utcnow().isoformat(),
            "scope": scope.value,
            "restaurant_id": restaurant_id,
            "settings": {}
        }
        
        for setting in settings:
            value = json.loads(setting.value) if setting.value else None
            export_data["settings"][setting.key] = value
            
            if include_metadata:
                export_data.setdefault("metadata", {})[setting.key] = {
                    "category": setting.category.value,
                    "label": setting.label,
                    "description": setting.description,
                    "value_type": setting.value_type.value,
                    "is_sensitive": setting.is_sensitive,
                    "modified_at": setting.modified_at.isoformat() if setting.modified_at else None,
                }
        
        return export_data
    
    def search_settings(
        self,
        query: str,
        scope: Optional[SettingScope],
        categories: Optional[List[SettingCategory]],
        include_advanced: bool,
        user: User,
    ) -> List[Dict[str, Any]]:
        """Search settings by key, label, or description"""
        
        # Get all definitions matching search
        definitions_query = self.db.query(SettingDefinition).filter(
            SettingDefinition.is_active == True
        )
        
        if scope:
            definitions_query = definitions_query.filter(SettingDefinition.scope == scope)
        
        if categories:
            definitions_query = definitions_query.filter(
                SettingDefinition.category.in_(categories)
            )
        
        # Search in key, label, and description
        search_pattern = f"%{query.lower()}%"
        definitions_query = definitions_query.filter(
            or_(
                func.lower(SettingDefinition.key).like(search_pattern),
                func.lower(SettingDefinition.label).like(search_pattern),
                func.lower(SettingDefinition.description).like(search_pattern),
            )
        )
        
        definitions = definitions_query.all()
        
        # Get current values for found settings
        setting_keys = [d.key for d in definitions]
        settings = self.db.query(Setting).filter(
            Setting.key.in_(setting_keys)
        ).all()
        settings_map = {s.key: s for s in settings}
        
        # Build search results
        results = []
        for definition in definitions:
            # Skip advanced if not requested
            if not include_advanced and definition.ui_config.get("advanced", False):
                continue
            
            setting = settings_map.get(definition.key)
            ui_field = self._create_ui_field(setting, definition)
            
            results.append({
                "key": definition.key,
                "label": definition.label,
                "description": definition.description,
                "category": definition.category.value,
                "value": ui_field.value,
                "field_type": ui_field.field_type.value,
                "is_modified": ui_field.is_modified,
            })
        
        return results
    
    def compare_with_template(
        self,
        template_id: int,
        scope: SettingScope,
        restaurant_id: Optional[int],
        user: User,
    ) -> SettingsComparisonResponse:
        """Compare current settings with a template"""
        
        # Get template
        template = self.db.query(ConfigurationTemplate).filter(
            ConfigurationTemplate.id == template_id
        ).first()
        
        if not template:
            raise NotFoundError("Configuration template", template_id)
        
        # Get current settings
        current_settings_query = self.db.query(Setting).filter(
            Setting.scope == scope
        )
        
        if restaurant_id:
            current_settings_query = current_settings_query.filter(
                Setting.restaurant_id == restaurant_id
            )
        
        current_settings = current_settings_query.all()
        current_map = {s.key: json.loads(s.value) if s.value else None for s in current_settings}
        
        # Compare with template
        differences = []
        template_settings = template.settings
        
        # Find differences and missing settings
        for key, template_value in template_settings.items():
            current_value = current_map.get(key)
            
            if key not in current_map:
                # Setting is missing
                definition = self.db.query(SettingDefinition).filter(
                    SettingDefinition.key == key
                ).first()
                
                differences.append(SettingDifference(
                    key=key,
                    label=definition.label if definition else key,
                    current_value=None,
                    template_value=template_value,
                    is_missing=True,
                    category=definition.category if definition else SettingCategory.GENERAL,
                ))
            elif current_value != template_value:
                # Values differ
                definition = self.db.query(SettingDefinition).filter(
                    SettingDefinition.key == key
                ).first()
                
                differences.append(SettingDifference(
                    key=key,
                    label=definition.label if definition else key,
                    current_value=current_value,
                    template_value=template_value,
                    category=definition.category if definition else SettingCategory.GENERAL,
                ))
        
        # Find extra settings (in current but not in template)
        for key, current_value in current_map.items():
            if key not in template_settings:
                setting = next(s for s in current_settings if s.key == key)
                differences.append(SettingDifference(
                    key=key,
                    label=setting.label,
                    current_value=current_value,
                    template_value=None,
                    is_extra=True,
                    category=setting.category,
                ))
        
        # Count differences
        missing_count = sum(1 for d in differences if d.is_missing)
        extra_count = sum(1 for d in differences if d.is_extra)
        different_count = len(differences) - missing_count - extra_count
        
        return SettingsComparisonResponse(
            template_name=template.name,
            template_description=template.description,
            differences=differences,
            missing_count=missing_count,
            extra_count=extra_count,
            different_count=different_count,
            can_apply=True,  # TODO: Check permissions
        )
    
    def get_pending_changes(
        self,
        scope: SettingScope,
        restaurant_id: Optional[int],
        user: User,
    ) -> Dict[str, Any]:
        """Get settings with pending changes or requiring restart"""
        
        # Get settings that require restart
        restart_settings = self.db.query(Setting).join(
            SettingDefinition,
            Setting.key == SettingDefinition.key
        ).filter(
            and_(
                Setting.scope == scope,
                SettingDefinition.requires_restart == True,
                Setting.modified_at > Setting.created_at,  # Has been modified
            )
        )
        
        if restaurant_id:
            restart_settings = restart_settings.filter(
                Setting.restaurant_id == restaurant_id
            )
        
        restart_settings = restart_settings.all()
        
        # Build pending changes list
        pending_changes = []
        for setting in restart_settings:
            definition = self.db.query(SettingDefinition).filter(
                SettingDefinition.key == setting.key
            ).first()
            
            # Get original value from history
            original_history = self.db.query(SettingHistory).filter(
                and_(
                    SettingHistory.setting_key == setting.key,
                    SettingHistory.change_type == "create",
                )
            ).order_by(SettingHistory.changed_at).first()
            
            original_value = json.loads(original_history.new_value) if original_history else None
            current_value = json.loads(setting.value) if setting.value else None
            
            pending_changes.append(PendingChange(
                key=setting.key,
                label=setting.label,
                current_value=original_value,
                new_value=current_value,
                requires_restart=True,
                requires_confirmation=definition.is_sensitive if definition else False,
                impact_description=f"Changing {setting.label} requires a system restart",
            ))
        
        return {
            "requires_restart": len(pending_changes) > 0,
            "settings": pending_changes,
            "restart_message": "The following settings require a restart to take effect",
            "can_restart_now": False,  # TODO: Check system status
            "estimated_downtime_seconds": 60,  # TODO: Calculate based on system
        }
    
    def get_ui_metadata(self, user: User) -> UIMetadataResponse:
        """Get UI metadata for settings interface"""
        
        # Categories
        categories = [
            {
                "key": cat.value,
                "label": cat.value.replace("_", " ").title(),
                "icon": self._get_category_icon(cat),
                "description": self._get_category_description(cat),
            }
            for cat in SettingCategory
        ]
        
        # Scopes
        scopes = [
            {
                "key": scope.value,
                "label": scope.value.title(),
                "description": self._get_scope_description(scope),
                "requires_permission": self._get_scope_permission(scope),
            }
            for scope in SettingScope
        ]
        
        # Field types
        field_types = [
            {
                "key": ft.value,
                "label": ft.value.replace("_", " ").title(),
                "component": self._get_field_component(ft),
            }
            for ft in UIFieldType
        ]
        
        # Permissions
        permissions = {
            "can_view": user.has_permission("settings.view"),
            "can_edit": user.has_permission("settings.manage"),
            "can_reset": user.has_permission("settings.reset"),
            "can_export": user.has_permission("settings.export"),
            "can_import": user.has_permission("settings.import"),
            "can_manage_system": user.has_permission("system.admin"),
        }
        
        # Feature flags
        feature_flags = {
            "advanced_settings": True,
            "bulk_operations": True,
            "import_export": True,
            "presets": True,
            "templates": True,
        }
        
        # UI configuration
        ui_config = {
            "auto_save": False,
            "confirm_reset": True,
            "show_tooltips": True,
            "group_by_category": True,
            "search_enabled": True,
            "history_enabled": True,
        }
        
        return UIMetadataResponse(
            categories=categories,
            scopes=scopes,
            field_types=field_types,
            validation_rules={},  # TODO: Add validation rule definitions
            presets=list(self.presets.keys()),
            permissions=permissions,
            feature_flags=feature_flags,
            ui_config=ui_config,
        )
    
    # Helper methods
    
    def _create_ui_field(
        self,
        setting: Optional[Setting],
        definition: SettingDefinition,
    ) -> SettingUIField:
        """Create UI field from setting and definition"""
        
        value = None
        is_modified = False
        
        if setting:
            value = json.loads(setting.value) if setting.value else None
            is_modified = setting.modified_at > setting.created_at
        else:
            value = json.loads(definition.default_value) if definition.default_value else None
        
        # Map setting type to UI field type
        field_type = self._map_to_ui_field_type(definition.value_type)
        
        # Build UI config
        ui_config = definition.ui_config or {}
        
        return SettingUIField(
            key=definition.key,
            label=definition.label,
            description=definition.description,
            help_text=definition.help_text,
            value=value,
            default_value=json.loads(definition.default_value) if definition.default_value else None,
            field_type=field_type,
            is_required=definition.is_required,
            is_sensitive=definition.is_sensitive,
            is_advanced=ui_config.get("advanced", False),
            validation_rules=definition.validation_rules or {},
            allowed_values=definition.allowed_values,
            placeholder=ui_config.get("placeholder"),
            prefix=ui_config.get("prefix"),
            suffix=ui_config.get("suffix"),
            icon=ui_config.get("icon"),
            columns=ui_config.get("columns", 12),
            depends_on=definition.depends_on,
            is_modified=is_modified,
            requires_restart=definition.requires_restart,
        )
    
    def _map_to_ui_field_type(self, setting_type: SettingType) -> UIFieldType:
        """Map setting type to UI field type"""
        
        mapping = {
            SettingType.STRING: UIFieldType.TEXT,
            SettingType.INTEGER: UIFieldType.NUMBER,
            SettingType.FLOAT: UIFieldType.NUMBER,
            SettingType.BOOLEAN: UIFieldType.TOGGLE,
            SettingType.JSON: UIFieldType.JSON,
            SettingType.DATETIME: UIFieldType.DATETIME,
            SettingType.ENUM: UIFieldType.SELECT,
            SettingType.FILE: UIFieldType.FILE,
            SettingType.SECRET: UIFieldType.PASSWORD,
        }
        
        return mapping.get(setting_type, UIFieldType.TEXT)
    
    def _get_category_icon(self, category: SettingCategory) -> str:
        """Get icon for category"""
        
        icons = {
            SettingCategory.GENERAL: "settings",
            SettingCategory.OPERATIONS: "business",
            SettingCategory.PAYMENT: "payment",
            SettingCategory.POS_INTEGRATION: "point_of_sale",
            SettingCategory.NOTIFICATIONS: "notifications",
            SettingCategory.SECURITY: "security",
            SettingCategory.DISPLAY: "display_settings",
            SettingCategory.FEATURES: "featured_play_list",
            SettingCategory.API: "api",
            SettingCategory.COMPLIANCE: "gavel",
        }
        
        return icons.get(category, "settings")
    
    def _get_category_description(self, category: SettingCategory) -> str:
        """Get description for category"""
        
        descriptions = {
            SettingCategory.GENERAL: "Basic restaurant configuration",
            SettingCategory.OPERATIONS: "Operational settings and workflows",
            SettingCategory.PAYMENT: "Payment processing configuration",
            SettingCategory.POS_INTEGRATION: "Point of Sale system integration",
            SettingCategory.NOTIFICATIONS: "Notification preferences and channels",
            SettingCategory.SECURITY: "Security and access control",
            SettingCategory.DISPLAY: "User interface and display options",
            SettingCategory.FEATURES: "Feature toggles and capabilities",
            SettingCategory.API: "API keys and webhooks",
            SettingCategory.COMPLIANCE: "Compliance and regulatory settings",
        }
        
        return descriptions.get(category, "")
    
    def _validate_type(self, value: Any, setting_type: SettingType) -> None:
        """Validate value matches expected type"""
        
        if setting_type == SettingType.STRING and not isinstance(value, str):
            raise ValueError("Value must be a string")
        elif setting_type == SettingType.INTEGER and not isinstance(value, int):
            raise ValueError("Value must be an integer")
        elif setting_type == SettingType.FLOAT and not isinstance(value, (int, float)):
            raise ValueError("Value must be a number")
        elif setting_type == SettingType.BOOLEAN and not isinstance(value, bool):
            raise ValueError("Value must be a boolean")
        elif setting_type == SettingType.JSON and not isinstance(value, (dict, list)):
            raise ValueError("Value must be a JSON object or array")
    
    def _load_presets(self) -> Dict[str, Dict[str, Any]]:
        """Load predefined settings presets"""
        
        return {
            "quick_service": {
                "name": "Quick Service",
                "description": "Optimized for fast food and quick service restaurants",
                "settings": {
                    "order_timeout_minutes": 15,
                    "table_turn_time_target": 30,
                    "auto_print_receipts": True,
                    "require_table_number": False,
                    "enable_self_service": True,
                    "default_tip_percentages": [10, 15, 20],
                }
            },
            "fine_dining": {
                "name": "Fine Dining",
                "description": "Optimized for upscale dining experience",
                "settings": {
                    "order_timeout_minutes": 120,
                    "table_turn_time_target": 90,
                    "auto_print_receipts": False,
                    "require_table_number": True,
                    "enable_self_service": False,
                    "default_tip_percentages": [18, 20, 25],
                    "enable_wine_pairing": True,
                    "enable_course_management": True,
                }
            },
            "casual_dining": {
                "name": "Casual Dining",
                "description": "Balanced settings for casual restaurants",
                "settings": {
                    "order_timeout_minutes": 60,
                    "table_turn_time_target": 60,
                    "auto_print_receipts": True,
                    "require_table_number": True,
                    "enable_self_service": False,
                    "default_tip_percentages": [15, 18, 20],
                }
            },
            "takeout_focused": {
                "name": "Takeout & Delivery",
                "description": "Optimized for takeout and delivery operations",
                "settings": {
                    "order_timeout_minutes": 30,
                    "enable_online_ordering": True,
                    "auto_confirm_orders": True,
                    "delivery_radius_miles": 5,
                    "pickup_time_minutes": 20,
                    "enable_order_tracking": True,
                    "require_phone_verification": True,
                }
            },
            "bar_lounge": {
                "name": "Bar & Lounge",
                "description": "Optimized for bars and lounges",
                "settings": {
                    "enable_tab_management": True,
                    "auto_gratuity_percentage": 18,
                    "auto_gratuity_party_size": 6,
                    "last_call_minutes": 30,
                    "enable_age_verification": True,
                    "track_drink_limits": True,
                }
            },
        }
    
    def _get_or_create_setting(
        self,
        key: str,
        scope: SettingScope,
        restaurant_id: Optional[int],
        location_id: Optional[int],
        user_id: Optional[int],
    ) -> Setting:
        """Get existing setting or create new one"""
        
        setting = self.db.query(Setting).filter(
            and_(
                Setting.key == key,
                Setting.scope == scope,
                Setting.restaurant_id == restaurant_id,
                Setting.location_id == location_id,
                Setting.user_id == user_id,
            )
        ).first()
        
        if not setting:
            definition = self.db.query(SettingDefinition).filter(
                SettingDefinition.key == key
            ).first()
            
            if not definition:
                raise NotFoundError("Setting definition", key)
            
            setting = Setting(
                key=key,
                category=definition.category,
                scope=scope,
                restaurant_id=restaurant_id,
                location_id=location_id,
                user_id=user_id,
                value_type=definition.value_type,
                label=definition.label,
                description=definition.description,
                is_sensitive=definition.is_sensitive,
                validation_rules=definition.validation_rules,
                allowed_values=definition.allowed_values,
                default_value=definition.default_value,
                ui_config=definition.ui_config,
            )
        
        return setting
    
    def _log_setting_change(
        self,
        setting: Setting,
        old_value: Optional[str],
        new_value: str,
        user: User,
        reason: Optional[str] = None,
    ) -> None:
        """Log setting change to history"""
        
        history = SettingHistory(
            setting_key=setting.key,
            scope=setting.scope,
            restaurant_id=setting.restaurant_id,
            location_id=setting.location_id,
            user_id=setting.user_id,
            old_value=old_value,
            new_value=new_value,
            change_type="update" if old_value else "create",
            changed_by_id=user.id,
            change_reason=reason,
        )
        
        self.db.add(history)
    
    def _check_dependencies(
        self,
        settings: Dict[str, Any],
        definitions: Dict[str, SettingDefinition],
    ) -> bool:
        """Check if all dependencies are met"""
        
        for key, value in settings.items():
            definition = definitions.get(key)
            if definition and definition.depends_on:
                for dep_key in definition.depends_on:
                    if dep_key not in settings:
                        return False
        
        return True
    
    def _check_conflicts(
        self,
        settings: Dict[str, Any],
        definitions: Dict[str, SettingDefinition],
    ) -> List[Dict[str, Any]]:
        """Check for conflicting settings"""
        
        conflicts = []
        
        for key, value in settings.items():
            definition = definitions.get(key)
            if definition and definition.conflicts_with:
                for conflict_key in definition.conflicts_with:
                    if conflict_key in settings:
                        conflicts.append({
                            "setting1": key,
                            "setting2": conflict_key,
                            "message": f"{key} conflicts with {conflict_key}",
                        })
        
        return conflicts
    
    def _apply_validation_rules(
        self,
        value: Any,
        rules: Dict[str, Any],
    ) -> List[ValidationError]:
        """Apply custom validation rules"""
        
        errors = []
        
        # Min/max validation
        if "min" in rules and value < rules["min"]:
            errors.append(ValidationError(
                field="value",
                message=f"Value must be at least {rules['min']}",
                code="min_value",
            ))
        
        if "max" in rules and value > rules["max"]:
            errors.append(ValidationError(
                field="value",
                message=f"Value must be at most {rules['max']}",
                code="max_value",
            ))
        
        # Pattern validation
        if "pattern" in rules and isinstance(value, str):
            import re
            if not re.match(rules["pattern"], value):
                errors.append(ValidationError(
                    field="value",
                    message=f"Value must match pattern: {rules['pattern']}",
                    code="pattern_mismatch",
                ))
        
        return errors
    
    def _get_scope_description(self, scope: SettingScope) -> str:
        """Get description for scope"""
        
        descriptions = {
            SettingScope.SYSTEM: "Global system-wide settings",
            SettingScope.RESTAURANT: "Restaurant-specific settings",
            SettingScope.LOCATION: "Location-specific settings",
            SettingScope.USER: "Individual user preferences",
        }
        
        return descriptions.get(scope, "")
    
    def _get_scope_permission(self, scope: SettingScope) -> str:
        """Get required permission for scope"""
        
        permissions = {
            SettingScope.SYSTEM: "system.admin",
            SettingScope.RESTAURANT: "settings.manage",
            SettingScope.LOCATION: "settings.manage",
            SettingScope.USER: None,  # Users can manage their own
        }
        
        return permissions.get(scope)
    
    def _get_field_component(self, field_type: UIFieldType) -> str:
        """Get UI component name for field type"""
        
        components = {
            UIFieldType.TEXT: "TextField",
            UIFieldType.NUMBER: "NumberField",
            UIFieldType.TOGGLE: "Switch",
            UIFieldType.SELECT: "Select",
            UIFieldType.MULTISELECT: "MultiSelect",
            UIFieldType.TEXTAREA: "TextArea",
            UIFieldType.JSON: "JsonEditor",
            UIFieldType.DATE: "DatePicker",
            UIFieldType.TIME: "TimePicker",
            UIFieldType.DATETIME: "DateTimePicker",
            UIFieldType.COLOR: "ColorPicker",
            UIFieldType.FILE: "FileUpload",
            UIFieldType.PASSWORD: "PasswordField",
            UIFieldType.EMAIL: "EmailField",
            UIFieldType.URL: "UrlField",
            UIFieldType.PHONE: "PhoneField",
            UIFieldType.CURRENCY: "CurrencyField",
            UIFieldType.PERCENTAGE: "PercentageField",
        }
        
        return components.get(field_type, "TextField")