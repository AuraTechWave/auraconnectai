from sqlalchemy.orm import Session
from typing import List, Optional
from fastapi import HTTPException
from ..services.webhook_service import WebhookService
from ..models.webhook_models import WebhookConfiguration, WebhookDeliveryLog
from ..schemas.webhook_schemas import (
    WebhookConfigurationCreate,
    WebhookConfigurationUpdate,
    WebhookConfigurationOut,
    WebhookDeliveryLogOut,
    WebhookTestResponse,
)


async def create_webhook_configuration(
    config_data: WebhookConfigurationCreate, db: Session
) -> WebhookConfigurationOut:
    service = WebhookService(db)
    webhook_config = await service.create_webhook_config(config_data)
    return WebhookConfigurationOut.from_orm(webhook_config)


async def get_webhook_configuration(
    config_id: int, db: Session
) -> WebhookConfigurationOut:
    webhook_config = (
        db.query(WebhookConfiguration)
        .filter(WebhookConfiguration.id == config_id)
        .first()
    )

    if not webhook_config:
        raise HTTPException(status_code=404, detail="Webhook configuration not found")

    return WebhookConfigurationOut.from_orm(webhook_config)


async def list_webhook_configurations(
    db: Session, is_active: Optional[bool] = None
) -> List[WebhookConfigurationOut]:
    query = db.query(WebhookConfiguration)

    if is_active is not None:
        query = query.filter(WebhookConfiguration.is_active == is_active)

    webhook_configs = query.all()
    return [WebhookConfigurationOut.from_orm(config) for config in webhook_configs]


async def update_webhook_configuration(
    config_id: int, update_data: WebhookConfigurationUpdate, db: Session
) -> WebhookConfigurationOut:
    service = WebhookService(db)
    webhook_config = await service.update_webhook_config(config_id, update_data)

    if not webhook_config:
        raise HTTPException(status_code=404, detail="Webhook configuration not found")

    return WebhookConfigurationOut.from_orm(webhook_config)


async def delete_webhook_configuration(config_id: int, db: Session) -> dict:
    webhook_config = (
        db.query(WebhookConfiguration)
        .filter(WebhookConfiguration.id == config_id)
        .first()
    )

    if not webhook_config:
        raise HTTPException(status_code=404, detail="Webhook configuration not found")

    db.delete(webhook_config)
    db.commit()

    return {"message": "Webhook configuration deleted successfully"}


async def test_webhook_configuration(
    config_id: int, db: Session
) -> WebhookTestResponse:
    service = WebhookService(db)
    return await service.test_webhook_config(config_id)


async def get_webhook_delivery_logs(
    db: Session,
    webhook_config_id: Optional[int] = None,
    order_id: Optional[int] = None,
    limit: int = 100,
) -> List[WebhookDeliveryLogOut]:
    query = db.query(WebhookDeliveryLog)

    if webhook_config_id:
        query = query.filter(WebhookDeliveryLog.webhook_config_id == webhook_config_id)

    if order_id:
        query = query.filter(WebhookDeliveryLog.order_id == order_id)

    logs = query.order_by(WebhookDeliveryLog.created_at.desc()).limit(limit).all()
    return [WebhookDeliveryLogOut.from_orm(log) for log in logs]
