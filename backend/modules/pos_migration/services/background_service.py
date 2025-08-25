"""
Background Migration Service

Handles asynchronous migration processing with Celery/Background tasks.
"""

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
from uuid import UUID
from celery import Celery, Task
from celery.result import AsyncResult
import redis
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from core.config import settings
from core.database import DATABASE_URL
from ..models.migration_models import (
    POSMigrationJob,
    MigrationLog,
    ValidationResult,
    MigrationStatus,
    DataEntityType
)
from ..adapters import get_pos_adapter
from ..utils.security import decrypt_credentials
from ..utils.metrics import track_migration_metrics

logger = logging.getLogger(__name__)

# Celery configuration
celery_app = Celery(
    "pos_migration",
    broker=settings.REDIS_URL or "redis://localhost:6379/0",
    backend=settings.REDIS_URL or "redis://localhost:6379/0"
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_time_limit=3600,  # 1 hour
    task_soft_time_limit=3300,  # 55 minutes
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    worker_max_tasks_per_child=100,
)

# Redis client for progress tracking
redis_client = redis.from_url(settings.REDIS_URL or "redis://localhost:6379/0")


class MigrationTask(Task):
    """Base task class with database session management."""
    
    _db_engine = None
    _SessionLocal = None
    
    @property
    def db_engine(self):
        if self._db_engine is None:
            self._db_engine = create_async_engine(DATABASE_URL, echo=False)
        return self._db_engine
    
    @property
    def SessionLocal(self):
        if self._SessionLocal is None:
            self._SessionLocal = sessionmaker(
                self.db_engine,
                class_=AsyncSession,
                expire_on_commit=False
            )
        return self._SessionLocal


@celery_app.task(base=MigrationTask, bind=True, max_retries=3)
def process_migration_job(self, job_id: str, restaurant_id: int):
    """
    Main background task for processing migration jobs.
    """
    asyncio.run(self._process_migration(job_id, restaurant_id))


async def _process_migration(self, job_id: str, restaurant_id: int):
    """Async migration processing logic."""
    async with self.SessionLocal() as db:
        try:
            # Get migration job
            job = await db.get(POSMigrationJob, UUID(job_id))
            if not job:
                logger.error(f"Migration job {job_id} not found")
                return
            
            # Update status
            job.status = MigrationStatus.MIGRATING
            job.started_at = datetime.utcnow()
            await db.commit()
            
            # Initialize POS adapter
            adapter = get_pos_adapter(
                job.source_provider,
                decrypt_credentials(job.source_credentials)
            )
            
            # Process each entity type
            total_entities = len(job.entities_to_migrate)
            for idx, entity_type in enumerate(job.entities_to_migrate):
                try:
                    await self._process_entity(
                        db, job, adapter, entity_type, idx, total_entities
                    )
                except Exception as e:
                    logger.error(f"Failed to process {entity_type}: {e}")
                    await self._log_error(db, job.id, entity_type, str(e))
            
            # Finalize migration
            job.status = MigrationStatus.COMPLETED
            job.completed_at = datetime.utcnow()
            job.progress_percentage = 100.0
            
            # Track metrics
            track_migration_metrics(
                provider=job.source_provider,
                duration=(job.completed_at - job.started_at).total_seconds(),
                records=job.records_succeeded,
                success=True
            )
            
        except Exception as e:
            logger.error(f"Migration job {job_id} failed: {e}")
            job.status = MigrationStatus.FAILED
            job.last_error = str(e)
            job.completed_at = datetime.utcnow()
            
            track_migration_metrics(
                provider=job.source_provider,
                duration=0,
                records=0,
                success=False
            )
        
        finally:
            await db.commit()


