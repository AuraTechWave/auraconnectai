# backend/modules/analytics/models/analytics_models.py

from sqlalchemy import (
    Column, Integer, String, ForeignKey, DateTime, Numeric, Boolean, 
    Index, text, func, Date, Enum as SQLEnum
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import relationship
from datetime import datetime, date
from enum import Enum
import uuid

from backend.core.database import Base
from backend.core.mixins import TimestampMixin


class ReportType(str, Enum):
    """Types of analytics reports"""
    SALES_SUMMARY = "sales_summary"
    SALES_DETAILED = "sales_detailed"
    STAFF_PERFORMANCE = "staff_performance"
    PRODUCT_PERFORMANCE = "product_performance"
    REVENUE_ANALYSIS = "revenue_analysis"
    CUSTOMER_ANALYTICS = "customer_analytics"
    TREND_ANALYSIS = "trend_analysis"


class AggregationPeriod(str, Enum):
    """Time period for data aggregation"""
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"
    QUARTERLY = "quarterly"
    YEARLY = "yearly"


class SalesAnalyticsSnapshot(Base, TimestampMixin):
    """
    Pre-aggregated sales data for faster reporting.
    Updated periodically via background jobs.
    """
    __tablename__ = "sales_analytics_snapshots"

    id = Column(Integer, primary_key=True, index=True)
    uuid = Column(UUID(as_uuid=True), default=uuid.uuid4, unique=True, index=True)
    
    # Time dimensions
    snapshot_date = Column(Date, nullable=False, index=True)
    period_type = Column(SQLEnum(AggregationPeriod), nullable=False, index=True)
    
    # Entity dimensions (nullable for different aggregation levels)
    staff_id = Column(Integer, ForeignKey("staff_members.id"), nullable=True, index=True)
    product_id = Column(Integer, nullable=True, index=True)  # Menu item ID
    category_id = Column(Integer, ForeignKey("categories.id"), nullable=True, index=True)
    customer_id = Column(Integer, ForeignKey("customers.id"), nullable=True, index=True)
    
    # Sales metrics
    total_orders = Column(Integer, nullable=False, default=0)
    total_revenue = Column(Numeric(12, 2), nullable=False, default=0.0)
    total_items_sold = Column(Integer, nullable=False, default=0)
    average_order_value = Column(Numeric(10, 2), nullable=False, default=0.0)
    
    # Discount and promotion metrics
    total_discounts = Column(Numeric(10, 2), nullable=False, default=0.0)
    total_tax = Column(Numeric(10, 2), nullable=False, default=0.0)
    net_revenue = Column(Numeric(12, 2), nullable=False, default=0.0)
    
    # Customer metrics
    unique_customers = Column(Integer, nullable=False, default=0)
    new_customers = Column(Integer, nullable=False, default=0)
    returning_customers = Column(Integer, nullable=False, default=0)
    
    # Staff metrics (when staff_id is specified)
    orders_handled = Column(Integer, nullable=True, default=0)
    average_processing_time = Column(Numeric(8, 2), nullable=True)  # minutes
    
    # Product metrics (when product_id is specified)
    product_quantity_sold = Column(Integer, nullable=True, default=0)
    product_revenue = Column(Numeric(10, 2), nullable=True, default=0.0)
    product_popularity_rank = Column(Integer, nullable=True)
    
    # Additional analytics data
    metadata = Column(JSONB, nullable=True)
    
    # Calculated timestamp for data freshness
    calculated_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    
    # Relationships
    staff_member = relationship("StaffMember", foreign_keys=[staff_id])
    category = relationship("Category", foreign_keys=[category_id])
    customer = relationship("Customer", foreign_keys=[customer_id])

    # Composite indexes for common query patterns
    __table_args__ = (
        Index('idx_snapshot_date_period', 'snapshot_date', 'period_type'),
        Index('idx_snapshot_staff_date', 'staff_id', 'snapshot_date'),
        Index('idx_snapshot_product_date', 'product_id', 'snapshot_date'),
        Index('idx_snapshot_category_date', 'category_id', 'snapshot_date'),
        Index('idx_snapshot_customer_date', 'customer_id', 'snapshot_date'),
        Index('idx_snapshot_calculated_at', 'calculated_at'),
    )


class ReportTemplate(Base, TimestampMixin):
    """
    Configurable report templates for sales analytics.
    Allows users to save and reuse report configurations.
    """
    __tablename__ = "report_templates"

    id = Column(Integer, primary_key=True, index=True)
    uuid = Column(UUID(as_uuid=True), default=uuid.uuid4, unique=True, index=True)
    
    # Template metadata
    name = Column(String(255), nullable=False, index=True)
    description = Column(String(1000), nullable=True)
    report_type = Column(SQLEnum(ReportType), nullable=False, index=True)
    
    # Template configuration
    filters_config = Column(JSONB, nullable=True)  # Date ranges, staff filters, etc.
    columns_config = Column(JSONB, nullable=True)  # Which columns to include
    sorting_config = Column(JSONB, nullable=True)  # Default sorting preferences
    visualization_config = Column(JSONB, nullable=True)  # Chart/graph settings
    
    # Access control
    created_by = Column(Integer, ForeignKey("staff_members.id"), nullable=False, index=True)
    is_public = Column(Boolean, nullable=False, default=False)
    is_system_template = Column(Boolean, nullable=False, default=False)
    
    # Usage tracking
    usage_count = Column(Integer, nullable=False, default=0)
    last_used_at = Column(DateTime, nullable=True)
    
    # Relationships
    created_by_staff = relationship("StaffMember", foreign_keys=[created_by])
    report_executions = relationship("ReportExecution", back_populates="template")


class ReportExecution(Base, TimestampMixin):
    """
    Track report generation history and performance.
    Useful for caching and audit trails.
    """
    __tablename__ = "report_executions"

    id = Column(Integer, primary_key=True, index=True)
    uuid = Column(UUID(as_uuid=True), default=uuid.uuid4, unique=True, index=True)
    
    # Execution metadata
    template_id = Column(Integer, ForeignKey("report_templates.id"), nullable=True, index=True)
    report_type = Column(SQLEnum(ReportType), nullable=False, index=True)
    executed_by = Column(Integer, ForeignKey("staff_members.id"), nullable=False, index=True)
    
    # Execution parameters
    parameters = Column(JSONB, nullable=True)  # Filters, date ranges, etc.
    execution_time_ms = Column(Integer, nullable=True)  # Performance tracking
    
    # Results metadata
    total_records = Column(Integer, nullable=True)
    file_path = Column(String(500), nullable=True)  # For exported reports
    file_format = Column(String(20), nullable=True)  # pdf, csv, xlsx, etc.
    file_size_bytes = Column(Integer, nullable=True)
    
    # Status tracking
    status = Column(String(50), nullable=False, default="completed", index=True)
    error_message = Column(String(1000), nullable=True)
    
    # Cache information
    cache_key = Column(String(255), nullable=True, index=True)
    expires_at = Column(DateTime, nullable=True)
    
    # Relationships
    template = relationship("ReportTemplate", back_populates="report_executions")
    executed_by_staff = relationship("StaffMember", foreign_keys=[executed_by])

    __table_args__ = (
        Index('idx_execution_status_created', 'status', 'created_at'),
        Index('idx_execution_cache_expires', 'cache_key', 'expires_at'),
        Index('idx_execution_executed_by_date', 'executed_by', 'created_at'),
    )


class SalesMetric(Base, TimestampMixin):
    """
    Real-time sales metrics for dashboard displays.
    Updated frequently for live reporting.
    """
    __tablename__ = "sales_metrics"

    id = Column(Integer, primary_key=True, index=True)
    
    # Metric identification
    metric_name = Column(String(100), nullable=False, index=True)
    metric_category = Column(String(50), nullable=False, index=True)
    
    # Time dimension
    metric_date = Column(Date, nullable=False, index=True)
    metric_hour = Column(Integer, nullable=True)  # 0-23 for hourly metrics
    
    # Entity dimensions
    entity_type = Column(String(50), nullable=True, index=True)  # staff, product, category
    entity_id = Column(Integer, nullable=True, index=True)
    
    # Metric values
    value_numeric = Column(Numeric(15, 4), nullable=True)
    value_integer = Column(Integer, nullable=True)
    value_text = Column(String(255), nullable=True)
    value_json = Column(JSONB, nullable=True)
    
    # Comparison data
    previous_value = Column(Numeric(15, 4), nullable=True)
    change_percentage = Column(Numeric(8, 2), nullable=True)
    
    # Metadata
    unit = Column(String(20), nullable=True)  # currency, percentage, count, etc.
    tags = Column(JSONB, nullable=True)
    is_estimate = Column(Boolean, nullable=False, default=False)
    
    __table_args__ = (
        Index('idx_metric_name_date', 'metric_name', 'metric_date'),
        Index('idx_metric_category_date', 'metric_category', 'metric_date'),
        Index('idx_metric_entity', 'entity_type', 'entity_id', 'metric_date'),
        Index('idx_metric_realtime', 'metric_date', 'metric_hour', 'created_at'),
    )


class AlertRule(Base, TimestampMixin):
    """
    Configurable alerts for sales analytics.
    Trigger notifications when metrics meet certain conditions.
    """
    __tablename__ = "alert_rules"

    id = Column(Integer, primary_key=True, index=True)
    uuid = Column(UUID(as_uuid=True), default=uuid.uuid4, unique=True, index=True)
    
    # Rule configuration
    name = Column(String(255), nullable=False, index=True)
    description = Column(String(1000), nullable=True)
    
    # Trigger conditions
    metric_name = Column(String(100), nullable=False, index=True)
    condition_type = Column(String(50), nullable=False)  # above, below, change, etc.
    threshold_value = Column(Numeric(15, 4), nullable=False)
    
    # Time settings
    evaluation_period = Column(String(50), nullable=False)  # hourly, daily, etc.
    comparison_period = Column(String(50), nullable=True)  # previous_day, previous_week
    
    # Notification settings
    notification_channels = Column(JSONB, nullable=True)  # email, slack, etc.
    notification_recipients = Column(JSONB, nullable=True)
    
    # Rule status
    is_active = Column(Boolean, nullable=False, default=True, index=True)
    last_triggered_at = Column(DateTime, nullable=True)
    trigger_count = Column(Integer, nullable=False, default=0)
    
    # Rule ownership
    created_by = Column(Integer, ForeignKey("staff_members.id"), nullable=False, index=True)
    
    # Relationships
    created_by_staff = relationship("StaffMember", foreign_keys=[created_by])

    __table_args__ = (
        Index('idx_alert_active_metric', 'is_active', 'metric_name'),
        Index('idx_alert_evaluation_period', 'evaluation_period', 'last_triggered_at'),
    )


# Create view for easier reporting queries
sales_summary_view = text("""
CREATE OR REPLACE VIEW v_sales_summary AS
SELECT 
    s.snapshot_date,
    s.period_type,
    sm.name as staff_name,
    sm.id as staff_id,
    c.name as category_name,
    c.id as category_id,
    s.total_orders,
    s.total_revenue,
    s.total_items_sold,
    s.average_order_value,
    s.total_discounts,
    s.net_revenue,
    s.unique_customers,
    s.calculated_at
FROM sales_analytics_snapshots s
LEFT JOIN staff_members sm ON s.staff_id = sm.id
LEFT JOIN categories c ON s.category_id = c.id
WHERE s.calculated_at >= CURRENT_DATE - INTERVAL '90 days'
ORDER BY s.snapshot_date DESC, s.total_revenue DESC;
""")

# Create materialized view for performance
top_performers_view = text("""
CREATE MATERIALIZED VIEW mv_top_performers AS
SELECT 
    DATE_TRUNC('month', snapshot_date) as month,
    staff_id,
    sm.name as staff_name,
    SUM(total_revenue) as monthly_revenue,
    SUM(total_orders) as monthly_orders,
    AVG(average_order_value) as avg_order_value,
    RANK() OVER (PARTITION BY DATE_TRUNC('month', snapshot_date) ORDER BY SUM(total_revenue) DESC) as revenue_rank
FROM sales_analytics_snapshots s
JOIN staff_members sm ON s.staff_id = sm.id
WHERE s.staff_id IS NOT NULL 
    AND s.snapshot_date >= CURRENT_DATE - INTERVAL '12 months'
GROUP BY DATE_TRUNC('month', snapshot_date), staff_id, sm.name
ORDER BY month DESC, revenue_rank;
""")