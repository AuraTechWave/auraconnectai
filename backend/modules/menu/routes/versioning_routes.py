# backend/modules/menu/routes/versioning_routes.py

from fastapi import APIRouter, Depends, HTTPException, Query, BackgroundTasks
from sqlalchemy.orm import Session
from typing import List, Optional, Dict, Any
from datetime import datetime

from backend.core.database import get_db
from backend.core.menu_versioning_service import MenuVersioningService
from backend.core.menu_versioning_schemas import (
    MenuVersion, MenuVersionWithDetails, CreateVersionRequest, 
    PublishVersionRequest, RollbackVersionRequest, VersionComparisonRequest,
    MenuVersionComparison, PaginatedMenuVersions, PaginatedAuditLogs,
    MenuVersionStats, BulkChangeRequest, VersionExportRequest,
    VersionImportRequest, MenuVersionScheduleCreate, MenuVersionSchedule,
    VersionType, ChangeType
)
from backend.modules.auth.utils.dependencies import get_current_user, require_permission
from backend.modules.auth.models.auth_models import User

router = APIRouter(prefix="/menu/versions", tags=["Menu Versioning"])


@router.post("/", response_model=MenuVersion)
async def create_version(
    request: CreateVersionRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("menu:create"))
):
    """Create a new menu version from current active menu state"""
    service = MenuVersioningService(db)
    try:
        version = service.create_version(request, current_user.id)
        return version
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/", response_model=PaginatedMenuVersions)
async def get_versions(
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    version_type: Optional[VersionType] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("menu:read"))
):
    """Get paginated list of menu versions"""
    service = MenuVersioningService(db)
    versions, total = service.get_versions(page, size, version_type)
    
    return PaginatedMenuVersions(
        items=versions,
        total=total,
        page=page,
        size=size,
        pages=(total + size - 1) // size
    )


@router.get("/{version_id}", response_model=MenuVersionWithDetails)
async def get_version_details(
    version_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("menu:read"))
):
    """Get detailed information about a specific version"""
    service = MenuVersioningService(db)
    version = service.get_version_details(version_id)
    
    if not version:
        raise HTTPException(status_code=404, detail="Version not found")
    
    return version


@router.post("/{version_id}/publish", response_model=MenuVersion)
async def publish_version(
    version_id: int,
    request: PublishVersionRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("menu:update"))
):
    """Publish a menu version (make it active)"""
    service = MenuVersioningService(db)
    
    try:
        if request.scheduled_at and request.scheduled_at > datetime.utcnow():
            # Schedule the publication
            schedule_request = MenuVersionScheduleCreate(
                menu_version_id=version_id,
                scheduled_at=request.scheduled_at,
                notes=f"Scheduled publication by {current_user.username}"
            )
            # TODO: Add to background task queue
            background_tasks.add_task(_schedule_version_publication, schedule_request, current_user.id, db)
            
            version = service.get_version_details(version_id)
            if not version:
                raise HTTPException(status_code=404, detail="Version not found")
            return version
        else:
            # Publish immediately
            version = service.publish_version(version_id, request, current_user.id)
            return version
            
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/rollback", response_model=MenuVersion)
async def rollback_version(
    request: RollbackVersionRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("menu:update"))
):
    """Rollback to a previous version"""
    service = MenuVersioningService(db)
    
    try:
        version = service.rollback_to_version(request, current_user.id)
        return version
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/compare", response_model=MenuVersionComparison)
async def compare_versions(
    request: VersionComparisonRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("menu:read"))
):
    """Compare two menu versions and return differences"""
    service = MenuVersioningService(db)
    
    try:
        comparison = service.compare_versions(request)
        return comparison
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/audit/logs", response_model=PaginatedAuditLogs)
async def get_audit_logs(
    version_id: Optional[int] = None,
    page: int = Query(1, ge=1),
    size: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("menu:read"))
):
    """Get paginated audit logs for menu changes"""
    service = MenuVersioningService(db)
    logs, total = service.get_audit_logs(version_id, page, size)
    
    return PaginatedAuditLogs(
        items=logs,
        total=total,
        page=page,
        size=size,
        pages=(total + size - 1) // size
    )


