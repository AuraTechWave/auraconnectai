from sqlalchemy import (Column, Integer, String, ForeignKey, DateTime,
                        Text, Boolean, Enum)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship
from core.database import Base
from core.mixins import TimestampMixin
from ..enums.webhook_enums import (WebhookEventType, WebhookStatus,
                                   WebhookDeliveryStatus)


class WebhookConfiguration(Base, TimestampMixin):
    __tablename__ = "webhook_configurations"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False)
    url = Column(String(500), nullable=False)
    secret = Column(String(255), nullable=True)
    event_types = Column(JSONB, nullable=False)
    is_active = Column(Boolean, default=True, index=True)
    headers = Column(JSONB, nullable=True)
    timeout_seconds = Column(Integer, default=30)

    delivery_logs = relationship(
        "WebhookDeliveryLog",
        back_populates="webhook_config"
    )


class WebhookDeliveryLog(Base, TimestampMixin):
    __tablename__ = "webhook_delivery_logs"

    id = Column(Integer, primary_key=True, index=True)
    webhook_config_id = Column(
        Integer,
        ForeignKey("webhook_configurations.id"),
        nullable=False, index=True
    )
    order_id = Column(
        Integer, ForeignKey("orders.id"),
        nullable=False, index=True
    )
    event_type = Column(Enum(WebhookEventType), nullable=False, index=True)
    status = Column(
        Enum(WebhookStatus), nullable=False,
        default=WebhookStatus.PENDING, index=True
    )
    delivery_status = Column(
        Enum(WebhookDeliveryStatus),
        nullable=True, index=True
    )

    payload = Column(JSONB, nullable=False)
    response_status_code = Column(Integer, nullable=True)
    response_body = Column(Text, nullable=True)
    error_message = Column(Text, nullable=True)

    attempt_count = Column(Integer, default=0)
    max_retries = Column(Integer, default=3)
    next_retry_at = Column(DateTime, nullable=True)
    delivered_at = Column(DateTime, nullable=True)
    failed_at = Column(DateTime, nullable=True)

    webhook_config = relationship(
        "WebhookConfiguration",
        back_populates="delivery_logs"
    )
    order = relationship("Order")
