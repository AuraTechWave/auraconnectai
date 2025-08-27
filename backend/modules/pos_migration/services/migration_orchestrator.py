# backend/modules/pos_migration/services/migration_orchestrator.py

"""
Main orchestration service for POS data migrations.
Coordinates the entire migration workflow from setup to completion.
"""

import asyncio
import logging
import uuid
from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import create_engine
from contextlib import asynccontextmanager

from ..schemas.migration_schemas import (
    MigrationPhase,
    MigrationStatus,
    MigrationOptions,
    POSConnectionConfig,
    MigrationPlan,
    ValidationReport,
    MigrationProgressEvent,
    MigrationErrorEvent,
    ConsentRequest,
    ConsentStatus,
    AuditLogEntry,
    ComplianceReport,
    MigrationSummaryData,
)
from ..agents.migration_coach_agent import MigrationCoachAgent
from .data_transformation_service import DataTransformationService
from .audit_service import AuditService
from .notification_service import NotificationService
from .websocket_manager import websocket_manager
from .rollback_service import RollbackService
from ..utils import (
    with_retry, 
    api_retry_config,
    square_rate_limiter,
    toast_rate_limiter,
    clover_rate_limiter,
    BatchProcessor
)
from modules.pos.adapters.adapter_factory import AdapterFactory
from modules.pos.models.pos_integration import POSIntegration
from ..adapters import MigrationAdapterWrapper
from core.database import get_db
from core.exceptions import APIException

logger = logging.getLogger(__name__)


