from fastapi import APIRouter, Depends, Query, Request, HTTPException
from sqlalchemy.orm import Session
from typing import List, Optional
import logging
from backend.core.database import get_db
from ..controllers.webhook_controller import (
    create_webhook_configuration, get_webhook_configuration,
    list_webhook_configurations, update_webhook_configuration,
    delete_webhook_configuration, test_webhook_configuration,
    get_webhook_delivery_logs
)
from ..schemas.webhook_schemas import (
    WebhookConfigurationCreate, WebhookConfigurationUpdate,
    WebhookConfigurationOut, WebhookDeliveryLogOut, WebhookTestResponse
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/webhooks", tags=["Webhooks"])


@router.post("/configurations", response_model=WebhookConfigurationOut)
async def create_webhook_config(
    config_data: WebhookConfigurationCreate,
    db: Session = Depends(get_db)
):
    return await create_webhook_configuration(config_data, db)


@router.get("/configurations", response_model=List[WebhookConfigurationOut])
async def list_webhook_configs(
    is_active: Optional[bool] = Query(None),
    db: Session = Depends(get_db)
):
    return await list_webhook_configurations(db, is_active)


@router.get(
    "/configurations/{config_id}",
    response_model=WebhookConfigurationOut
)
async def get_webhook_config(
    config_id: int,
    db: Session = Depends(get_db)
):
    return await get_webhook_configuration(config_id, db)


@router.put(
    "/configurations/{config_id}",
    response_model=WebhookConfigurationOut
)
async def update_webhook_config(
    config_id: int,
    update_data: WebhookConfigurationUpdate,
    db: Session = Depends(get_db)
):
    return await update_webhook_configuration(config_id, update_data, db)


@router.delete("/configurations/{config_id}")
async def delete_webhook_config(
    config_id: int,
    db: Session = Depends(get_db)
):
    return await delete_webhook_configuration(config_id, db)


@router.post(
    "/configurations/{config_id}/test",
    response_model=WebhookTestResponse
)
async def test_webhook_config(
    config_id: int,
    db: Session = Depends(get_db)
):
    return await test_webhook_configuration(config_id, db)


@router.get("/delivery-logs", response_model=List[WebhookDeliveryLogOut])
async def get_delivery_logs(
    webhook_config_id: Optional[int] = Query(None),
    order_id: Optional[int] = Query(None),
    limit: int = Query(100, le=1000),
    db: Session = Depends(get_db)
):
    return await get_webhook_delivery_logs(
        db, webhook_config_id, order_id, limit
    )


@router.post("/incoming/{webhook_id}")
async def receive_incoming_webhook(
    webhook_id: str,
    request: Request,
    db: Session = Depends(get_db)
):
    try:
        body = await request.body()
        headers = dict(request.headers)

        logger.info(f"Received incoming webhook {webhook_id}")
        logger.debug(f"Headers: {headers}")
        logger.debug(f"Body: {body.decode('utf-8')[:500]}")

        return {
            "status": "received",
            "webhook_id": webhook_id,
            "timestamp": "2024-01-01T00:00:00Z"
        }
    except Exception as e:
        logger.error(
            f"Error processing incoming webhook {webhook_id}: {str(e)}"
        )
        raise HTTPException(
            status_code=500,
            detail="Failed to process incoming webhook"
        )


@router.get("/health")
async def webhook_health_check():
    return {
        "status": "healthy",
        "service": "webhook_system",
        "timestamp": "2024-01-01T00:00:00Z"
    }
