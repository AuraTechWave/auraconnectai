# backend/modules/analytics/schemas/analytics_schemas.py

from pydantic import BaseModel, Field, validator
from typing import Optional, List, Dict, Any, Union
from datetime import datetime, date
from decimal import Decimal
from enum import Enum

from ..models.analytics_models import ReportType, AggregationPeriod


class SalesFilterRequest(BaseModel):
    """Request schema for filtering sales data"""

    # Date range filters
    date_from: Optional[date] = Field(None, description="Start date for the report")
    date_to: Optional[date] = Field(None, description="End date for the report")

    # Entity filters
    staff_ids: Optional[List[int]] = Field(
        None, description="Filter by specific staff members"
    )
    product_ids: Optional[List[int]] = Field(
        None, description="Filter by specific products/menu items"
    )
    category_ids: Optional[List[int]] = Field(
        None, description="Filter by product categories"
    )
    customer_ids: Optional[List[int]] = Field(
        None, description="Filter by specific customers"
    )

    # Time aggregation
    period_type: Optional[AggregationPeriod] = Field(
        AggregationPeriod.DAILY, description="Time period for data aggregation"
    )

    # Additional filters
    include_discounts: bool = Field(True, description="Include discount information")
    include_tax: bool = Field(True, description="Include tax information")
    only_completed_orders: bool = Field(
        True, description="Only include completed orders"
    )
    min_order_value: Optional[Decimal] = Field(None, description="Minimum order value")
    max_order_value: Optional[Decimal] = Field(None, description="Maximum order value")

    @field_validator("date_to", mode="after")
    def validate_date_range(cls, v, values):
        if v and "date_from" in values and values["date_from"]:
            if v < values["date_from"]:
                raise ValueError("date_to must be after date_from")
        return v

    @field_validator("staff_ids", "product_ids", "category_ids", "customer_ids", mode="after")
    def validate_id_lists(cls, v):
        if v is not None:
            if not isinstance(v, list) or not all(
                isinstance(x, int) and x > 0 for x in v
            ):
                raise ValueError("IDs must be a list of positive integers")
        return v


class SalesSummaryResponse(BaseModel):
    """Response schema for sales summary data"""

    # Time period
    period_start: date
    period_end: date
    period_type: AggregationPeriod

    # Overall metrics
    total_orders: int = Field(description="Total number of orders")
    total_revenue: Decimal = Field(description="Total revenue amount")
    total_items_sold: int = Field(description="Total number of items sold")
    average_order_value: Decimal = Field(description="Average order value")

    # Financial breakdown
    gross_revenue: Decimal = Field(description="Revenue before discounts")
    total_discounts: Decimal = Field(description="Total discount amount")
    total_tax: Decimal = Field(description="Total tax amount")
    net_revenue: Decimal = Field(description="Net revenue after discounts")

    # Customer metrics
    unique_customers: int = Field(description="Number of unique customers")
    new_customers: int = Field(description="Number of new customers")
    returning_customers: int = Field(description="Number of returning customers")
    customer_retention_rate: Optional[Decimal] = Field(
        description="Customer retention percentage"
    )

    # Growth metrics
    revenue_growth: Optional[Decimal] = Field(
        description="Revenue growth vs previous period"
    )
    order_growth: Optional[Decimal] = Field(
        description="Order count growth vs previous period"
    )

    class Config:
        from_attributes = True
        json_encoders = {Decimal: lambda v: float(v)}


class SalesDetailResponse(BaseModel):
    """Response schema for detailed sales data"""

    # Snapshot identification
    id: int
    snapshot_date: date
    period_type: AggregationPeriod

    # Entity information
    staff_id: Optional[int] = None
    staff_name: Optional[str] = None
    product_id: Optional[int] = None
    product_name: Optional[str] = None
    category_id: Optional[int] = None
    category_name: Optional[str] = None

    # Sales metrics
    total_orders: int
    total_revenue: Decimal
    total_items_sold: int
    average_order_value: Decimal

    # Additional metrics
    total_discounts: Decimal
    total_tax: Decimal
    net_revenue: Decimal
    unique_customers: int

    # Staff-specific metrics (when applicable)
    orders_handled: Optional[int] = None
    average_processing_time: Optional[Decimal] = None

    # Product-specific metrics (when applicable)
    product_quantity_sold: Optional[int] = None
    product_revenue: Optional[Decimal] = None
    product_popularity_rank: Optional[int] = None

    # Timestamp
    calculated_at: datetime

    class Config:
        from_attributes = True
        json_encoders = {Decimal: lambda v: float(v)}


