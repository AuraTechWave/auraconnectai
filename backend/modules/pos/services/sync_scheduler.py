from sqlalchemy.orm import Session
from backend.modules.settings.models.pos_sync_models import POSSyncSetting
from typing import Optional
import logging

logger = logging.getLogger(__name__)


class SyncScheduler:
    def __init__(self, db: Session):
        self.db = db

    def is_sync_enabled(
        self,
        tenant_id: Optional[int] = None,
        team_id: Optional[int] = None
    ) -> bool:
        if team_id:
            team_setting = self.db.query(POSSyncSetting).filter(
                POSSyncSetting.tenant_id == tenant_id,
                POSSyncSetting.team_id == team_id
            ).first()
            if team_setting:
                return team_setting.enabled

        global_setting = self.db.query(POSSyncSetting).filter(
            POSSyncSetting.tenant_id == tenant_id,
            POSSyncSetting.team_id.is_(None)
        ).first()

        if global_setting:
            return global_setting.enabled

        return True

    async def trigger_scheduled_sync(
        self,
        tenant_id: Optional[int] = None,
        team_id: Optional[int] = None
    ):
        if not self.is_sync_enabled(tenant_id, team_id):
            logger.info(
                f"Scheduled sync skipped for tenant {tenant_id}, "
                f"team {team_id} - sync disabled"
            )
            return False

        logger.info(
            f"Triggering scheduled sync for tenant {tenant_id}, team {team_id}"
        )
        return True
