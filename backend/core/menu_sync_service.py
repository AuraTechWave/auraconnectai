# backend/core/menu_sync_service.py

from sqlalchemy.orm import Session
from sqlalchemy import and_, or_, func
from typing import Dict, Any, List, Optional, Tuple, Union
from datetime import datetime, timedelta
import asyncio
import json
import hashlib
import uuid
from contextlib import contextmanager

from .menu_sync_models import (
    POSMenuMapping,
    MenuSyncJob,
    MenuSyncLog,
    MenuSyncConflict,
    MenuSyncConfig,
    MenuSyncStatistics,
    SyncDirection,
    SyncStatus,
    ConflictResolution,
)
from .menu_sync_schemas import (
    StartSyncRequest,
    SyncStatusResponse,
    MenuCategorySync,
    MenuItemSync,
    ModifierGroupSync,
    ModifierSync,
)
from .menu_models import MenuCategory, MenuItem, ModifierGroup, Modifier
from .menu_versioning_service import MenuVersioningService
from ..modules.pos.models.pos_integration import POSIntegration
from ..modules.pos.adapters.square_adapter import SquareAdapter
from ..modules.pos.adapters.toast_adapter import ToastAdapter
from ..modules.pos.adapters.clover_adapter import CloverAdapter


class MenuSyncService:
    """Service for synchronizing menu data between AuraConnect and POS systems"""

    def __init__(self, db: Session):
        self.db = db
        self.versioning_service = MenuVersioningService(db)
        self._pos_adapters = {
            "square": SquareAdapter,
            "toast": ToastAdapter,
            "clover": CloverAdapter,
        }

    def get_pos_adapter(self, pos_integration: POSIntegration):
        """Get the appropriate POS adapter for the integration"""
        adapter_class = self._pos_adapters.get(pos_integration.vendor.lower())
        if not adapter_class:
            raise ValueError(f"Unsupported POS vendor: {pos_integration.vendor}")
        return adapter_class(pos_integration.credentials)

    async def start_sync(
        self, request: StartSyncRequest, user_id: Optional[int] = None
    ) -> MenuSyncJob:
        """Start a new menu synchronization job"""

        # Get POS integration and config
        pos_integration = (
            self.db.query(POSIntegration)
            .filter(POSIntegration.id == request.pos_integration_id)
            .first()
        )
        if not pos_integration:
            raise ValueError(f"POS integration {request.pos_integration_id} not found")

        sync_config = (
            self.db.query(MenuSyncConfig)
            .filter(MenuSyncConfig.pos_integration_id == request.pos_integration_id)
            .first()
        )
        if not sync_config or not sync_config.sync_enabled:
            raise ValueError("Menu sync is not enabled for this POS integration")

        # Check for active jobs
        active_jobs = (
            self.db.query(MenuSyncJob)
            .filter(
                and_(
                    MenuSyncJob.pos_integration_id == request.pos_integration_id,
                    MenuSyncJob.status.in_(
                        [SyncStatus.PENDING, SyncStatus.IN_PROGRESS]
                    ),
                )
            )
            .count()
        )

        if active_jobs >= sync_config.max_concurrent_jobs:
            raise ValueError("Maximum concurrent sync jobs exceeded")

        # Create sync job
        sync_job = MenuSyncJob(
            pos_integration_id=request.pos_integration_id,
            sync_direction=request.sync_direction,
            entity_types=request.entity_types,
            entity_ids=request.entity_ids,
            triggered_by="user" if user_id else "api",
            triggered_by_id=user_id,
            job_config={
                "force_sync": request.force_sync,
                "conflict_resolution": request.conflict_resolution
                or sync_config.default_conflict_resolution,
            },
        )

        self.db.add(sync_job)
        self.db.commit()
        self.db.refresh(sync_job)

        # Start async sync process
        asyncio.create_task(self._execute_sync_job(sync_job))

        return sync_job

    async def _execute_sync_job(self, sync_job: MenuSyncJob):
        """Execute the synchronization job"""
        try:
            # Update job status
            sync_job.status = SyncStatus.IN_PROGRESS
            sync_job.started_at = datetime.utcnow()
            self.db.commit()

            # Get POS integration and adapter
            pos_integration = self.db.query(POSIntegration).get(
                sync_job.pos_integration_id
            )
            pos_adapter = self.get_pos_adapter(pos_integration)

            # Test connection
            if not await pos_adapter.test_connection():
                raise Exception("Failed to connect to POS system")

            # Execute sync based on direction
            if sync_job.sync_direction == SyncDirection.PUSH:
                await self._push_to_pos(sync_job, pos_adapter)
            elif sync_job.sync_direction == SyncDirection.PULL:
                await self._pull_from_pos(sync_job, pos_adapter)
            elif sync_job.sync_direction == SyncDirection.BIDIRECTIONAL:
                await self._bidirectional_sync(sync_job, pos_adapter)

            # Mark job as completed
            sync_job.status = SyncStatus.SUCCESS
            sync_job.completed_at = datetime.utcnow()

        except Exception as e:
            sync_job.status = SyncStatus.ERROR
            sync_job.error_message = str(e)
            sync_job.completed_at = datetime.utcnow()

            # Retry logic
            if sync_job.retry_count < sync_job.max_retries:
                sync_job.retry_count += 1
                sync_job.status = SyncStatus.PENDING
                sync_job.started_at = None
                sync_job.completed_at = None
                # Schedule retry (implement with task queue in production)
                asyncio.create_task(
                    self._delayed_retry(
                        sync_job, delay_seconds=60 * (2**sync_job.retry_count)
                    )
                )

        finally:
            self.db.commit()
            await self._update_sync_statistics(sync_job)

    async def _delayed_retry(self, sync_job: MenuSyncJob, delay_seconds: int):
        """Retry sync job after delay"""
        await asyncio.sleep(delay_seconds)
        await self._execute_sync_job(sync_job)

    async def _push_to_pos(self, sync_job: MenuSyncJob, pos_adapter):
        """Push AuraConnect menu data to POS system"""
        entity_types = sync_job.entity_types or [
            "category",
            "item",
            "modifier_group",
            "modifier",
        ]

        with self._sync_context(sync_job) as ctx:
            for entity_type in entity_types:
                await self._push_entity_type(sync_job, pos_adapter, entity_type, ctx)

    async def _pull_from_pos(self, sync_job: MenuSyncJob, pos_adapter):
        """Pull menu data from POS system to AuraConnect"""
        sync_config = (
            self.db.query(MenuSyncConfig)
            .filter(MenuSyncConfig.pos_integration_id == sync_job.pos_integration_id)
            .first()
        )

        # Create version before pull if configured
        version_id = None
        if sync_config.create_version_on_pull:
            version_name = self._generate_version_name(sync_config, "POS_PULL")
            with self.versioning_service.audit_context(
                user_id=sync_job.triggered_by_id or 0,
                action="pos_sync_pull",
                session_id=str(sync_job.job_id),
            ):
                version = self.versioning_service.create_version(
                    version_name=version_name,
                    description=f"Version created before POS pull sync (Job: {sync_job.job_id})",
                    user_id=sync_job.triggered_by_id or 0,
                )
                version_id = version.id

        with self._sync_context(sync_job, version_id) as ctx:
            # Pull categories first (hierarchical dependency)
            if not sync_job.entity_types or "category" in sync_job.entity_types:
                await self._pull_categories(sync_job, pos_adapter, ctx)

            # Pull items
            if not sync_job.entity_types or "item" in sync_job.entity_types:
                await self._pull_items(sync_job, pos_adapter, ctx)

            # Pull modifiers
            if not sync_job.entity_types or "modifier" in sync_job.entity_types:
                await self._pull_modifiers(sync_job, pos_adapter, ctx)

    async def _bidirectional_sync(self, sync_job: MenuSyncJob, pos_adapter):
        """Perform bidirectional synchronization with conflict detection"""

        with self._sync_context(sync_job) as ctx:
            # Get all mappings for this integration
            mappings = (
                self.db.query(POSMenuMapping)
                .filter(
                    and_(
                        POSMenuMapping.pos_integration_id
                        == sync_job.pos_integration_id,
                        POSMenuMapping.sync_enabled == True,
                        POSMenuMapping.is_active == True,
                    )
                )
                .all()
            )

            sync_job.total_entities = len(mappings)

            for mapping in mappings:
                try:
                    await self._sync_entity_bidirectional(
                        sync_job, pos_adapter, mapping, ctx
                    )
                    sync_job.processed_entities += 1

                except Exception as e:
                    sync_job.failed_entities += 1
                    await self._log_sync_error(sync_job, mapping, str(e), ctx)

                self.db.commit()

    async def _sync_entity_bidirectional(
        self, sync_job: MenuSyncJob, pos_adapter, mapping: POSMenuMapping, ctx
    ):
        """Sync a single entity bidirectionally"""

        # Get current data from both systems
        aura_data = await self._get_aura_entity_data(
            mapping.entity_type, mapping.aura_entity_id
        )
        pos_data = await self._get_pos_entity_data(
            pos_adapter, mapping.entity_type, mapping.pos_entity_id
        )

        if not aura_data and not pos_data:
            # Both entities deleted, clean up mapping
            mapping.is_active = False
            return

        # Detect changes using hash comparison
        aura_hash = self._calculate_entity_hash(aura_data) if aura_data else None
        pos_hash = self._calculate_entity_hash(pos_data) if pos_data else None

        # Check if either side has changed since last sync
        aura_changed = aura_hash != mapping.sync_hash
        pos_changed = pos_hash != mapping.sync_hash

        if not aura_changed and not pos_changed:
            # No changes detected
            await self._log_sync_operation(
                sync_job,
                mapping,
                "no_change",
                SyncDirection.BIDIRECTIONAL,
                SyncStatus.SUCCESS,
                ctx,
            )
            return

        # Handle different change scenarios
        if aura_changed and not pos_changed:
            # Only AuraConnect changed, push to POS
            if mapping.sync_direction in [
                SyncDirection.PUSH,
                SyncDirection.BIDIRECTIONAL,
            ]:
                await self._push_entity_to_pos(
                    sync_job, pos_adapter, mapping, aura_data, ctx
                )

        elif pos_changed and not aura_changed:
            # Only POS changed, pull to AuraConnect
            if mapping.sync_direction in [
                SyncDirection.PULL,
                SyncDirection.BIDIRECTIONAL,
            ]:
                await self._pull_entity_to_aura(sync_job, mapping, pos_data, ctx)

        else:
            # Both changed - conflict detected
            await self._handle_sync_conflict(
                sync_job, mapping, aura_data, pos_data, ctx
            )

    async def _handle_sync_conflict(
        self,
        sync_job: MenuSyncJob,
        mapping: POSMenuMapping,
        aura_data: Dict,
        pos_data: Dict,
        ctx,
    ):
        """Handle synchronization conflicts"""

        sync_job.conflicts_detected += 1

        # Determine conflict resolution strategy
        resolution_strategy = mapping.conflict_resolution
        if sync_job.job_config and "conflict_resolution" in sync_job.job_config:
            resolution_strategy = ConflictResolution(
                sync_job.job_config["conflict_resolution"]
            )

        # Create conflict record
        conflict = MenuSyncConflict(
            sync_job_id=sync_job.id,
            sync_log_id=0,  # Will be updated after log creation
            mapping_id=mapping.id,
            entity_type=mapping.entity_type,
            aura_entity_id=mapping.aura_entity_id,
            pos_entity_id=mapping.pos_entity_id,
            conflict_type="data_mismatch",
            conflict_description="Both systems have changes since last sync",
            aura_current_data=aura_data,
            pos_current_data=pos_data,
            conflicting_fields=self._detect_conflicting_fields(aura_data, pos_data),
            auto_resolvable=(resolution_strategy != ConflictResolution.MANUAL),
            priority=self._calculate_conflict_priority(aura_data, pos_data),
            severity=self._calculate_conflict_severity(aura_data, pos_data),
        )

        # Log the conflict
        sync_log = await self._log_sync_operation(
            sync_job,
            mapping,
            "conflict",
            SyncDirection.BIDIRECTIONAL,
            SyncStatus.CONFLICT,
            ctx,
            aura_data_before=aura_data,
            pos_data_before=pos_data,
            conflict_type="data_mismatch",
        )

        conflict.sync_log_id = sync_log.id
        self.db.add(conflict)

        # Auto-resolve if possible
        if conflict.auto_resolvable:
            await self._auto_resolve_conflict(conflict, resolution_strategy, ctx)
        else:
            sync_job.status = SyncStatus.CONFLICT

    async def _auto_resolve_conflict(
        self, conflict: MenuSyncConflict, strategy: ConflictResolution, ctx
    ):
        """Automatically resolve conflicts based on strategy"""

        try:
            if strategy == ConflictResolution.AURA_WINS:
                # Use AuraConnect data
                await self._apply_resolution_data(
                    conflict, conflict.aura_current_data, "aura", ctx
                )

            elif strategy == ConflictResolution.POS_WINS:
                # Use POS data
                await self._apply_resolution_data(
                    conflict, conflict.pos_current_data, "pos", ctx
                )

            elif strategy == ConflictResolution.LATEST_WINS:
                # Compare timestamps and use most recent
                aura_modified = (
                    conflict.aura_current_data.get("updated_at")
                    if conflict.aura_current_data
                    else None
                )
                pos_modified = (
                    conflict.pos_current_data.get("updated_at")
                    if conflict.pos_current_data
                    else None
                )

                if aura_modified and pos_modified:
                    if aura_modified > pos_modified:
                        await self._apply_resolution_data(
                            conflict, conflict.aura_current_data, "aura", ctx
                        )
                    else:
                        await self._apply_resolution_data(
                            conflict, conflict.pos_current_data, "pos", ctx
                        )
                else:
                    # Fall back to manual resolution
                    return

            # Mark conflict as resolved
            conflict.status = "resolved"
            conflict.resolution_strategy = strategy
            conflict.resolved_at = datetime.utcnow()
            conflict.resolved_by = 0  # System resolution

        except Exception as e:
            conflict.resolution_notes = f"Auto-resolution failed: {str(e)}"

    async def _apply_resolution_data(
        self, conflict: MenuSyncConflict, resolution_data: Dict, source: str, ctx
    ):
        """Apply conflict resolution data to both systems"""

        mapping = self.db.query(POSMenuMapping).get(conflict.mapping_id)
        sync_job = self.db.query(MenuSyncJob).get(conflict.sync_job_id)
        pos_integration = self.db.query(POSIntegration).get(sync_job.pos_integration_id)
        pos_adapter = self.get_pos_adapter(pos_integration)

        if source == "aura":
            # Push AuraConnect data to POS
            await self._push_entity_to_pos(
                sync_job, pos_adapter, mapping, resolution_data, ctx
            )
        else:
            # Pull POS data to AuraConnect
            await self._pull_entity_to_aura(sync_job, mapping, resolution_data, ctx)

    def _detect_conflicting_fields(self, aura_data: Dict, pos_data: Dict) -> List[str]:
        """Detect which fields have conflicts between systems"""
        conflicting_fields = []

        # Compare common fields
        common_fields = ["name", "description", "price", "is_active", "is_available"]

        for field in common_fields:
            aura_value = aura_data.get(field)
            pos_value = pos_data.get(field)

            if aura_value != pos_value:
                conflicting_fields.append(field)

        return conflicting_fields

    def _calculate_conflict_priority(self, aura_data: Dict, pos_data: Dict) -> int:
        """Calculate conflict priority (1-10, higher = more urgent)"""
        priority = 5  # Default medium priority

        # High priority if price conflicts
        if aura_data.get("price") != pos_data.get("price"):
            priority = 8

        # High priority if availability conflicts
        if aura_data.get("is_available") != pos_data.get("is_available"):
            priority = 7

        return priority

    def _calculate_conflict_severity(self, aura_data: Dict, pos_data: Dict) -> str:
        """Calculate conflict severity"""
        # High severity for price mismatches
        if aura_data.get("price") != pos_data.get("price"):
            return "high"

        # Medium severity for availability mismatches
        if aura_data.get("is_available") != pos_data.get("is_available"):
            return "medium"

        return "low"

    @contextmanager
    def _sync_context(self, sync_job: MenuSyncJob, version_id: Optional[int] = None):
        """Context manager for sync operations"""
        context = {
            "sync_job": sync_job,
            "version_id": version_id,
            "start_time": datetime.utcnow(),
        }

        try:
            yield context
        except Exception as e:
            # Log any unhandled exceptions
            print(f"Sync context error: {str(e)}")
            raise

    async def _log_sync_operation(
        self,
        sync_job: MenuSyncJob,
        mapping: Optional[POSMenuMapping],
        operation: str,
        direction: SyncDirection,
        status: SyncStatus,
        ctx: Dict,
        **kwargs,
    ) -> MenuSyncLog:
        """Log a sync operation"""

        sync_log = MenuSyncLog(
            sync_job_id=sync_job.id,
            mapping_id=mapping.id if mapping else None,
            entity_type=(
                mapping.entity_type if mapping else kwargs.get("entity_type", "")
            ),
            aura_entity_id=(
                mapping.aura_entity_id if mapping else kwargs.get("aura_entity_id")
            ),
            pos_entity_id=(
                mapping.pos_entity_id if mapping else kwargs.get("pos_entity_id")
            ),
            operation=operation,
            sync_direction=direction,
            status=status,
            menu_version_id=ctx.get("version_id"),
            processing_time_ms=int(
                (datetime.utcnow() - ctx["start_time"]).total_seconds() * 1000
            ),
            **{
                k: v
                for k, v in kwargs.items()
                if k
                in [
                    "aura_data_before",
                    "aura_data_after",
                    "pos_data_before",
                    "pos_data_after",
                    "changes_detected",
                    "conflict_type",
                    "error_message",
                    "error_code",
                ]
            },
        )

        self.db.add(sync_log)
        self.db.flush()  # Get the ID without committing

        return sync_log

    async def _log_sync_error(
        self,
        sync_job: MenuSyncJob,
        mapping: POSMenuMapping,
        error_message: str,
        ctx: Dict,
    ):
        """Log a sync error"""
        await self._log_sync_operation(
            sync_job,
            mapping,
            "error",
            SyncDirection.BIDIRECTIONAL,
            SyncStatus.ERROR,
            ctx,
            error_message=error_message,
        )

    def _calculate_entity_hash(self, entity_data: Dict) -> str:
        """Calculate hash for entity data to detect changes"""
        if not entity_data:
            return ""

        # Create normalized data for hashing (exclude timestamps and IDs)
        hash_data = {
            k: v
            for k, v in entity_data.items()
            if k not in ["id", "created_at", "updated_at", "last_sync_at"]
        }

        return hashlib.sha256(
            json.dumps(hash_data, sort_keys=True).encode()
        ).hexdigest()

    def _generate_version_name(
        self, sync_config: MenuSyncConfig, operation: str
    ) -> str:
        """Generate version name for sync operations"""
        template = sync_config.version_name_template or "{operation}_{timestamp}"

        return template.format(
            operation=operation,
            timestamp=datetime.utcnow().strftime("%Y%m%d_%H%M%S"),
            vendor=(
                sync_config.pos_integration.vendor
                if hasattr(sync_config, "pos_integration")
                else "POS"
            ),
        )

    async def _update_sync_statistics(self, sync_job: MenuSyncJob):
        """Update sync statistics after job completion"""

        # Calculate job duration
        duration = None
        if sync_job.started_at and sync_job.completed_at:
            duration = (sync_job.completed_at - sync_job.started_at).total_seconds()

        # Get or create statistics record for current hour
        period_start = datetime.utcnow().replace(minute=0, second=0, microsecond=0)
        period_end = period_start + timedelta(hours=1)

        stats = (
            self.db.query(MenuSyncStatistics)
            .filter(
                and_(
                    MenuSyncStatistics.pos_integration_id
                    == sync_job.pos_integration_id,
                    MenuSyncStatistics.period_start == period_start,
                    MenuSyncStatistics.period_type == "hour",
                )
            )
            .first()
        )

        if not stats:
            stats = MenuSyncStatistics(
                pos_integration_id=sync_job.pos_integration_id,
                period_start=period_start,
                period_end=period_end,
                period_type="hour",
            )
            self.db.add(stats)

        # Update statistics
        stats.total_jobs += 1
        if sync_job.status == SyncStatus.SUCCESS:
            stats.successful_jobs += 1
        else:
            stats.failed_jobs += 1

        stats.total_entities_synced += sync_job.successful_entities
        stats.total_conflicts += sync_job.conflicts_detected

        # Update averages
        if duration:
            current_avg = stats.avg_job_duration_seconds or 0
            stats.avg_job_duration_seconds = (
                current_avg * (stats.total_jobs - 1) + duration
            ) / stats.total_jobs

        # Calculate success rate
        if stats.total_jobs > 0:
            stats.success_rate_percentage = (
                stats.successful_jobs / stats.total_jobs
            ) * 100
            stats.error_rate_percentage = (stats.failed_jobs / stats.total_jobs) * 100

        self.db.commit()

    async def get_sync_status(
        self, job_id: Union[str, uuid.UUID]
    ) -> Optional[SyncStatusResponse]:
        """Get status of a sync job"""

        sync_job = (
            self.db.query(MenuSyncJob).filter(MenuSyncJob.job_id == job_id).first()
        )

        if not sync_job:
            return None

        # Calculate estimated completion time
        estimated_completion = None
        if sync_job.status == SyncStatus.IN_PROGRESS and sync_job.started_at:
            if sync_job.processed_entities > 0 and sync_job.total_entities > 0:
                elapsed = datetime.utcnow() - sync_job.started_at
                rate = sync_job.processed_entities / elapsed.total_seconds()
                remaining = sync_job.total_entities - sync_job.processed_entities
                estimated_completion = datetime.utcnow() + timedelta(
                    seconds=remaining / rate
                )

        return SyncStatusResponse(
            job_id=sync_job.job_id,
            status=sync_job.status,
            progress={
                "processed": sync_job.processed_entities,
                "total": sync_job.total_entities,
                "conflicts": sync_job.conflicts_detected,
                "errors": sync_job.failed_entities,
            },
            started_at=sync_job.started_at,
            estimated_completion=estimated_completion,
            current_operation=f"Processing {sync_job.sync_direction.value} sync",
        )

    # Entity-specific operations implementation

    async def _get_aura_entity_data(
        self, entity_type: str, entity_id: int
    ) -> Optional[Dict]:
        """Get entity data from AuraConnect system"""
        try:
            if entity_type == "category":
                entity = (
                    self.db.query(MenuCategory)
                    .filter(
                        MenuCategory.id == entity_id, MenuCategory.deleted_at.is_(None)
                    )
                    .first()
                )
                if entity:
                    return {
                        "id": entity.id,
                        "name": entity.name,
                        "description": entity.description,
                        "display_order": entity.display_order,
                        "is_active": entity.is_active,
                        "parent_category_id": entity.parent_category_id,
                        "updated_at": (
                            entity.updated_at.isoformat() if entity.updated_at else None
                        ),
                    }

            elif entity_type == "item":
                entity = (
                    self.db.query(MenuItem)
                    .filter(MenuItem.id == entity_id, MenuItem.deleted_at.is_(None))
                    .first()
                )
                if entity:
                    return {
                        "id": entity.id,
                        "name": entity.name,
                        "description": entity.description,
                        "price": float(entity.price),
                        "category_id": entity.category_id,
                        "sku": entity.sku,
                        "is_active": entity.is_active,
                        "is_available": entity.is_available,
                        "calories": entity.calories,
                        "dietary_tags": entity.dietary_tags,
                        "allergens": entity.allergens,
                        "updated_at": (
                            entity.updated_at.isoformat() if entity.updated_at else None
                        ),
                    }

            elif entity_type == "modifier_group":
                entity = (
                    self.db.query(ModifierGroup)
                    .filter(
                        ModifierGroup.id == entity_id,
                        ModifierGroup.deleted_at.is_(None),
                    )
                    .first()
                )
                if entity:
                    return {
                        "id": entity.id,
                        "name": entity.name,
                        "description": entity.description,
                        "selection_type": entity.selection_type,
                        "min_selections": entity.min_selections,
                        "max_selections": entity.max_selections,
                        "is_required": entity.is_required,
                        "is_active": entity.is_active,
                        "updated_at": (
                            entity.updated_at.isoformat() if entity.updated_at else None
                        ),
                    }

            elif entity_type == "modifier":
                entity = (
                    self.db.query(Modifier)
                    .filter(Modifier.id == entity_id, Modifier.deleted_at.is_(None))
                    .first()
                )
                if entity:
                    return {
                        "id": entity.id,
                        "name": entity.name,
                        "description": entity.description,
                        "price_adjustment": float(entity.price_adjustment),
                        "price_type": entity.price_type,
                        "is_active": entity.is_active,
                        "is_available": entity.is_available,
                        "updated_at": (
                            entity.updated_at.isoformat() if entity.updated_at else None
                        ),
                    }

            return None

        except Exception as e:
            logger.error(
                f"Error fetching AuraConnect {entity_type} {entity_id}: {str(e)}"
            )
            return None

    async def _get_pos_entity_data(
        self, pos_adapter, entity_type: str, pos_entity_id: str
    ) -> Optional[Dict]:
        """Get entity data from POS system"""
        try:
            if entity_type == "category":
                categories = await pos_adapter.get_menu_categories()
                for category in categories:
                    if category.get("id") == pos_entity_id:
                        return category

            elif entity_type == "item":
                items = await pos_adapter.get_menu_items()
                for item in items:
                    if item.get("id") == pos_entity_id:
                        return item

            elif entity_type == "modifier_group":
                modifier_groups = await pos_adapter.get_modifier_groups()
                for group in modifier_groups:
                    if group.get("id") == pos_entity_id:
                        return group

            elif entity_type == "modifier":
                # For modifiers, we need to find the parent group first
                # This is a simplified implementation
                logger.warning(
                    f"Getting individual modifier {pos_entity_id} not fully implemented"
                )
                return None

            return None

        except Exception as e:
            logger.error(f"Error fetching POS {entity_type} {pos_entity_id}: {str(e)}")
            return None

    async def _push_entity_type(
        self, sync_job: MenuSyncJob, pos_adapter, entity_type: str, ctx
    ):
        """Push all entities of a specific type to POS"""
        try:
            # Get all mappings for this entity type
            mappings = (
                self.db.query(POSMenuMapping)
                .filter(
                    and_(
                        POSMenuMapping.pos_integration_id
                        == sync_job.pos_integration_id,
                        POSMenuMapping.entity_type == entity_type,
                        POSMenuMapping.sync_enabled == True,
                        POSMenuMapping.is_active == True,
                        POSMenuMapping.sync_direction.in_(
                            [SyncDirection.PUSH, SyncDirection.BIDIRECTIONAL]
                        ),
                    )
                )
                .all()
            )

            for mapping in mappings:
                try:
                    # Get current AuraConnect data
                    aura_data = await self._get_aura_entity_data(
                        entity_type, mapping.aura_entity_id
                    )
                    if aura_data:
                        await self._push_entity_to_pos(
                            sync_job, pos_adapter, mapping, aura_data, ctx
                        )
                        sync_job.successful_entities += 1
                    else:
                        logger.warning(
                            f"AuraConnect {entity_type} {mapping.aura_entity_id} not found"
                        )
                        sync_job.failed_entities += 1

                except Exception as e:
                    logger.error(
                        f"Error pushing {entity_type} {mapping.aura_entity_id}: {str(e)}"
                    )
                    sync_job.failed_entities += 1
                    await self._log_sync_error(sync_job, mapping, str(e), ctx)

                sync_job.processed_entities += 1

        except Exception as e:
            logger.error(f"Error pushing {entity_type} entities: {str(e)}")
            raise

    async def _pull_categories(self, sync_job: MenuSyncJob, pos_adapter, ctx):
        """Pull categories from POS system"""
        try:
            pos_categories = await pos_adapter.get_menu_categories()

            for pos_category in pos_categories:
                try:
                    await self._process_pos_entity(
                        sync_job, "category", pos_category, pos_adapter, ctx
                    )
                    sync_job.processed_entities += 1

                except Exception as e:
                    logger.error(
                        f"Error processing POS category {pos_category.get('id', 'unknown')}: {str(e)}"
                    )
                    sync_job.failed_entities += 1

        except Exception as e:
            logger.error(f"Error pulling categories: {str(e)}")
            raise

    async def _pull_items(self, sync_job: MenuSyncJob, pos_adapter, ctx):
        """Pull menu items from POS system"""
        try:
            pos_items = await pos_adapter.get_menu_items()

            for pos_item in pos_items:
                try:
                    await self._process_pos_entity(
                        sync_job, "item", pos_item, pos_adapter, ctx
                    )
                    sync_job.processed_entities += 1

                except Exception as e:
                    logger.error(
                        f"Error processing POS item {pos_item.get('id', 'unknown')}: {str(e)}"
                    )
                    sync_job.failed_entities += 1

        except Exception as e:
            logger.error(f"Error pulling items: {str(e)}")
            raise

    async def _pull_modifiers(self, sync_job: MenuSyncJob, pos_adapter, ctx):
        """Pull modifiers from POS system"""
        try:
            pos_modifier_groups = await pos_adapter.get_modifier_groups()

            for pos_group in pos_modifier_groups:
                try:
                    await self._process_pos_entity(
                        sync_job, "modifier_group", pos_group, pos_adapter, ctx
                    )
                    sync_job.processed_entities += 1

                    # Also pull individual modifiers in the group
                    pos_modifiers = await pos_adapter.get_modifiers(pos_group.get("id"))
                    for pos_modifier in pos_modifiers:
                        try:
                            await self._process_pos_entity(
                                sync_job, "modifier", pos_modifier, pos_adapter, ctx
                            )
                            sync_job.processed_entities += 1
                        except Exception as e:
                            logger.error(f"Error processing POS modifier: {str(e)}")
                            sync_job.failed_entities += 1

                except Exception as e:
                    logger.error(
                        f"Error processing POS modifier group {pos_group.get('id', 'unknown')}: {str(e)}"
                    )
                    sync_job.failed_entities += 1

        except Exception as e:
            logger.error(f"Error pulling modifiers: {str(e)}")
            raise

    async def _process_pos_entity(
        self,
        sync_job: MenuSyncJob,
        entity_type: str,
        pos_entity_data: Dict,
        pos_adapter,
        ctx,
    ):
        """Process a single entity from POS system"""
        pos_entity_id = pos_entity_data.get("id")
        if not pos_entity_id:
            logger.warning(f"POS {entity_type} missing ID, skipping")
            return

        # Check if mapping exists
        mapping = (
            self.db.query(POSMenuMapping)
            .filter(
                and_(
                    POSMenuMapping.pos_integration_id == sync_job.pos_integration_id,
                    POSMenuMapping.entity_type == entity_type,
                    POSMenuMapping.pos_entity_id == pos_entity_id,
                )
            )
            .first()
        )

        if mapping:
            # Update existing mapping
            await self._pull_entity_to_aura(sync_job, mapping, pos_entity_data, ctx)
        else:
            # Create new entity and mapping
            await self._create_aura_entity_from_pos(
                sync_job, entity_type, pos_entity_data, ctx
            )

    async def _push_entity_to_pos(
        self,
        sync_job: MenuSyncJob,
        pos_adapter,
        mapping: POSMenuMapping,
        entity_data: Dict,
        ctx,
    ):
        """Push a single entity to POS system"""
        try:
            entity_type = mapping.entity_type
            pos_entity_id = mapping.pos_entity_id

            if entity_type == "category":
                if pos_entity_id and pos_entity_id != "new":
                    # Update existing category
                    result = await pos_adapter.update_menu_category(
                        pos_entity_id, entity_data
                    )
                else:
                    # Create new category
                    result = await pos_adapter.create_menu_category(entity_data)
                    if result and "id" in result:
                        mapping.pos_entity_id = result["id"]

            elif entity_type == "item":
                if pos_entity_id and pos_entity_id != "new":
                    result = await pos_adapter.update_menu_item(
                        pos_entity_id, entity_data
                    )
                else:
                    result = await pos_adapter.create_menu_item(entity_data)
                    if result and "id" in result:
                        mapping.pos_entity_id = result["id"]

            elif entity_type == "modifier_group":
                if pos_entity_id and pos_entity_id != "new":
                    result = await pos_adapter.update_modifier_group(
                        pos_entity_id, entity_data
                    )
                else:
                    result = await pos_adapter.create_modifier_group(entity_data)
                    if result and "id" in result:
                        mapping.pos_entity_id = result["id"]

            elif entity_type == "modifier":
                # Modifiers require parent group handling
                logger.warning(f"Modifier push to POS not fully implemented")
                return

            # Update mapping metadata
            mapping.last_sync_at = datetime.utcnow()
            mapping.last_sync_direction = SyncDirection.PUSH
            mapping.sync_hash = self._calculate_entity_hash(entity_data)

            await self._log_sync_operation(
                sync_job,
                mapping,
                "push",
                SyncDirection.PUSH,
                SyncStatus.SUCCESS,
                ctx,
                aura_data_after=entity_data,
            )

        except Exception as e:
            logger.error(f"Error pushing {mapping.entity_type} to POS: {str(e)}")
            await self._log_sync_operation(
                sync_job,
                mapping,
                "push",
                SyncDirection.PUSH,
                SyncStatus.ERROR,
                ctx,
                error_message=str(e),
            )
            raise

    async def _pull_entity_to_aura(
        self, sync_job: MenuSyncJob, mapping: POSMenuMapping, entity_data: Dict, ctx
    ):
        """Pull a single entity to AuraConnect system"""
        try:
            entity_type = mapping.entity_type
            aura_entity_id = mapping.aura_entity_id

            # Get current AuraConnect entity
            if entity_type == "category":
                entity = self.db.query(MenuCategory).get(aura_entity_id)
                if entity:
                    self._update_aura_category(entity, entity_data)

            elif entity_type == "item":
                entity = self.db.query(MenuItem).get(aura_entity_id)
                if entity:
                    self._update_aura_item(entity, entity_data)

            elif entity_type == "modifier_group":
                entity = self.db.query(ModifierGroup).get(aura_entity_id)
                if entity:
                    self._update_aura_modifier_group(entity, entity_data)

            elif entity_type == "modifier":
                entity = self.db.query(Modifier).get(aura_entity_id)
                if entity:
                    self._update_aura_modifier(entity, entity_data)

            # Update mapping metadata
            mapping.last_sync_at = datetime.utcnow()
            mapping.last_sync_direction = SyncDirection.PULL
            mapping.sync_hash = self._calculate_entity_hash(entity_data)
            mapping.pos_entity_data = entity_data

            await self._log_sync_operation(
                sync_job,
                mapping,
                "pull",
                SyncDirection.PULL,
                SyncStatus.SUCCESS,
                ctx,
                pos_data_after=entity_data,
            )

        except Exception as e:
            logger.error(
                f"Error pulling {mapping.entity_type} to AuraConnect: {str(e)}"
            )
            await self._log_sync_operation(
                sync_job,
                mapping,
                "pull",
                SyncDirection.PULL,
                SyncStatus.ERROR,
                ctx,
                error_message=str(e),
            )
            raise

    async def _create_aura_entity_from_pos(
        self, sync_job: MenuSyncJob, entity_type: str, pos_entity_data: Dict, ctx
    ):
        """Create new AuraConnect entity from POS data"""
        try:
            new_entity = None

            if entity_type == "category":
                new_entity = MenuCategory(
                    name=pos_entity_data.get("name", ""),
                    description=pos_entity_data.get("description", ""),
                    display_order=pos_entity_data.get("display_order", 0),
                    is_active=pos_entity_data.get("is_active", True),
                )
                self.db.add(new_entity)
                self.db.flush()  # Get the ID

            elif entity_type == "item":
                new_entity = MenuItem(
                    name=pos_entity_data.get("name", ""),
                    description=pos_entity_data.get("description", ""),
                    price=pos_entity_data.get("price", 0.0),
                    category_id=self._resolve_category_id(
                        pos_entity_data.get("category_id")
                    ),
                    sku=pos_entity_data.get("sku", ""),
                    is_active=pos_entity_data.get("is_active", True),
                    is_available=pos_entity_data.get("is_available", True),
                )
                self.db.add(new_entity)
                self.db.flush()

            # Create mapping
            if new_entity:
                mapping = POSMenuMapping(
                    pos_integration_id=sync_job.pos_integration_id,
                    pos_vendor=sync_job.pos_integration.vendor,
                    entity_type=entity_type,
                    aura_entity_id=new_entity.id,
                    pos_entity_id=pos_entity_data.get("id"),
                    pos_entity_data=pos_entity_data,
                    last_sync_at=datetime.utcnow(),
                    last_sync_direction=SyncDirection.PULL,
                    sync_hash=self._calculate_entity_hash(pos_entity_data),
                )
                self.db.add(mapping)

                await self._log_sync_operation(
                    sync_job,
                    mapping,
                    "create",
                    SyncDirection.PULL,
                    SyncStatus.SUCCESS,
                    ctx,
                    pos_data_after=pos_entity_data,
                )

        except Exception as e:
            logger.error(
                f"Error creating AuraConnect {entity_type} from POS data: {str(e)}"
            )
            await self._log_sync_error(sync_job, None, str(e), ctx)
            raise

    def _update_aura_category(self, category: MenuCategory, pos_data: Dict):
        """Update AuraConnect category with POS data"""
        if "name" in pos_data:
            category.name = pos_data["name"]
        if "description" in pos_data:
            category.description = pos_data["description"]
        if "is_active" in pos_data:
            category.is_active = pos_data["is_active"]
        if "display_order" in pos_data:
            category.display_order = pos_data["display_order"]

    def _update_aura_item(self, item: MenuItem, pos_data: Dict):
        """Update AuraConnect item with POS data"""
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
        if "sku" in pos_data:
            item.sku = pos_data["sku"]

    def _update_aura_modifier_group(
        self, modifier_group: ModifierGroup, pos_data: Dict
    ):
        """Update AuraConnect modifier group with POS data"""
        if "name" in pos_data:
            modifier_group.name = pos_data["name"]
        if "description" in pos_data:
            modifier_group.description = pos_data["description"]
        if "selection_type" in pos_data:
            modifier_group.selection_type = pos_data["selection_type"]
        if "is_required" in pos_data:
            modifier_group.is_required = pos_data["is_required"]
        if "min_selections" in pos_data:
            modifier_group.min_selections = pos_data["min_selections"]
        if "max_selections" in pos_data:
            modifier_group.max_selections = pos_data["max_selections"]

    def _update_aura_modifier(self, modifier: Modifier, pos_data: Dict):
        """Update AuraConnect modifier with POS data"""
        if "name" in pos_data:
            modifier.name = pos_data["name"]
        if "description" in pos_data:
            modifier.description = pos_data["description"]
        if "price_adjustment" in pos_data:
            modifier.price_adjustment = pos_data["price_adjustment"]
        if "price_type" in pos_data:
            modifier.price_type = pos_data["price_type"]
        if "is_active" in pos_data:
            modifier.is_active = pos_data["is_active"]
        if "is_available" in pos_data:
            modifier.is_available = pos_data["is_available"]

    def _resolve_category_id(self, pos_category_id: Optional[str]) -> Optional[int]:
        """Resolve POS category ID to AuraConnect category ID"""
        if not pos_category_id:
            return None

        # Look up the mapping
        mapping = (
            self.db.query(POSMenuMapping)
            .filter(
                and_(
                    POSMenuMapping.entity_type == "category",
                    POSMenuMapping.pos_entity_id == pos_category_id,
                )
            )
            .first()
        )

        return mapping.aura_entity_id if mapping else None
