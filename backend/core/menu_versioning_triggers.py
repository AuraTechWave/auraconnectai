# backend/core/menu_versioning_triggers.py

from sqlalchemy.orm import Session
from sqlalchemy import event
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone
import json

from backend.core.menu_models import MenuCategory, MenuItem, ModifierGroup, Modifier
from backend.core.menu_versioning_service import MenuVersioningService
from backend.core.menu_versioning_schemas import CreateVersionRequest, VersionType, ChangeType
from backend.core.menu_versioning_models import MenuAuditLog


class MenuVersioningTriggers:
    """
    Handles automated versioning triggers based on menu changes.
    This class manages when and how automatic versions are created.
    """
    
    def __init__(self):
        self.auto_version_threshold = 10  # Number of changes before auto-version
        self.change_buffer: List[Dict[str, Any]] = []
        self.enabled = True
    
    def setup_event_listeners(self):
        """Setup SQLAlchemy event listeners for menu changes"""
        
        # Category events
        event.listen(MenuCategory, 'after_insert', self._on_category_insert)
        event.listen(MenuCategory, 'after_update', self._on_category_update)
        event.listen(MenuCategory, 'after_delete', self._on_category_delete)
        
        # Menu item events
        event.listen(MenuItem, 'after_insert', self._on_item_insert)
        event.listen(MenuItem, 'after_update', self._on_item_update)
        event.listen(MenuItem, 'after_delete', self._on_item_delete)
        
        # Modifier group events
        event.listen(ModifierGroup, 'after_insert', self._on_modifier_group_insert)
        event.listen(ModifierGroup, 'after_update', self._on_modifier_group_update)
        event.listen(ModifierGroup, 'after_delete', self._on_modifier_group_delete)
        
        # Modifier events
        event.listen(Modifier, 'after_insert', self._on_modifier_insert)
        event.listen(Modifier, 'after_update', self._on_modifier_update)
        event.listen(Modifier, 'after_delete', self._on_modifier_delete)
    
    def should_create_auto_version(self, change_type: str, entity_type: str, changes: Dict[str, Any]) -> bool:
        """Determine if an automatic version should be created based on the change"""
        
        if not self.enabled:
            return False
        
        # Create version for critical changes
        critical_changes = [
            'price_change',
            'availability_change',
            'menu_restructure'
        ]
        
        if change_type in critical_changes:
            return True
        
        # Create version when buffer threshold is reached
        if len(self.change_buffer) >= self.auto_version_threshold:
            return True
        
        # Create version for significant batch operations
        if 'batch_operation' in changes and changes.get('affected_count', 0) > 5:
            return True
        
        return False
    
    def create_auto_version(self, db: Session, trigger_reason: str, user_id: int = 1) -> Optional[int]:
        """Create an automatic version with buffered changes"""
        
        try:
            service = MenuVersioningService(db)
            
            # Summarize changes for version description
            change_summary = self._summarize_changes()
            
            request = CreateVersionRequest(
                version_name=f"Auto-save {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M')}",
                description=f"Automatic version created due to: {trigger_reason}. {change_summary}",
                version_type=VersionType.AUTO_SAVE,
                include_inactive=False
            )
            
            version = service.create_version(request, user_id)
            
            # Clear the buffer after successful version creation
            self.change_buffer.clear()
            
            return version.id
            
        except Exception as e:
            # Log error but don't fail the original operation
            print(f"Failed to create auto-version: {str(e)}")
            return None
    
    def add_change_to_buffer(self, change_data: Dict[str, Any]):
        """Add a change to the buffer for potential auto-versioning"""
        change_data['timestamp'] = datetime.now(timezone.utc).isoformat()
        self.change_buffer.append(change_data)
        
        # Keep buffer size manageable
        if len(self.change_buffer) > 50:
            self.change_buffer = self.change_buffer[-25:]  # Keep last 25 changes
    
    def _summarize_changes(self) -> str:
        """Create a summary of buffered changes"""
        if not self.change_buffer:
            return "No changes recorded"
        
        change_types = {}
        entity_types = {}
        
        for change in self.change_buffer:
            change_type = change.get('change_type', 'unknown')
            entity_type = change.get('entity_type', 'unknown')
            
            change_types[change_type] = change_types.get(change_type, 0) + 1
            entity_types[entity_type] = entity_types.get(entity_type, 0) + 1
        
        summary_parts = []
        
        if change_types:
            changes_str = ', '.join([f"{count} {type}" for type, count in change_types.items()])
            summary_parts.append(f"Changes: {changes_str}")
        
        if entity_types:
            entities_str = ', '.join([f"{count} {type}" for type, count in entity_types.items()])
            summary_parts.append(f"Entities: {entities_str}")
        
        return '; '.join(summary_parts)
    
    # Event handlers for categories
    def _on_category_insert(self, mapper, connection, target):
        """Handle category insertion"""
        change_data = {
            'entity_type': 'category',
            'entity_id': target.id,
            'entity_name': target.name,
            'change_type': 'create',
            'operation': 'insert',
            'new_values': {
                'name': target.name,
                'description': target.description,
                'is_active': target.is_active
            }
        }
        
        self.add_change_to_buffer(change_data)
        
        if self.should_create_auto_version('create', 'category', change_data):
            # Note: We can't access the session here, so we'll need to handle this differently
            # This would typically be handled by a background task or a post-commit hook
            pass
    
    def _on_category_update(self, mapper, connection, target):
        """Handle category updates"""
        # Get the old values from the session
        state = target.__dict__
        history = {}
        
        # Check for significant changes
        critical_fields = ['name', 'is_active', 'parent_category_id']
        has_critical_change = any(field in state.get('_sa_instance_state', {}).get('committed_state', {}) 
                                 for field in critical_fields)
        
        change_data = {
            'entity_type': 'category',
            'entity_id': target.id,
            'entity_name': target.name,
            'change_type': 'update',
            'operation': 'update',
            'has_critical_change': has_critical_change,
            'new_values': {
                'name': target.name,
                'description': target.description,
                'is_active': target.is_active
            }
        }
        
        self.add_change_to_buffer(change_data)
    
    def _on_category_delete(self, mapper, connection, target):
        """Handle category deletion"""
        change_data = {
            'entity_type': 'category',
            'entity_id': target.id,
            'entity_name': target.name,
            'change_type': 'delete',
            'operation': 'delete',
            'old_values': {
                'name': target.name,
                'description': target.description,
                'is_active': target.is_active
            }
        }
        
        self.add_change_to_buffer(change_data)
        
        # Deletion is always significant
        if self.should_create_auto_version('delete', 'category', change_data):
            pass
    
    # Event handlers for menu items
    def _on_item_insert(self, mapper, connection, target):
        """Handle menu item insertion"""
        change_data = {
            'entity_type': 'menu_item',
            'entity_id': target.id,
            'entity_name': target.name,
            'change_type': 'create',
            'operation': 'insert',
            'new_values': {
                'name': target.name,
                'price': target.price,
                'category_id': target.category_id,
                'is_active': target.is_active,
                'is_available': target.is_available
            }
        }
        
        self.add_change_to_buffer(change_data)
    
    def _on_item_update(self, mapper, connection, target):
        """Handle menu item updates"""
        # Price changes are critical
        change_type = 'update'
        if hasattr(target, '_price_changed') and target._price_changed:
            change_type = 'price_change'
        elif hasattr(target, '_availability_changed') and target._availability_changed:  
            change_type = 'availability_change'
        
        change_data = {
            'entity_type': 'menu_item',
            'entity_id': target.id,
            'entity_name': target.name,
            'change_type': change_type,
            'operation': 'update',
            'new_values': {
                'name': target.name,
                'price': target.price,
                'is_active': target.is_active,
                'is_available': target.is_available
            }
        }
        
        self.add_change_to_buffer(change_data)
        
        if self.should_create_auto_version(change_type, 'menu_item', change_data):
            pass
    
    def _on_item_delete(self, mapper, connection, target):
        """Handle menu item deletion"""
        change_data = {
            'entity_type': 'menu_item',
            'entity_id': target.id,
            'entity_name': target.name,
            'change_type': 'delete',
            'operation': 'delete',
            'old_values': {
                'name': target.name,
                'price': target.price,
                'category_id': target.category_id
            }
        }
        
        self.add_change_to_buffer(change_data)
    
    # Event handlers for modifier groups
    def _on_modifier_group_insert(self, mapper, connection, target):
        """Handle modifier group insertion"""
        change_data = {
            'entity_type': 'modifier_group',
            'entity_id': target.id,
            'entity_name': target.name,
            'change_type': 'create',
            'operation': 'insert',
            'new_values': {
                'name': target.name,
                'selection_type': target.selection_type,
                'is_required': target.is_required,
                'is_active': target.is_active
            }
        }
        
        self.add_change_to_buffer(change_data)
    
    def _on_modifier_group_update(self, mapper, connection, target):
        """Handle modifier group updates"""
        change_data = {
            'entity_type': 'modifier_group',
            'entity_id': target.id,
            'entity_name': target.name,
            'change_type': 'modifier_change',
            'operation': 'update',
            'new_values': {
                'name': target.name,
                'selection_type': target.selection_type,
                'is_required': target.is_required,
                'is_active': target.is_active
            }
        }
        
        self.add_change_to_buffer(change_data)
    
    def _on_modifier_group_delete(self, mapper, connection, target):
        """Handle modifier group deletion"""
        change_data = {
            'entity_type': 'modifier_group',
            'entity_id': target.id,
            'entity_name': target.name,
            'change_type': 'delete',
            'operation': 'delete',
            'old_values': {
                'name': target.name,
                'selection_type': target.selection_type,
                'is_required': target.is_required
            }
        }
        
        self.add_change_to_buffer(change_data)
    
    # Event handlers for modifiers
    def _on_modifier_insert(self, mapper, connection, target):
        """Handle modifier insertion"""
        change_data = {
            'entity_type': 'modifier',
            'entity_id': target.id,
            'entity_name': target.name,
            'change_type': 'create',
            'operation': 'insert',
            'new_values': {
                'name': target.name,
                'price_adjustment': target.price_adjustment,
                'is_active': target.is_active
            }
        }
        
        self.add_change_to_buffer(change_data)
    
    def _on_modifier_update(self, mapper, connection, target):
        """Handle modifier updates"""
        # Price adjustment changes are critical
        change_type = 'modifier_change'
        if hasattr(target, '_price_adjustment_changed') and target._price_adjustment_changed:
            change_type = 'price_change'
        
        change_data = {
            'entity_type': 'modifier',
            'entity_id': target.id,
            'entity_name': target.name,
            'change_type': change_type,
            'operation': 'update',
            'new_values': {
                'name': target.name,
                'price_adjustment': target.price_adjustment,
                'is_active': target.is_active
            }
        }
        
        self.add_change_to_buffer(change_data)
    
    def _on_modifier_delete(self, mapper, connection, target):
        """Handle modifier deletion"""
        change_data = {
            'entity_type': 'modifier',
            'entity_id': target.id,
            'entity_name': target.name,
            'change_type': 'delete',
            'operation': 'delete',
            'old_values': {
                'name': target.name,
                'price_adjustment': target.price_adjustment
            }
        }
        
        self.add_change_to_buffer(change_data)


