"""
POS Migration Service

Core service for managing POS migrations with security,
compliance, and tenant isolation.
"""

import asyncio
import hashlib
import json
import logging
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List
from uuid import UUID
import aiohttp
from cryptography.fernet import Fernet
from sqlalchemy import select, and_, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from core.database import get_db
from core.auth import get_current_user
from core.exceptions import (
    NotFoundException, 
    ForbiddenException,
    ValidationException,
    ConflictException
)
from ..models.migration_models import (
    POSMigrationJob,
    DataMapping,
    MigrationLog,
    ValidationResult,
    MigrationTemplate,
    MigrationStatus,
    POSProvider,
    DataEntityType
)
from ..schemas.migration_schemas import (
    MigrationJobCreate,
    MigrationJobUpdate,
    MigrationAnalysisRequest,
    MigrationAnalysisResponse,
    DataMappingCreate
)
from .ai_mapping_service import AIMappingService
from .validation_service import ValidationService
from ..utils.security import encrypt_credentials, decrypt_credentials
from ..utils.audit import audit_log

logger = logging.getLogger(__name__)


class MigrationService:
    """
    Manages POS migration lifecycle with security and compliance.
    """
    
    def __init__(self, db: AsyncSession, current_user: dict):
        self.db = db
        self.current_user = current_user
        self.restaurant_id = current_user.get("restaurant_id")
        self.ai_service = AIMappingService()
        self.validation_service = ValidationService(db)
    
    async def create_migration_job(
        self,
        job_data: MigrationJobCreate
    ) -> POSMigrationJob:
        """
        Create a new migration job with security checks.
        """
        # Check permissions
        if not self._has_permission("migration.create"):
            raise ForbiddenException("Insufficient permissions to create migration jobs")
        
        # Validate restaurant context
        if not self.restaurant_id:
            raise ValidationException("Restaurant context required")
        
        # Check for existing active migrations
        existing = await self.db.execute(
            select(POSMigrationJob).where(
                and_(
                    POSMigrationJob.restaurant_id == self.restaurant_id,
                    POSMigrationJob.status.in_([
                        MigrationStatus.PENDING,
                        MigrationStatus.ANALYZING,
                        MigrationStatus.MIGRATING
                    ])
                )
            )
        )
        if existing.scalar_one_or_none():
            raise ConflictException("An active migration already exists for this restaurant")
        
        # Encrypt credentials
        encrypted_creds = encrypt_credentials(job_data.source_credentials)
        
        # Create job
        job = POSMigrationJob(
            **job_data.model_dump(exclude={"source_credentials"}),
            source_credentials=encrypted_creds,
            restaurant_id=self.restaurant_id,
            created_by=self.current_user.get("id"),
            status=MigrationStatus.PENDING
        )
        
        self.db.add(job)
        
        # Add audit log
        await audit_log(
            self.db,
            user_id=self.current_user.get("id"),
            action="migration.create",
            resource_type="migration_job",
            resource_id=str(job.id),
            details={
                "job_name": job.job_name,
                "source_provider": job.source_provider,
                "entities": job.entities_to_migrate
            }
        )
        
        await self.db.commit()
        await self.db.refresh(job)
        
        # Schedule analysis if not scheduled
        if not job.scheduled_at:
            asyncio.create_task(self._start_analysis(job.id))
        
        return job
    
    async def get_migration_job(self, job_id: UUID) -> POSMigrationJob:
        """
        Get migration job with tenant isolation.
        """
        result = await self.db.execute(
            select(POSMigrationJob)
            .options(
                selectinload(POSMigrationJob.mappings),
                selectinload(POSMigrationJob.logs),
                selectinload(POSMigrationJob.validations)
            )
            .where(
                and_(
                    POSMigrationJob.id == job_id,
                    POSMigrationJob.restaurant_id == self.restaurant_id
                )
            )
        )
        job = result.scalar_one_or_none()
        
        if not job:
            raise NotFoundException(f"Migration job {job_id} not found")
        
        # Mask sensitive data based on role
        if not self._has_permission("migration.view_credentials"):
            job.source_credentials = {"masked": True}
        
        return job
    
    async def list_migration_jobs(
        self,
        status: Optional[MigrationStatus] = None,
        limit: int = 50,
        offset: int = 0
    ) -> List[POSMigrationJob]:
        """
        List migration jobs for current restaurant.
        """
        query = select(POSMigrationJob).where(
            POSMigrationJob.restaurant_id == self.restaurant_id
        )
        
        if status:
            query = query.where(POSMigrationJob.status == status)
        
        query = query.order_by(POSMigrationJob.created_at.desc())
        query = query.limit(limit).offset(offset)
        
        result = await self.db.execute(query)
        return result.scalars().all()
    
    async def analyze_source_system(
        self,
        request: MigrationAnalysisRequest
    ) -> MigrationAnalysisResponse:
        """
        Analyze source POS system and suggest mappings.
        """
        # Check permissions
        if not self._has_permission("migration.analyze"):
            raise ForbiddenException("Insufficient permissions to analyze POS systems")
        
        # Perform analysis (mock implementation - replace with actual API calls)
        analysis_results = await self._analyze_pos_data(
            request.source_provider,
            decrypt_credentials(encrypt_credentials(request.source_credentials)),
            request.entities_to_analyze,
            request.sample_size
        )
        
        # Get AI-suggested mappings
        suggested_mappings = await self.ai_service.suggest_mappings(
            request.source_provider,
            analysis_results["schema"]
        )
        
        # Calculate compatibility score
        compatibility_score = self._calculate_compatibility(
            analysis_results,
            suggested_mappings
        )
        
        # Estimate duration
        estimated_duration = self._estimate_migration_duration(
            analysis_results["record_counts"],
            request.entities_to_analyze
        )
        
        # Identify potential issues
        potential_issues = self._identify_migration_issues(
            request.source_provider,
            analysis_results
        )
        
        return MigrationAnalysisResponse(
            source_provider=request.source_provider,
            analysis_date=datetime.utcnow(),
            entities_analyzed=analysis_results["entities"],
            suggested_mappings=suggested_mappings,
            compatibility_score=compatibility_score,
            estimated_duration_minutes=estimated_duration,
            potential_issues=potential_issues,
            recommendations=self._generate_recommendations(potential_issues)
        )
    
    async def start_migration(self, job_id: UUID) -> POSMigrationJob:
        """
        Start or resume a migration job.
        """
        job = await self.get_migration_job(job_id)
        
        # Check permissions
        if not self._has_permission("migration.execute"):
            raise ForbiddenException("Insufficient permissions to execute migrations")
        
        # Validate job status
        if job.status not in [MigrationStatus.PENDING, MigrationStatus.PAUSED]:
            raise ValidationException(f"Cannot start migration in {job.status} status")
        
        # Update status
        job.status = MigrationStatus.MIGRATING
        job.started_at = datetime.utcnow()
        
        # Create background task for migration
        asyncio.create_task(self._execute_migration(job_id))
        
        # Audit log
        await audit_log(
            self.db,
            user_id=self.current_user.get("id"),
            action="migration.start",
            resource_type="migration_job",
            resource_id=str(job_id),
            details={"status": job.status}
        )
        
        await self.db.commit()
        return job
    
    async def pause_migration(self, job_id: UUID) -> POSMigrationJob:
        """
        Pause an active migration.
        """
        job = await self.get_migration_job(job_id)
        
        if job.status != MigrationStatus.MIGRATING:
            raise ValidationException("Can only pause active migrations")
        
        job.status = MigrationStatus.PAUSED
        
        # Save checkpoint for resume
        job.rollback_checkpoint = {
            "entity": job.current_entity,
            "progress": job.progress_percentage,
            "records_processed": job.records_processed,
            "timestamp": datetime.utcnow().isoformat()
        }
        
        await audit_log(
            self.db,
            user_id=self.current_user.get("id"),
            action="migration.pause",
            resource_type="migration_job",
            resource_id=str(job_id)
        )
        
        await self.db.commit()
        return job
    
    async def cancel_migration(self, job_id: UUID) -> POSMigrationJob:
        """
        Cancel a migration with optional rollback.
        """
        job = await self.get_migration_job(job_id)
        
        # Check permissions
        if not self._has_permission("migration.cancel"):
            raise ForbiddenException("Insufficient permissions to cancel migrations")
        
        if job.status in [MigrationStatus.COMPLETED, MigrationStatus.CANCELLED]:
            raise ValidationException(f"Cannot cancel migration in {job.status} status")
        
        # Initiate rollback if enabled and data was migrated
        if job.rollback_enabled and job.records_processed > 0:
            job.status = MigrationStatus.ROLLBACK
            asyncio.create_task(self._rollback_migration(job_id))
        else:
            job.status = MigrationStatus.CANCELLED
            job.completed_at = datetime.utcnow()
        
        await audit_log(
            self.db,
            user_id=self.current_user.get("id"),
            action="migration.cancel",
            resource_type="migration_job",
            resource_id=str(job_id),
            details={"rollback": job.rollback_enabled}
        )
        
        await self.db.commit()
        return job
    
    async def update_mappings(
        self,
        job_id: UUID,
        mappings: List[DataMappingCreate]
    ) -> List[DataMapping]:
        """
        Update field mappings for a migration job.
        """
        job = await self.get_migration_job(job_id)
        
        if job.status not in [MigrationStatus.PENDING, MigrationStatus.MAPPING]:
            raise ValidationException("Cannot update mappings after migration has started")
        
        # Clear existing mappings
        await self.db.execute(
            select(DataMapping).where(DataMapping.migration_job_id == job_id)
        )
        
        # Add new mappings
        new_mappings = []
        for mapping_data in mappings:
            mapping = DataMapping(
                migration_job_id=job_id,
                **mapping_data.model_dump()
            )
            self.db.add(mapping)
            new_mappings.append(mapping)
        
        await self.db.commit()
        return new_mappings
    
    async def get_migration_stats(self) -> Dict[str, Any]:
        """
        Get migration statistics for dashboard.
        """
        # Jobs by status
        status_counts = await self.db.execute(
            select(
                POSMigrationJob.status,
                func.count(POSMigrationJob.id)
            )
            .where(POSMigrationJob.restaurant_id == self.restaurant_id)
            .group_by(POSMigrationJob.status)
        )
        
        jobs_by_status = {
            status: count for status, count in status_counts
        }
        
        # Total records migrated
        total_records = await self.db.execute(
            select(func.sum(POSMigrationJob.records_succeeded))
            .where(POSMigrationJob.restaurant_id == self.restaurant_id)
        )
        
        # Recent jobs
        recent_jobs = await self.list_migration_jobs(limit=10)
        
        return {
            "total_jobs": sum(jobs_by_status.values()),
            "jobs_by_status": jobs_by_status,
            "total_records_migrated": total_records.scalar() or 0,
            "recent_jobs": recent_jobs
        }
    
    # Private helper methods
    
    def _has_permission(self, permission: str) -> bool:
        """Check if current user has permission."""
        user_permissions = self.current_user.get("permissions", [])
        user_role = self.current_user.get("role")
        
        # Admin has all permissions
        if user_role == "admin":
            return True
        
        # Check specific permission
        return permission in user_permissions
    
    async def _analyze_pos_data(
        self,
        provider: POSProvider,
        credentials: Dict[str, Any],
        entities: List[DataEntityType],
        sample_size: int
    ) -> Dict[str, Any]:
        """Analyze POS data structure and content."""
        # This would connect to actual POS APIs
        # For now, return mock data
        return {
            "schema": {
                "menu_items": {
                    "fields": ["id", "name", "price", "category_id", "description"],
                    "types": ["string", "string", "decimal", "string", "text"]
                }
            },
            "record_counts": {
                "menu_items": 250,
                "categories": 20,
                "customers": 1500
            },
            "entities": {
                entity.value: {
                    "total_records": 100,
                    "sample_data": [],
                    "field_statistics": {}
                }
                for entity in entities
            }
        }
    
    def _calculate_compatibility(
        self,
        analysis: Dict[str, Any],
        mappings: List[Any]
    ) -> float:
        """Calculate compatibility score."""
        # Simplified calculation
        mapped_fields = len(mappings)
        total_fields = sum(
            len(schema.get("fields", []))
            for schema in analysis.get("schema", {}).values()
        )
        
        if total_fields == 0:
            return 0.0
        
        return min(mapped_fields / total_fields, 1.0)
    
    def _estimate_migration_duration(
        self,
        record_counts: Dict[str, int],
        entities: List[DataEntityType]
    ) -> int:
        """Estimate migration duration in minutes."""
        # Rough estimate: 100 records per minute
        total_records = sum(
            count for entity, count in record_counts.items()
            if DataEntityType(entity) in entities
        )
        return max(1, total_records // 100)
    
    def _identify_migration_issues(
        self,
        provider: POSProvider,
        analysis: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """Identify potential migration issues."""
        issues = []
        
        # Check for missing required fields
        schema = analysis.get("schema", {})
        for entity, fields in schema.items():
            required_fields = ["id", "name"]  # Example required fields
            missing = [f for f in required_fields if f not in fields.get("fields", [])]
            if missing:
                issues.append({
                    "type": "missing_fields",
                    "entity": entity,
                    "fields": missing,
                    "severity": "high"
                })
        
        return issues
    
    def _generate_recommendations(
        self,
        issues: List[Dict[str, Any]]
    ) -> List[str]:
        """Generate recommendations based on issues."""
        recommendations = []
        
        for issue in issues:
            if issue["type"] == "missing_fields":
                recommendations.append(
                    f"Configure default values for missing {issue['entity']} fields: {', '.join(issue['fields'])}"
                )
        
        return recommendations
    
    async def _start_analysis(self, job_id: UUID):
        """Background task to analyze source system."""
        try:
            # Update job status
            await self.db.execute(
                select(POSMigrationJob)
                .where(POSMigrationJob.id == job_id)
                .with_for_update()
            )
            # Implementation would go here
            pass
        except Exception as e:
            logger.error(f"Analysis failed for job {job_id}: {e}")
    
    async def _execute_migration(self, job_id: UUID):
        """Background task to execute migration."""
        try:
            # Implementation would process entities in batches
            # Update progress periodically
            # Handle errors and retries
            pass
        except Exception as e:
            logger.error(f"Migration failed for job {job_id}: {e}")
    
    async def _rollback_migration(self, job_id: UUID):
        """Background task to rollback migration."""
        try:
            # Implementation would reverse migrated data
            pass
        except Exception as e:
            logger.error(f"Rollback failed for job {job_id}: {e}")