class StaffPerformanceResponse(BaseModel):
    """Response schema for staff performance analytics"""

    staff_id: int
    staff_name: str

    # Performance metrics
    total_orders_handled: int
    total_revenue_generated: Decimal
    average_order_value: Decimal
    orders_per_hour: Optional[Decimal] = None
    average_processing_time: Optional[Decimal] = None

    # Rankings
    revenue_rank: Optional[int] = None
    order_count_rank: Optional[int] = None
    efficiency_rank: Optional[int] = None

    # Growth metrics
    revenue_growth: Optional[Decimal] = None
    order_growth: Optional[Decimal] = None

    # Time period
    period_start: date
    period_end: date

    class Config:
        from_attributes = True
        json_encoders = {Decimal: lambda v: float(v)}


class ProductPerformanceResponse(BaseModel):
    """Response schema for product performance analytics"""

    product_id: int
    product_name: Optional[str] = None
    category_id: Optional[int] = None
    category_name: Optional[str] = None

    # Performance metrics
    quantity_sold: int
    revenue_generated: Decimal
    average_price: Decimal
    order_frequency: int  # Number of orders containing this product

    # Rankings
    popularity_rank: Optional[int] = None
    revenue_rank: Optional[int] = None
    growth_rank: Optional[int] = None

    # Growth metrics
    quantity_growth: Optional[Decimal] = None
    revenue_growth: Optional[Decimal] = None

    # Market share
    revenue_share: Optional[Decimal] = None  # Percentage of total revenue
    quantity_share: Optional[Decimal] = None  # Percentage of total items sold

    # Time period
    period_start: date
    period_end: date

    class Config:
        from_attributes = True
        json_encoders = {Decimal: lambda v: float(v)}


class SalesReportRequest(BaseModel):
    """Request schema for generating sales reports"""

    report_type: ReportType = Field(description="Type of report to generate")
    filters: SalesFilterRequest = Field(description="Filters to apply to the report")

    # Report configuration
    include_charts: bool = Field(True, description="Include visualization charts")
    export_format: Optional[str] = Field(
        None, description="Export format (pdf, csv, xlsx)"
    )
    template_id: Optional[int] = Field(None, description="Use saved report template")

    # Sorting and pagination
    sort_by: Optional[str] = Field("total_revenue", description="Field to sort by")
    sort_order: Optional[str] = Field("desc", description="Sort order (asc/desc)")
    page: int = Field(1, ge=1, description="Page number for pagination")
    per_page: int = Field(50, ge=1, le=1000, description="Items per page")

    @field_validator("export_format", mode="after")
    def validate_export_format(cls, v):
        if v and v not in ["pdf", "csv", "xlsx", "json"]:
            raise ValueError("export_format must be one of: pdf, csv, xlsx, json")
        return v

    @field_validator("sort_order", mode="after")
    def validate_sort_order(cls, v):
        if v and v not in ["asc", "desc"]:
            raise ValueError("sort_order must be either asc or desc")
        return v


class ReportExecutionResponse(BaseModel):
    """Response schema for report execution status"""

    execution_id: str  # UUID
    report_type: ReportType
    status: str

    # Execution details
    executed_by: int
    executed_at: datetime
    execution_time_ms: Optional[int] = None

    # Results
    total_records: Optional[int] = None
    file_path: Optional[str] = None
    file_format: Optional[str] = None
    file_size_bytes: Optional[int] = None

    # Error handling
    error_message: Optional[str] = None

    # Cache information
    cache_key: Optional[str] = None
    expires_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class DashboardMetricsResponse(BaseModel):
    """Response schema for dashboard metrics"""

    current_period: Dict[str, Any] = Field(description="Current period metrics")
    previous_period: Dict[str, Any] = Field(
        description="Previous period for comparison"
    )

    # Real-time metrics
    today_revenue: Decimal
    today_orders: int
    today_customers: int

    # Growth indicators
    revenue_growth_percentage: Decimal
    order_growth_percentage: Decimal
    customer_growth_percentage: Decimal

    # Top performers
    top_staff: List[Dict[str, Any]] = Field(description="Top performing staff")
    top_products: List[Dict[str, Any]] = Field(description="Top selling products")

    # Trends data for charts
    revenue_trend: List[Dict[str, Any]] = Field(description="Revenue trend data")
    order_trend: List[Dict[str, Any]] = Field(description="Order count trend data")

    # Alerts and notifications
    active_alerts: List[Dict[str, Any]] = Field(description="Active alert conditions")

    # Data freshness
    last_updated: datetime

    class Config:
        json_encoders = {Decimal: lambda v: float(v)}