# Global instance
menu_versioning_triggers = MenuVersioningTriggers()


def init_versioning_triggers():
    """Initialize the versioning trigger system"""
    menu_versioning_triggers.setup_event_listeners()


def create_manual_version_on_bulk_change(db: Session, operation: str, affected_count: int, user_id: int = 1):
    """
    Manually trigger version creation for bulk operations.
    This should be called after bulk operations in the API endpoints.
    """
    change_data = {
        'batch_operation': True,
        'operation': operation,
        'affected_count': affected_count,
        'entity_type': 'bulk_operation'
    }
    
    if menu_versioning_triggers.should_create_auto_version('bulk_operation', 'multiple', change_data):
        version_id = menu_versioning_triggers.create_auto_version(
            db, 
            f"Bulk {operation} operation affecting {affected_count} items",
            user_id
        )
        return version_id
    
    return None


def disable_auto_versioning():
    """Disable automatic versioning (useful for migrations or bulk imports)"""
    menu_versioning_triggers.enabled = False


def enable_auto_versioning():
    """Re-enable automatic versioning"""
    menu_versioning_triggers.enabled = True


def get_change_buffer_status() -> Dict[str, Any]:
    """Get current status of the change buffer"""
    return {
        'buffer_size': len(menu_versioning_triggers.change_buffer),
        'threshold': menu_versioning_triggers.auto_version_threshold,
        'enabled': menu_versioning_triggers.enabled,
        'recent_changes': menu_versioning_triggers.change_buffer[-5:] if menu_versioning_triggers.change_buffer else []
    }