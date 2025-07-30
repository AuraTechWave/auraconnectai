# backend/modules/orders/routers/sync/config_router.py

"""
Sync configuration management endpoints.

Handles sync settings and configuration updates.
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import Dict
import logging

from backend.core.database import get_db
from backend.core.auth import get_current_user
from backend.modules.staff.models import StaffMember
from backend.modules.orders.models.sync_models import SyncConfiguration
from backend.modules.orders.tasks.sync_tasks import order_sync_scheduler
from backend.modules.orders.schemas.sync_schemas import SyncConfigurationUpdate

logger = logging.getLogger(__name__)
router = APIRouter(tags=["sync-config"])


@router.put("/configuration")
async def update_sync_configuration(
    config: SyncConfigurationUpdate,
    db: Session = Depends(get_db),
    current_user: StaffMember = Depends(get_current_user)
) -> Dict[str, str]:
    """
    Update sync configuration.
    
    Allows enabling/disabling sync and changing sync interval.
    """
    # Require admin permission
    if current_user.role not in ["admin", "manager"]:
        raise HTTPException(
            status_code=403,
            detail="Only administrators can modify sync configuration"
        )
    
    updated = []
    
    # Update sync enabled
    if config.sync_enabled is not None:
        sync_config = db.query(SyncConfiguration).filter(
            SyncConfiguration.config_key == "sync_enabled"
        ).first()
        
        if sync_config:
            sync_config.config_value = config.sync_enabled
        else:
            sync_config = SyncConfiguration(
                config_key="sync_enabled",
                config_value=config.sync_enabled,
                description="Enable or disable automatic order synchronization"
            )
            db.add(sync_config)
        
        sync_config.updated_by = current_user.id
        updated.append("sync_enabled")
    
    # Update sync interval
    if config.sync_interval_minutes is not None:
        if config.sync_interval_minutes < 1 or config.sync_interval_minutes > 1440:
            raise HTTPException(
                status_code=400,
                detail="Sync interval must be between 1 and 1440 minutes"
            )
        
        sync_config = db.query(SyncConfiguration).filter(
            SyncConfiguration.config_key == "sync_interval_minutes"
        ).first()
        
        if sync_config:
            sync_config.config_value = config.sync_interval_minutes
        else:
            sync_config = SyncConfiguration(
                config_key="sync_interval_minutes",
                config_value=config.sync_interval_minutes,
                description="Interval in minutes between automatic sync runs"
            )
            db.add(sync_config)
        
        sync_config.updated_by = current_user.id
        updated.append("sync_interval_minutes")
        
        # Update scheduler
        order_sync_scheduler.update_sync_interval(config.sync_interval_minutes)
    
    # Update conflict resolution mode
    if config.conflict_resolution_mode is not None:
        if config.conflict_resolution_mode not in ["auto", "manual"]:
            raise HTTPException(
                status_code=400,
                detail="Invalid conflict resolution mode"
            )
        
        sync_config = db.query(SyncConfiguration).filter(
            SyncConfiguration.config_key == "conflict_resolution_mode"
        ).first()
        
        if sync_config:
            sync_config.config_value = config.conflict_resolution_mode
        else:
            sync_config = SyncConfiguration(
                config_key="conflict_resolution_mode",
                config_value=config.conflict_resolution_mode,
                description="How to handle sync conflicts (auto or manual)"
            )
            db.add(sync_config)
        
        sync_config.updated_by = current_user.id
        updated.append("conflict_resolution_mode")
    
    db.commit()
    
    return {
        "status": "updated",
        "updated_fields": updated
    }