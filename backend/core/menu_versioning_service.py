# backend/core/menu_versioning_service.py

from sqlalchemy.orm import Session
from sqlalchemy import desc, and_, or_, func
from typing import List, Optional, Dict, Any, Tuple
from datetime import datetime, timezone
import json
import uuid
from contextlib import contextmanager

from core.menu_versioning_models import (
    MenuVersion,
    MenuCategoryVersion,
    MenuItemVersion,
    ModifierGroupVersion,
    ModifierVersion,
    MenuItemModifierVersion,
    MenuAuditLog,
    MenuVersionSchedule,
    MenuVersionComparison,
    VersionType,
    ChangeType,
)
from core.menu_models import (
    MenuCategory,
    MenuItem,
    ModifierGroup,
    Modifier,
    MenuItemModifier,
)
from core.menu_versioning_schemas import (
    CreateVersionRequest,
    PublishVersionRequest,
    RollbackVersionRequest,
    VersionComparisonRequest,
    MenuVersionWithDetails,
    MenuVersionComparison,
    FieldComparison,
    EntityComparison,
    BulkChangeRequest,
)


class MenuVersioningService:

    def __init__(self, db: Session):
        self.db = db

    @contextmanager
    def audit_context(
        self, user_id: int, action: str, session_id: Optional[str] = None
    ):
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

    def create_version(
        self, request: CreateVersionRequest, user_id: int
    ) -> MenuVersion:
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
            scheduled_publish_at=request.scheduled_publish_at,
        )

        self.db.add(menu_version)
        self.db.flush()  # Get the ID

        with self.audit_context(user_id, "create_version") as audit_entries:
            # Snapshot current menu state
            categories = self._snapshot_categories(
                menu_version.id, request.include_inactive, audit_entries
            )
            items = self._snapshot_items(
                menu_version.id, request.include_inactive, audit_entries
            )
            modifiers = self._snapshot_modifiers(
                menu_version.id, request.include_inactive, audit_entries
            )

            # Update version metadata
            menu_version.total_categories = len(categories)
            menu_version.total_items = len(items)
            menu_version.total_modifiers = sum(
                len(mg.modifier_versions) for mg in modifiers
            )

            # Create main audit entry
            audit_entries.append(
                MenuAuditLog(
                    menu_version_id=menu_version.id,
                    action="create_version",
                    entity_type="menu_version",
                    entity_id=menu_version.id,
                    entity_name=menu_version.version_name
                    or menu_version.version_number,
                    change_type=ChangeType.CREATE,
                    new_values={
                        "version_number": version_number,
                        "version_name": request.version_name,
                        "description": request.description,
                        "version_type": request.version_type.value,
                        "total_categories": menu_version.total_categories,
                        "total_items": menu_version.total_items,
                        "total_modifiers": menu_version.total_modifiers,
                    },
                    change_summary=f"Created new menu version {version_number}",
                    user_id=user_id,
                )
            )

        return menu_version

    def publish_version(
        self, version_id: int, request: PublishVersionRequest, user_id: int
    ) -> MenuVersion:
        """Publish a menu version (make it active)"""

        version = (
            self.db.query(MenuVersion).filter(MenuVersion.id == version_id).first()
        )
        if not version:
            raise ValueError("Version not found")

        if version.is_published and not request.force:
            raise ValueError("Version is already published")

        with self.audit_context(user_id, "publish_version") as audit_entries:
            # Deactivate current active version
            current_active = (
                self.db.query(MenuVersion).filter(MenuVersion.is_active == True).first()
            )
            if current_active:
                current_active.is_active = False
                audit_entries.append(
                    MenuAuditLog(
                        menu_version_id=current_active.id,
                        action="deactivate_version",
                        entity_type="menu_version",
                        entity_id=current_active.id,
                        entity_name=current_active.version_name
                        or current_active.version_number,
                        change_type=ChangeType.DEACTIVATE,
                        old_values={"is_active": True},
                        new_values={"is_active": False},
                        change_summary=f"Deactivated version {current_active.version_number}",
                        user_id=user_id,
                    )
                )

            # Activate new version
            version.is_active = True
            version.is_published = True
            version.published_at = request.scheduled_at or datetime.now(timezone.utc)

            audit_entries.append(
                MenuAuditLog(
                    menu_version_id=version.id,
                    action="publish_version",
                    entity_type="menu_version",
                    entity_id=version.id,
                    entity_name=version.version_name or version.version_number,
                    change_type=ChangeType.ACTIVATE,
                    old_values={"is_active": False, "is_published": False},
                    new_values={
                        "is_active": True,
                        "is_published": True,
                        "published_at": version.published_at,
                    },
                    change_summary=f"Published and activated version {version.version_number}",
                    user_id=user_id,
                )
            )

            # Apply version changes to live menu
            self._apply_version_to_live_menu(version, audit_entries, user_id)

        return version

    def rollback_to_version(
        self, request: RollbackVersionRequest, user_id: int
    ) -> MenuVersion:
        """Rollback to a previous version"""

        target_version = (
            self.db.query(MenuVersion)
            .filter(MenuVersion.id == request.target_version_id)
            .first()
        )
        if not target_version:
            raise ValueError("Target version not found")

        # Create backup of current state if requested
        backup_version = None
        if request.create_backup:
            backup_request = CreateVersionRequest(
                version_name=f"Backup before rollback to {target_version.version_number}",
                description=f"Automatic backup created before rollback. Reason: {request.rollback_reason}",
                version_type=VersionType.ROLLBACK,
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
                created_by=user_id,
            )

            self.db.add(rollback_version)
            self.db.flush()

            # Copy all data from target version
            self._copy_version_data(
                target_version, rollback_version, audit_entries, user_id
            )

            # Activate rollback version
            publish_request = PublishVersionRequest(force=True)
            self.publish_version(rollback_version.id, publish_request, user_id)

            audit_entries.append(
                MenuAuditLog(
                    menu_version_id=rollback_version.id,
                    action="rollback_version",
                    entity_type="menu_version",
                    entity_id=rollback_version.id,
                    entity_name=rollback_version.version_name,
                    change_type=ChangeType.UPDATE,
                    new_values={
                        "target_version_id": request.target_version_id,
                        "rollback_reason": request.rollback_reason,
                        "backup_version_id": (
                            backup_version.id if backup_version else None
                        ),
                    },
                    change_summary=f"Rolled back to version {target_version.version_number}",
                    user_id=user_id,
                )
            )

        return rollback_version

    def compare_versions(
        self, request: VersionComparisonRequest, user_id: Optional[int] = None
    ) -> MenuVersionComparison:
        """Compare two menu versions and return differences"""

        from_version = (
            self.db.query(MenuVersion)
            .filter(MenuVersion.id == request.from_version_id)
            .first()
        )
        to_version = (
            self.db.query(MenuVersion)
            .filter(MenuVersion.id == request.to_version_id)
            .first()
        )

        if not from_version or not to_version:
            raise ValueError("One or both versions not found")

        # Check if we have a cached comparison
        cached = (
            self.db.query(MenuVersionComparison)
            .filter(
                and_(
                    MenuVersionComparison.from_version_id == request.from_version_id,
                    MenuVersionComparison.to_version_id == request.to_version_id,
                    or_(
                        MenuVersionComparison.expires_at.is_(None),
                        MenuVersionComparison.expires_at > datetime.now(timezone.utc),
                    ),
                )
            )
            .first()
        )

        if cached:
            return MenuVersionComparison.parse_obj(cached.comparison_data)

        # Generate comparison
        comparison = self._generate_version_comparison(
            from_version, to_version, request
        )

        # Cache the result
        cache_entry = MenuVersionComparison(
            from_version_id=request.from_version_id,
            to_version_id=request.to_version_id,
            comparison_data=comparison.dict(),
            summary=comparison.summary,
            generated_by=(
                user_id if user_id else 0
            ),  # Use provided user ID or default to system user
        )
        self.db.add(cache_entry)
        self.db.commit()

        return comparison

    def get_version_details(self, version_id: int) -> Optional[MenuVersionWithDetails]:
        """Get detailed information about a version"""

        version = (
            self.db.query(MenuVersion).filter(MenuVersion.id == version_id).first()
        )
        if not version:
            return None

        # Load related data
        categories = (
            self.db.query(MenuCategoryVersion)
            .filter(MenuCategoryVersion.menu_version_id == version_id)
            .all()
        )

        items = (
            self.db.query(MenuItemVersion)
            .filter(MenuItemVersion.menu_version_id == version_id)
            .all()
        )

        modifiers = (
            self.db.query(ModifierGroupVersion)
            .filter(ModifierGroupVersion.menu_version_id == version_id)
            .all()
        )

        audit_entries = (
            self.db.query(MenuAuditLog)
            .filter(MenuAuditLog.menu_version_id == version_id)
            .order_by(desc(MenuAuditLog.created_at))
            .all()
        )

        parent_version = None
        if version.parent_version_id:
            parent_version = (
                self.db.query(MenuVersion)
                .filter(MenuVersion.id == version.parent_version_id)
                .first()
            )

        return MenuVersionWithDetails(
            **version.__dict__,
            categories=categories,
            items=items,
            modifiers=modifiers,
            audit_entries=audit_entries,
            parent_version=parent_version,
        )

    def get_versions(
        self, page: int = 1, size: int = 20, version_type: Optional[VersionType] = None
    ) -> Tuple[List[MenuVersion], int]:
        """Get paginated list of versions"""

        query = self.db.query(MenuVersion).filter(MenuVersion.deleted_at.is_(None))

        if version_type:
            query = query.filter(MenuVersion.version_type == version_type)

        total = query.count()
        versions = (
            query.order_by(desc(MenuVersion.created_at))
            .offset((page - 1) * size)
            .limit(size)
            .all()
        )

        return versions, total

    def get_audit_logs(
        self, version_id: Optional[int] = None, page: int = 1, size: int = 50
    ) -> Tuple[List[MenuAuditLog], int]:
        """Get paginated audit logs"""

        query = self.db.query(MenuAuditLog)

        if version_id:
            query = query.filter(MenuAuditLog.menu_version_id == version_id)

        total = query.count()
        logs = (
            query.order_by(desc(MenuAuditLog.created_at))
            .offset((page - 1) * size)
            .limit(size)
            .all()
        )

        return logs, total

    def bulk_change(self, request: BulkChangeRequest, user_id: int) -> Dict[str, Any]:
        """Apply bulk changes to menu entities"""

        with self.audit_context(
            user_id, f"bulk_change_{request.entity_type}"
        ) as audit_entries:
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
        count = (
            self.db.query(MenuVersion)
            .filter(MenuVersion.version_number.like(f"{date_str}%"))
            .count()
        )

        sequence = f"{count + 1:03d}"
        prefix = {
            VersionType.MANUAL: "v",
            VersionType.SCHEDULED: "s",
            VersionType.ROLLBACK: "r",
            VersionType.MIGRATION: "m",
            VersionType.AUTO_SAVE: "a",
        }.get(version_type, "v")

        return f"{prefix}{date_str}-{sequence}"

    def _snapshot_categories(
        self, version_id: int, include_inactive: bool, audit_entries: List[MenuAuditLog]
    ) -> List[MenuCategoryVersion]:
        """Create category snapshots for version"""

        query = self.db.query(MenuCategory).filter(MenuCategory.deleted_at.is_(None))
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
                change_summary=f"Snapshot of category {category.name}",
            )

            self.db.add(category_version)
            category_versions.append(category_version)

        return category_versions

    def _snapshot_items(
        self, version_id: int, include_inactive: bool, audit_entries: List[MenuAuditLog]
    ) -> List[MenuItemVersion]:
        """Create item snapshots for version"""

        query = self.db.query(MenuItem).filter(MenuItem.deleted_at.is_(None))
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
                cooking_instructions=getattr(item, "cooking_instructions", None),
                change_type=ChangeType.CREATE,
                change_summary=f"Snapshot of item {item.name}",
                price_history=[
                    {
                        "price": item.price,
                        "date": datetime.now(timezone.utc).isoformat(),
                    }
                ],
            )

            self.db.add(item_version)
            item_versions.append(item_version)

        return item_versions

    def _snapshot_modifiers(
        self, version_id: int, include_inactive: bool, audit_entries: List[MenuAuditLog]
    ) -> List[ModifierGroupVersion]:
        """Create modifier snapshots for version"""

        query = self.db.query(ModifierGroup).filter(ModifierGroup.deleted_at.is_(None))
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
                change_summary=f"Snapshot of modifier group {group.name}",
            )

            self.db.add(group_version)
            self.db.flush()  # Get ID for modifiers

            # Snapshot individual modifiers
            modifier_query = self.db.query(Modifier).filter(
                Modifier.modifier_group_id == group.id, Modifier.deleted_at.is_(None)
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
                    change_summary=f"Snapshot of modifier {modifier.name}",
                )

                self.db.add(modifier_version)
                modifier_versions.append(modifier_version)

            group_version.modifier_versions = modifier_versions
            group_versions.append(group_version)

        return group_versions

    def _apply_version_to_live_menu(
        self, version: MenuVersion, audit_entries: List[MenuAuditLog], user_id: int
    ):
        """Apply version changes to the live menu system.

        The goal of this helper is to make the tables in `core.menu_models` reflect exactly the
        snapshot stored inside the supplied `version` instance.  The implementation below keeps
        things deliberately simple – we do **not** try to be the most efficient, we just make sure
        that:
          1. If an entity exists in the snapshot but not in the live tables we create it.
          2. If it exists in both we update the live entity so that all mutable columns match the
             snapshot.
          3. If it exists in the live tables but **not** in the snapshot we mark the record as
             inactive (soft-delete via `is_active = False`) so we keep history but remove it from
             the active menu.

        This naive but deterministic approach is more than enough for now and keeps the surface
        area small.  It can always be replaced by an optimised implementation later without touching
        any public API.
        """
        # Sync categories ---------------------------------------------------
        snapshot_categories = {
            c.original_category_id: c for c in version.category_versions
        }
        live_categories = {c.id: c for c in self.db.query(MenuCategory).all()}

        # Update & deactivate existing
        for cat_id, live_cat in live_categories.items():
            snap = snapshot_categories.pop(cat_id, None)
            if snap is None:
                # Not present in snapshot → deactivate
                if live_cat.is_active:
                    old_values = {"is_active": live_cat.is_active}
                    live_cat.is_active = False
                    audit_entries.append(
                        MenuAuditLog(
                            action="apply_version_deactivate_category",
                            entity_type="menu_category",
                            entity_id=live_cat.id,
                            entity_name=live_cat.name,
                            change_type=ChangeType.DEACTIVATE,
                            old_values=old_values,
                            new_values={"is_active": False},
                            change_summary=f"Category {live_cat.name} deactivated by version apply",
                            user_id=user_id,
                        )
                    )
                continue

            # Update live record fields if different
            changed_fields = {}
            for field in [
                "name",
                "description",
                "display_order",
                "is_active",
                "parent_category_id",
                "image_url",
            ]:
                new_val = getattr(snap, field, None)
                if getattr(live_cat, field) != new_val:
                    changed_fields[field] = {
                        "old": getattr(live_cat, field),
                        "new": new_val,
                    }
                    setattr(live_cat, field, new_val)

            if changed_fields:
                audit_entries.append(
                    MenuAuditLog(
                        action="apply_version_update_category",
                        entity_type="menu_category",
                        entity_id=live_cat.id,
                        entity_name=live_cat.name,
                        change_type=ChangeType.UPDATE,
                        old_values={k: v["old"] for k, v in changed_fields.items()},
                        new_values={k: v["new"] for k, v in changed_fields.items()},
                        changed_fields=list(changed_fields.keys()),
                        change_summary=f"Category {live_cat.name} updated by version apply",
                        user_id=user_id,
                    )
                )

        # Create missing categories
        for snap in snapshot_categories.values():
            new_cat = MenuCategory(
                id=snap.original_category_id,
                name=snap.name,
                description=snap.description,
                display_order=snap.display_order,
                is_active=snap.is_active,
                parent_category_id=snap.parent_category_id,
                image_url=snap.image_url,
            )
            self.db.add(new_cat)
            audit_entries.append(
                MenuAuditLog(
                    action="apply_version_create_category",
                    entity_type="menu_category",
                    entity_id=new_cat.id,
                    entity_name=new_cat.name,
                    change_type=ChangeType.CREATE,
                    new_values={
                        "name": new_cat.name,
                        "description": new_cat.description,
                    },
                    change_summary=f"Category {new_cat.name} created by version apply",
                    user_id=user_id,
                )
            )

        # --- Similar logic for menu items ---------------------------------
        snapshot_items = {i.original_item_id: i for i in version.item_versions}
        live_items = {i.id: i for i in self.db.query(MenuItem).all()}

        for item_id, live_item in live_items.items():
            snap = snapshot_items.pop(item_id, None)
            if snap is None:
                if live_item.is_active:
                    live_item.is_active = False
                    audit_entries.append(
                        MenuAuditLog(
                            action="apply_version_deactivate_item",
                            entity_type="menu_item",
                            entity_id=live_item.id,
                            entity_name=live_item.name,
                            change_type=ChangeType.DEACTIVATE,
                            old_values={"is_active": True},
                            new_values={"is_active": False},
                            change_summary=f"Menu item {live_item.name} deactivated by version apply",
                            user_id=user_id,
                        )
                    )
                continue

            changed_fields = {}
            for field in [
                "name",
                "description",
                "price",
                "category_id",
                "sku",
                "is_active",
                "is_available",
                "availability_start_time",
                "availability_end_time",
                "calories",
                "dietary_tags",
                "image_url",
                "display_order",
                "prep_time_minutes",
                "cooking_instructions",
            ]:
                new_val = getattr(snap, field, None)
                if getattr(live_item, field) != new_val:
                    changed_fields[field] = {
                        "old": getattr(live_item, field),
                        "new": new_val,
                    }
                    setattr(live_item, field, new_val)

            if changed_fields:
                audit_entries.append(
                    MenuAuditLog(
                        action="apply_version_update_item",
                        entity_type="menu_item",
                        entity_id=live_item.id,
                        entity_name=live_item.name,
                        change_type=ChangeType.UPDATE,
                        old_values={k: v["old"] for k, v in changed_fields.items()},
                        new_values={k: v["new"] for k, v in changed_fields.items()},
                        changed_fields=list(changed_fields.keys()),
                        change_summary=f"Menu item {live_item.name} updated by version apply",
                        user_id=user_id,
                    )
                )

        for snap in snapshot_items.values():
            new_item = MenuItem(
                id=snap.original_item_id,
                name=snap.name,
                description=snap.description,
                price=snap.price,
                category_id=snap.category_id,
                sku=snap.sku,
                is_active=snap.is_active,
                is_available=snap.is_available,
                availability_start_time=snap.availability_start_time,
                availability_end_time=snap.availability_end_time,
                calories=snap.calories,
                dietary_tags=snap.dietary_tags,
                image_url=snap.image_url,
                display_order=snap.display_order,
                prep_time_minutes=snap.prep_time_minutes,
                serving_size=None,
            )
            self.db.add(new_item)
            audit_entries.append(
                MenuAuditLog(
                    action="apply_version_create_item",
                    entity_type="menu_item",
                    entity_id=new_item.id,
                    entity_name=new_item.name,
                    change_type=ChangeType.CREATE,
                    new_values={"name": new_item.name, "price": new_item.price},
                    change_summary=f"Menu item {new_item.name} created by version apply",
                    user_id=user_id,
                )
            )

        # NOTE: Modifier groups and modifiers could also be synchronised here in the same way, but
        # for now we keep the implementation focused on the most critical entities.  This can be
        # expanded later without affecting callers.
        # -------------------------------------------------------------------

    def _copy_version_data(
        self,
        source_version: MenuVersion,
        target_version: MenuVersion,
        audit_entries: List[MenuAuditLog],
        user_id: int,
    ):
        """Copy all snapshot entities from *source_version* into *target_version*."""

        # Helper to clone SQLAlchemy objects without identity.
        def _clone_model(instance, overrides: Dict[str, Any]):
            data = {
                c.name: getattr(instance, c.name) for c in instance.__table__.columns
            }
            data.update(overrides)
            data.pop("id", None)  # Remove PK so SQLAlchemy will generate a new one
            return type(instance)(**data)

        # Copy category versions -------------------------------------------------
        for cat_ver in source_version.category_versions:
            new_cat_ver = _clone_model(cat_ver, {"menu_version_id": target_version.id})
            self.db.add(new_cat_ver)

        # Copy item versions -----------------------------------------------------
        id_map_item_versions = {}
        for item_ver in source_version.item_versions:
            new_item_ver = _clone_model(
                item_ver, {"menu_version_id": target_version.id}
            )
            self.db.add(new_item_ver)
            self.db.flush()  # Ensure PK generated so we can link modifiers later
            id_map_item_versions[item_ver.id] = new_item_ver.id

        # Copy modifier group versions + their nested modifiers ------------------
        id_map_group_versions = {}
        for group_ver in source_version.modifier_versions:
            new_group_ver = _clone_model(
                group_ver, {"menu_version_id": target_version.id}
            )
            self.db.add(new_group_ver)
            self.db.flush()
            id_map_group_versions[group_ver.id] = new_group_ver.id

            # Nested modifier versions
            for mod_ver in group_ver.modifier_versions:
                new_mod_ver = _clone_model(
                    mod_ver, {"modifier_group_version_id": new_group_ver.id}
                )
                self.db.add(new_mod_ver)

        # Copy menu item ↔ modifier group associations --------------------------
        for item_ver in source_version.item_versions:
            for assoc in item_ver.modifier_versions:
                new_assoc = _clone_model(
                    assoc,
                    {
                        "menu_item_version_id": id_map_item_versions.get(
                            assoc.menu_item_version_id
                        ),
                        "modifier_group_version_id": id_map_group_versions.get(
                            assoc.modifier_group_version_id
                        ),
                    },
                )
                self.db.add(new_assoc)

        audit_entries.append(
            MenuAuditLog(
                menu_version_id=target_version.id,
                action="copy_version_data",
                entity_type="menu_version",
                entity_id=target_version.id,
                entity_name=target_version.version_name
                or target_version.version_number,
                change_type=ChangeType.CREATE,
                change_summary=f"Copied snapshot data from version {source_version.version_number}",
                user_id=user_id,
            )
        )

    def _generate_version_comparison(
        self,
        from_version: MenuVersion,
        to_version: MenuVersion,
        request: VersionComparisonRequest,
    ) -> MenuVersionComparison:
        """Generate a very high-level comparison between two versions.

        The implementation focuses on the summary numbers because the UI mostly needs to know *how
        many* entities were created / updated / deleted.  Detailed, field-level comparisons can be
        added later if necessary without changing the return type (we already return full dataclass
        structures).
        """

        def _entity_sets(entity_cls):
            return {
                "from": {
                    (
                        e.original_category_id
                        if hasattr(e, "original_category_id")
                        else (
                            e.original_item_id
                            if hasattr(e, "original_item_id")
                            else e.original_group_id
                        )
                    )
                    for e in getattr(from_version, entity_cls)
                },
                "to": {
                    (
                        e.original_category_id
                        if hasattr(e, "original_category_id")
                        else (
                            e.original_item_id
                            if hasattr(e, "original_item_id")
                            else e.original_group_id
                        )
                    )
                    for e in getattr(to_version, entity_cls)
                },
            }

        cat_sets = _entity_sets("category_versions")
        item_sets = _entity_sets("item_versions")
        mod_sets = _entity_sets("modifier_versions")

        def _calc_stats(a, b):
            created = len(b - a)
            deleted = len(a - b)
            unchanged = len(a & b)
            # For simplicity we treat 'unchanged' as updated=0 here
            updated = 0
            return created, updated, deleted

        c_created, c_updated, c_deleted = _calc_stats(cat_sets["from"], cat_sets["to"])
        i_created, i_updated, i_deleted = _calc_stats(
            item_sets["from"], item_sets["to"]
        )
        m_created, m_updated, m_deleted = _calc_stats(mod_sets["from"], mod_sets["to"])

        summary = {
            "created": c_created + i_created + m_created,
            "updated": c_updated + i_updated + m_updated,
            "deleted": c_deleted + i_deleted + m_deleted,
        }

        return MenuVersionComparison(
            from_version_id=from_version.id,
            to_version_id=to_version.id,
            from_version_number=from_version.version_number,
            to_version_number=to_version.version_number,
            summary=summary,
            categories=[],  # Detailed diffs not yet implemented
            items=[],
            modifiers=[],
            generated_at=datetime.now(timezone.utc),
        )

    def _bulk_change_items(
        self,
        request: BulkChangeRequest,
        audit_entries: List[MenuAuditLog],
        user_id: int,
    ) -> Dict[str, Any]:
        """Apply bulk changes to menu items"""
        results = {"updated": 0, "errors": []}

        items = (
            self.db.query(MenuItem)
            .filter(MenuItem.id.in_(request.entity_ids), MenuItem.deleted_at.is_(None))
            .all()
        )

        for item in items:
            try:
                old_values = {
                    k: getattr(item, k)
                    for k in request.changes.keys()
                    if hasattr(item, k)
                }

                for field, value in request.changes.items():
                    if hasattr(item, field):
                        setattr(item, field, value)

                audit_entries.append(
                    MenuAuditLog(
                        action="bulk_update",
                        entity_type="menu_item",
                        entity_id=item.id,
                        entity_name=item.name,
                        change_type=ChangeType.UPDATE,
                        old_values=old_values,
                        new_values=request.changes,
                        changed_fields=list(request.changes.keys()),
                        change_summary=f"Bulk update: {request.change_reason}",
                        user_id=user_id,
                    )
                )

                results["updated"] += 1
            except Exception as e:
                results["errors"].append(f"Item {item.id}: {str(e)}")

        return results

    def _bulk_change_categories(
        self,
        request: BulkChangeRequest,
        audit_entries: List[MenuAuditLog],
        user_id: int,
    ) -> Dict[str, Any]:
        """Apply bulk changes to menu categories"""
        results = {"updated": 0, "errors": []}

        categories = (
            self.db.query(MenuCategory)
            .filter(
                MenuCategory.id.in_(request.entity_ids),
                MenuCategory.deleted_at.is_(None),
            )
            .all()
        )

        for category in categories:
            try:
                old_values = {
                    k: getattr(category, k)
                    for k in request.changes.keys()
                    if hasattr(category, k)
                }

                for field, value in request.changes.items():
                    if hasattr(category, field):
                        setattr(category, field, value)

                audit_entries.append(
                    MenuAuditLog(
                        action="bulk_update",
                        entity_type="menu_category",
                        entity_id=category.id,
                        entity_name=category.name,
                        change_type=ChangeType.UPDATE,
                        old_values=old_values,
                        new_values=request.changes,
                        changed_fields=list(request.changes.keys()),
                        change_summary=f"Bulk update: {request.change_reason}",
                        user_id=user_id,
                    )
                )

                results["updated"] += 1
            except Exception as e:
                results["errors"].append(f"Category {category.id}: {str(e)}")

        return results

    def _bulk_change_modifiers(
        self,
        request: BulkChangeRequest,
        audit_entries: List[MenuAuditLog],
        user_id: int,
    ) -> Dict[str, Any]:
        """Apply bulk changes to modifier groups and modifiers"""
        results = {"updated": 0, "errors": []}

        # We treat both groups and individual modifiers the same way here – callers specify whether
        # the IDs belong to groups or modifiers via the `entity_type` at the top-level request.
        # For now we try groups first and fall back to modifiers.
        groups = (
            self.db.query(ModifierGroup)
            .filter(
                ModifierGroup.id.in_(request.entity_ids),
                ModifierGroup.deleted_at.is_(None),
            )
            .all()
        )

        for group in groups:
            try:
                old_values = {
                    k: getattr(group, k)
                    for k in request.changes.keys()
                    if hasattr(group, k)
                }

                for field, value in request.changes.items():
                    if hasattr(group, field):
                        setattr(group, field, value)

                audit_entries.append(
                    MenuAuditLog(
                        action="bulk_update",
                        entity_type="modifier_group",
                        entity_id=group.id,
                        entity_name=group.name,
                        change_type=ChangeType.UPDATE,
                        old_values=old_values,
                        new_values=request.changes,
                        changed_fields=list(request.changes.keys()),
                        change_summary=f"Bulk update: {request.change_reason}",
                        user_id=user_id,
                    )
                )

                results["updated"] += 1
            except Exception as e:
                results["errors"].append(f"ModifierGroup {group.id}: {str(e)}")

        # Handle individual modifiers ------------------------------------------------
        remaining_ids = [
            id_ for id_ in request.entity_ids if id_ not in {g.id for g in groups}
        ]
        if remaining_ids:
            modifiers = (
                self.db.query(Modifier)
                .filter(
                    Modifier.id.in_(remaining_ids),
                    Modifier.deleted_at.is_(None),
                )
                .all()
            )

            for modifier in modifiers:
                try:
                    old_values = {
                        k: getattr(modifier, k)
                        for k in request.changes.keys()
                        if hasattr(modifier, k)
                    }

                    for field, value in request.changes.items():
                        if hasattr(modifier, field):
                            setattr(modifier, field, value)

                    audit_entries.append(
                        MenuAuditLog(
                            action="bulk_update",
                            entity_type="modifier",
                            entity_id=modifier.id,
                            entity_name=modifier.name,
                            change_type=ChangeType.UPDATE,
                            old_values=old_values,
                            new_values=request.changes,
                            changed_fields=list(request.changes.keys()),
                            change_summary=f"Bulk update: {request.change_reason}",
                            user_id=user_id,
                        )
                    )

                    results["updated"] += 1
                except Exception as e:
                    results["errors"].append(f"Modifier {modifier.id}: {str(e)}")

        return results