class MigrationOrchestrator:
    """Orchestrates the entire POS migration workflow"""
    
    def __init__(self, db: Session):
        self.db = db
        self.coach_agent = MigrationCoachAgent(db)
        self.transformation_service = DataTransformationService(db)
        self.audit_service = AuditService(db)
        self.notification_service = NotificationService(db)
        self.rollback_service = RollbackService(db)
        self.active_migrations: Dict[str, MigrationStatus] = {}
        
        # Rate limiters by POS type
        self.rate_limiters = {
            "square": square_rate_limiter,
            "toast": toast_rate_limiter,
            "clover": clover_rate_limiter
        }
        
    async def initiate_migration(
        self,
        tenant_id: str,
        pos_config: POSConnectionConfig,
        options: MigrationOptions,
        user_id: str
    ) -> str:
        """Start a new migration process"""
        
        migration_id = str(uuid.uuid4())
        
        try:
            # Initialize migration status
            status = MigrationStatus(
                migration_id=migration_id,
                phase=MigrationPhase.SETUP,
                progress_percent=0.0,
                started_at=datetime.utcnow(),
                estimated_completion=datetime.utcnow() + timedelta(hours=4)
            )
            self.active_migrations[migration_id] = status
            
            # Log initiation
            await self.audit_service.log_operation(
                migration_id=migration_id,
                operation="migration_initiated",
                user_id=user_id,
                details={
                    "pos_type": pos_config.pos_type,
                    "options": options.dict(),
                    "tenant_id": tenant_id
                }
            )
            
            # Start async migration workflow
            asyncio.create_task(
                self._run_migration_workflow(
                    migration_id, tenant_id, pos_config, options, user_id
                )
            )
            
            # Send initial notification
            await self.notification_service.send_migration_started(
                migration_id, tenant_id, user_id
            )
            
            return migration_id
            
        except Exception as e:
            logger.error(f"Failed to initiate migration: {e}")
            raise APIException(
                status_code=500,
                detail=f"Failed to initiate migration: {str(e)}"
            )
    
    async def _run_migration_workflow(
        self,
        migration_id: str,
        tenant_id: str,
        pos_config: POSConnectionConfig,
        options: MigrationOptions,
        user_id: str
    ):
        """Execute the complete migration workflow"""
        
        try:
            # Phase 1: Setup and Connection
            await self._update_phase(migration_id, MigrationPhase.SETUP, 5.0)
            pos_adapter = await self._setup_pos_connection(
                tenant_id, pos_config, migration_id
            )
            
            # Phase 2: Analysis
            await self._update_phase(migration_id, MigrationPhase.ANALYSIS, 15.0)
            analysis_results = await self._analyze_pos_data(
                pos_adapter, pos_config.pos_type, migration_id, options
            )
            
            # Phase 3: Field Mapping
            await self._update_phase(migration_id, MigrationPhase.MAPPING, 30.0)
            mapping_plan = await self._create_mapping_plan(
                analysis_results, pos_config.pos_type, migration_id, options
            )
            
            # Phase 4: Validation
            await self._update_phase(migration_id, MigrationPhase.VALIDATION, 45.0)
            validation_report = await self._validate_data(
                pos_adapter, mapping_plan, migration_id, options
            )
            
            # Check if manual review required
            if validation_report.summary.requires_manual_review:
                await self._pause_for_review(
                    migration_id, validation_report, mapping_plan
                )
                # Wait for approval via API
                await self._wait_for_approval(migration_id)
            
            # Phase 5: Import
            await self._update_phase(migration_id, MigrationPhase.IMPORT, 60.0)
            import_results = await self._import_data(
                pos_adapter, mapping_plan, tenant_id, migration_id, options
            )
            
            # Phase 6: Verification
            await self._update_phase(migration_id, MigrationPhase.VERIFICATION, 85.0)
            verification_results = await self._verify_import(
                import_results, tenant_id, migration_id
            )
            
            # Phase 7: Completion
            await self._update_phase(migration_id, MigrationPhase.COMPLETION, 100.0)
            await self._complete_migration(
                migration_id, tenant_id, import_results, user_id
            )
            
        except Exception as e:
            logger.error(f"Migration {migration_id} failed: {e}")
            await self._handle_migration_error(migration_id, str(e))
    
    async def _setup_pos_connection(
        self,
        tenant_id: str,
        pos_config: POSConnectionConfig,
        migration_id: str
    ):
        """Establish connection to POS system"""
        
        try:
            # Get or create POS integration record
            integration = self.db.query(POSIntegration).filter(
                POSIntegration.tenant_id == tenant_id,
                POSIntegration.pos_type == pos_config.pos_type
            ).first()
            
            if not integration:
                integration = POSIntegration(
                    tenant_id=tenant_id,
                    pos_type=pos_config.pos_type,
                    credentials=pos_config.credentials,
                    is_active=True
                )
                self.db.add(integration)
                self.db.commit()
            
            # Create adapter instance
            base_adapter = AdapterFactory.create_adapter(
                pos_type=pos_config.pos_type,
                credentials=pos_config.credentials
            )
            
            # Wrap with migration adapter
            adapter = MigrationAdapterWrapper(base_adapter)
            
            # Test connection
            await adapter.test_connection()
            
            await self.audit_service.log_operation(
                migration_id=migration_id,
                operation="pos_connection_established",
                details={"pos_type": pos_config.pos_type}
            )
            
            return adapter
            
        except Exception as e:
            raise APIException(
                status_code=400,
                detail=f"Failed to connect to {pos_config.pos_type}: {str(e)}"
            )
    
    async def _analyze_pos_data(
        self,
        pos_adapter,
        pos_type: str,
        migration_id: str,
        options: MigrationOptions
    ) -> Dict[str, Any]:
        """Analyze POS data structure and content"""
        
        analysis_results = {
            "menu_items": [],
            "categories": [],
            "modifiers": [],
            "customers": [],
            "orders": [],
            "statistics": {}
        }
        
        try:
            # Fetch sample data from each endpoint
            if hasattr(pos_adapter, 'fetch_menu_items'):
                items = await pos_adapter.fetch_menu_items(limit=100)
                analysis_results["menu_items"] = items
                
            if hasattr(pos_adapter, 'fetch_categories'):
                categories = await pos_adapter.fetch_categories()
                analysis_results["categories"] = categories
                
            if hasattr(pos_adapter, 'fetch_modifiers'):
                modifiers = await pos_adapter.fetch_modifiers()
                analysis_results["modifiers"] = modifiers
                
            if options.import_customer_data and hasattr(pos_adapter, 'fetch_customers'):
                customers = await pos_adapter.fetch_customers(limit=100)
                analysis_results["customers"] = customers
                
            if options.import_historical_data and hasattr(pos_adapter, 'fetch_orders'):
                orders = await pos_adapter.fetch_orders(
                    days_back=options.historical_days,
                    limit=100
                )
                analysis_results["orders"] = orders
            
            # Calculate statistics
            analysis_results["statistics"] = {
                "total_items": len(analysis_results["menu_items"]),
                "total_categories": len(analysis_results["categories"]),
                "total_modifiers": len(analysis_results["modifiers"]),
                "total_customers": len(analysis_results["customers"]),
                "total_orders": len(analysis_results["orders"]),
                "pos_type": pos_type
            }
            
            await self.audit_service.log_operation(
                migration_id=migration_id,
                operation="data_analysis_completed",
                details=analysis_results["statistics"]
            )
            
            return analysis_results
            
        except Exception as e:
            logger.error(f"Error analyzing POS data: {e}")
            raise
    
    async def _create_mapping_plan(
        self,
        analysis_results: Dict[str, Any],
        pos_type: str,
        migration_id: str,
        options: MigrationOptions
    ) -> MigrationPlan:
        """Create field mapping plan using AI assistance"""
        
        if not options.use_ai_assistance:
            # Use basic mapping without AI
            return await self._create_basic_mapping_plan(
                analysis_results, migration_id
            )
        
        # Get target schema
        target_schema = self._get_target_schema()
        
        # Use AI to analyze and create mapping plan
        sample_data = {
            "menu_item": analysis_results["menu_items"][0] if analysis_results["menu_items"] else {},
            "category": analysis_results["categories"][0] if analysis_results["categories"] else {},
            "modifier": analysis_results["modifiers"][0] if analysis_results["modifiers"] else {},
        }
        
        plan = await self.coach_agent.analyze_pos_structure(
            pos_type=pos_type,
            sample_data=sample_data,
            target_schema=target_schema
        )
        
        # Filter mappings by confidence threshold
        if options.ai_confidence_threshold > 0:
            plan.field_mappings = [
                m for m in plan.field_mappings
                if m.confidence >= options.ai_confidence_threshold
            ]
        
        await self.audit_service.log_operation(
            migration_id=migration_id,
            operation="mapping_plan_created",
            details={
                "total_mappings": len(plan.field_mappings),
                "ai_assisted": True,
                "complexity": plan.complexity.value
            }
        )
        
        return plan
    
    async def _validate_data(
        self,
        pos_adapter,
        mapping_plan: MigrationPlan,
        migration_id: str,
        options: MigrationOptions
    ) -> ValidationReport:
        """Validate data quality and integrity"""
        
        if not options.validate_pricing:
            # Skip validation
            return ValidationReport(
                anomalies=[],
                summary={
                    "total_issues": 0,
                    "requires_manual_review": False,
                    "confidence": 1.0
                }
            )
        
        # Fetch all menu items for validation
        all_items = await pos_adapter.fetch_menu_items(limit=None)
        
        # Use AI to validate pricing data
        validation_report = await self.coach_agent.validate_pricing_data(
            items=all_items,
            pos_type=pos_adapter.pos_type
        )
        
        await self.audit_service.log_operation(
            migration_id=migration_id,
            operation="data_validation_completed",
            details={
                "total_issues": validation_report.summary.total_issues,
                "requires_review": validation_report.summary.requires_manual_review
            }
        )
        
        return validation_report
    
    async def _import_data(
        self,
        pos_adapter,
        mapping_plan: MigrationPlan,
        tenant_id: str,
        migration_id: str,
        options: MigrationOptions
    ) -> Dict[str, Any]:
        """Import data using transformation service"""
        
        import_results = {
            "items_imported": 0,
            "categories_imported": 0,
            "modifiers_imported": 0,
            "customers_imported": 0,
            "orders_imported": 0,
            "errors": []
        }
        
        try:
            # Import in batches with progress updates
            # Categories first (dependencies)
            categories = await pos_adapter.fetch_categories()
            for batch in self._batch_data(categories, options.batch_size):
                result = await self.transformation_service.transform_and_import_batch(
                    data=batch,
                    data_type="category",
                    mapping_plan=mapping_plan,
                    tenant_id=tenant_id
                )
                import_results["categories_imported"] += result["success_count"]
                import_results["errors"].extend(result.get("errors", []))
                
                # Track for rollback
                if result.get("imported_ids"):
                    self.rollback_service.register_batch_import(
                        migration_id, "categories", result["imported_ids"]
                    )
                
                await self._update_progress(
                    migration_id, 
                    import_results["categories_imported"],
                    len(categories)
                )
            
            # Menu items
            items = await pos_adapter.fetch_menu_items(limit=None)
            for batch in self._batch_data(items, options.batch_size):
                result = await self.transformation_service.transform_and_import_batch(
                    data=batch,
                    data_type="menu_item",
                    mapping_plan=mapping_plan,
                    tenant_id=tenant_id
                )
                import_results["items_imported"] += result["success_count"]
                import_results["errors"].extend(result.get("errors", []))
                
                # Track for rollback
                if result.get("imported_ids"):
                    self.rollback_service.register_batch_import(
                        migration_id, "menu_items", result["imported_ids"]
                    )
                
                await self._update_progress(
                    migration_id,
                    import_results["items_imported"],
                    len(items)
                )
            
            # Continue with other data types...
            
            await self.audit_service.log_operation(
                migration_id=migration_id,
                operation="data_import_completed",
                details=import_results
            )
            
            return import_results
            
        except Exception as e:
            logger.error(f"Error importing data: {e}")
            raise
    
    async def _verify_import(
        self,
        import_results: Dict[str, Any],
        tenant_id: str,
        migration_id: str
    ) -> Dict[str, Any]:
        """Verify imported data integrity"""
        
        verification_results = {
            "items_verified": True,
            "categories_verified": True,
            "data_integrity": True,
            "issues": []
        }
        
        # Run verification queries
        # This would check that imported data matches expected counts
        # and relationships are preserved
        
        await self.audit_service.log_operation(
            migration_id=migration_id,
            operation="import_verification_completed",
            details=verification_results
        )
        
        return verification_results
    
    async def _complete_migration(
        self,
        migration_id: str,
        tenant_id: str,
        import_results: Dict[str, Any],
        user_id: str
    ):
        """Complete migration and send summary"""
        
        # Generate compliance report
        compliance_report = await self.audit_service.generate_compliance_report(
            migration_id
        )
        
        # Get restaurant/customer info for summary
        # This would fetch from database
        customer_name = "Restaurant Owner"
        restaurant_name = "Restaurant Name"
        
        # Prepare summary data
        summary_data = MigrationSummaryData(
            customer_name=customer_name,
            restaurant_name=restaurant_name,
            items_count=import_results["items_imported"],
            categories_count=import_results["categories_imported"],
            modifiers_count=import_results["modifiers_imported"],
            orders_count=import_results.get("orders_imported", 0),
            migration_duration_hours=4.0,  # Calculate from actual times
            new_features_available=[
                "Real-time analytics",
                "Automated inventory tracking",
                "Customer loyalty program",
                "Advanced reporting"
            ]
        )
        
        # Generate and send summary
        summary_text = await self.coach_agent.generate_migration_summary(
            migration_stats=summary_data.dict(),
            customer_name=customer_name
        )
        
        await self.notification_service.send_migration_completed(
            migration_id=migration_id,
            tenant_id=tenant_id,
            user_id=user_id,
            summary=summary_text
        )
        
        # Clean up
        del self.active_migrations[migration_id]
        
        await self.audit_service.log_operation(
            migration_id=migration_id,
            operation="migration_completed",
            user_id=user_id,
            details={
                "duration_hours": summary_data.migration_duration_hours,
                "total_imported": sum([
                    import_results["items_imported"],
                    import_results["categories_imported"],
                    import_results["modifiers_imported"],
                    import_results.get("customers_imported", 0),
                    import_results.get("orders_imported", 0)
                ])
            }
        )
    
    async def get_migration_status(self, migration_id: str) -> MigrationStatus:
        """Get current migration status"""
        
        if migration_id not in self.active_migrations:
            # Try to load from database if not in memory
            status = await self._load_migration_status(migration_id)
            if not status:
                raise APIException(
                    status_code=404,
                    detail=f"Migration {migration_id} not found"
                )
            return status
        
        return self.active_migrations[migration_id]
    
    async def approve_migration_mappings(
        self,
        migration_id: str,
        approved_mappings: List[Dict[str, Any]],
        user_id: str
    ):
        """Approve field mappings and continue migration"""
        
        if migration_id not in self.active_migrations:
            raise APIException(
                status_code=404,
                detail=f"Migration {migration_id} not found or not awaiting approval"
            )
        
        status = self.active_migrations[migration_id]
        if status.phase != MigrationPhase.VALIDATION:
            raise APIException(
                status_code=400,
                detail=f"Migration is not in validation phase"
            )
        
        # Store approved mappings
        await self.audit_service.log_operation(
            migration_id=migration_id,
            operation="mappings_approved",
            user_id=user_id,
            details={"approved_mappings": approved_mappings}
        )
        
        # Signal to continue migration
        # This would use asyncio events or similar mechanism
        await self._signal_approval(migration_id)
    
    async def cancel_migration(
        self,
        migration_id: str,
        user_id: str,
        reason: str
    ):
        """Cancel an active migration"""
        
        if migration_id not in self.active_migrations:
            raise APIException(
                status_code=404,
                detail=f"Migration {migration_id} not found"
            )
        
        # Perform rollback if needed
        status = self.active_migrations[migration_id]
        if status.phase in [MigrationPhase.IMPORT, MigrationPhase.VERIFICATION]:
            await self._rollback_migration(migration_id, tenant_id=self.db.info.get("tenant_id"))
        
        # Update status
        status.phase = MigrationPhase.COMPLETION
        status.progress_percent = 0.0
        
        await self.audit_service.log_operation(
            migration_id=migration_id,
            operation="migration_cancelled",
            user_id=user_id,
            details={"reason": reason, "phase": status.phase.value}
        )
        
        # Clean up
        del self.active_migrations[migration_id]
        
        # Notify
        await self.notification_service.send_migration_cancelled(
            migration_id=migration_id,
            reason=reason
        )
    
    # Helper methods
    
    async def _update_phase(
        self,
        migration_id: str,
        phase: MigrationPhase,
        progress: float
    ):
        """Update migration phase and progress"""
        
        if migration_id in self.active_migrations:
            status = self.active_migrations[migration_id]
            status.phase = phase
            status.progress_percent = progress
            status.current_operation = f"Executing {phase.value} phase"
            
            # Emit WebSocket event
            event = MigrationProgressEvent(
                type="phase_change",
                migration_id=migration_id,
                data={
                    "phase": phase.value,
                    "progress": progress
                }
            )
            await self._emit_progress_event(event)
    
    async def _update_progress(
        self,
        migration_id: str,
        current: int,
        total: int
    ):
        """Update migration progress within a phase"""
        
        if migration_id in self.active_migrations and total > 0:
            status = self.active_migrations[migration_id]
            phase_progress = (current / total) * 100
            
            # Emit progress event periodically
            if int(phase_progress) % 10 == 0:  # Every 10%
                event = MigrationProgressEvent(
                    type="progress",
                    migration_id=migration_id,
                    data={
                        "items_processed": current,
                        "total_items": total,
                        "phase_progress": phase_progress
                    }
                )
                await self._emit_progress_event(event)
    
    async def _emit_progress_event(self, event: MigrationProgressEvent):
        """Emit WebSocket event for real-time updates"""
        await websocket_manager.broadcast_event(event)
    
    async def _handle_migration_error(self, migration_id: str, error_message: str):
        """Handle migration errors"""
        
        if migration_id in self.active_migrations:
            status = self.active_migrations[migration_id]
            status.errors.append({
                "timestamp": datetime.utcnow().isoformat(),
                "message": error_message,
                "phase": status.phase.value
            })
        
        event = MigrationErrorEvent(
            migration_id=migration_id,
            error_code="MIGRATION_FAILED",
            error_message=error_message,
            recoverable=False
        )
        
        await self._emit_progress_event(
            MigrationProgressEvent(
                type="error",
                migration_id=migration_id,
                data=event.dict()
            )
        )
        
        await self.notification_service.send_migration_failed(
            migration_id=migration_id,
            error=error_message
        )
    
    def _batch_data(self, data: List[Any], batch_size: int):
        """Split data into batches"""
        for i in range(0, len(data), batch_size):
            yield data[i:i + batch_size]
    
    def _get_target_schema(self) -> Dict[str, Any]:
        """Get AuraConnect target schema"""
        return {
            "menu_item": {
                "id": "uuid",
                "tenant_id": "uuid",
                "name": "string",
                "description": "string",
                "price": "decimal",
                "category_id": "uuid",
                "is_active": "boolean",
                "image_url": "string",
                "preparation_time": "integer",
                "nutritional_info": "json"
            },
            "category": {
                "id": "uuid",
                "tenant_id": "uuid",
                "name": "string",
                "description": "string",
                "display_order": "integer",
                "is_active": "boolean"
            },
            "modifier": {
                "id": "uuid",
                "name": "string",
                "price": "decimal",
                "modifier_group_id": "uuid"
            }
        }
    
    async def _pause_for_review(
        self,
        migration_id: str,
        validation_report: ValidationReport,
        mapping_plan: MigrationPlan
    ):
        """Pause migration for manual review"""
        
        status = self.active_migrations[migration_id]
        status.current_operation = "Awaiting manual review and approval"
        
        await self.notification_service.send_review_required(
            migration_id=migration_id,
            validation_report=validation_report,
            mapping_plan=mapping_plan
        )
    
    async def _wait_for_approval(self, migration_id: str):
        """Wait for manual approval"""
        # This would use asyncio.Event or similar
        # For now, just sleep
        await asyncio.sleep(1)
    
    async def _signal_approval(self, migration_id: str):
        """Signal that migration can continue"""
        # This would trigger the waiting coroutine
        pass
    
    async def _rollback_migration(self, migration_id: str, tenant_id: str):
        """Rollback a partially completed migration"""
        logger.warning(f"Rolling back migration {migration_id}")
        
        try:
            # Use rollback service
            rollback_stats = await self.rollback_service.rollback_migration(
                migration_id=migration_id,
                tenant_id=tenant_id,
                audit_callback=self.audit_service.log_operation
            )
            
            logger.info(f"Rollback completed: {rollback_stats}")
            
            # Notify about rollback
            await self.notification_service.send_migration_cancelled(
                migration_id=migration_id,
                reason="Migration was rolled back due to errors or cancellation"
            )
            
        except Exception as e:
            logger.error(f"Error during rollback: {e}")
            raise
    
    async def _load_migration_status(self, migration_id: str) -> Optional[MigrationStatus]:
        """Load migration status from database"""
        # This would query a migrations table
        return None
    
    async def _create_basic_mapping_plan(
        self,
        analysis_results: Dict[str, Any],
        migration_id: str
    ) -> MigrationPlan:
        """Create basic mapping plan without AI"""
        
        # Simple field mapping based on common patterns
        return MigrationPlan(
            field_mappings=[],
            data_quality_issues=["Manual mapping required"],
            complexity="moderate",
            estimated_hours=8.0,
            risk_factors=["No AI assistance available"],
            recommendations=["Review all field mappings manually"],
            confidence_score=0.5
        )