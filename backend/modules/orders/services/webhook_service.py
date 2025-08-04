import asyncio
import logging
import hmac
import hashlib
import json
from datetime import datetime, timedelta
from typing import Optional
from sqlalchemy.orm import Session
import httpx
from core.config import settings
from ..models.webhook_models import WebhookConfiguration, WebhookDeliveryLog
from ..models.order_models import Order
from ..schemas.webhook_schemas import (
    WebhookConfigurationCreate, WebhookConfigurationUpdate,
    WebhookPayload, WebhookTestResponse
)
from ..enums.webhook_enums import (WebhookEventType, WebhookStatus,
                                   WebhookDeliveryStatus)

logger = logging.getLogger(__name__)


class WebhookService:
    def __init__(self, db: Session):
        self.db = db
        self.max_retries = settings.WEBHOOK_MAX_RETRY_ATTEMPTS
        self.retry_delays = [delay // 60 for delay in settings.WEBHOOK_RETRY_DELAYS]  # Convert seconds to minutes
        self.timeout = settings.WEBHOOK_HTTP_TIMEOUT_SECONDS

    async def create_webhook_config(
        self,
        config_data: WebhookConfigurationCreate
    ) -> WebhookConfiguration:
        webhook_config = WebhookConfiguration(
            name=config_data.name,
            url=str(config_data.url),
            secret=config_data.secret,
            event_types=[event.value for event in config_data.event_types],
            headers=config_data.headers,
            timeout_seconds=config_data.timeout_seconds
        )

        self.db.add(webhook_config)
        self.db.commit()
        self.db.refresh(webhook_config)
        return webhook_config

    async def update_webhook_config(
        self,
        config_id: int,
        update_data: WebhookConfigurationUpdate
    ) -> Optional[WebhookConfiguration]:
        webhook_config = self.db.query(WebhookConfiguration).filter(
            WebhookConfiguration.id == config_id
        ).first()

        if not webhook_config:
            return None

        update_dict = update_data.dict(exclude_unset=True)
        if 'url' in update_dict:
            update_dict['url'] = str(update_dict['url'])
        if 'event_types' in update_dict:
            update_dict['event_types'] = [
                event.value for event in update_dict['event_types']
            ]

        for field, value in update_dict.items():
            setattr(webhook_config, field, value)

        self.db.commit()
        self.db.refresh(webhook_config)
        return webhook_config

    async def trigger_webhook(
        self,
        order_id: int,
        event_type: WebhookEventType,
        previous_status: Optional[str] = None,
        new_status: Optional[str] = None
    ):
        order = self.db.query(Order).filter(Order.id == order_id).first()
        if not order:
            logger.warning(f"Order {order_id} not found for webhook trigger")
            return

        active_configs = self.db.query(WebhookConfiguration).filter(
            WebhookConfiguration.is_active is True,
            WebhookConfiguration.event_types.contains([event_type.value])
        ).all()

        if not active_configs:
            logger.debug(
                f"No active webhook configurations for event {event_type}"
            )
            return

        for config in active_configs:
            await self._create_delivery_log(
                config, order, event_type, previous_status, new_status
            )

    async def _create_delivery_log(
        self,
        config: WebhookConfiguration,
        order: Order,
        event_type: WebhookEventType,
        previous_status: Optional[str],
        new_status: Optional[str]
    ):
        payload = WebhookPayload(
            event_type=event_type,
            timestamp=datetime.utcnow(),
            order_id=order.id,
            order_data={
                "id": order.id,
                "status": order.status,
                "staff_id": order.staff_id,
                "table_no": order.table_no,
                "customer_notes": order.customer_notes,
                "created_at": (
                    order.created_at.isoformat()
                    if order.created_at else None
                ),
                "updated_at": (
                    order.updated_at.isoformat()
                    if order.updated_at else None
                ),
                "items": [
                    {
                        "id": item.id,
                        "menu_item_id": item.menu_item_id,
                        "quantity": item.quantity,
                        "price": float(item.price),
                        "notes": item.notes
                    }
                    for item in order.order_items
                ]
            },
            previous_status=previous_status,
            new_status=new_status
        )

        delivery_log = WebhookDeliveryLog(
            webhook_config_id=config.id,
            order_id=order.id,
            event_type=event_type,
            payload=payload.dict(),
            max_retries=self.max_retries
        )

        self.db.add(delivery_log)
        self.db.commit()
        self.db.refresh(delivery_log)

        await self._deliver_webhook(delivery_log)

    async def _deliver_webhook(self, delivery_log: WebhookDeliveryLog):
        config = delivery_log.webhook_config

        for attempt in range(self.max_retries):
            try:
                headers = {"Content-Type": "application/json"}
                if config.headers:
                    headers.update(config.headers)

                payload_json = json.dumps(delivery_log.payload)
                if config.secret:
                    signature = self._generate_signature(
                        payload_json, config.secret
                    )
                    headers["X-Webhook-Signature"] = signature

                async with httpx.AsyncClient(
                    timeout=config.timeout_seconds
                ) as client:
                    response = await client.post(
                        config.url,
                        content=payload_json,
                        headers=headers
                    )

                    delivery_log.attempt_count = attempt + 1
                    delivery_log.response_status_code = response.status_code
                    delivery_log.response_body = response.text[:settings.WEBHOOK_LOG_RESPONSE_TRUNCATE]
                    delivery_log.delivered_at = datetime.utcnow()

                    if settings.WEBHOOK_SUCCESS_STATUS_MIN <= response.status_code < settings.WEBHOOK_SUCCESS_STATUS_MAX:
                        delivery_log.status = WebhookStatus.DELIVERED
                        delivery_log.delivery_status = (
                            WebhookDeliveryStatus.SUCCESS
                        )
                    else:
                        delivery_log.delivery_status = (
                            WebhookDeliveryStatus.INVALID_RESPONSE
                        )
                        if attempt < self.max_retries - 1:
                            delivery_log.status = WebhookStatus.RETRY
                            delivery_log.next_retry_at = (
                                datetime.utcnow() + timedelta(
                                    seconds=self.retry_delays[attempt]
                                )
                            )
                        else:
                            delivery_log.status = WebhookStatus.FAILED
                            delivery_log.failed_at = datetime.utcnow()

                    self.db.commit()

                    if delivery_log.status == WebhookStatus.DELIVERED:
                        logger.info(
                            f"Webhook delivered successfully to {config.url}"
                        )
                        return
                    elif attempt < self.max_retries - 1:
                        logger.warning(
                            f"Webhook failed (attempt {attempt + 1}), "
                            "retrying..."
                        )
                        await asyncio.sleep(self.retry_delays[attempt])
            except Exception as e:
                delivery_log.attempt_count = attempt + 1
                delivery_log.error_message = str(e)
                delivery_log.delivery_status = WebhookDeliveryStatus.FAILURE

                if attempt < self.max_retries - 1:
                    delivery_log.status = WebhookStatus.RETRY
                    delivery_log.next_retry_at = (
                        datetime.utcnow() + timedelta(
                            seconds=self.retry_delays[attempt]
                        )
                    )
                    logger.warning(
                        f"Webhook delivery error (attempt {attempt + 1}): "
                        f"{str(e)}"
                    )
                    await asyncio.sleep(self.retry_delays[attempt])
                else:
                    delivery_log.status = WebhookStatus.FAILED
                    delivery_log.failed_at = datetime.utcnow()
                    logger.error(
                        f"Webhook delivery failed after {self.max_retries} "
                        f"attempts: {str(e)}"
                    )

                self.db.commit()

    def _generate_signature(self, payload: str, secret: str) -> str:
        signature = hmac.new(
            secret.encode(),
            payload.encode(),
            hashlib.sha256
        ).hexdigest()
        return f"sha256={signature}"

    async def test_webhook_config(
        self, config_id: int
    ) -> WebhookTestResponse:
        config = self.db.query(WebhookConfiguration).filter(
            WebhookConfiguration.id == config_id
        ).first()

        if not config:
            return WebhookTestResponse(
                success=False,
                error_message="Webhook configuration not found"
            )

        test_payload = {
            "event_type": "webhook.test",
            "timestamp": datetime.utcnow().isoformat(),
            "test": True
        }

        try:
            headers = {"Content-Type": "application/json"}
            if config.headers:
                headers.update(config.headers)

            payload_json = json.dumps(test_payload)
            if config.secret:
                signature = self._generate_signature(
                    payload_json, config.secret
                )
                headers["X-Webhook-Signature"] = signature

            async with httpx.AsyncClient(
                timeout=config.timeout_seconds
            ) as client:
                response = await client.post(
                    config.url,
                    content=payload_json,
                    headers=headers
                )

                return WebhookTestResponse(
                    success=settings.WEBHOOK_SUCCESS_STATUS_MIN <= response.status_code < settings.WEBHOOK_SUCCESS_STATUS_MAX,
                    status_code=response.status_code,
                    response_body=response.text[:500],
                    error_message=(
                        None if settings.WEBHOOK_SUCCESS_STATUS_MIN <= response.status_code < settings.WEBHOOK_SUCCESS_STATUS_MAX
                        else "HTTP error"
                    )
                )

        except Exception as e:
            return WebhookTestResponse(
                success=False,
                error_message=str(e)
            )
