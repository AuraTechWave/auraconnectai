# backend/modules/payroll/routes/payment_export_routes.py

"""
Payment export endpoints with background task processing.
"""

from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import date, datetime, timedelta
import uuid

from core.database import get_db
from core.auth import require_payroll_write, get_current_user, User
from ..models.payroll_models import EmployeePayment
from ..models.payroll_configuration import PayrollJobTracking
from ..schemas.payroll_schemas import (
    PaymentExportRequest,
    PaymentExportResponse,
    PayrollJobResponse
)
from ..schemas.error_schemas import ErrorResponse, PayrollErrorCodes
from ..enums.payroll_enums import PayrollJobStatus
from ..services.payment_export_service import PaymentExportService

router = APIRouter()


async def process_payment_export(
    db: Session,
    job_id: str,
    export_request: PaymentExportRequest,
    user_id: int
):
    """
    Background task to process payment export.
    """
    try:
        # Update job status to processing
        job = db.query(PayrollJobTracking).filter(
            PayrollJobTracking.job_id == job_id
        ).first()
        
        if job:
            job.status = PayrollJobStatus.PROCESSING
            job.metadata["started_processing"] = datetime.utcnow().isoformat()
            db.commit()
        
        # Process export
        export_service = PaymentExportService(db)
        result = await export_service.export_payments(
            start_date=export_request.start_date,
            end_date=export_request.end_date,
            employee_ids=export_request.employee_ids,
            format=export_request.format,
            include_details=export_request.include_details
        )
        
        # Update job with results
        if job:
            job.status = PayrollJobStatus.COMPLETED
            job.completed_at = datetime.utcnow()
            job.metadata.update({
                "file_path": result["file_path"],
                "record_count": result["record_count"],
                "file_size": result["file_size"]
            })
            db.commit()
        
    except Exception as e:
        # Update job with error
        if job:
            job.status = PayrollJobStatus.FAILED
            job.completed_at = datetime.utcnow()
            job.error_message = str(e)
            db.commit()
        raise


@router.post("", response_model=PaymentExportResponse)
async def export_payment_data(
    export_request: PaymentExportRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_payroll_write)
):
    """
    Export payment data asynchronously.
    
    ## Request Body
    - **start_date**: Export period start
    - **end_date**: Export period end
    - **employee_ids**: Optional list of employee IDs
    - **format**: Export format (csv, excel, pdf)
    - **include_details**: Include detailed breakdown
    
    ## Response
    Returns job information for tracking export progress.
    
    ## Error Responses
    - **422**: Invalid date range or format
    - **429**: Too many export requests (rate limited)
    """
    try:
        # Validate date range
        if export_request.start_date > export_request.end_date:
            raise HTTPException(
                status_code=422,
                detail=ErrorResponse(
                    error="ValidationError",
                    message="Start date must be before end date",
                    code=PayrollErrorCodes.INVALID_DATE_RANGE
                ).dict()
            )
        
        # Check for existing active exports (rate limiting)
        active_exports = db.query(PayrollJobTracking).filter(
            PayrollJobTracking.job_type == "payment_export",
            PayrollJobTracking.status.in_([PayrollJobStatus.PENDING, PayrollJobStatus.PROCESSING]),
            PayrollJobTracking.created_at >= datetime.utcnow() - timedelta(minutes=5)
        ).count()
        
        if active_exports >= 3:
            raise HTTPException(
                status_code=429,
                detail=ErrorResponse(
                    error="RateLimitExceeded",
                    message="Too many export requests. Please wait for existing exports to complete.",
                    code="PAYROLL_RATE_LIMIT_EXCEEDED"
                ).dict()
            )
        
        # Create job tracking record
        job_id = str(uuid.uuid4())
        job = PayrollJobTracking(
            job_id=job_id,
            job_type="payment_export",
            status=PayrollJobStatus.PENDING,
            started_at=datetime.utcnow(),
            metadata={
                "user_id": current_user.id,
                "request": export_request.dict(),
                "format": export_request.format
            },
            tenant_id=current_user.tenant_id
        )
        
        db.add(job)
        db.commit()
        
        # Queue background task
        background_tasks.add_task(
            process_payment_export,
            db,
            job_id,
            export_request,
            current_user.id
        )
        
        return PaymentExportResponse(
            status="accepted",
            message="Export request accepted and queued for processing",
            export_id=job_id,
            format=export_request.format,
            record_count=0,  # Will be updated by background task
            download_url=f"/api/payroll/payments/export/download/{job_id}"
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=ErrorResponse(
                error="ExportError",
                message=f"Failed to initiate export: {str(e)}",
                code=PayrollErrorCodes.DATABASE_ERROR
            ).dict()
        )


@router.get("/status/{job_id}", response_model=PayrollJobResponse)
async def get_export_status(
    job_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_payroll_write)
):
    """
    Get status of an export job.
    
    ## Path Parameters
    - **job_id**: Export job ID
    
    ## Response
    Returns current job status and metadata.
    
    ## Error Responses
    - **404**: Job not found
    """
    job = db.query(PayrollJobTracking).filter(
        PayrollJobTracking.job_id == job_id,
        PayrollJobTracking.job_type == "payment_export"
    ).first()
    
    if not job:
        raise HTTPException(
            status_code=404,
            detail=ErrorResponse(
                error="NotFound",
                message=f"Export job {job_id} not found",
                code=PayrollErrorCodes.RECORD_NOT_FOUND
            ).dict()
        )
    
    return PayrollJobResponse(
        id=job.id,
        job_id=job.job_id,
        job_type=job.job_type,
        status=job.status,
        started_at=job.started_at,
        completed_at=job.completed_at,
        error_message=job.error_message,
        metadata=job.metadata,
        tenant_id=job.tenant_id
    )


@router.get("/download/{job_id}")
async def download_export(
    job_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_payroll_write)
):
    """
    Download completed export file.
    
    ## Path Parameters
    - **job_id**: Export job ID
    
    ## Response
    Returns file download if export is complete.
    
    ## Error Responses
    - **404**: Job not found
    - **425**: Export not ready
    - **410**: Export expired
    """
    job = db.query(PayrollJobTracking).filter(
        PayrollJobTracking.job_id == job_id,
        PayrollJobTracking.job_type == "payment_export"
    ).first()
    
    if not job:
        raise HTTPException(
            status_code=404,
            detail=ErrorResponse(
                error="NotFound",
                message=f"Export job {job_id} not found",
                code=PayrollErrorCodes.RECORD_NOT_FOUND
            ).dict()
        )
    
    if job.status != PayrollJobStatus.COMPLETED:
        raise HTTPException(
            status_code=425,
            detail=ErrorResponse(
                error="ExportNotReady",
                message=f"Export is not ready. Current status: {job.status.value}",
                code="PAYROLL_EXPORT_NOT_READY"
            ).dict()
        )
    
    # Check if export has expired (24 hours)
    if job.completed_at and (datetime.utcnow() - job.completed_at).total_seconds() > 86400:
        raise HTTPException(
            status_code=410,
            detail=ErrorResponse(
                error="ExportExpired",
                message="Export file has expired. Please create a new export.",
                code="PAYROLL_EXPORT_EXPIRED"
            ).dict()
        )
    
    # In a real implementation, this would return the actual file
    # For now, return file metadata
    return {
        "job_id": job_id,
        "file_path": job.metadata.get("file_path"),
        "file_size": job.metadata.get("file_size"),
        "record_count": job.metadata.get("record_count"),
        "format": job.metadata.get("format"),
        "download_link": f"/files/exports/{job_id}"
    }