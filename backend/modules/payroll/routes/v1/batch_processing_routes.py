# backend/modules/payroll/routes/v1/batch_processing_routes.py

"""
Batch payroll processing endpoints.

Provides endpoints for processing payroll in batches with
job tracking and status monitoring.
"""

from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import date, datetime
import uuid

from .....core.database import get_db
from .....core.auth import require_payroll_write, get_current_user, User
from ...models.payroll_configuration import PayrollJobTracking
from ...schemas.batch_processing_schemas import (
    BatchPayrollRequest,
    BatchPayrollResponse,
    BatchJobStatus,
    BatchJobDetail,
    EmployeePayrollResult
)
from ...schemas.error_schemas import ErrorResponse, PayrollErrorCodes
from ...services.batch_payroll_service import BatchPayrollService
from ...enums.payroll_enums import PayrollJobStatus

router = APIRouter()


async def process_payroll_batch(
    db: Session,
    job_id: str,
    batch_request: BatchPayrollRequest,
    user_id: int
):
    """
    Background task to process payroll batch.
    """
    try:
        # Update job status
        job = db.query(PayrollJobTracking).filter(
            PayrollJobTracking.job_id == job_id
        ).first()
        
        if job:
            job.status = PayrollJobStatus.PROCESSING
            db.commit()
        
        # Process batch
        batch_service = BatchPayrollService(db)
        results = await batch_service.process_batch(
            employee_ids=batch_request.employee_ids,
            pay_period_start=batch_request.pay_period_start,
            pay_period_end=batch_request.pay_period_end,
            calculation_options=batch_request.calculation_options
        )
        
        # Update job with results
        if job:
            job.status = PayrollJobStatus.COMPLETED
            job.completed_at = datetime.utcnow()
            job.metadata.update({
                "total_processed": len(results),
                "successful": sum(1 for r in results if r.success),
                "failed": sum(1 for r in results if not r.success),
                "total_gross": str(sum(r.gross_amount for r in results if r.success)),
                "total_net": str(sum(r.net_amount for r in results if r.success))
            })
            db.commit()
        
    except Exception as e:
        if job:
            job.status = PayrollJobStatus.FAILED
            job.completed_at = datetime.utcnow()
            job.error_message = str(e)
            db.commit()
        raise


@router.post("/run", response_model=BatchPayrollResponse)
async def run_batch_payroll(
    batch_request: BatchPayrollRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_payroll_write)
):
    """
    Run payroll processing for multiple employees in batch.
    
    ## Request Body
    - **employee_ids**: List of employee IDs to process (or null for all)
    - **pay_period_start**: Start of pay period
    - **pay_period_end**: End of pay period
    - **calculation_options**: Optional calculation settings
    
    ## Response
    Returns job information for tracking batch progress.
    
    ## Permissions
    Requires payroll write permissions.
    """
    try:
        # Validate date range
        if batch_request.pay_period_start >= batch_request.pay_period_end:
            raise HTTPException(
                status_code=422,
                detail=ErrorResponse(
                    error="ValidationError",
                    message="Pay period end must be after start",
                    code=PayrollErrorCodes.INVALID_DATE_RANGE
                ).dict()
            )
        
        # Create job tracking
        job_id = str(uuid.uuid4())
        job = PayrollJobTracking(
            job_id=job_id,
            job_type="batch_payroll",
            status=PayrollJobStatus.PENDING,
            started_at=datetime.utcnow(),
            metadata={
                "user_id": current_user.id,
                "request": batch_request.dict(),
                "employee_count": len(batch_request.employee_ids) if batch_request.employee_ids else "all"
            },
            tenant_id=current_user.tenant_id if hasattr(current_user, 'tenant_id') else None
        )
        
        db.add(job)
        db.commit()
        
        # Queue background task
        background_tasks.add_task(
            process_payroll_batch,
            db,
            job_id,
            batch_request,
            current_user.id
        )
        
        return BatchPayrollResponse(
            job_id=job_id,
            status="pending",
            message="Batch payroll processing started",
            employee_count=len(batch_request.employee_ids) if batch_request.employee_ids else None,
            estimated_completion_time=datetime.utcnow().replace(minute=datetime.utcnow().minute + 5)
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=ErrorResponse(
                error="BatchProcessingError",
                message=f"Failed to start batch processing: {str(e)}",
                code=PayrollErrorCodes.DATABASE_ERROR
            ).dict()
        )


@router.get("/status/{job_id}", response_model=BatchJobStatus)
async def get_batch_job_status(
    job_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_payroll_write)
):
    """
    Get status of a batch payroll job.
    
    ## Path Parameters
    - **job_id**: Batch job ID
    
    ## Response
    Returns current job status and progress.
    """
    job = db.query(PayrollJobTracking).filter(
        PayrollJobTracking.job_id == job_id,
        PayrollJobTracking.job_type == "batch_payroll"
    ).first()
    
    if not job:
        raise HTTPException(
            status_code=404,
            detail=ErrorResponse(
                error="NotFound",
                message=f"Batch job {job_id} not found",
                code=PayrollErrorCodes.RECORD_NOT_FOUND
            ).dict()
        )
    
    # Calculate progress
    total = job.metadata.get("employee_count", 0)
    if isinstance(total, str) and total == "all":
        total = 100  # Placeholder for "all employees"
    
    processed = job.metadata.get("total_processed", 0)
    progress = (processed / total * 100) if total > 0 else 0
    
    return BatchJobStatus(
        job_id=job.job_id,
        status=job.status,
        progress=progress,
        started_at=job.started_at,
        completed_at=job.completed_at,
        total_employees=total,
        processed_employees=processed,
        successful_count=job.metadata.get("successful", 0),
        failed_count=job.metadata.get("failed", 0),
        error_message=job.error_message
    )