class ReportTemplateRequest(BaseModel):
    """Request schema for creating/updating report templates"""

    name: str = Field(max_length=255, description="Template name")
    description: Optional[str] = Field(
        max_length=1000, description="Template description"
    )
    report_type: ReportType = Field(description="Type of report")

    # Configuration
    filters_config: Dict[str, Any] = Field(description="Default filter settings")
    columns_config: Optional[Dict[str, Any]] = Field(
        None, description="Column configuration"
    )
    sorting_config: Optional[Dict[str, Any]] = Field(
        None, description="Sorting preferences"
    )
    visualization_config: Optional[Dict[str, Any]] = Field(
        None, description="Chart settings"
    )

    # Access control
    is_public: bool = Field(False, description="Make template available to all users")


class ReportTemplateResponse(BaseModel):
    """Response schema for report templates"""

    id: int
    uuid: str
    name: str
    description: Optional[str]
    report_type: ReportType

    # Configuration
    filters_config: Dict[str, Any]
    columns_config: Optional[Dict[str, Any]]
    sorting_config: Optional[Dict[str, Any]]
    visualization_config: Optional[Dict[str, Any]]

    # Metadata
    created_by: int
    created_by_name: Optional[str] = None
    is_public: bool
    is_system_template: bool

    # Usage stats
    usage_count: int
    last_used_at: Optional[datetime]

    # Timestamps
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class PaginatedSalesResponse(BaseModel):
    """Paginated response for sales data"""

    items: List[
        Union[SalesDetailResponse, StaffPerformanceResponse, ProductPerformanceResponse]
    ]
    total: int
    page: int
    per_page: int
    total_pages: int
    has_next: bool
    has_prev: bool

    # Summary for the current page/filter
    page_summary: Optional[SalesSummaryResponse] = None


class SalesComparisonRequest(BaseModel):
    """Request schema for comparing sales across different periods or entities"""

    # Base period
    base_period_start: date
    base_period_end: date

    # Comparison period
    comparison_period_start: date
    comparison_period_end: date

    # What to compare
    compare_by: str = Field(description="Compare by: period, staff, product, category")
    entity_ids: Optional[List[int]] = Field(
        None, description="Specific entities to compare"
    )

    # Metrics to include
    metrics: List[str] = Field(
        default=["revenue", "orders", "customers"], description="Metrics to compare"
    )

    @field_validator("compare_by", mode="after")
    def validate_compare_by(cls, v):
        if v not in ["period", "staff", "product", "category"]:
            raise ValueError(
                "compare_by must be one of: period, staff, product, category"
            )
        return v


class SalesComparisonResponse(BaseModel):
    """Response schema for sales comparison data"""

    comparison_type: str
    base_period: Dict[str, Any]
    comparison_period: Dict[str, Any]

    # Comparison results
    differences: Dict[
        str, Dict[str, Any]
    ]  # Metric -> {absolute_change, percentage_change, etc.}
    trends: List[Dict[str, Any]]  # Trend data for visualization

    # Statistical significance
    significance_test: Optional[Dict[str, Any]] = None

    class Config:
        json_encoders = {Decimal: lambda v: float(v)}


class MenuPerformanceResponse(BaseModel):
    """Response schema for menu item performance analytics including profitability"""

    menu_item_id: int
    menu_item_name: Optional[str] = None
    category_id: Optional[int] = None
    category_name: Optional[str] = None

    # Sales performance metrics
    quantity_sold: int
    revenue_generated: Decimal
    average_price: Decimal
    order_frequency: int  # Number of orders containing this menu item

    # Cost & profitability metrics
    total_cost: Decimal
    profit: Decimal
    profit_margin: Optional[Decimal] = None  # Percentage

    # Rankings
    popularity_rank: Optional[int] = None
    revenue_rank: Optional[int] = None
    profit_rank: Optional[int] = None

    # Time period
    period_start: date
    period_end: date

    class Config:
        from_attributes = True
        json_encoders = {Decimal: lambda v: float(v)}
