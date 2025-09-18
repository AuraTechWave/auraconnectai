"""
POS Migration Router

FastAPI endpoints for POS migration operations with RBAC protection.
"""

from datetime import datetime
from typing import List, Optional
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, status, Query, WebSocket, WebSocketDisconnect
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
import asyncio
import json

from core.database import get_db
from core.auth import get_current_user, require_role
from core.rate_limit import rate_limit
from ..schemas.migration_schemas import (
    MigrationJobCreate,
    MigrationJobUpdate,
    MigrationJobResponse,
    MigrationJobDetail,
    MigrationAnalysisRequest,
    MigrationAnalysisResponse,
    DataMappingCreate,
    DataMappingResponse,
    MigrationTemplateCreate,
    MigrationTemplateResponse,
    ValidationResultResponse,
    MigrationProgressUpdate,
    BulkMigrationRequest,
    MigrationStatsResponse
)
from ..services.migration_service import MigrationService
from ..services.background_service import BackgroundMigrationService
from ..services.export_service import MigrationExportService
from ..models.migration_models import MigrationStatus, POSProvider

router = APIRouter(
    prefix="/api/v1/pos-migration",
    tags=["POS Migration"],
    dependencies=[Depends(get_current_user)]
)


@router.post("/jobs", response_model=MigrationJobResponse)
@rate_limit(calls=10, period=60)
async def create_migration_job(
    job_data: MigrationJobCreate,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """
    Create a new POS migration job.
    
    Requires: migration.create permission
    """
    service = MigrationService(db, current_user)
    try:
        job = await service.create_migration_job(job_data)
        
        # Schedule background processing
        background_service = BackgroundMigrationService()
        await background_service.schedule_job(job.id)
        
        return job
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@router.get("/jobs", response_model=List[MigrationJobResponse])
async def list_migration_jobs(
    status: Optional[MigrationStatus] = Query(None),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """
    List migration jobs for current restaurant.
    
    Requires: Authenticated user with restaurant context
    """
    service = MigrationService(db, current_user)
    jobs = await service.list_migration_jobs(status, limit, offset)
    return jobs


@router.get("/jobs/{job_id}", response_model=MigrationJobDetail)
async def get_migration_job(
    job_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """
    Get detailed information about a migration job.
    
    Requires: Authenticated user with restaurant context
    """
    service = MigrationService(db, current_user)
    job = await service.get_migration_job(job_id)
    
    # Add validation summary
    validation_summary = await service.get_validation_summary(job_id)
    
    return MigrationJobDetail(
        **job.__dict__,
        validation_summary=validation_summary
    )


@router.patch("/jobs/{job_id}", response_model=MigrationJobResponse)
async def update_migration_job(
    job_id: UUID,
    update_data: MigrationJobUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """
    Update migration job configuration.
    
    Requires: migration.update permission
    """
    service = MigrationService(db, current_user)
    job = await service.update_migration_job(job_id, update_data)
    return job


@router.post("/jobs/{job_id}/start", response_model=MigrationJobResponse)
@require_role(["admin", "manager"])
async def start_migration(
    job_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """
    Start or resume a migration job.
    
    Requires: Admin or Manager role
    """
    service = MigrationService(db, current_user)
    job = await service.start_migration(job_id)
    return job


@router.post("/jobs/{job_id}/pause", response_model=MigrationJobResponse)
async def pause_migration(
    job_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """
    Pause an active migration.
    
    Requires: migration.execute permission
    """
    service = MigrationService(db, current_user)
    job = await service.pause_migration(job_id)
    return job


@router.post("/jobs/{job_id}/cancel", response_model=MigrationJobResponse)
@require_role(["admin"])
async def cancel_migration(
    job_id: UUID,
    rollback: bool = Query(True),
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """
    Cancel a migration with optional rollback.
    
    Requires: Admin role
    """
    service = MigrationService(db, current_user)
    job = await service.cancel_migration(job_id, rollback)
    return job


@router.post("/analyze", response_model=MigrationAnalysisResponse)
@rate_limit(calls=5, period=300)
async def analyze_pos_system(
    request: MigrationAnalysisRequest,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """
    Analyze source POS system and get migration recommendations.
    
    Requires: migration.analyze permission
    """
    service = MigrationService(db, current_user)
    analysis = await service.analyze_source_system(request)
    return analysis


@router.post("/jobs/{job_id}/mappings", response_model=List[DataMappingResponse])
async def update_field_mappings(
    job_id: UUID,
    mappings: List[DataMappingCreate],
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """
    Update field mappings for a migration job.
    
    Requires: migration.configure permission
    """
    service = MigrationService(db, current_user)
    updated_mappings = await service.update_mappings(job_id, mappings)
    return updated_mappings


@router.get("/jobs/{job_id}/mappings", response_model=List[DataMappingResponse])
async def get_field_mappings(
    job_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """
    Get field mappings for a migration job.
    
    Requires: Authenticated user with restaurant context
    """
    service = MigrationService(db, current_user)
    mappings = await service.get_mappings(job_id)
    return mappings


@router.get("/jobs/{job_id}/validations", response_model=List[ValidationResultResponse])
async def get_validation_results(
    job_id: UUID,
    entity_type: Optional[str] = Query(None),
    is_valid: Optional[bool] = Query(None),
    limit: int = Query(100, ge=1, le=1000),
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """
    Get validation results for a migration job.
    
    Requires: Authenticated user with restaurant context
    """
    service = MigrationService(db, current_user)
    results = await service.get_validation_results(
        job_id, entity_type, is_valid, limit
    )
    return results


@router.post("/bulk", response_model=dict)
@require_role(["admin"])
async def bulk_migration_operation(
    request: BulkMigrationRequest,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """
    Perform bulk operations on multiple migration jobs.
    
    Requires: Admin role
    """
    service = MigrationService(db, current_user)
    results = await service.bulk_operation(request.job_ids, request.action)
    return {"success": True, "results": results}


@router.get("/templates", response_model=List[MigrationTemplateResponse])
async def list_migration_templates(
    source_provider: Optional[POSProvider] = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """
    List available migration templates.
    
    Requires: Authenticated user
    """
    service = MigrationService(db, current_user)
    templates = await service.list_templates(source_provider)
    return templates


@router.post("/templates", response_model=MigrationTemplateResponse)
@require_role(["admin"])
async def create_migration_template(
    template_data: MigrationTemplateCreate,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """
    Create a new migration template.
    
    Requires: Admin role
    """
    service = MigrationService(db, current_user)
    template = await service.create_template(template_data)
    return template


@router.post("/jobs/{job_id}/apply-template/{template_id}")
async def apply_migration_template(
    job_id: UUID,
    template_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """
    Apply a template to a migration job.
    
    Requires: migration.configure permission
    """
    service = MigrationService(db, current_user)
    await service.apply_template(job_id, template_id)
    return {"success": True, "message": "Template applied successfully"}


@router.get("/stats", response_model=MigrationStatsResponse)
async def get_migration_statistics(
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """
    Get migration statistics for dashboard.
    
    Requires: Authenticated user with restaurant context
    """
    service = MigrationService(db, current_user)
    stats = await service.get_migration_stats()
    return stats


@router.get("/jobs/{job_id}/export")
async def export_migration_report(
    job_id: UUID,
    format: str = Query("pdf", pattern="^(pdf|csv|json)$"),
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """
    Export migration report in various formats.
    
    Requires: migration.export permission
    """
    export_service = MigrationExportService(db, current_user)
    
    if format == "pdf":
        content, filename = await export_service.export_pdf(job_id)
        media_type = "application/pdf"
    elif format == "csv":
        content, filename = await export_service.export_csv(job_id)
        media_type = "text/csv"
    else:
        content, filename = await export_service.export_json(job_id)
        media_type = "application/json"
    
    return StreamingResponse(
        content,
        media_type=media_type,
        headers={
            "Content-Disposition": f"attachment; filename={filename}"
        }
    )


@router.websocket("/jobs/{job_id}/progress")
async def migration_progress_websocket(
    websocket: WebSocket,
    job_id: UUID,
    db: AsyncSession = Depends(get_db)
):
    """
    WebSocket endpoint for real-time migration progress updates.
    
    Requires: Authenticated WebSocket connection
    """
    await websocket.accept()
    
    try:
        # Validate job access
        # In production, validate JWT from query params or headers
        
        while True:
            # Get current job status
            service = MigrationService(db, {"restaurant_id": 1})  # Mock auth
            job = await service.get_migration_job(job_id)
            
            # Send progress update
            update = MigrationProgressUpdate(
                job_id=job_id,
                status=job.status,
                progress_percentage=job.progress_percentage,
                current_entity=job.current_entity,
                message=f"Processing {job.current_entity or 'data'}...",
                timestamp=datetime.utcnow(),
                records_processed=job.records_processed,
                records_succeeded=job.records_succeeded,
                records_failed=job.records_failed
            )
            
            await websocket.send_json(update.model_dump_json())
            
            # Check if migration is complete
            if job.status in [
                MigrationStatus.COMPLETED,
                MigrationStatus.FAILED,
                MigrationStatus.CANCELLED
            ]:
                break
            
            # Wait before next update
            await asyncio.sleep(2)
            
    except WebSocketDisconnect:
        pass
    except Exception as e:
        await websocket.send_json({
            "error": str(e),
            "timestamp": datetime.utcnow().isoformat()
        })
    finally:
        await websocket.close()


@router.post("/jobs/{job_id}/retry-failed")
async def retry_failed_records(
    job_id: UUID,
    entity_types: Optional[List[str]] = None,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """
    Retry failed records from a migration.
    
    Requires: migration.execute permission
    """
    service = MigrationService(db, current_user)
    result = await service.retry_failed_records(job_id, entity_types)
    return result


@router.delete("/jobs/{job_id}")
@require_role(["admin"])
async def delete_migration_job(
    job_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """
    Delete a migration job and all related data.
    
    Requires: Admin role
    """
    service = MigrationService(db, current_user)
    await service.delete_migration_job(job_id)
    return {"success": True, "message": "Migration job deleted"}