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
    POSMenuMapping, MenuSyncJob, MenuSyncLog, MenuSyncConflict, 
    MenuSyncConfig, MenuSyncStatistics, SyncDirection, SyncStatus, 
    ConflictResolution
)
from .menu_sync_schemas import (
    StartSyncRequest, SyncStatusResponse, MenuCategorySync, 
    MenuItemSync, ModifierGroupSync, ModifierSync
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
            'square': SquareAdapter,
            'toast': ToastAdapter,
            'clover': CloverAdapter
        }
    
    def get_pos_adapter(self, pos_integration: POSIntegration):
        """Get the appropriate POS adapter for the integration"""
        adapter_class = self._pos_adapters.get(pos_integration.vendor.lower())
        if not adapter_class:
            raise ValueError(f"Unsupported POS vendor: {pos_integration.vendor}")
        return adapter_class(pos_integration.credentials)
    
    async def start_sync(self, request: StartSyncRequest, user_id: Optional[int] = None) -> MenuSyncJob:
        """Start a new menu synchronization job"""
        
        # Get POS integration and config
        pos_integration = self.db.query(POSIntegration).filter(
            POSIntegration.id == request.pos_integration_id
        ).first()
        if not pos_integration:
            raise ValueError(f"POS integration {request.pos_integration_id} not found")
        
        sync_config = self.db.query(MenuSyncConfig).filter(
            MenuSyncConfig.pos_integration_id == request.pos_integration_id
        ).first()
        if not sync_config or not sync_config.sync_enabled:
            raise ValueError("Menu sync is not enabled for this POS integration")
        
        # Check for active jobs
        active_jobs = self.db.query(MenuSyncJob).filter(
            and_(
                MenuSyncJob.pos_integration_id == request.pos_integration_id,
                MenuSyncJob.status.in_([SyncStatus.PENDING, SyncStatus.IN_PROGRESS])
            )
        ).count()
        
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
                "conflict_resolution": request.conflict_resolution or sync_config.default_conflict_resolution
            }
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
            pos_integration = self.db.query(POSIntegration).get(sync_job.pos_integration_id)
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
                    self._delayed_retry(sync_job, delay_seconds=60 * (2 ** sync_job.retry_count))
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
        entity_types = sync_job.entity_types or ['category', 'item', 'modifier_group', 'modifier']
        
        with self._sync_context(sync_job) as ctx:
            for entity_type in entity_types:
                await self._push_entity_type(sync_job, pos_adapter, entity_type, ctx)
    
    async def _pull_from_pos(self, sync_job: MenuSyncJob, pos_adapter):
        """Pull menu data from POS system to AuraConnect"""
        sync_config = self.db.query(MenuSyncConfig).filter(
            MenuSyncConfig.pos_integration_id == sync_job.pos_integration_id
        ).first()
        
        # Create version before pull if configured
        version_id = None
        if sync_config.create_version_on_pull:
            version_name = self._generate_version_name(sync_config, "POS_PULL")
            with self.versioning_service.audit_context(
                user_id=sync_job.triggered_by_id or 0,
                action="pos_sync_pull",
                session_id=str(sync_job.job_id)
            ):
                version = self.versioning_service.create_version(
                    version_name=version_name,
                    description=f"Version created before POS pull sync (Job: {sync_job.job_id})",
                    user_id=sync_job.triggered_by_id or 0
                )
                version_id = version.id
        
        with self._sync_context(sync_job, version_id) as ctx:
            # Pull categories first (hierarchical dependency)
            if not sync_job.entity_types or 'category' in sync_job.entity_types:
                await self._pull_categories(sync_job, pos_adapter, ctx)
            
            # Pull items
            if not sync_job.entity_types or 'item' in sync_job.entity_types:
                await self._pull_items(sync_job, pos_adapter, ctx)
            
            # Pull modifiers
            if not sync_job.entity_types or 'modifier' in sync_job.entity_types:
                await self._pull_modifiers(sync_job, pos_adapter, ctx)
    
    async def _bidirectional_sync(self, sync_job: MenuSyncJob, pos_adapter):
        """Perform bidirectional synchronization with conflict detection"""
        
        with self._sync_context(sync_job) as ctx:
            # Get all mappings for this integration
            mappings = self.db.query(POSMenuMapping).filter(
                and_(
                    POSMenuMapping.pos_integration_id == sync_job.pos_integration_id,
                    POSMenuMapping.sync_enabled == True,
                    POSMenuMapping.is_active == True
                )
            ).all()
            
            sync_job.total_entities = len(mappings)
            
            for mapping in mappings:
                try:
                    await self._sync_entity_bidirectional(sync_job, pos_adapter, mapping, ctx)
                    sync_job.processed_entities += 1
                    
                except Exception as e:
                    sync_job.failed_entities += 1
                    await self._log_sync_error(sync_job, mapping, str(e), ctx)
                
                self.db.commit()
    
    async def _sync_entity_bidirectional(self, sync_job: MenuSyncJob, pos_adapter, mapping: POSMenuMapping, ctx):
        """Sync a single entity bidirectionally"""
        
        # Get current data from both systems
        aura_data = await self._get_aura_entity_data(mapping.entity_type, mapping.aura_entity_id)
        pos_data = await self._get_pos_entity_data(pos_adapter, mapping.entity_type, mapping.pos_entity_id)
        
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
                sync_job, mapping, "no_change", SyncDirection.BIDIRECTIONAL, 
                SyncStatus.SUCCESS, ctx
            )
            return
        
        # Handle different change scenarios
        if aura_changed and not pos_changed:
            # Only AuraConnect changed, push to POS
            if mapping.sync_direction in [SyncDirection.PUSH, SyncDirection.BIDIRECTIONAL]:
                await self._push_entity_to_pos(sync_job, pos_adapter, mapping, aura_data, ctx)
        
        elif pos_changed and not aura_changed:
            # Only POS changed, pull to AuraConnect
            if mapping.sync_direction in [SyncDirection.PULL, SyncDirection.BIDIRECTIONAL]:
                await self._pull_entity_to_aura(sync_job, mapping, pos_data, ctx)
        
        else:
            # Both changed - conflict detected
            await self._handle_sync_conflict(sync_job, mapping, aura_data, pos_data, ctx)
    
    async def _handle_sync_conflict(self, sync_job: MenuSyncJob, mapping: POSMenuMapping, 
                                  aura_data: Dict, pos_data: Dict, ctx):
        """Handle synchronization conflicts"""
        
        sync_job.conflicts_detected += 1
        
        # Determine conflict resolution strategy
        resolution_strategy = mapping.conflict_resolution
        if sync_job.job_config and "conflict_resolution" in sync_job.job_config:
            resolution_strategy = ConflictResolution(sync_job.job_config["conflict_resolution"])
        
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
            severity=self._calculate_conflict_severity(aura_data, pos_data)
        )
        
        # Log the conflict
        sync_log = await self._log_sync_operation(
            sync_job, mapping, "conflict", SyncDirection.BIDIRECTIONAL,
            SyncStatus.CONFLICT, ctx, 
            aura_data_before=aura_data, pos_data_before=pos_data,
            conflict_type="data_mismatch"
        )
        
        conflict.sync_log_id = sync_log.id
        self.db.add(conflict)
        
        # Auto-resolve if possible
        if conflict.auto_resolvable:
            await self._auto_resolve_conflict(conflict, resolution_strategy, ctx)
        else:
            sync_job.status = SyncStatus.CONFLICT
    
    async def _auto_resolve_conflict(self, conflict: MenuSyncConflict, 
                                   strategy: ConflictResolution, ctx):
        """Automatically resolve conflicts based on strategy"""
        
        try:
            if strategy == ConflictResolution.AURA_WINS:
                # Use AuraConnect data
                await self._apply_resolution_data(conflict, conflict.aura_current_data, "aura", ctx)
            
            elif strategy == ConflictResolution.POS_WINS:
                # Use POS data
                await self._apply_resolution_data(conflict, conflict.pos_current_data, "pos", ctx)
            
            elif strategy == ConflictResolution.LATEST_WINS:
                # Compare timestamps and use most recent
                aura_modified = conflict.aura_current_data.get('updated_at') if conflict.aura_current_data else None
                pos_modified = conflict.pos_current_data.get('updated_at') if conflict.pos_current_data else None
                
                if aura_modified and pos_modified:
                    if aura_modified > pos_modified:
                        await self._apply_resolution_data(conflict, conflict.aura_current_data, "aura", ctx)
                    else:
                        await self._apply_resolution_data(conflict, conflict.pos_current_data, "pos", ctx)
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
    
    async def _apply_resolution_data(self, conflict: MenuSyncConflict, 
                                   resolution_data: Dict, source: str, ctx):
        """Apply conflict resolution data to both systems"""
        
        mapping = self.db.query(POSMenuMapping).get(conflict.mapping_id)
        sync_job = self.db.query(MenuSyncJob).get(conflict.sync_job_id)
        pos_integration = self.db.query(POSIntegration).get(sync_job.pos_integration_id)
        pos_adapter = self.get_pos_adapter(pos_integration)
        
        if source == "aura":
            # Push AuraConnect data to POS
            await self._push_entity_to_pos(sync_job, pos_adapter, mapping, resolution_data, ctx)
        else:
            # Pull POS data to AuraConnect
            await self._pull_entity_to_aura(sync_job, mapping, resolution_data, ctx)
    
    def _detect_conflicting_fields(self, aura_data: Dict, pos_data: Dict) -> List[str]:
        """Detect which fields have conflicts between systems"""
        conflicting_fields = []
        
        # Compare common fields
        common_fields = ['name', 'description', 'price', 'is_active', 'is_available']
        
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
        if aura_data.get('price') != pos_data.get('price'):
            priority = 8
        
        # High priority if availability conflicts
        if aura_data.get('is_available') != pos_data.get('is_available'):
            priority = 7
        
        return priority
    
    def _calculate_conflict_severity(self, aura_data: Dict, pos_data: Dict) -> str:
        """Calculate conflict severity"""
        # High severity for price mismatches
        if aura_data.get('price') != pos_data.get('price'):
            return "high"
        
        # Medium severity for availability mismatches
        if aura_data.get('is_available') != pos_data.get('is_available'):
            return "medium"
        
        return "low"
    
    @contextmanager
    def _sync_context(self, sync_job: MenuSyncJob, version_id: Optional[int] = None):
        """Context manager for sync operations"""
        context = {
            'sync_job': sync_job,
            'version_id': version_id,
            'start_time': datetime.utcnow()
        }
        
        try:
            yield context
        except Exception as e:
            # Log any unhandled exceptions
            print(f"Sync context error: {str(e)}")
            raise
    
    async def _log_sync_operation(self, sync_job: MenuSyncJob, mapping: Optional[POSMenuMapping],
                                operation: str, direction: SyncDirection, status: SyncStatus,
                                ctx: Dict, **kwargs) -> MenuSyncLog:
        """Log a sync operation"""
        
        sync_log = MenuSyncLog(
            sync_job_id=sync_job.id,
            mapping_id=mapping.id if mapping else None,
            entity_type=mapping.entity_type if mapping else kwargs.get('entity_type', ''),
            aura_entity_id=mapping.aura_entity_id if mapping else kwargs.get('aura_entity_id'),
            pos_entity_id=mapping.pos_entity_id if mapping else kwargs.get('pos_entity_id'),
            operation=operation,
            sync_direction=direction,
            status=status,
            menu_version_id=ctx.get('version_id'),
            processing_time_ms=int((datetime.utcnow() - ctx['start_time']).total_seconds() * 1000),
            **{k: v for k, v in kwargs.items() if k in [
                'aura_data_before', 'aura_data_after', 'pos_data_before', 'pos_data_after',
                'changes_detected', 'conflict_type', 'error_message', 'error_code'
            ]}
        )
        
        self.db.add(sync_log)
        self.db.flush()  # Get the ID without committing
        
        return sync_log
    
    async def _log_sync_error(self, sync_job: MenuSyncJob, mapping: POSMenuMapping, 
                            error_message: str, ctx: Dict):
        """Log a sync error"""
        await self._log_sync_operation(
            sync_job, mapping, "error", SyncDirection.BIDIRECTIONAL,
            SyncStatus.ERROR, ctx, error_message=error_message
        )
    
    def _calculate_entity_hash(self, entity_data: Dict) -> str:
        """Calculate hash for entity data to detect changes"""
        if not entity_data:
            return ""
        
        # Create normalized data for hashing (exclude timestamps and IDs)
        hash_data = {k: v for k, v in entity_data.items() 
                    if k not in ['id', 'created_at', 'updated_at', 'last_sync_at']}
        
        return hashlib.sha256(json.dumps(hash_data, sort_keys=True).encode()).hexdigest()
    
    def _generate_version_name(self, sync_config: MenuSyncConfig, operation: str) -> str:
        """Generate version name for sync operations"""
        template = sync_config.version_name_template or "{operation}_{timestamp}"
        
        return template.format(
            operation=operation,
            timestamp=datetime.utcnow().strftime("%Y%m%d_%H%M%S"),
            vendor=sync_config.pos_integration.vendor if hasattr(sync_config, 'pos_integration') else 'POS'
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
        
        stats = self.db.query(MenuSyncStatistics).filter(
            and_(
                MenuSyncStatistics.pos_integration_id == sync_job.pos_integration_id,
                MenuSyncStatistics.period_start == period_start,
                MenuSyncStatistics.period_type == "hour"
            )
        ).first()
        
        if not stats:
            stats = MenuSyncStatistics(
                pos_integration_id=sync_job.pos_integration_id,
                period_start=period_start,
                period_end=period_end,
                period_type="hour"
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
            stats.avg_job_duration_seconds = (current_avg * (stats.total_jobs - 1) + duration) / stats.total_jobs
        
        # Calculate success rate
        if stats.total_jobs > 0:
            stats.success_rate_percentage = (stats.successful_jobs / stats.total_jobs) * 100
            stats.error_rate_percentage = (stats.failed_jobs / stats.total_jobs) * 100
        
        self.db.commit()
    
    async def get_sync_status(self, job_id: Union[str, uuid.UUID]) -> Optional[SyncStatusResponse]:
        """Get status of a sync job"""
        
        sync_job = self.db.query(MenuSyncJob).filter(
            MenuSyncJob.job_id == job_id
        ).first()
        
        if not sync_job:
            return None
        
        # Calculate estimated completion time
        estimated_completion = None
        if sync_job.status == SyncStatus.IN_PROGRESS and sync_job.started_at:
            if sync_job.processed_entities > 0 and sync_job.total_entities > 0:
                elapsed = datetime.utcnow() - sync_job.started_at
                rate = sync_job.processed_entities / elapsed.total_seconds()
                remaining = sync_job.total_entities - sync_job.processed_entities
                estimated_completion = datetime.utcnow() + timedelta(seconds=remaining / rate)
        
        return SyncStatusResponse(
            job_id=sync_job.job_id,
            status=sync_job.status,
            progress={
                "processed": sync_job.processed_entities,
                "total": sync_job.total_entities,
                "conflicts": sync_job.conflicts_detected,
                "errors": sync_job.failed_entities
            },
            started_at=sync_job.started_at,
            estimated_completion=estimated_completion,
            current_operation=f"Processing {sync_job.sync_direction.value} sync"
        )
    
    # Placeholder methods for entity-specific operations
    # These would be implemented based on specific POS adapter capabilities
    
    async def _get_aura_entity_data(self, entity_type: str, entity_id: int) -> Optional[Dict]:
        """Get entity data from AuraConnect system"""
        # Implementation would fetch from appropriate model based on entity_type
        pass
    
    async def _get_pos_entity_data(self, pos_adapter, entity_type: str, pos_entity_id: str) -> Optional[Dict]:
        """Get entity data from POS system"""
        # Implementation would use pos_adapter to fetch data
        pass
    
    async def _push_entity_type(self, sync_job: MenuSyncJob, pos_adapter, entity_type: str, ctx):
        """Push all entities of a specific type to POS"""
        pass
    
    async def _pull_categories(self, sync_job: MenuSyncJob, pos_adapter, ctx):
        """Pull categories from POS system"""
        pass
    
    async def _pull_items(self, sync_job: MenuSyncJob, pos_adapter, ctx):
        """Pull menu items from POS system"""
        pass
    
    async def _pull_modifiers(self, sync_job: MenuSyncJob, pos_adapter, ctx):
        """Pull modifiers from POS system"""
        pass
    
    async def _push_entity_to_pos(self, sync_job: MenuSyncJob, pos_adapter, 
                                mapping: POSMenuMapping, entity_data: Dict, ctx):
        """Push a single entity to POS system"""
        pass
    
    async def _pull_entity_to_aura(self, sync_job: MenuSyncJob, mapping: POSMenuMapping, 
                                 entity_data: Dict, ctx):
        """Pull a single entity to AuraConnect system"""
        pass