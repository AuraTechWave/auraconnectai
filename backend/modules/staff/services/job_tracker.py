"""
Persistent job tracking service for background payroll processing.

Addresses the concern about in-memory BATCH_JOBS dict by providing
database-backed job tracking with Redis fallback for performance.
"""

import json
import uuid
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from enum import Enum
from dataclasses import dataclass, asdict
from sqlalchemy.orm import Session

from ...payroll.models.payroll_configuration import PayrollJobTracking


class JobStatus(Enum):
    """Job status enumeration."""
    PENDING = "pending"
    RUNNING = "running"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class JobType(Enum):
    """Job type enumeration."""
    BATCH_PAYROLL = "batch_payroll"
    SINGLE_PAYROLL = "single_payroll"
    PAYROLL_EXPORT = "payroll_export"
    TAX_CALCULATION = "tax_calculation"
    HOURS_CALCULATION = "hours_calculation"


@dataclass
class JobProgress:
    """Job progress information."""
    total_items: int
    completed_items: int
    failed_items: int
    current_item: Optional[str] = None
    estimated_completion: Optional[datetime] = None
    
    @property
    def progress_percentage(self) -> int:
        """Calculate progress percentage."""
        if self.total_items == 0:
            return 100
        return int((self.completed_items / self.total_items) * 100)
    
    @property
    def is_complete(self) -> bool:
        """Check if job is complete."""
        return self.completed_items + self.failed_items >= self.total_items


@dataclass
class JobResult:
    """Job execution result."""
    success_count: int
    failure_count: int
    total_processed: int
    errors: List[Dict[str, Any]]
    output_data: Optional[Dict[str, Any]] = None
    
    @property
    def success_rate(self) -> float:
        """Calculate success rate."""
        if self.total_processed == 0:
            return 0.0
        return (self.success_count / self.total_processed) * 100


