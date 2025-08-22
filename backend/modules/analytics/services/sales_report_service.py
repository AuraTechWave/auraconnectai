# backend/modules/analytics/services/sales_report_service.py

import logging
from typing import Dict, List, Optional, Any, Tuple, Union
from datetime import datetime, date, timedelta
from decimal import Decimal
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_, func, desc, asc, text, case
from dataclasses import dataclass

from core.tenant_context import (
    TenantContext,
    apply_tenant_filter,
    validate_tenant_access,
    CrossTenantAccessLogger,
)

from ..models.analytics_models import (
    SalesAnalyticsSnapshot,
    ReportTemplate,
    ReportExecution,
    SalesMetric,
    AggregationPeriod,
    ReportType,
)
from ..schemas.analytics_schemas import (
    SalesFilterRequest,
    SalesSummaryResponse,
    SalesDetailResponse,
    StaffPerformanceResponse,
    ProductPerformanceResponse,
    PaginatedSalesResponse,
    SalesReportRequest,
    ReportExecutionResponse,
    DashboardMetricsResponse,
)
from modules.orders.models.order_models import Order, OrderItem
from modules.staff.models.staff_models import StaffMember
from .optimized_queries import OptimizedAnalyticsQueries
from ..utils.query_monitor import monitor_query_performance
from ..utils.cache_manager import cached_query

# Custom exceptions replaced with standard Python exceptions

logger = logging.getLogger(__name__)


@dataclass
class SalesCalculationResult:
    """Result container for sales calculations"""

    total_orders: int
    total_revenue: Decimal
    total_items_sold: int
    average_order_value: Decimal
    total_discounts: Decimal
    total_tax: Decimal
    net_revenue: Decimal
    unique_customers: int
    new_customers: int = 0
    returning_customers: int = 0