@router.get("/stats", response_model=MenuVersionStats)
async def get_version_stats(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("menu:read"))
):
    """Get statistics about menu versions"""
    from sqlalchemy import func, desc
    from backend.core.menu_versioning_models import MenuVersion, MenuAuditLog
    
    # Get basic counts
    total_versions = db.query(MenuVersion).filter(MenuVersion.deleted_at == None).count()
    published_versions = db.query(MenuVersion).filter(
        MenuVersion.is_published == True,
        MenuVersion.deleted_at == None
    ).count()
    draft_versions = db.query(MenuVersion).filter(
        MenuVersion.is_published == False,
        MenuVersion.deleted_at == None
    ).count()
    scheduled_versions = db.query(MenuVersion).filter(
        MenuVersion.scheduled_publish_at != None,
        MenuVersion.is_published == False,
        MenuVersion.deleted_at == None
    ).count()
    
    # Get active version
    active_version = db.query(MenuVersion).filter(MenuVersion.is_active == True).first()
    
    # Get latest change
    latest_change = db.query(MenuAuditLog.created_at).order_by(desc(MenuAuditLog.created_at)).first()
    
    # Get today's changes
    today = datetime.utcnow().date()
    total_changes_today = db.query(MenuAuditLog).filter(
        func.date(MenuAuditLog.created_at) == today
    ).count()
    
    # Get most changed items (mock data for now)
    most_changed_items = [
        {"name": "Popular Item 1", "changes": 15},
        {"name": "Popular Item 2", "changes": 12},
        {"name": "Popular Item 3", "changes": 8}
    ]
    
    return MenuVersionStats(
        total_versions=total_versions,
        active_version=active_version,
        published_versions=published_versions,
        draft_versions=draft_versions,
        scheduled_versions=scheduled_versions,
        latest_change=latest_change[0] if latest_change else None,
        total_changes_today=total_changes_today,
        most_changed_items=most_changed_items
    )


@router.post("/bulk-change", response_model=Dict[str, Any])
async def bulk_change(
    request: BulkChangeRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("menu:update"))
):
    """Apply bulk changes to menu entities"""
    service = MenuVersioningService(db)
    
    try:
        results = service.bulk_change(request, current_user.id)
        return results
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{version_id}/export")
async def export_version(
    version_id: int,
    request: VersionExportRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("menu:read"))
):
    """Export a menu version to various formats"""
    service = MenuVersioningService(db)
    version = service.get_version_details(version_id)
    
    if not version:
        raise HTTPException(status_code=404, detail="Version not found")
    
    # TODO: Implement export functionality based on format
    if request.format == "json":
        export_data = {
            "version": version.dict(),
            "exported_at": datetime.utcnow().isoformat(),
            "exported_by": current_user.username,
            "include_audit_trail": request.include_audit_trail,
            "include_inactive": request.include_inactive
        }
        return export_data
    
    raise HTTPException(status_code=400, detail=f"Export format '{request.format}' not supported yet")


@router.post("/import", response_model=MenuVersion)
async def import_version(
    request: VersionImportRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("menu:create"))
):
    """Import menu data and optionally create a new version"""
    # TODO: Implement import functionality
    raise HTTPException(status_code=501, detail="Import functionality not implemented yet")


@router.delete("/{version_id}")
async def delete_version(
    version_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("menu:delete"))
):
    """Soft delete a menu version"""
    version = db.query(MenuVersion).filter(MenuVersion.id == version_id).first()
    
    if not version:
        raise HTTPException(status_code=404, detail="Version not found")
    
    if version.is_active:
        raise HTTPException(status_code=400, detail="Cannot delete the active version")
    
    if version.is_published:
        raise HTTPException(status_code=400, detail="Cannot delete a published version")
    
    version.deleted_at = datetime.utcnow()
    db.commit()
    
    return {"message": "Version deleted successfully"}


# Background task functions
async def _schedule_version_publication(
    schedule_request: MenuVersionScheduleCreate,
    user_id: int,
    db: Session
):
    """Background task to handle scheduled version publication"""
    # TODO: Implement scheduling logic with celery or similar
    pass


# Webhook endpoints for external integrations
@router.post("/webhooks/auto-version")
async def auto_version_webhook(
    data: Dict[str, Any],
    db: Session = Depends(get_db)
):
    """Webhook endpoint for automatic version creation based on external triggers"""
    # TODO: Implement webhook logic for external systems
    # This could be triggered by POS systems, inventory updates, etc.
    return {"message": "Auto-versioning webhook received"}


@router.get("/{version_id}/preview")
async def preview_version(
    version_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("menu:read"))
):
    """Preview what the menu would look like with this version active"""
    service = MenuVersioningService(db)
    version = service.get_version_details(version_id)
    
    if not version:
        raise HTTPException(status_code=404, detail="Version not found")
    
    # TODO: Generate preview data showing how the live menu would look
    preview_data = {
        "version_info": {
            "id": version.id,
            "version_number": version.version_number,
            "version_name": version.version_name,
            "description": version.description
        },
        "categories": len(version.categories),
        "items": len(version.items),
        "modifiers": sum(len(mg.modifier_versions) for mg in version.modifiers),
        "preview_generated_at": datetime.utcnow().isoformat()
    }
    
    return preview_data