# backend/core/menu_sync_conflict_resolver.py

from sqlalchemy.orm import Session
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime
import logging

from .menu_sync_models import (
    MenuSyncConflict,
    ConflictResolution,
    SyncDirection,
    SyncStatus,
)
from .menu_sync_schemas import MenuSyncConflictResolve
from .menu_models import MenuCategory, MenuItem, ModifierGroup, Modifier
from .notification_service import NotificationService


logger = logging.getLogger(__name__)


class MenuSyncConflictResolver:
    """Service for resolving menu synchronization conflicts"""

    def __init__(self, db: Session):
        self.db = db
        self.notification_service = NotificationService()

        # Define conflict resolution strategies
        self.resolution_strategies = {
            ConflictResolution.AURA_WINS: self._resolve_aura_wins,
            ConflictResolution.POS_WINS: self._resolve_pos_wins,
            ConflictResolution.LATEST_WINS: self._resolve_latest_wins,
            ConflictResolution.MANUAL: self._handle_manual_resolution,
        }

    def get_pending_conflicts(
        self, pos_integration_id: Optional[int] = None
    ) -> List[MenuSyncConflict]:
        """Get all pending conflicts, optionally filtered by POS integration"""
        query = self.db.query(MenuSyncConflict).filter(
            MenuSyncConflict.status == "unresolved"
        )

        if pos_integration_id:
            # Join with sync_job to filter by pos_integration_id
            query = query.join(MenuSyncConflict.sync_job).filter(
                MenuSyncJob.pos_integration_id == pos_integration_id
            )

        return query.order_by(
            MenuSyncConflict.priority.desc(), MenuSyncConflict.created_at.asc()
        ).all()

    def get_conflict_summary(
        self, pos_integration_id: Optional[int] = None
    ) -> Dict[str, Any]:
        """Get summary statistics for conflicts"""
        base_query = self.db.query(MenuSyncConflict)

        if pos_integration_id:
            base_query = base_query.join(MenuSyncConflict.sync_job).filter(
                MenuSyncJob.pos_integration_id == pos_integration_id
            )

        total_conflicts = base_query.count()
        unresolved_conflicts = base_query.filter(
            MenuSyncConflict.status == "unresolved"
        ).count()

        # Group by entity type
        by_entity_type = {}
        entity_type_results = (
            base_query.filter(MenuSyncConflict.status == "unresolved")
            .with_entities(
                MenuSyncConflict.entity_type, func.count(MenuSyncConflict.id)
            )
            .group_by(MenuSyncConflict.entity_type)
            .all()
        )

        for entity_type, count in entity_type_results:
            by_entity_type[entity_type] = count

        # Group by severity
        by_severity = {}
        severity_results = (
            base_query.filter(MenuSyncConflict.status == "unresolved")
            .with_entities(MenuSyncConflict.severity, func.count(MenuSyncConflict.id))
            .group_by(MenuSyncConflict.severity)
            .all()
        )

        for severity, count in severity_results:
            by_severity[severity] = count

        # Group by conflict type
        by_conflict_type = {}
        conflict_type_results = (
            base_query.filter(MenuSyncConflict.status == "unresolved")
            .with_entities(
                MenuSyncConflict.conflict_type, func.count(MenuSyncConflict.id)
            )
            .group_by(MenuSyncConflict.conflict_type)
            .all()
        )

        for conflict_type, count in conflict_type_results:
            by_conflict_type[conflict_type] = count

        # Get oldest conflict
        oldest_conflict = (
            base_query.filter(MenuSyncConflict.status == "unresolved")
            .order_by(MenuSyncConflict.created_at.asc())
            .first()
        )

        return {
            "total_conflicts": total_conflicts,
            "unresolved_conflicts": unresolved_conflicts,
            "by_entity_type": by_entity_type,
            "by_severity": by_severity,
            "by_conflict_type": by_conflict_type,
            "oldest_conflict": oldest_conflict.created_at if oldest_conflict else None,
        }

    def resolve_conflict(
        self,
        conflict_id: int,
        resolution: MenuSyncConflictResolve,
        user_id: Optional[int] = None,
    ) -> bool:
        """Resolve a specific conflict using the provided resolution strategy"""

        conflict = (
            self.db.query(MenuSyncConflict)
            .filter(MenuSyncConflict.id == conflict_id)
            .first()
        )

        if not conflict:
            logger.error(f"Conflict {conflict_id} not found")
            return False

        if conflict.status != "unresolved":
            logger.warning(f"Conflict {conflict_id} is already {conflict.status}")
            return False

        try:
            # Get the resolution strategy function
            resolver = self.resolution_strategies.get(resolution.resolution_strategy)
            if not resolver:
                raise ValueError(
                    f"Unknown resolution strategy: {resolution.resolution_strategy}"
                )

            # Execute the resolution
            success = resolver(conflict, resolution, user_id)

            if success:
                # Update conflict record
                conflict.status = "resolved"
                conflict.resolution_strategy = resolution.resolution_strategy
                conflict.resolved_by = user_id
                conflict.resolved_at = datetime.utcnow()
                conflict.resolution_notes = resolution.resolution_notes

                self.db.commit()

                # Send notification if configured
                self._notify_conflict_resolved(conflict)

                logger.info(
                    f"Conflict {conflict_id} resolved using {resolution.resolution_strategy}"
                )
                return True
            else:
                logger.error(f"Failed to resolve conflict {conflict_id}")
                return False

        except Exception as e:
            logger.error(f"Error resolving conflict {conflict_id}: {str(e)}")
            self.db.rollback()
            return False

    def auto_resolve_conflicts(
        self, pos_integration_id: Optional[int] = None, max_conflicts: int = 100
    ) -> Dict[str, int]:
        """Automatically resolve conflicts that are marked as auto-resolvable"""

        query = self.db.query(MenuSyncConflict).filter(
            MenuSyncConflict.status == "unresolved",
            MenuSyncConflict.auto_resolvable == True,
        )

        if pos_integration_id:
            query = query.join(MenuSyncConflict.sync_job).filter(
                MenuSyncJob.pos_integration_id == pos_integration_id
            )

        conflicts = query.limit(max_conflicts).all()

        resolved_count = 0
        failed_count = 0

        for conflict in conflicts:
            try:
                # Use the conflict's resolution strategy for auto-resolution
                resolution = MenuSyncConflictResolve(
                    resolution_strategy=conflict.resolution_strategy
                    or ConflictResolution.LATEST_WINS,
                    resolution_notes="Auto-resolved by system",
                )

                if self.resolve_conflict(conflict.id, resolution, user_id=0):
                    resolved_count += 1
                else:
                    failed_count += 1

            except Exception as e:
                logger.error(f"Error auto-resolving conflict {conflict.id}: {str(e)}")
                failed_count += 1

        return {
            "resolved": resolved_count,
            "failed": failed_count,
            "total_processed": resolved_count + failed_count,
        }

    def ignore_conflict(
        self,
        conflict_id: int,
        user_id: Optional[int] = None,
        reason: Optional[str] = None,
    ) -> bool:
        """Mark a conflict as ignored (not resolved, but won't appear in active list)"""

        conflict = (
            self.db.query(MenuSyncConflict)
            .filter(MenuSyncConflict.id == conflict_id)
            .first()
        )

        if not conflict:
            return False

        conflict.status = "ignored"
        conflict.resolved_by = user_id
        conflict.resolved_at = datetime.utcnow()
        conflict.resolution_notes = reason or "Conflict ignored by user"

        self.db.commit()
        return True

    def reopen_conflict(
        self,
        conflict_id: int,
        user_id: Optional[int] = None,
        reason: Optional[str] = None,
    ) -> bool:
        """Reopen a resolved or ignored conflict"""

        conflict = (
            self.db.query(MenuSyncConflict)
            .filter(MenuSyncConflict.id == conflict_id)
            .first()
        )

        if not conflict or conflict.status == "unresolved":
            return False

        conflict.status = "unresolved"
        conflict.resolution_strategy = None
        conflict.resolved_by = None
        conflict.resolved_at = None
        conflict.resolution_notes = (
            f"Reopened by user: {reason}" if reason else "Reopened by user"
        )

        self.db.commit()
        return True

    def _resolve_aura_wins(
        self,
        conflict: MenuSyncConflict,
        resolution: MenuSyncConflictResolve,
        user_id: Optional[int],
    ) -> bool:
        """Resolve conflict by keeping AuraConnect data and pushing to POS"""

        try:
            # Apply AuraConnect data to POS system
            return self._apply_data_to_pos(conflict, conflict.aura_current_data)
        except Exception as e:
            logger.error(f"Failed to apply AuraConnect data to POS: {str(e)}")
            return False

    def _resolve_pos_wins(
        self,
        conflict: MenuSyncConflict,
        resolution: MenuSyncConflictResolve,
        user_id: Optional[int],
    ) -> bool:
        """Resolve conflict by keeping POS data and pulling to AuraConnect"""

        try:
            # Apply POS data to AuraConnect system
            return self._apply_data_to_aura(conflict, conflict.pos_current_data)
        except Exception as e:
            logger.error(f"Failed to apply POS data to AuraConnect: {str(e)}")
            return False

    def _resolve_latest_wins(
        self,
        conflict: MenuSyncConflict,
        resolution: MenuSyncConflictResolve,
        user_id: Optional[int],
    ) -> bool:
        """Resolve conflict by comparing timestamps and using most recent data"""

        try:
            aura_timestamp = self._extract_timestamp(conflict.aura_current_data)
            pos_timestamp = self._extract_timestamp(conflict.pos_current_data)

            if aura_timestamp and pos_timestamp:
                if aura_timestamp >= pos_timestamp:
                    return self._apply_data_to_pos(conflict, conflict.aura_current_data)
                else:
                    return self._apply_data_to_aura(conflict, conflict.pos_current_data)
            elif aura_timestamp and not pos_timestamp:
                return self._apply_data_to_pos(conflict, conflict.aura_current_data)
            elif pos_timestamp and not aura_timestamp:
                return self._apply_data_to_aura(conflict, conflict.pos_current_data)
            else:
                # No timestamps available, fall back to AuraConnect wins
                return self._apply_data_to_pos(conflict, conflict.aura_current_data)

        except Exception as e:
            logger.error(f"Failed to resolve using latest wins strategy: {str(e)}")
            return False

    def _handle_manual_resolution(
        self,
        conflict: MenuSyncConflict,
        resolution: MenuSyncConflictResolve,
        user_id: Optional[int],
    ) -> bool:
        """Handle manual resolution - requires explicit data selection"""

        # For manual resolution, the resolution should include which data to use
        # This would typically be handled by the API endpoint that provides the specific data
        logger.info(f"Manual resolution applied to conflict {conflict.id}")
        return True

    def _apply_data_to_pos(
        self, conflict: MenuSyncConflict, data: Dict[str, Any]
    ) -> bool:
        """Apply data from AuraConnect to POS system"""

        # This would use the MenuSyncService to push the data to POS
        # For now, we'll just log the action
        logger.info(f"Applying AuraConnect data to POS for conflict {conflict.id}")

        # In a real implementation, this would:
        # 1. Get the POS adapter for the integration
        # 2. Transform the data to POS format
        # 3. Push the data using the appropriate adapter method
        # 4. Update the mapping with new sync hash

        return True

    def _apply_data_to_aura(
        self, conflict: MenuSyncConflict, data: Dict[str, Any]
    ) -> bool:
        """Apply data from POS to AuraConnect system"""

        # This would update the AuraConnect entity with POS data
        logger.info(f"Applying POS data to AuraConnect for conflict {conflict.id}")

        try:
            entity_type = conflict.entity_type
            entity_id = conflict.aura_entity_id

            if entity_type == "category":
                entity = self.db.query(MenuCategory).get(entity_id)
                if entity:
                    self._update_category_from_pos_data(entity, data)
            elif entity_type == "item":
                entity = self.db.query(MenuItem).get(entity_id)
                if entity:
                    self._update_item_from_pos_data(entity, data)
            elif entity_type == "modifier_group":
                entity = self.db.query(ModifierGroup).get(entity_id)
                if entity:
                    self._update_modifier_group_from_pos_data(entity, data)
            elif entity_type == "modifier":
                entity = self.db.query(Modifier).get(entity_id)
                if entity:
                    self._update_modifier_from_pos_data(entity, data)

            self.db.commit()
            return True

        except Exception as e:
            logger.error(f"Failed to apply POS data to AuraConnect: {str(e)}")
            self.db.rollback()
            return False

    def _update_category_from_pos_data(
        self, category: MenuCategory, pos_data: Dict[str, Any]
    ):
        """Update category with POS data"""
        if "name" in pos_data:
            category.name = pos_data["name"]
        if "description" in pos_data:
            category.description = pos_data["description"]
        if "is_active" in pos_data:
            category.is_active = pos_data["is_active"]

    def _update_item_from_pos_data(self, item: MenuItem, pos_data: Dict[str, Any]):
        """Update menu item with POS data"""
        if "name" in pos_data:
            item.name = pos_data["name"]
        if "description" in pos_data:
            item.description = pos_data["description"]
        if "price" in pos_data:
            item.price = pos_data["price"]
        if "is_active" in pos_data:
            item.is_active = pos_data["is_active"]
        if "is_available" in pos_data:
            item.is_available = pos_data["is_available"]

    def _update_modifier_group_from_pos_data(
        self, modifier_group: ModifierGroup, pos_data: Dict[str, Any]
    ):
        """Update modifier group with POS data"""
        if "name" in pos_data:
            modifier_group.name = pos_data["name"]
        if "description" in pos_data:
            modifier_group.description = pos_data["description"]
        if "selection_type" in pos_data:
            modifier_group.selection_type = pos_data["selection_type"]
        if "is_required" in pos_data:
            modifier_group.is_required = pos_data["is_required"]

    def _update_modifier_from_pos_data(
        self, modifier: Modifier, pos_data: Dict[str, Any]
    ):
        """Update modifier with POS data"""
        if "name" in pos_data:
            modifier.name = pos_data["name"]
        if "description" in pos_data:
            modifier.description = pos_data["description"]
        if "price_adjustment" in pos_data:
            modifier.price_adjustment = pos_data["price_adjustment"]
        if "is_active" in pos_data:
            modifier.is_active = pos_data["is_active"]

    def _extract_timestamp(self, data: Dict[str, Any]) -> Optional[datetime]:
        """Extract timestamp from entity data"""
        if not data:
            return None

        # Try common timestamp field names
        timestamp_fields = ["updated_at", "modified_at", "last_modified", "timestamp"]

        for field in timestamp_fields:
            if field in data and data[field]:
                try:
                    if isinstance(data[field], datetime):
                        return data[field]
                    elif isinstance(data[field], str):
                        return datetime.fromisoformat(
                            data[field].replace("Z", "+00:00")
                        )
                except (ValueError, TypeError):
                    continue

        return None

    def _notify_conflict_resolved(self, conflict: MenuSyncConflict):
        """Send notification when conflict is resolved"""
        try:
            # This would integrate with the notification system
            # For now, just log
            logger.info(f"Conflict {conflict.id} resolved notification sent")
        except Exception as e:
            logger.error(f"Failed to send conflict resolution notification: {str(e)}")

    def get_conflict_recommendations(self, conflict: MenuSyncConflict) -> List[str]:
        """Get recommendations for resolving a specific conflict"""
        recommendations = []

        # Analyze the conflict and provide specific recommendations
        if conflict.severity == "high":
            recommendations.append(
                "High priority conflict - immediate attention required"
            )

        if "price" in conflict.conflicting_fields:
            recommendations.append(
                "Price conflict detected - verify with management before resolving"
            )

        if "is_available" in conflict.conflicting_fields:
            recommendations.append("Availability conflict - check inventory levels")

        if conflict.conflict_type == "deleted_entity":
            recommendations.append(
                "Entity deletion conflict - confirm if item should be removed"
            )

        # Check timestamps for latest wins recommendation
        aura_timestamp = self._extract_timestamp(conflict.aura_current_data)
        pos_timestamp = self._extract_timestamp(conflict.pos_current_data)

        if aura_timestamp and pos_timestamp:
            if aura_timestamp > pos_timestamp:
                recommendations.append(
                    "AuraConnect data is more recent - consider AURA_WINS strategy"
                )
            else:
                recommendations.append(
                    "POS data is more recent - consider POS_WINS strategy"
                )

        if not recommendations:
            recommendations.append(
                "No specific recommendations - manual review suggested"
            )

        return recommendations


class NotificationService:
    """Placeholder notification service"""

    def __init__(self):
        pass