class SalesReportService:
    """Service for generating sales reports and analytics with tenant isolation"""

    def __init__(self, db: Session):
        self.db = db
        self.access_logger = CrossTenantAccessLogger(db)

    @monitor_query_performance("sales_report.generate_summary")
    def generate_sales_summary(
        self, filters: SalesFilterRequest
    ) -> SalesSummaryResponse:
        """Generate a comprehensive sales summary report with tenant isolation"""

        # Ensure tenant context is established
        TenantContext.require_context()

        try:
            # Get current period data
            current_data = self._calculate_sales_metrics(filters)

            # Get comparison period data for growth calculation
            comparison_data = None
            if filters.date_from and filters.date_to:
                comparison_filters = self._create_comparison_filters(filters)
                if comparison_filters:
                    comparison_data = self._calculate_sales_metrics(comparison_filters)

            # Calculate growth metrics
            revenue_growth = None
            order_growth = None
            if comparison_data:
                if comparison_data.total_revenue > 0:
                    revenue_growth = (
                        (current_data.total_revenue - comparison_data.total_revenue)
                        / comparison_data.total_revenue
                        * 100
                    )
                if comparison_data.total_orders > 0:
                    order_growth = (
                        (current_data.total_orders - comparison_data.total_orders)
                        / comparison_data.total_orders
                        * 100
                    )

            # Calculate customer retention rate
            customer_retention_rate = None
            if current_data.unique_customers > 0:
                customer_retention_rate = (
                    current_data.returning_customers
                    / current_data.unique_customers
                    * 100
                )

            return SalesSummaryResponse(
                period_start=filters.date_from
                or (datetime.now().date() - timedelta(days=30)),
                period_end=filters.date_to or datetime.now().date(),
                period_type=filters.period_type,
                total_orders=current_data.total_orders,
                total_revenue=current_data.total_revenue,
                total_items_sold=current_data.total_items_sold,
                average_order_value=current_data.average_order_value,
                gross_revenue=current_data.total_revenue + current_data.total_discounts,
                total_discounts=current_data.total_discounts,
                total_tax=current_data.total_tax,
                net_revenue=current_data.net_revenue,
                unique_customers=current_data.unique_customers,
                new_customers=current_data.new_customers,
                returning_customers=current_data.returning_customers,
                customer_retention_rate=customer_retention_rate,
                revenue_growth=revenue_growth,
                order_growth=order_growth,
            )

        except Exception as e:
            logger.error(f"Error generating sales summary: {e}")
            raise

    def generate_detailed_sales_report(
        self,
        filters: SalesFilterRequest,
        page: int = 1,
        per_page: int = 50,
        sort_by: str = "total_revenue",
        sort_order: str = "desc",
    ) -> PaginatedSalesResponse:
        """Generate detailed sales report with pagination"""

        try:
            # Build base query for snapshots
            query = self._build_snapshots_query(filters)

            # Apply sorting
            query = self._apply_sorting(query, sort_by, sort_order)

            # Get total count
            total = query.count()

            # Apply pagination
            offset = (page - 1) * per_page
            snapshots = query.offset(offset).limit(per_page).all()

            # Convert to response objects
            items = [self._format_sales_detail(snapshot) for snapshot in snapshots]

            # Calculate page summary
            page_summary = None
            if items:
                page_summary = self._calculate_page_summary(items, filters)

            return PaginatedSalesResponse(
                items=items,
                total=total,
                page=page,
                per_page=per_page,
                total_pages=(total + per_page - 1) // per_page,
                has_next=page * per_page < total,
                has_prev=page > 1,
                page_summary=page_summary,
            )

        except Exception as e:
            logger.error(f"Error generating detailed sales report: {e}")
            raise

    def generate_staff_performance_report(
        self, filters: SalesFilterRequest, page: int = 1, per_page: int = 50
    ) -> List[StaffPerformanceResponse]:
        """Generate staff performance analytics using optimized queries"""

        try:
            # Get date range for the query
            start_date = filters.date_from or (datetime.now().date() - timedelta(days=30))
            end_date = filters.date_to or datetime.now().date()

            # Use optimized query that combines staff metrics with shift hours
            results = OptimizedAnalyticsQueries.get_staff_performance_with_shifts(
                self.db,
                start_date,
                end_date,
                filters.staff_ids,
            )

            # Apply pagination
            offset = (page - 1) * per_page
            paginated_results = results[offset : offset + per_page]

            staff_performance = []
            for result in paginated_results:
                # Calculate additional metrics
                orders_per_hour = None
                if result.total_hours and result.total_hours > 0:
                    orders_per_hour = result.orders_handled / float(result.total_hours)

                staff_performance.append(
                    StaffPerformanceResponse(
                        staff_id=result.staff_id,
                        staff_name=result.staff_name,
                        total_orders_handled=result.orders_handled or 0,
                        total_revenue_generated=result.total_revenue or Decimal("0"),
                        average_order_value=result.average_order_value or Decimal("0"),
                        orders_per_hour=orders_per_hour,
                        average_processing_time=result.average_processing_time,
                        revenue_rank=result.revenue_rank,
                        order_count_rank=result.order_count_rank,
                        period_start=start_date,
                        period_end=end_date,
                    )
                )

            return staff_performance

        except Exception as e:
            logger.error(f"Error generating staff performance report: {e}")
            raise

    def generate_product_performance_report(
        self, filters: SalesFilterRequest, page: int = 1, per_page: int = 50
    ) -> List[ProductPerformanceResponse]:
        """Generate product performance analytics using optimized queries"""

        try:
            # Use optimized query that eliminates N+1 patterns
            results = OptimizedAnalyticsQueries.get_product_performance_with_categories(
                self.db, filters, page, per_page
            )

            # Calculate total revenue for market share calculations
            total_revenue = self._get_total_revenue(filters)
            total_quantity = self._get_total_quantity(filters)

            product_performance = []
            for result in results:
                # Calculate market share
                revenue_share = None
                quantity_share = None
                if total_revenue > 0:
                    revenue_share = result.revenue_generated / total_revenue * 100
                if total_quantity > 0:
                    quantity_share = result.quantity_sold / total_quantity * 100

                product_performance.append(
                    ProductPerformanceResponse(
                        product_id=result.product_id,
                        product_name=result.product_name,
                        category_id=result.category_id,
                        category_name=result.category_name,
                        quantity_sold=result.quantity_sold or 0,
                        revenue_generated=result.revenue_generated or Decimal("0"),
                        average_price=result.average_price or Decimal("0"),
                        order_frequency=result.order_frequency or 0,
                        popularity_rank=result.popularity_rank,
                        revenue_rank=result.revenue_rank,
                        revenue_share=revenue_share,
                        quantity_share=quantity_share,
                        period_start=filters.date_from
                        or (datetime.now().date() - timedelta(days=30)),
                        period_end=filters.date_to or datetime.now().date(),
                    )
                )

            return product_performance

        except Exception as e:
            logger.error(f"Error generating product performance report: {e}")
            raise

    def get_dashboard_metrics(
        self, current_date: Optional[date] = None
    ) -> DashboardMetricsResponse:
        """Get real-time dashboard metrics"""

        try:
            if not current_date:
                current_date = datetime.now().date()

            # Define periods
            yesterday = current_date - timedelta(days=1)
            week_ago = current_date - timedelta(days=7)

            # Get today's metrics
            today_filters = SalesFilterRequest(
                date_from=current_date, date_to=current_date
            )
            today_data = self._calculate_sales_metrics(today_filters)

            # Get yesterday's metrics for comparison
            yesterday_filters = SalesFilterRequest(
                date_from=yesterday, date_to=yesterday
            )
            yesterday_data = self._calculate_sales_metrics(yesterday_filters)

            # Calculate growth percentages
            revenue_growth = self._calculate_growth_percentage(
                today_data.total_revenue, yesterday_data.total_revenue
            )
            order_growth = self._calculate_growth_percentage(
                today_data.total_orders, yesterday_data.total_orders
            )
            customer_growth = self._calculate_growth_percentage(
                today_data.unique_customers, yesterday_data.unique_customers
            )

            # Get top performers (last 7 days)
            week_filters = SalesFilterRequest(date_from=week_ago, date_to=current_date)
            top_staff = self.generate_staff_performance_report(week_filters, per_page=5)
            top_products = self.generate_product_performance_report(
                week_filters, per_page=5
            )

            # Get trend data (last 30 days)
            revenue_trend, order_trend = self._get_trend_data(current_date)

            # Get active alerts (placeholder - would integrate with AlertRule model)
            active_alerts = []

            return DashboardMetricsResponse(
                current_period=self._format_period_data(today_data),
                previous_period=self._format_period_data(yesterday_data),
                today_revenue=today_data.total_revenue,
                today_orders=today_data.total_orders,
                today_customers=today_data.unique_customers,
                revenue_growth_percentage=revenue_growth,
                order_growth_percentage=order_growth,
                customer_growth_percentage=customer_growth,
                top_staff=[self._format_staff_summary(staff) for staff in top_staff],
                top_products=[
                    self._format_product_summary(product) for product in top_products
                ],
                revenue_trend=revenue_trend,
                order_trend=order_trend,
                active_alerts=active_alerts,
                last_updated=datetime.now(),
            )

        except Exception as e:
            logger.error(f"Error getting dashboard metrics: {e}")
            raise

    # Private helper methods

    @monitor_query_performance("sales_report.calculate_metrics")
    @cached_query("sales_metrics", ttl=600, key_params=["filters"])
    def _calculate_sales_metrics(
        self, filters: SalesFilterRequest
    ) -> SalesCalculationResult:
        """Calculate core sales metrics from orders data with tenant isolation"""

        # Build base query from orders
        query = self.db.query(Order).join(OrderItem)

        # Apply all filters including tenant filtering (done once in _apply_order_filters)
        query = self._apply_order_filters(query, filters)

        # Calculate aggregated metrics
        metrics_query = query.with_entities(
            func.count(func.distinct(Order.id)).label("total_orders"),
            func.coalesce(func.sum(Order.total_amount), 0).label("total_revenue"),
            func.coalesce(func.sum(OrderItem.quantity), 0).label("total_items_sold"),
            func.coalesce(func.avg(Order.total_amount), 0).label("average_order_value"),
            func.coalesce(func.sum(Order.discount_amount), 0).label("total_discounts"),
            func.coalesce(func.sum(Order.tax_amount), 0).label("total_tax"),
            func.count(func.distinct(Order.customer_id)).label("unique_customers"),
        ).first()

        # Calculate net revenue
        net_revenue = (metrics_query.total_revenue or 0) - (
            metrics_query.total_discounts or 0
        )

        # Calculate new vs returning customers (simplified logic)
        new_customers = 0
        returning_customers = metrics_query.unique_customers or 0

        return SalesCalculationResult(
            total_orders=metrics_query.total_orders or 0,
            total_revenue=Decimal(str(metrics_query.total_revenue or 0)),
            total_items_sold=metrics_query.total_items_sold or 0,
            average_order_value=Decimal(str(metrics_query.average_order_value or 0)),
            total_discounts=Decimal(str(metrics_query.total_discounts or 0)),
            total_tax=Decimal(str(metrics_query.total_tax or 0)),
            net_revenue=Decimal(str(net_revenue)),
            unique_customers=metrics_query.unique_customers or 0,
            new_customers=new_customers,
            returning_customers=returning_customers,
        )

    def _apply_order_filters(
        self, query, filters: SalesFilterRequest, skip_tenant_filter: bool = False
    ):
        """Apply filters to order query with tenant validation

        Args:
            query: The SQLAlchemy query to filter
            filters: The filter request parameters
            skip_tenant_filter: If True, skip tenant filtering (use when already applied)
        """

        # Apply tenant filtering first (only if not already applied)
        if not skip_tenant_filter:
            query = apply_tenant_filter(query, Order)

        # Date range filters
        if filters.date_from:
            query = query.filter(Order.created_at >= filters.date_from)
        if filters.date_to:
            query = query.filter(
                Order.created_at <= filters.date_to + timedelta(days=1)
            )

        # Staff filters with tenant validation
        if filters.staff_ids:
            # Validate staff IDs belong to current tenant
            staff_query = self.db.query(StaffMember.id)
            staff_query = apply_tenant_filter(staff_query, StaffMember)
            valid_staff_ids = [
                s[0]
                for s in staff_query.filter(StaffMember.id.in_(filters.staff_ids)).all()
            ]
            if valid_staff_ids:
                query = query.filter(Order.staff_id.in_(valid_staff_ids))
            else:
                # Return empty result if no valid staff IDs
                query = query.filter(False)

        # Product filters
        if filters.product_ids:
            query = query.filter(OrderItem.menu_item_id.in_(filters.product_ids))

        # Category filters
        if filters.category_ids:
            query = query.filter(Order.category_id.in_(filters.category_ids))

        # Customer filters with tenant validation
        if filters.customer_ids:
            # Validate customer IDs belong to current tenant
            from modules.customers.models.customer_models import Customer

            customer_query = self.db.query(Customer.id)
            customer_query = apply_tenant_filter(customer_query, Customer)
            valid_customer_ids = [
                c[0]
                for c in customer_query.filter(
                    Customer.id.in_(filters.customer_ids)
                ).all()
            ]
            if valid_customer_ids:
                query = query.filter(Order.customer_id.in_(valid_customer_ids))
            else:
                # Return empty result if no valid customer IDs
                query = query.filter(False)

        # Order value filters
        if filters.min_order_value:
            query = query.filter(Order.total_amount >= filters.min_order_value)
        if filters.max_order_value:
            query = query.filter(Order.total_amount <= filters.max_order_value)

        # Only completed orders
        if filters.only_completed_orders:
            query = query.filter(Order.status == "completed")

        return query

    def _build_snapshots_query(self, filters: SalesFilterRequest):
        """Build query for sales analytics snapshots with tenant filtering"""

        query = self.db.query(SalesAnalyticsSnapshot)

        # Apply tenant filtering first
        query = apply_tenant_filter(query, SalesAnalyticsSnapshot)

        # Apply filters
        if filters.date_from:
            query = query.filter(
                SalesAnalyticsSnapshot.snapshot_date >= filters.date_from
            )
        if filters.date_to:
            query = query.filter(
                SalesAnalyticsSnapshot.snapshot_date <= filters.date_to
            )

        if filters.staff_ids:
            query = query.filter(SalesAnalyticsSnapshot.staff_id.in_(filters.staff_ids))

        if filters.product_ids:
            query = query.filter(
                SalesAnalyticsSnapshot.product_id.in_(filters.product_ids)
            )

        if filters.category_ids:
            query = query.filter(
                SalesAnalyticsSnapshot.category_id.in_(filters.category_ids)
            )

        return query

    def _build_staff_performance_query(self, filters: SalesFilterRequest):
        """Build staff performance query with rankings and tenant isolation"""

        # Subquery for staff metrics with tenant filtering
        staff_metrics_query = self.db.query(
            SalesAnalyticsSnapshot.staff_id,
            func.sum(SalesAnalyticsSnapshot.total_orders).label("orders_handled"),
            func.sum(SalesAnalyticsSnapshot.total_revenue).label("total_revenue"),
            func.avg(SalesAnalyticsSnapshot.average_order_value).label(
                "average_order_value"
            ),
            func.avg(SalesAnalyticsSnapshot.average_processing_time).label(
                "average_processing_time"
            ),
        )

        # Apply tenant filtering to the subquery
        staff_metrics_query = apply_tenant_filter(
            staff_metrics_query, SalesAnalyticsSnapshot
        )

        staff_metrics = staff_metrics_query.filter(
            SalesAnalyticsSnapshot.staff_id.isnot(None)
        )

        # Apply date filters
        if filters.date_from:
            staff_metrics = staff_metrics.filter(
                SalesAnalyticsSnapshot.snapshot_date >= filters.date_from
            )
        if filters.date_to:
            staff_metrics = staff_metrics.filter(
                SalesAnalyticsSnapshot.snapshot_date <= filters.date_to
            )

        staff_metrics = staff_metrics.group_by(
            SalesAnalyticsSnapshot.staff_id
        ).subquery()

        # Main query with rankings and tenant-filtered staff
        query = self.db.query(
            staff_metrics.c.staff_id,
            StaffMember.name.label("staff_name"),
            staff_metrics.c.orders_handled,
            staff_metrics.c.total_revenue,
            staff_metrics.c.average_order_value,
            staff_metrics.c.average_processing_time,
            func.rank()
            .over(order_by=desc(staff_metrics.c.total_revenue))
            .label("revenue_rank"),
            func.rank()
            .over(order_by=desc(staff_metrics.c.orders_handled))
            .label("order_count_rank"),
            text("NULL as total_hours"),  # Placeholder for hours calculation
        ).join(StaffMember, staff_metrics.c.staff_id == StaffMember.id)

        # Apply tenant filtering to staff members
        query = apply_tenant_filter(query, StaffMember)
        query = query.order_by(desc(staff_metrics.c.total_revenue))

        return query

    def _build_product_performance_query(self, filters: SalesFilterRequest):
        """Build product performance query with tenant isolation"""

        # Product metrics from order items with tenant-filtered orders
        product_metrics_query = self.db.query(
            OrderItem.menu_item_id.label("product_id"),
            func.sum(OrderItem.quantity).label("quantity_sold"),
            func.sum(OrderItem.price * OrderItem.quantity).label("revenue_generated"),
            func.avg(OrderItem.price).label("average_price"),
            func.count(func.distinct(OrderItem.order_id)).label("order_frequency"),
        ).join(Order)

        # Apply tenant filtering to orders
        product_metrics_query = apply_tenant_filter(product_metrics_query, Order)
        product_metrics = product_metrics_query

        # Apply filters through Order join
        if filters.date_from:
            product_metrics = product_metrics.filter(
                Order.created_at >= filters.date_from
            )
        if filters.date_to:
            product_metrics = product_metrics.filter(
                Order.created_at <= filters.date_to + timedelta(days=1)
            )

        if filters.staff_ids:
            # Validate staff IDs belong to current tenant
            staff_query = self.db.query(StaffMember.id)
            staff_query = apply_tenant_filter(staff_query, StaffMember)
            valid_staff_ids = [
                s[0]
                for s in staff_query.filter(StaffMember.id.in_(filters.staff_ids)).all()
            ]
            if valid_staff_ids:
                product_metrics = product_metrics.filter(
                    Order.staff_id.in_(valid_staff_ids)
                )
            else:
                # Log potential cross-tenant access attempt
                context = TenantContext.get()
                if context:
                    for staff_id in filters.staff_ids:
                        self.access_logger.log_access_attempt(
                            requested_tenant_id=context.get("restaurant_id"),
                            actual_tenant_id=None,  # Unknown
                            resource_type="StaffMember",
                            resource_id=staff_id,
                            action="filter",
                            success=False,
                        )

        if filters.product_ids:
            product_metrics = product_metrics.filter(
                OrderItem.menu_item_id.in_(filters.product_ids)
            )

        product_metrics = product_metrics.group_by(OrderItem.menu_item_id).subquery()

        # Main query with rankings (simplified without menu table join)
        query = self.db.query(
            product_metrics.c.product_id,
            text("'Product ' || product_metrics.product_id").label("product_name"),
            text("NULL::integer").label("category_id"),
            text("NULL").label("category_name"),
            product_metrics.c.quantity_sold,
            product_metrics.c.revenue_generated,
            product_metrics.c.average_price,
            product_metrics.c.order_frequency,
            func.rank()
            .over(order_by=desc(product_metrics.c.quantity_sold))
            .label("popularity_rank"),
            func.rank()
            .over(order_by=desc(product_metrics.c.revenue_generated))
            .label("revenue_rank"),
        ).order_by(desc(product_metrics.c.revenue_generated))

        return query

    def _apply_sorting(self, query, sort_by: str, sort_order: str):
        """Apply sorting to query"""

        sort_column = None
        if hasattr(SalesAnalyticsSnapshot, sort_by):
            sort_column = getattr(SalesAnalyticsSnapshot, sort_by)

        if sort_column is not None:
            if sort_order.lower() == "desc":
                query = query.order_by(desc(sort_column))
            else:
                query = query.order_by(asc(sort_column))

        return query

    def _format_sales_detail(
        self, snapshot: SalesAnalyticsSnapshot
    ) -> SalesDetailResponse:
        """Format snapshot data for detailed response"""

        return SalesDetailResponse(
            id=snapshot.id,
            snapshot_date=snapshot.snapshot_date,
            period_type=snapshot.period_type,
            staff_id=snapshot.staff_id,
            staff_name=snapshot.staff_member.name if snapshot.staff_member else None,
            product_id=snapshot.product_id,
            category_id=snapshot.category_id,
            category_name=snapshot.category.name if snapshot.category else None,
            total_orders=snapshot.total_orders,
            total_revenue=snapshot.total_revenue,
            total_items_sold=snapshot.total_items_sold,
            average_order_value=snapshot.average_order_value,
            total_discounts=snapshot.total_discounts,
            total_tax=snapshot.total_tax,
            net_revenue=snapshot.net_revenue,
            unique_customers=snapshot.unique_customers,
            orders_handled=snapshot.orders_handled,
            average_processing_time=snapshot.average_processing_time,
            product_quantity_sold=snapshot.product_quantity_sold,
            product_revenue=snapshot.product_revenue,
            product_popularity_rank=snapshot.product_popularity_rank,
            calculated_at=snapshot.calculated_at,
        )

    def _create_comparison_filters(
        self, filters: SalesFilterRequest
    ) -> Optional[SalesFilterRequest]:
        """Create filters for comparison period"""

        if not filters.date_from or not filters.date_to:
            return None

        # Calculate period length
        period_length = (filters.date_to - filters.date_from).days

        # Create comparison period (same length, immediately before)
        comparison_end = filters.date_from - timedelta(days=1)
        comparison_start = comparison_end - timedelta(days=period_length)

        comparison_filters = filters.copy()
        comparison_filters.date_from = comparison_start
        comparison_filters.date_to = comparison_end

        return comparison_filters

    def _calculate_growth_percentage(
        self, current: Union[int, Decimal], previous: Union[int, Decimal]
    ) -> Decimal:
        """Calculate growth percentage between two values"""

        if previous is None or previous == 0:
            return Decimal("0")

        current = Decimal(str(current))
        previous = Decimal(str(previous))

        return ((current - previous) / previous) * 100

    def _get_total_revenue(self, filters: SalesFilterRequest) -> Decimal:
        """Get total revenue for market share calculations with tenant isolation"""

        query = self.db.query(func.coalesce(func.sum(Order.total_amount), 0)).join(
            OrderItem
        )
        # Apply all filters including tenant (done once in _apply_order_filters)
        query = self._apply_order_filters(query, filters)

        return Decimal(str(query.scalar() or 0))

    def _get_total_quantity(self, filters: SalesFilterRequest) -> int:
        """Get total quantity sold for market share calculations with tenant isolation"""

        query = self.db.query(func.coalesce(func.sum(OrderItem.quantity), 0)).join(
            Order
        )
        # Apply all filters including tenant (done once in _apply_order_filters)
        query = self._apply_order_filters(query, filters)

        return query.scalar() or 0

    def _calculate_page_summary(
        self, items: List[SalesDetailResponse], filters: SalesFilterRequest
    ) -> SalesSummaryResponse:
        """Calculate summary for current page of results"""

        total_orders = sum(item.total_orders for item in items)
        total_revenue = sum(item.total_revenue for item in items)
        total_items_sold = sum(item.total_items_sold for item in items)

        average_order_value = (
            total_revenue / total_orders if total_orders > 0 else Decimal("0")
        )

        return SalesSummaryResponse(
            period_start=filters.date_from
            or (datetime.now().date() - timedelta(days=30)),
            period_end=filters.date_to or datetime.now().date(),
            period_type=filters.period_type,
            total_orders=total_orders,
            total_revenue=total_revenue,
            total_items_sold=total_items_sold,
            average_order_value=average_order_value,
            gross_revenue=total_revenue,  # Simplified for page summary
            total_discounts=sum(item.total_discounts for item in items),
            total_tax=sum(item.total_tax for item in items),
            net_revenue=sum(item.net_revenue for item in items),
            unique_customers=sum(item.unique_customers for item in items),
            new_customers=0,  # Not available at page level
            returning_customers=0,  # Not available at page level
        )

    def _format_period_data(self, data: SalesCalculationResult) -> Dict[str, Any]:
        """Format sales calculation result for API response"""

        return {
            "total_orders": data.total_orders,
            "total_revenue": float(data.total_revenue),
            "total_items_sold": data.total_items_sold,
            "average_order_value": float(data.average_order_value),
            "unique_customers": data.unique_customers,
        }

    def _format_staff_summary(self, staff: StaffPerformanceResponse) -> Dict[str, Any]:
        """Format staff performance for dashboard"""

        return {
            "staff_id": staff.staff_id,
            "staff_name": staff.staff_name,
            "total_revenue": float(staff.total_revenue_generated),
            "total_orders": staff.total_orders_handled,
            "revenue_rank": staff.revenue_rank,
        }

    def _format_product_summary(
        self, product: ProductPerformanceResponse
    ) -> Dict[str, Any]:
        """Format product performance for dashboard"""

        return {
            "product_id": product.product_id,
            "product_name": product.product_name,
            "quantity_sold": product.quantity_sold,
            "revenue_generated": float(product.revenue_generated),
            "popularity_rank": product.popularity_rank,
        }

    def _get_trend_data(
        self, current_date: date
    ) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
        """Get trend data for the last 30 days"""

        start_date = current_date - timedelta(days=30)

        # Daily revenue trend
        revenue_trend = []
        order_trend = []

        for i in range(30):
            trend_date = start_date + timedelta(days=i)

            # Get data for this date
            filters = SalesFilterRequest(date_from=trend_date, date_to=trend_date)
            day_data = self._calculate_sales_metrics(filters)

            revenue_trend.append(
                {"date": trend_date.isoformat(), "value": float(day_data.total_revenue)}
            )

            order_trend.append(
                {"date": trend_date.isoformat(), "value": day_data.total_orders}
            )

        return revenue_trend, order_trend
