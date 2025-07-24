from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from typing import List, Optional
from backend.core.database import get_db
from backend.modules.settings.controllers.pos_sync_controller import (
    get_pos_sync_settings_controller,
    create_or_update_pos_sync_setting_controller
)
from backend.modules.settings.schemas.pos_sync_schemas import (
    POSSyncSettingOut, POSSyncSettingCreate
)

router = APIRouter(prefix="/settings/pos-sync", tags=["POS Sync Settings"])


@router.get("/", response_model=List[POSSyncSettingOut])
async def get_pos_sync_settings(
    tenant_id: Optional[int] = Query(None, description="Filter by tenant ID"),
    team_id: Optional[int] = Query(None, description="Filter by team ID"),
    db: Session = Depends(get_db)
):
    return await get_pos_sync_settings_controller(db, tenant_id, team_id)


@router.post("/", response_model=POSSyncSettingOut)
async def create_or_update_pos_sync_setting(
    setting_data: POSSyncSettingCreate,
    db: Session = Depends(get_db)
):
    return await create_or_update_pos_sync_setting_controller(db, setting_data)
