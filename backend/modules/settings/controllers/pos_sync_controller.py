from modules.settings.services.pos_sync_service import (
    get_pos_sync_settings, create_or_update_pos_sync_setting
)


async def get_pos_sync_settings_controller(db, tenant_id=None, team_id=None):
    return await get_pos_sync_settings(db, tenant_id, team_id)


async def create_or_update_pos_sync_setting_controller(db, setting_data):
    return await create_or_update_pos_sync_setting(db, setting_data)