async def _process_entity(
    self,
    db: AsyncSession,
    job: POSMigrationJob,
    adapter: Any,
    entity_type: str,
    entity_index: int,
    total_entities: int
):
    """Process a single entity type."""
    logger.info(f"Processing {entity_type} for job {job.id}")
    
    # Update current entity
    job.current_entity = entity_type
    base_progress = (entity_index / total_entities) * 100
    job.progress_percentage = base_progress
    await db.commit()
    
    # Fetch data from source
    batch_size = job.batch_size or 100
    offset = 0
    entity_succeeded = 0
    entity_failed = 0
    
    while True:
        try:
            # Fetch batch
            data = await adapter.fetch_data(
                entity_type,
                limit=batch_size,
                offset=offset
            )
            
            if not data:
                break
            
            # Process batch
            for record in data:
                try:
                    # Transform data
                    transformed = await self._transform_record(
                        job, entity_type, record
                    )
                    
                    # Validate data
                    validation_result = await self._validate_record(
                        db, job.id, entity_type, transformed
                    )
                    
                    if validation_result.is_valid:
                        # Import to target system
                        await self._import_record(
                            db, entity_type, transformed, job.restaurant_id
                        )
                        entity_succeeded += 1
                    else:
                        entity_failed += 1
                        await self._log_validation_failure(
                            db, job.id, entity_type, record, validation_result
                        )
                    
                except Exception as e:
                    entity_failed += 1
                    await self._log_error(
                        db, job.id, entity_type, str(e), record
                    )
            
            # Update progress
            offset += batch_size
            job.records_processed += len(data)
            job.records_succeeded += entity_succeeded
            job.records_failed += entity_failed
            
            # Calculate entity progress
            entity_progress = min(offset / (offset + batch_size), 1.0) * (100 / total_entities)
            job.progress_percentage = base_progress + entity_progress
            
            # Update Redis for real-time tracking
            await self._update_redis_progress(job)
            
            await db.commit()
            
            # Rate limiting
            if job.rate_limit:
                await asyncio.sleep(60 / job.rate_limit)
            
        except Exception as e:
            logger.error(f"Batch processing failed: {e}")
            job.error_count += 1
            
            if job.error_count > 10:
                raise Exception(f"Too many errors processing {entity_type}")
    
    # Mark entity as completed
    job.entities_completed = job.entities_completed or []
    job.entities_completed.append(entity_type)
    await db.commit()


async def _transform_record(
    self,
    job: POSMigrationJob,
    entity_type: str,
    record: Dict[str, Any]
) -> Dict[str, Any]:
    """Transform record based on mapping rules."""
    transformed = {}
    mappings = job.mapping_rules or {}
    entity_mappings = mappings.get(entity_type, {})
    
    for source_field, target_field in entity_mappings.items():
        if source_field in record:
            value = record[source_field]
            
            # Apply transformation functions
            transformations = job.transformation_rules or {}
            if target_field in transformations:
                func_name = transformations[target_field]
                value = self._apply_transformation(func_name, value)
            
            transformed[target_field] = value
    
    return transformed


def _apply_transformation(self, func_name: str, value: Any) -> Any:
    """Apply transformation function to value."""
    transformations = {
        "uppercase": lambda x: str(x).upper() if x else None,
        "lowercase": lambda x: str(x).lower() if x else None,
        "strip": lambda x: str(x).strip() if x else None,
        "to_decimal": lambda x: float(x) if x else 0.0,
        "to_int": lambda x: int(x) if x else 0,
        "to_bool": lambda x: bool(x),
        "date_format": lambda x: datetime.fromisoformat(x).date() if x else None,
    }
    
    if func_name in transformations:
        try:
            return transformations[func_name](value)
        except Exception:
            return value
    
    return value


async def _validate_record(
    self,
    db: AsyncSession,
    job_id: UUID,
    entity_type: str,
    record: Dict[str, Any]
) -> ValidationResult:
    """Validate transformed record."""
    validation_errors = []
    
    # Check required fields
    required_fields = self._get_required_fields(entity_type)
    for field in required_fields:
        if field not in record or record[field] is None:
            validation_errors.append({
                "field": field,
                "error": "Required field missing"
            })
    
    # Create validation result
    result = ValidationResult(
        migration_job_id=job_id,
        entity_type=entity_type,
        is_valid=len(validation_errors) == 0,
        validation_errors=validation_errors if validation_errors else None,
        validated_data=record
    )
    
    db.add(result)
    return result


