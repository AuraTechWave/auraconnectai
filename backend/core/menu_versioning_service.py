# backend/core/menu_versioning_service.py

from sqlalchemy.orm import Session
from sqlalchemy import desc, and_, or_, func
from typing import List, Optional, Dict, Any, Tuple
from datetime import datetime, timezone
import json
import uuid
from contextlib import contextmanager

from core.menu_versioning_models import (
    MenuVersion, MenuCategoryVersion, MenuItemVersion, 
    ModifierGroupVersion, ModifierVersion, MenuItemModifierVersion,
    MenuAuditLog, MenuVersionSchedule, MenuVersionComparison,
    VersionType, ChangeType
)
from core.menu_models import (
    MenuCategory, MenuItem, ModifierGroup, Modifier, MenuItemModifier
)
from core.menu_versioning_schemas import (
    CreateVersionRequest, PublishVersionRequest, RollbackVersionRequest,
    VersionComparisonRequest, MenuVersionWithDetails, MenuVersionComparison,
    FieldComparison, EntityComparison, BulkChangeRequest
)


class MenuVersioningService:
    
    def __init__(self, db: Session):
        self.db = db
    
    @contextmanager
    def audit_context(self, user_id: int, action: str, session_id: Optional[str] = None):
        """Context manager for audit trail tracking"""
        batch_id = str(uuid.uuid4())
        audit_entries = []
        
        try:
            yield audit_entries
            # Commit all audit entries at once
            for entry in audit_entries:
                entry.batch_id = batch_id
                self.db.add(entry)
            self.db.commit()
        except Exception as e:
            self.db.rollback()
            raise e
    
    def create_version(self, request: CreateVersionRequest, user_id: int) -> MenuVersion:
        """Create a new menu version from current active menu state"""
        
        # Generate version number
        version_number = self._generate_version_number(request.version_type)
        
        # Create the version record
        menu_version = MenuVersion(
            version_number=version_number,
            version_name=request.version_name,
            description=request.description,
            version_type=request.version_type,
            created_by=user_id,
            scheduled_publish_at=request.scheduled_publish_at
        )
        
        self.db.add(menu_version)
        self.db.flush()  # Get the ID
        
        with self.audit_context(user_id, "create_version") as audit_entries:
            # Snapshot current menu state
            categories = self._snapshot_categories(menu_version.id, request.include_inactive, audit_entries)
            items = self._snapshot_items(menu_version.id, request.include_inactive, audit_entries)
            modifiers = self._snapshot_modifiers(menu_version.id, request.include_inactive, audit_entries)
            
            # Update version metadata
            menu_version.total_categories = len(categories)
            menu_version.total_items = len(items)
            menu_version.total_modifiers = sum(len(mg.modifier_versions) for mg in modifiers)
            
            # Create main audit entry
            audit_entries.append(MenuAuditLog(
                menu_version_id=menu_version.id,
                action="create_version",
                entity_type="menu_version",
                entity_id=menu_version.id,
                entity_name=menu_version.version_name or menu_version.version_number,
                change_type=ChangeType.CREATE,
                new_values={
                    "version_number": version_number,
                    "version_name": request.version_name,
                    "description": request.description,
                    "version_type": request.version_type.value,
                    "total_categories": menu_version.total_categories,
                    "total_items": menu_version.total_items,
                    "total_modifiers": menu_version.total_modifiers
                },
                change_summary=f"Created new menu version {version_number}",
                user_id=user_id
            ))
        
        return menu_version
    
    def publish_version(self, version_id: int, request: PublishVersionRequest, user_id: int) -> MenuVersion:
        """Publish a menu version (make it active)"""
        
        version = self.db.query(MenuVersion).filter(MenuVersion.id == version_id).first()
        if not version:
            raise ValueError("Version not found")
        
        if version.is_published and not request.force:
            raise ValueError("Version is already published")
        
        with self.audit_context(user_id, "publish_version") as audit_entries:
            # Deactivate current active version
            current_active = self.db.query(MenuVersion).filter(MenuVersion.is_active == True).first()
            if current_active:
                current_active.is_active = False
                audit_entries.append(MenuAuditLog(
                    menu_version_id=current_active.id,
                    action="deactivate_version",
                    entity_type="menu_version",
                    entity_id=current_active.id,
                    entity_name=current_active.version_name or current_active.version_number,
                    change_type=ChangeType.DEACTIVATE,
                    old_values={"is_active": True},
                    new_values={"is_active": False},
                    change_summary=f"Deactivated version {current_active.version_number}",
                    user_id=user_id
                ))
            
            # Activate new version
            version.is_active = True
            version.is_published = True
            version.published_at = request.scheduled_at or datetime.now(timezone.utc)
            
            audit_entries.append(MenuAuditLog(
                menu_version_id=version.id,
                action="publish_version",
                entity_type="menu_version",
                entity_id=version.id,
                entity_name=version.version_name or version.version_number,
                change_type=ChangeType.ACTIVATE,
                old_values={"is_active": False, "is_published": False},
                new_values={"is_active": True, "is_published": True, "published_at": version.published_at},
                change_summary=f"Published and activated version {version.version_number}",
                user_id=user_id
            ))
            
            # Apply version changes to live menu
            self._apply_version_to_live_menu(version, audit_entries, user_id)
        
        return version
    
    def rollback_to_version(self, request: RollbackVersionRequest, user_id: int) -> MenuVersion:
        """Rollback to a previous version"""
        
        target_version = self.db.query(MenuVersion).filter(MenuVersion.id == request.target_version_id).first()
        if not target_version:
            raise ValueError("Target version not found")
        
        # Create backup of current state if requested
        backup_version = None
        if request.create_backup:
            backup_request = CreateVersionRequest(
                version_name=f"Backup before rollback to {target_version.version_number}",
                description=f"Automatic backup created before rollback. Reason: {request.rollback_reason}",
                version_type=VersionType.ROLLBACK
            )
            backup_version = self.create_version(backup_request, user_id)
        
        with self.audit_context(user_id, "rollback_version") as audit_entries:
            # Create new version based on target
            rollback_version = MenuVersion(
                version_number=self._generate_version_number(VersionType.ROLLBACK),
                version_name=f"Rollback to {target_version.version_number}",
                description=f"Rollback to version {target_version.version_number}. Reason: {request.rollback_reason}",
                version_type=VersionType.ROLLBACK,
                parent_version_id=target_version.id,
                created_by=user_id
            )
            
            self.db.add(rollback_version)
            self.db.flush()
            
            # Copy all data from target version
            self._copy_version_data(target_version, rollback_version, audit_entries, user_id)
            
            # Activate rollback version
            publish_request = PublishVersionRequest(force=True)
            self.publish_version(rollback_version.id, publish_request, user_id)
            
            audit_entries.append(MenuAuditLog(
                menu_version_id=rollback_version.id,
                action="rollback_version",
                entity_type="menu_version",
                entity_id=rollback_version.id,
                entity_name=rollback_version.version_name,
                change_type=ChangeType.UPDATE,
                new_values={
                    "target_version_id": request.target_version_id,
                    "rollback_reason": request.rollback_reason,
                    "backup_version_id": backup_version.id if backup_version else None
                },
                change_summary=f"Rolled back to version {target_version.version_number}",
                user_id=user_id
            ))
        
        return rollback_version
    
    def compare_versions(self, request: VersionComparisonRequest) -> MenuVersionComparison:
        """Compare two menu versions and return differences"""
        
        from_version = self.db.query(MenuVersion).filter(MenuVersion.id == request.from_version_id).first()
        to_version = self.db.query(MenuVersion).filter(MenuVersion.id == request.to_version_id).first()
        
        if not from_version or not to_version:
            raise ValueError("One or both versions not found")
        
        # Check if we have a cached comparison
        cached = self.db.query(MenuVersionComparison).filter(
            and_(
                MenuVersionComparison.from_version_id == request.from_version_id,
                MenuVersionComparison.to_version_id == request.to_version_id,
                or_(MenuVersionComparison.expires_at == None, MenuVersionComparison.expires_at > datetime.now(timezone.utc))
            )
        ).first()
        
        if cached:
            return MenuVersionComparison.parse_obj(cached.comparison_data)
        
        # Generate comparison
        comparison = self._generate_version_comparison(from_version, to_version, request)
        
        # Cache the result
        cache_entry = MenuVersionComparison(
            from_version_id=request.from_version_id,
            to_version_id=request.to_version_id,
            comparison_data=comparison.dict(),
            summary=comparison.summary,
            generated_by=1  # TODO: Get actual user ID
        )
        self.db.add(cache_entry)
        self.db.commit()
        
        return comparison
    
    def get_version_details(self, version_id: int) -> Optional[MenuVersionWithDetails]:
        """Get detailed information about a version"""
        
        version = self.db.query(MenuVersion).filter(MenuVersion.id == version_id).first()
        if not version:
            return None
        
        # Load related data
        categories = self.db.query(MenuCategoryVersion).filter(
            MenuCategoryVersion.menu_version_id == version_id
        ).all()
        
        items = self.db.query(MenuItemVersion).filter(
            MenuItemVersion.menu_version_id == version_id
        ).all()
        
        modifiers = self.db.query(ModifierGroupVersion).filter(
            ModifierGroupVersion.menu_version_id == version_id
        ).all()
        
        audit_entries = self.db.query(MenuAuditLog).filter(
            MenuAuditLog.menu_version_id == version_id
        ).order_by(desc(MenuAuditLog.created_at)).all()
        
        parent_version = None
        if version.parent_version_id:
            parent_version = self.db.query(MenuVersion).filter(
                MenuVersion.id == version.parent_version_id
            ).first()
        
        return MenuVersionWithDetails(
            **version.__dict__,
            categories=categories,
            items=items,
            modifiers=modifiers,
            audit_entries=audit_entries,
            parent_version=parent_version
        )
    
    def get_versions(self, page: int = 1, size: int = 20, version_type: Optional[VersionType] = None) -> Tuple[List[MenuVersion], int]:
        """Get paginated list of versions"""
        
        query = self.db.query(MenuVersion).filter(MenuVersion.deleted_at == None)
        
        if version_type:
            query = query.filter(MenuVersion.version_type == version_type)
        
        total = query.count()
        versions = query.order_by(desc(MenuVersion.created_at)).offset((page - 1) * size).limit(size).all()
        
        return versions, total
    
    def get_audit_logs(self, version_id: Optional[int] = None, page: int = 1, size: int = 50) -> Tuple[List[MenuAuditLog], int]:
        """Get paginated audit logs"""
        
        query = self.db.query(MenuAuditLog)
        
        if version_id:
            query = query.filter(MenuAuditLog.menu_version_id == version_id)
        
        total = query.count()
        logs = query.order_by(desc(MenuAuditLog.created_at)).offset((page - 1) * size).limit(size).all()
        
        return logs, total
    
    def bulk_change(self, request: BulkChangeRequest, user_id: int) -> Dict[str, Any]:
        """Apply bulk changes to menu entities"""
        
        with self.audit_context(user_id, f"bulk_change_{request.entity_type}") as audit_entries:
            results = {"updated": 0, "errors": []}
            
            if request.entity_type == "item":
                results = self._bulk_change_items(request, audit_entries, user_id)
            elif request.entity_type == "category":
                results = self._bulk_change_categories(request, audit_entries, user_id)
            elif request.entity_type == "modifier":
                results = self._bulk_change_modifiers(request, audit_entries, user_id)
            else:
                raise ValueError(f"Unsupported entity type: {request.entity_type}")
            
            return results
    
    # Private helper methods
    
    def _generate_version_number(self, version_type: VersionType) -> str:
        """Generate a unique version number"""
        now = datetime.now(timezone.utc)
        date_str = now.strftime("%Y%m%d")
        
        # Count existing versions for today
        count = self.db.query(MenuVersion).filter(
            MenuVersion.version_number.like(f"{date_str}%")
        ).count()
        
        sequence = f"{count + 1:03d}"
        prefix = {
            VersionType.MANUAL: "v",
            VersionType.SCHEDULED: "s",
            VersionType.ROLLBACK: "r",
            VersionType.MIGRATION: "m",
            VersionType.AUTO_SAVE: "a"
        }.get(version_type, "v")
        
        return f"{prefix}{date_str}-{sequence}"
    
    def _snapshot_categories(self, version_id: int, include_inactive: bool, audit_entries: List[MenuAuditLog]) -> List[MenuCategoryVersion]:
        """Create category snapshots for version"""
        
        query = self.db.query(MenuCategory).filter(MenuCategory.deleted_at == None)
        if not include_inactive:
            query = query.filter(MenuCategory.is_active == True)
        
        categories = query.all()
        category_versions = []
        
        for category in categories:
            category_version = MenuCategoryVersion(
                menu_version_id=version_id,
                original_category_id=category.id,
                name=category.name,
                description=category.description,
                display_order=category.display_order,
                is_active=category.is_active,
                parent_category_id=category.parent_category_id,
                image_url=category.image_url,
                change_type=ChangeType.CREATE,
                change_summary=f"Snapshot of category {category.name}"
            )
            
            self.db.add(category_version)
            category_versions.append(category_version)
        
        return category_versions
    
    def _snapshot_items(self, version_id: int, include_inactive: bool, audit_entries: List[MenuAuditLog]) -> List[MenuItemVersion]:
        """Create item snapshots for version"""
        
        query = self.db.query(MenuItem).filter(MenuItem.deleted_at == None)
        if not include_inactive:
            query = query.filter(MenuItem.is_active == True)
        
        items = query.all()
        item_versions = []
        
        for item in items:
            item_version = MenuItemVersion(
                menu_version_id=version_id,
                original_item_id=item.id,
                name=item.name,
                description=item.description,
                price=item.price,
                category_id=item.category_id,
                sku=item.sku,
                is_active=item.is_active,
                is_available=item.is_available,
                availability_start_time=item.availability_start_time,
                availability_end_time=item.availability_end_time,
                calories=item.calories,
                dietary_tags=item.dietary_tags,
                allergen_info=item.allergens,
                image_url=item.image_url,
                display_order=item.display_order,
                prep_time_minutes=item.prep_time_minutes,
                cooking_instructions=getattr(item, 'cooking_instructions', None),
                change_type=ChangeType.CREATE,
                change_summary=f"Snapshot of item {item.name}",
                price_history=[{"price": item.price, "date": datetime.now(timezone.utc).isoformat()}]
            )
            
            self.db.add(item_version)
            item_versions.append(item_version)
        
        return item_versions
    
    def _snapshot_modifiers(self, version_id: int, include_inactive: bool, audit_entries: List[MenuAuditLog]) -> List[ModifierGroupVersion]:
        """Create modifier snapshots for version"""
        
        query = self.db.query(ModifierGroup).filter(ModifierGroup.deleted_at == None)
        if not include_inactive:
            query = query.filter(ModifierGroup.is_active == True)
        
        groups = query.all()
        group_versions = []
        
        for group in groups:
            group_version = ModifierGroupVersion(
                menu_version_id=version_id,
                original_group_id=group.id,
                name=group.name,
                description=group.description,
                selection_type=group.selection_type,
                is_required=group.is_required,
                min_selections=group.min_selections,
                max_selections=group.max_selections,
                display_order=group.display_order,
                is_active=group.is_active,
                change_type=ChangeType.CREATE,
                change_summary=f"Snapshot of modifier group {group.name}"
            )
            
            self.db.add(group_version)
            self.db.flush()  # Get ID for modifiers
            
            # Snapshot individual modifiers
            modifier_query = self.db.query(Modifier).filter(
                Modifier.modifier_group_id == group.id,
                Modifier.deleted_at == None
            )
            if not include_inactive:
                modifier_query = modifier_query.filter(Modifier.is_active == True)
            
            modifiers = modifier_query.all()
            modifier_versions = []
            
            for modifier in modifiers:
                modifier_version = ModifierVersion(
                    modifier_group_version_id=group_version.id,
                    original_modifier_id=modifier.id,
                    name=modifier.name,
                    description=modifier.description,
                    price_adjustment=modifier.price_adjustment,
                    is_active=modifier.is_active,
                    display_order=modifier.display_order,
                    change_type=ChangeType.CREATE,
                    change_summary=f"Snapshot of modifier {modifier.name}"
                )
                
                self.db.add(modifier_version)
                modifier_versions.append(modifier_version)
            
            group_version.modifier_versions = modifier_versions
            group_versions.append(group_version)
        
        return group_versions
    
    def _apply_version_to_live_menu(self, version: MenuVersion, audit_entries: List[MenuAuditLog], user_id: int):
        """Apply version changes to the live menu system"""
        # This would update the actual menu tables based on the version data
        # Implementation depends on business rules for how versions affect live data
        pass
    
    def _copy_version_data(self, source_version: MenuVersion, target_version: MenuVersion, audit_entries: List[MenuAuditLog], user_id: int):
        """Copy all data from source version to target version"""
        # Implementation would copy categories, items, and modifiers
        pass
    
    def _generate_version_comparison(self, from_version: MenuVersion, to_version: MenuVersion, request: VersionComparisonRequest) -> MenuVersionComparison:
        """Generate detailed comparison between versions"""
        # Implementation would compare all entities and generate diff data
        return MenuVersionComparison(
            from_version_id=from_version.id,
            to_version_id=to_version.id,
            from_version_number=from_version.version_number,
            to_version_number=to_version.version_number,
            summary={"created": 0, "updated": 0, "deleted": 0},
            categories=[],
            items=[],
            modifiers=[],
            generated_at=datetime.now(timezone.utc)
        )
    
    def _bulk_change_items(self, request: BulkChangeRequest, audit_entries: List[MenuAuditLog], user_id: int) -> Dict[str, Any]:
        """Apply bulk changes to menu items"""
        results = {"updated": 0, "errors": []}
        
        items = self.db.query(MenuItem).filter(
            MenuItem.id.in_(request.entity_ids),
            MenuItem.deleted_at == None
        ).all()
        
        for item in items:
            try:
                old_values = {k: getattr(item, k) for k in request.changes.keys() if hasattr(item, k)}
                
                for field, value in request.changes.items():
                    if hasattr(item, field):
                        setattr(item, field, value)
                
                audit_entries.append(MenuAuditLog(
                    action="bulk_update",
                    entity_type="menu_item",
                    entity_id=item.id,
                    entity_name=item.name,
                    change_type=ChangeType.UPDATE,
                    old_values=old_values,
                    new_values=request.changes,
                    changed_fields=list(request.changes.keys()),
                    change_summary=f"Bulk update: {request.change_reason}",
                    user_id=user_id
                ))
                
                results["updated"] += 1
                
            except Exception as e:
                results["errors"].append(f"Item {item.id}: {str(e)}")
        
        return results
    
    def _bulk_change_categories(self, request: BulkChangeRequest, audit_entries: List[MenuAuditLog], user_id: int) -> Dict[str, Any]:
        """Apply bulk changes to menu categories"""
        # Similar implementation to _bulk_change_items
        return {"updated": 0, "errors": []}
    
    def _bulk_change_modifiers(self, request: BulkChangeRequest, audit_entries: List[MenuAuditLog], user_id: int) -> Dict[str, Any]:
        """Apply bulk changes to modifiers"""
        # Similar implementation to _bulk_change_items
        return {"updated": 0, "errors": []}