class JobTracker:
    """Persistent job tracking service with database and optional Redis."""
    
    def __init__(self, db: Session, redis_client=None):
        self.db = db
        self.redis = redis_client
        self.redis_ttl = 3600  # 1 hour TTL for Redis cache
    
    def create_job(
        self,
        job_type: JobType,
        job_data: Dict[str, Any],
        total_items: int = 0,
        created_by: Optional[int] = None,
        tenant_id: Optional[int] = None
    ) -> str:
        """
        Create a new job and return job ID.
        
        Args:
            job_type: Type of job being created
            job_data: Job parameters and configuration
            total_items: Total number of items to process
            created_by: User ID who created the job
            tenant_id: Tenant ID for multi-tenant setups
            
        Returns:
            Unique job ID
        """
        job_id = str(uuid.uuid4())
        
        # Create database record
        job_record = PayrollJobTracking(
            job_id=job_id,
            job_type=job_type.value,
            status=JobStatus.PENDING.value,
            job_data=job_data,
            total_items=total_items,
            completed_items=0,
            failed_items=0,
            created_by=created_by,
            tenant_id=tenant_id,
            created_at=datetime.utcnow()
        )
        
        self.db.add(job_record)
        self.db.commit()
        
        # Cache in Redis if available
        if self.redis:
            self._cache_job_in_redis(job_id, job_record)
        
        return job_id
    
    def update_job_status(
        self,
        job_id: str,
        status: JobStatus,
        progress: Optional[JobProgress] = None,
        error_message: Optional[str] = None
    ) -> bool:
        """
        Update job status and progress.
        
        Args:
            job_id: Job identifier
            status: New job status
            progress: Updated progress information
            error_message: Error message if job failed
            
        Returns:
            True if update was successful
        """
        # Update database
        job_record = self.db.query(PayrollJobTracking).filter(
            PayrollJobTracking.job_id == job_id
        ).first()
        
        if not job_record:
            return False
        
        job_record.status = status.value
        job_record.updated_at = datetime.utcnow()
        
        if progress:
            job_record.total_items = progress.total_items
            job_record.completed_items = progress.completed_items
            job_record.failed_items = progress.failed_items
            job_record.estimated_completion = progress.estimated_completion
        
        if error_message:
            job_record.error_message = error_message
        
        if status in [JobStatus.COMPLETED, JobStatus.FAILED, JobStatus.CANCELLED]:
            job_record.finished_at = datetime.utcnow()
        
        self.db.commit()
        
        # Update Redis cache
        if self.redis:
            self._cache_job_in_redis(job_id, job_record)
        
        return True
    
    def get_job_status(self, job_id: str) -> Optional[Dict[str, Any]]:
        """
        Get current job status and progress.
        
        Args:
            job_id: Job identifier
            
        Returns:
            Job status information or None if not found
        """
        # Try Redis cache first
        if self.redis:
            cached_data = self._get_job_from_redis(job_id)
            if cached_data:
                return cached_data
        
        # Fallback to database
        job_record = self.db.query(PayrollJobTracking).filter(
            PayrollJobTracking.job_id == job_id
        ).first()
        
        if not job_record:
            return None
        
        job_data = {
            "job_id": job_record.job_id,
            "job_type": job_record.job_type,
            "status": job_record.status,
            "progress": {
                "total_items": job_record.total_items,
                "completed_items": job_record.completed_items,
                "failed_items": job_record.failed_items,
                "progress_percentage": int(
                    (job_record.completed_items / max(job_record.total_items, 1)) * 100
                )
            },
            "created_at": job_record.created_at.isoformat(),
            "updated_at": job_record.updated_at.isoformat() if job_record.updated_at else None,
            "finished_at": job_record.finished_at.isoformat() if job_record.finished_at else None,
            "estimated_completion": job_record.estimated_completion.isoformat() if job_record.estimated_completion else None,
            "error_message": job_record.error_message,
            "created_by": job_record.created_by,
            "tenant_id": job_record.tenant_id
        }
        
        # Cache in Redis for future requests
        if self.redis:
            self._cache_job_in_redis(job_id, job_record)
        
        return job_data
    
    def complete_job(
        self,
        job_id: str,
        result: JobResult
    ) -> bool:
        """
        Mark job as completed with results.
        
        Args:
            job_id: Job identifier
            result: Job execution results
            
        Returns:
            True if update was successful
        """
        job_record = self.db.query(PayrollJobTracking).filter(
            PayrollJobTracking.job_id == job_id
        ).first()
        
        if not job_record:
            return False
        
        job_record.status = JobStatus.COMPLETED.value
        job_record.completed_items = result.success_count
        job_record.failed_items = result.failure_count
        job_record.finished_at = datetime.utcnow()
        job_record.result_data = {
            "success_count": result.success_count,
            "failure_count": result.failure_count,
            "total_processed": result.total_processed,
            "success_rate": result.success_rate,
            "errors": result.errors,
            "output_data": result.output_data
        }
        
        self.db.commit()
        
        # Update Redis cache
        if self.redis:
            self._cache_job_in_redis(job_id, job_record)
        
        return True
    
    def get_jobs_by_status(
        self,
        status: JobStatus,
        job_type: Optional[JobType] = None,
        tenant_id: Optional[int] = None,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """Get jobs by status with optional filtering."""
        query = self.db.query(PayrollJobTracking).filter(
            PayrollJobTracking.status == status.value
        )
        
        if job_type:
            query = query.filter(PayrollJobTracking.job_type == job_type.value)
        
        if tenant_id:
            query = query.filter(PayrollJobTracking.tenant_id == tenant_id)
        
        jobs = query.order_by(PayrollJobTracking.created_at.desc()).limit(limit).all()
        
        return [
            {
                "job_id": job.job_id,
                "job_type": job.job_type,
                "status": job.status,
                "created_at": job.created_at.isoformat(),
                "total_items": job.total_items,
                "completed_items": job.completed_items,
                "failed_items": job.failed_items
            }
            for job in jobs
        ]
    
    def cleanup_old_jobs(self, days_old: int = 7) -> int:
        """
        Clean up completed jobs older than specified days.
        
        Args:
            days_old: Number of days after which to clean up jobs
            
        Returns:
            Number of jobs cleaned up
        """
        cutoff_date = datetime.utcnow() - timedelta(days=days_old)
        
        deleted_count = self.db.query(PayrollJobTracking).filter(
            PayrollJobTracking.status.in_([
                JobStatus.COMPLETED.value,
                JobStatus.FAILED.value,
                JobStatus.CANCELLED.value
            ]),
            PayrollJobTracking.finished_at < cutoff_date
        ).delete()
        
        self.db.commit()
        return deleted_count
    
    def cancel_job(self, job_id: str, reason: str = "") -> bool:
        """Cancel a running or pending job."""
        job_record = self.db.query(PayrollJobTracking).filter(
            PayrollJobTracking.job_id == job_id,
            PayrollJobTracking.status.in_([
                JobStatus.PENDING.value,
                JobStatus.RUNNING.value,
                JobStatus.PROCESSING.value
            ])
        ).first()
        
        if not job_record:
            return False
        
        job_record.status = JobStatus.CANCELLED.value
        job_record.finished_at = datetime.utcnow()
        job_record.error_message = f"Cancelled: {reason}" if reason else "Cancelled by user"
        
        self.db.commit()
        
        # Update Redis cache
        if self.redis:
            self._cache_job_in_redis(job_id, job_record)
        
        return True
    
    def _cache_job_in_redis(self, job_id: str, job_record: PayrollJobTracking):
        """Cache job data in Redis."""
        try:
            if not self.redis:
                return
            
            cache_data = {
                "job_id": job_record.job_id,
                "job_type": job_record.job_type,
                "status": job_record.status,
                "total_items": job_record.total_items,
                "completed_items": job_record.completed_items,
                "failed_items": job_record.failed_items,
                "created_at": job_record.created_at.isoformat(),
                "updated_at": job_record.updated_at.isoformat() if job_record.updated_at else None,
                "error_message": job_record.error_message
            }
            
            self.redis.setex(
                f"job:{job_id}",
                self.redis_ttl,
                json.dumps(cache_data, default=str)
            )
        except Exception:
            # Redis failures shouldn't break the application
            pass
    
    def _get_job_from_redis(self, job_id: str) -> Optional[Dict[str, Any]]:
        """Get job data from Redis cache."""
        try:
            if not self.redis:
                return None
            
            cached = self.redis.get(f"job:{job_id}")
            if cached:
                return json.loads(cached)
        except Exception:
            # Redis failures shouldn't break the application
            pass
        
        return None