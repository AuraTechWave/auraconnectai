from sqlalchemy.orm import Session
from modules.settings.models.pos_sync_models import POSSyncSetting
from modules.settings.schemas.pos_sync_schemas import (
    POSSyncSettingCreate
)
from typing import List, Optional
from datetime import datetime


async def get_pos_sync_settings(
    db: Session,
    tenant_id: Optional[int] = None,
    team_id: Optional[int] = None
) -> List[POSSyncSetting]:
    query = db.query(POSSyncSetting)

    if tenant_id:
        query = query.filter(POSSyncSetting.tenant_id == tenant_id)
    if team_id:
        query = query.filter(POSSyncSetting.team_id == team_id)

    return query.all()


async def create_or_update_pos_sync_setting(
    db: Session,
    setting_data: POSSyncSettingCreate
) -> POSSyncSetting:
    existing = db.query(POSSyncSetting).filter(
        POSSyncSetting.tenant_id == setting_data.tenant_id,
        POSSyncSetting.team_id == setting_data.team_id
    ).first()

    if existing:
        existing.enabled = setting_data.enabled
        existing.updated_by = setting_data.updated_by
        existing.updated_at = datetime.utcnow()
        db.commit()
        db.refresh(existing)
        return existing
    else:
        db_setting = POSSyncSetting(**setting_data.dict())
        db.add(db_setting)
        db.commit()
        db.refresh(db_setting)
        return db_setting