def _get_required_fields(self, entity_type: str) -> List[str]:
    """Get required fields for entity type."""
    required = {
        DataEntityType.MENU_ITEMS: ["name", "price"],
        DataEntityType.CATEGORIES: ["name"],
        DataEntityType.CUSTOMERS: ["email"],
        DataEntityType.ORDERS: ["total", "customer_id"],
        DataEntityType.INVENTORY: ["item_name", "quantity"],
    }
    
    return required.get(DataEntityType(entity_type), [])


async def _import_record(
    self,
    db: AsyncSession,
    entity_type: str,
    record: Dict[str, Any],
    restaurant_id: int
):
    """Import record to target system."""
    # This would import to actual AuraConnect tables
    # Implementation depends on entity type
    
    # Add restaurant context
    record["restaurant_id"] = restaurant_id
    
    # Map to appropriate model and save
    # Example for menu items:
    if entity_type == DataEntityType.MENU_ITEMS:
        from menu.models import MenuItem
        item = MenuItem(**record)
        db.add(item)


async def _log_error(
    self,
    db: AsyncSession,
    job_id: UUID,
    entity_type: str,
    error: str,
    record: Optional[Dict] = None
):
    """Log migration error."""
    log = MigrationLog(
        migration_job_id=job_id,
        log_level="ERROR",
        entity_type=entity_type,
        action="process",
        message=error,
        error_type="ProcessingError",
        error_message=error,
        source_data=record
    )
    db.add(log)
    await db.commit()


async def _log_validation_failure(
    self,
    db: AsyncSession,
    job_id: UUID,
    entity_type: str,
    record: Dict[str, Any],
    validation_result: ValidationResult
):
    """Log validation failure."""
    log = MigrationLog(
        migration_job_id=job_id,
        log_level="WARNING",
        entity_type=entity_type,
        action="validate",
        message=f"Validation failed: {validation_result.validation_errors}",
        source_data=record
    )
    db.add(log)


async def _update_redis_progress(self, job: POSMigrationJob):
    """Update migration progress in Redis for real-time tracking."""
    progress_key = f"migration:progress:{job.id}"
    progress_data = {
        "status": job.status,
        "progress": job.progress_percentage,
        "current_entity": job.current_entity,
        "records_processed": job.records_processed,
        "records_succeeded": job.records_succeeded,
        "records_failed": job.records_failed,
        "updated_at": datetime.utcnow().isoformat()
    }
    
    redis_client.setex(
        progress_key,
        300,  # 5 minutes TTL
        json.dumps(progress_data)
    )


class BackgroundMigrationService:
    """Service for managing background migration tasks."""
    
    @staticmethod
    async def schedule_job(job_id: UUID, delay: Optional[int] = None):
        """Schedule a migration job for processing."""
        task = process_migration_job.apply_async(
            args=[str(job_id)],
            countdown=delay
        )
        return task.id
    
    @staticmethod
    async def cancel_job(task_id: str):
        """Cancel a running migration task."""
        result = AsyncResult(task_id, app=celery_app)
        result.revoke(terminate=True)
    
    @staticmethod
    async def get_task_status(task_id: str) -> Dict[str, Any]:
        """Get status of a background task."""
        result = AsyncResult(task_id, app=celery_app)
        return {
            "task_id": task_id,
            "status": result.status,
            "ready": result.ready(),
            "successful": result.successful() if result.ready() else None,
            "result": result.result if result.ready() else None
        }
    
    @staticmethod
    async def retry_failed_job(job_id: UUID):
        """Retry a failed migration job."""
        task = process_migration_job.apply_async(
            args=[str(job_id)],
            retry=True,
            retry_policy={
                "max_retries": 3,
                "interval_start": 60,
                "interval_step": 120,
                "interval_max": 600,
            }
        )
        return task.id