@router.get("/details/{job_id}", response_model=BatchJobDetail)
async def get_batch_job_details(
    job_id: str,
    include_results: bool = True,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_payroll_write)
):
    """
    Get detailed results of a batch payroll job.
    
    ## Path Parameters
    - **job_id**: Batch job ID
    
    ## Query Parameters
    - **include_results**: Include individual employee results
    
    ## Response
    Returns detailed job information with optional employee results.
    """
    job = db.query(PayrollJobTracking).filter(
        PayrollJobTracking.job_id == job_id,
        PayrollJobTracking.job_type == "batch_payroll"
    ).first()
    
    if not job:
        raise HTTPException(
            status_code=404,
            detail=ErrorResponse(
                error="NotFound",
                message=f"Batch job {job_id} not found",
                code=PayrollErrorCodes.RECORD_NOT_FOUND
            ).dict()
        )
    
    # Get results if requested and job is complete
    results = []
    if include_results and job.status == PayrollJobStatus.COMPLETED:
        # In a real implementation, fetch from results table
        # For now, return mock data from metadata
        pass
    
    return BatchJobDetail(
        job_id=job.job_id,
        status=job.status,
        started_at=job.started_at,
        completed_at=job.completed_at,
        request_parameters={
            "pay_period_start": job.metadata.get("request", {}).get("pay_period_start"),
            "pay_period_end": job.metadata.get("request", {}).get("pay_period_end"),
            "employee_count": job.metadata.get("employee_count")
        },
        summary={
            "total_employees": job.metadata.get("employee_count", 0),
            "processed": job.metadata.get("total_processed", 0),
            "successful": job.metadata.get("successful", 0),
            "failed": job.metadata.get("failed", 0),
            "total_gross": job.metadata.get("total_gross", "0"),
            "total_net": job.metadata.get("total_net", "0")
        },
        employee_results=results if include_results else None,
        error_details=job.error_message
    )


@router.post("/cancel/{job_id}")
async def cancel_batch_job(
    job_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_payroll_write)
):
    """
    Cancel a running batch payroll job.
    
    ## Path Parameters
    - **job_id**: Batch job ID to cancel
    
    ## Response
    Returns cancellation confirmation.
    """
    job = db.query(PayrollJobTracking).filter(
        PayrollJobTracking.job_id == job_id,
        PayrollJobTracking.job_type == "batch_payroll"
    ).first()
    
    if not job:
        raise HTTPException(
            status_code=404,
            detail=ErrorResponse(
                error="NotFound",
                message=f"Batch job {job_id} not found",
                code=PayrollErrorCodes.RECORD_NOT_FOUND
            ).dict()
        )
    
    if job.status not in [PayrollJobStatus.PENDING, PayrollJobStatus.PROCESSING]:
        raise HTTPException(
            status_code=400,
            detail=ErrorResponse(
                error="InvalidOperation",
                message=f"Cannot cancel job in {job.status.value} status",
                code=PayrollErrorCodes.PAYMENT_ALREADY_PROCESSED
            ).dict()
        )
    
    # Update job status
    job.status = PayrollJobStatus.CANCELLED
    job.completed_at = datetime.utcnow()
    job.error_message = "Cancelled by user"
    
    try:
        db.commit()
        return {
            "job_id": job_id,
            "status": "cancelled",
            "cancelled_at": datetime.utcnow().isoformat(),
            "cancelled_by": current_user.email
        }
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail=ErrorResponse(
                error="DatabaseError",
                message="Failed to cancel job",
                code=PayrollErrorCodes.DATABASE_ERROR
            ).dict()
        )


@router.get("/history")
async def get_batch_job_history(
    limit: int = 10,
    offset: int = 0,
    status: Optional[PayrollJobStatus] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_payroll_write)
):
    """
    Get history of batch payroll jobs.
    
    ## Query Parameters
    - **limit**: Maximum records to return
    - **offset**: Number of records to skip
    - **status**: Filter by job status
    
    ## Response
    Returns list of batch job summaries.
    """
    query = db.query(PayrollJobTracking).filter(
        PayrollJobTracking.job_type == "batch_payroll"
    )
    
    if status:
        query = query.filter(PayrollJobTracking.status == status)
    
    if hasattr(current_user, 'tenant_id'):
        query = query.filter(PayrollJobTracking.tenant_id == current_user.tenant_id)
    
    total = query.count()
    jobs = query.order_by(
        PayrollJobTracking.started_at.desc()
    ).limit(limit).offset(offset).all()
    
    return {
        "total": total,
        "limit": limit,
        "offset": offset,
        "jobs": [
            {
                "job_id": job.job_id,
                "status": job.status.value,
                "started_at": job.started_at.isoformat(),
                "completed_at": job.completed_at.isoformat() if job.completed_at else None,
                "employee_count": job.metadata.get("employee_count"),
                "successful": job.metadata.get("successful", 0),
                "failed": job.metadata.get("failed", 0)
            }
            for job in jobs
        ]
    }