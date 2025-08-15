# backend/modules/insights/models/insight_models.py

from sqlalchemy import (
    Column,
    Integer,
    String,
    Text,
    DateTime,
    ForeignKey,
    JSON,
    Boolean,
    Enum as SQLEnum,
    DECIMAL,
)
from sqlalchemy.orm import relationship
from datetime import datetime
from enum import Enum

from core.database import Base, TimestampMixin


class InsightType(str, Enum):
    """Types of insights"""

    PERFORMANCE = "performance"
    TREND = "trend"
    ANOMALY = "anomaly"
    OPTIMIZATION = "optimization"
    WARNING = "warning"
    OPPORTUNITY = "opportunity"


class InsightSeverity(str, Enum):
    """Severity levels for insights"""

    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFO = "info"


class InsightStatus(str, Enum):
    """Status of insights"""

    ACTIVE = "active"
    ACKNOWLEDGED = "acknowledged"
    RESOLVED = "resolved"
    DISMISSED = "dismissed"
    EXPIRED = "expired"


class InsightDomain(str, Enum):
    """Business domains for insights"""

    SALES = "sales"
    INVENTORY = "inventory"
    STAFF = "staff"
    CUSTOMER = "customer"
    OPERATIONS = "operations"
    FINANCE = "finance"
    MARKETING = "marketing"


class NotificationChannel(str, Enum):
    """Notification delivery channels"""

    EMAIL = "email"
    SLACK = "slack"
    WEBHOOK = "webhook"
    IN_APP = "in_app"
    SMS = "sms"


class Insight(Base, TimestampMixin):
    """System-generated business insights"""

    __tablename__ = "insights"

    id = Column(Integer, primary_key=True)
    restaurant_id = Column(Integer, ForeignKey("restaurants.id"), nullable=False)

    # Insight details
    type = Column(SQLEnum(InsightType), nullable=False)
    severity = Column(SQLEnum(InsightSeverity), nullable=False)
    domain = Column(SQLEnum(InsightDomain), nullable=False)
    status = Column(SQLEnum(InsightStatus), default=InsightStatus.ACTIVE)

    title = Column(String(200), nullable=False)
    description = Column(Text, nullable=False)

    # Impact and recommendations
    impact_score = Column(DECIMAL(5, 2))  # 0-100 score
    estimated_value = Column(DECIMAL(10, 2))  # Potential monetary impact
    recommendations = Column(JSON, default=list)  # List of action items

    # Data and metrics
    metrics = Column(JSON, default={})  # Related metrics/data
    trend_data = Column(JSON, default={})  # Historical trend if applicable
    comparison_data = Column(JSON, default={})  # Comparative data

    # Context
    related_entity_type = Column(String(50))  # e.g., "product", "staff", "table"
    related_entity_id = Column(Integer)
    time_period = Column(JSON, default={})  # {"start": "...", "end": "..."}

    # Threading
    thread_id = Column(String(100))  # For grouping related insights
    parent_insight_id = Column(Integer, ForeignKey("insights.id"))

    # Metadata
    generated_by = Column(String(100))  # System/algorithm that generated it
    confidence_score = Column(DECIMAL(3, 2))  # 0.00-1.00
    expires_at = Column(DateTime)

    # User interaction
    acknowledged_by_id = Column(Integer, ForeignKey("staff.id"))
    acknowledged_at = Column(DateTime)
    resolved_by_id = Column(Integer, ForeignKey("staff.id"))
    resolved_at = Column(DateTime)
    resolution_notes = Column(Text)

    # Notification tracking
    notifications_sent = Column(JSON, default={})  # Channel -> timestamp
    notification_config = Column(JSON, default={})  # Custom notification settings

    # Relationships
    restaurant = relationship("Restaurant")
    parent_insight = relationship("Insight", remote_side=[id])
    acknowledged_by = relationship("Staff", foreign_keys=[acknowledged_by_id])
    resolved_by = relationship("Staff", foreign_keys=[resolved_by_id])
    ratings = relationship("InsightRating", back_populates="insight")
    actions = relationship("InsightAction", back_populates="insight")


class InsightRating(Base, TimestampMixin):
    """User ratings/feedback on insights"""

    __tablename__ = "insight_ratings"

    id = Column(Integer, primary_key=True)
    insight_id = Column(Integer, ForeignKey("insights.id"), nullable=False)
    user_id = Column(Integer, ForeignKey("staff.id"), nullable=False)

    rating = Column(String(20), nullable=False)  # useful, irrelevant, needs_followup
    comment = Column(Text)

    # Relationships
    insight = relationship("Insight", back_populates="ratings")
    user = relationship("Staff")


class InsightAction(Base, TimestampMixin):
    """Actions taken based on insights"""

    __tablename__ = "insight_actions"

    id = Column(Integer, primary_key=True)
    insight_id = Column(Integer, ForeignKey("insights.id"), nullable=False)
    user_id = Column(Integer, ForeignKey("staff.id"), nullable=False)

    action_type = Column(
        String(50), nullable=False
    )  # viewed, shared, exported, implemented
    action_details = Column(JSON, default={})

    # Relationships
    insight = relationship("Insight", back_populates="actions")
    user = relationship("Staff")


class InsightNotificationRule(Base, TimestampMixin):
    """Rules for insight notifications"""

    __tablename__ = "insight_notification_rules"

    id = Column(Integer, primary_key=True)
    restaurant_id = Column(Integer, ForeignKey("restaurants.id"), nullable=False)

    name = Column(String(100), nullable=False)
    description = Column(Text)
    is_active = Column(Boolean, default=True)

    # Rule conditions
    domains = Column(JSON, default=[])  # List of domains to monitor
    types = Column(JSON, default=[])  # List of insight types
    min_severity = Column(SQLEnum(InsightSeverity))
    min_impact_score = Column(DECIMAL(5, 2))
    min_estimated_value = Column(DECIMAL(10, 2))

    # Notification settings
    channels = Column(JSON, default=[])  # List of channels
    recipients = Column(JSON, default={})  # Channel -> recipient list

    # Timing
    immediate = Column(Boolean, default=True)
    batch_hours = Column(JSON, default=[])  # Hours to send batch notifications

    # Rate limiting
    max_per_hour = Column(Integer)
    max_per_day = Column(Integer)

    # Relationships
    restaurant = relationship("Restaurant")


class InsightThread(Base, TimestampMixin):
    """Grouping for related insights"""

    __tablename__ = "insight_threads"

    id = Column(Integer, primary_key=True)
    thread_id = Column(String(100), unique=True, nullable=False)
    restaurant_id = Column(Integer, ForeignKey("restaurants.id"), nullable=False)

    title = Column(String(200), nullable=False)
    description = Column(Text)
    category = Column(String(50))

    # Thread metadata
    first_insight_date = Column(DateTime)
    last_insight_date = Column(DateTime)
    total_insights = Column(Integer, default=0)
    total_value = Column(DECIMAL(12, 2), default=0)

    # Status
    is_active = Column(Boolean, default=True)
    is_recurring = Column(Boolean, default=False)
    recurrence_pattern = Column(JSON)  # Pattern detection data

    # Relationships
    restaurant = relationship("Restaurant")
