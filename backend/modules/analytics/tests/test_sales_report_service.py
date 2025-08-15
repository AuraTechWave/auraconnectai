# backend/modules/analytics/tests/test_sales_report_service.py

import pytest
from datetime import datetime, date, timedelta
from decimal import Decimal
from unittest.mock import Mock, patch

from modules.analytics.services.sales_report_service import (
    SalesReportService,
    SalesCalculationResult,
)
from modules.analytics.schemas.analytics_schemas import (
    SalesFilterRequest,
    AggregationPeriod,
)


class TestSalesReportService:
    """Test cases for SalesReportService"""

    def test_service_initialization(self, db_session):
        """Test service initialization"""
        service = SalesReportService(db_session)
        assert service.db == db_session

    def test_generate_sales_summary_basic(
        self, db_session, sample_orders, sample_sales_filter
    ):
        """Test basic sales summary generation"""
        service = SalesReportService(db_session)

        summary = service.generate_sales_summary(sample_sales_filter)

        assert summary is not None
        assert summary.total_orders >= 0
        assert summary.total_revenue >= 0
        assert summary.average_order_value >= 0
        assert summary.period_start == sample_sales_filter.date_from
        assert summary.period_end == sample_sales_filter.date_to
        assert summary.period_type == sample_sales_filter.period_type

    def test_generate_sales_summary_with_growth(self, db_session, sample_orders):
        """Test sales summary with growth calculation"""
        service = SalesReportService(db_session)

        # Test with specific date range for growth calculation
        filters = SalesFilterRequest(
            date_from=date.today() - timedelta(days=3),
            date_to=date.today(),
            period_type=AggregationPeriod.DAILY,
        )

        summary = service.generate_sales_summary(filters)

        assert summary is not None
        # Growth might be None if comparison data is not available
        assert summary.revenue_growth is None or isinstance(
            summary.revenue_growth, Decimal
        )
        assert summary.order_growth is None or isinstance(summary.order_growth, Decimal)

    def test_generate_detailed_sales_report(
        self, db_session, sample_sales_snapshots, sample_sales_filter
    ):
        """Test detailed sales report generation"""
        service = SalesReportService(db_session)

        report = service.generate_detailed_sales_report(
            sample_sales_filter, page=1, per_page=10
        )

        assert report is not None
        assert report.page == 1
        assert report.per_page == 10
        assert len(report.items) <= 10
        assert report.total >= 0
        assert isinstance(report.has_next, bool)
        assert isinstance(report.has_prev, bool)

    def test_generate_detailed_sales_report_pagination(
        self, db_session, sample_sales_snapshots, sample_sales_filter
    ):
        """Test pagination in detailed sales report"""
        service = SalesReportService(db_session)

        # First page
        page1 = service.generate_detailed_sales_report(
            sample_sales_filter, page=1, per_page=5
        )

        # Second page
        page2 = service.generate_detailed_sales_report(
            sample_sales_filter, page=2, per_page=5
        )

        assert page1.page == 1
        assert page2.page == 2
        assert page1.has_prev == False
        assert page2.has_prev == True

        # Ensure different data on different pages (if enough data exists)
        if page1.total > 5:
            assert page1.items != page2.items

    def test_generate_detailed_sales_report_sorting(
        self, db_session, sample_sales_snapshots, sample_sales_filter
    ):
        """Test sorting in detailed sales report"""
        service = SalesReportService(db_session)

        # Sort by revenue descending
        report_desc = service.generate_detailed_sales_report(
            sample_sales_filter, sort_by="total_revenue", sort_order="desc"
        )

        # Sort by revenue ascending
        report_asc = service.generate_detailed_sales_report(
            sample_sales_filter, sort_by="total_revenue", sort_order="asc"
        )

        assert report_desc is not None
        assert report_asc is not None

        # If there are multiple items, check sorting
        if len(report_desc.items) > 1:
            assert (
                report_desc.items[0].total_revenue >= report_desc.items[1].total_revenue
            )

        if len(report_asc.items) > 1:
            assert (
                report_asc.items[0].total_revenue <= report_asc.items[1].total_revenue
            )

    def test_generate_staff_performance_report(
        self, db_session, sample_sales_snapshots, sample_sales_filter
    ):
        """Test staff performance report generation"""
        service = SalesReportService(db_session)

        performance = service.generate_staff_performance_report(
            sample_sales_filter, page=1, per_page=10
        )

        assert isinstance(performance, list)

        # Check structure if data exists
        if performance:
            staff_perf = performance[0]
            assert hasattr(staff_perf, "staff_id")
            assert hasattr(staff_perf, "staff_name")
            assert hasattr(staff_perf, "total_orders_handled")
            assert hasattr(staff_perf, "total_revenue_generated")
            assert hasattr(staff_perf, "average_order_value")
            assert hasattr(staff_perf, "period_start")
            assert hasattr(staff_perf, "period_end")

    def test_generate_product_performance_report(
        self, db_session, sample_orders, sample_sales_filter
    ):
        """Test product performance report generation"""
        service = SalesReportService(db_session)

        performance = service.generate_product_performance_report(
            sample_sales_filter, page=1, per_page=10
        )

        assert isinstance(performance, list)

        # Check structure if data exists
        if performance:
            product_perf = performance[0]
            assert hasattr(product_perf, "product_id")
            assert hasattr(product_perf, "quantity_sold")
            assert hasattr(product_perf, "revenue_generated")
            assert hasattr(product_perf, "average_price")
            assert hasattr(product_perf, "order_frequency")
            assert hasattr(product_perf, "period_start")
            assert hasattr(product_perf, "period_end")

    def test_get_dashboard_metrics(self, db_session, sample_orders):
        """Test dashboard metrics retrieval"""
        service = SalesReportService(db_session)

        metrics = service.get_dashboard_metrics()

        assert metrics is not None
        assert hasattr(metrics, "today_revenue")
        assert hasattr(metrics, "today_orders")
        assert hasattr(metrics, "today_customers")
        assert hasattr(metrics, "revenue_growth_percentage")
        assert hasattr(metrics, "order_growth_percentage")
        assert hasattr(metrics, "customer_growth_percentage")
        assert hasattr(metrics, "top_staff")
        assert hasattr(metrics, "top_products")
        assert hasattr(metrics, "revenue_trend")
        assert hasattr(metrics, "order_trend")
        assert hasattr(metrics, "last_updated")

        assert isinstance(metrics.top_staff, list)
        assert isinstance(metrics.top_products, list)
        assert isinstance(metrics.revenue_trend, list)
        assert isinstance(metrics.order_trend, list)

    def test_calculate_sales_metrics(self, db_session, sample_orders):
        """Test internal sales metrics calculation"""
        service = SalesReportService(db_session)

        filters = SalesFilterRequest(
            date_from=date.today() - timedelta(days=7), date_to=date.today()
        )

        result = service._calculate_sales_metrics(filters)

        assert isinstance(result, SalesCalculationResult)
        assert result.total_orders >= 0
        assert result.total_revenue >= 0
        assert result.total_items_sold >= 0
        assert result.average_order_value >= 0
        assert result.total_discounts >= 0
        assert result.total_tax >= 0
        assert result.net_revenue >= 0
        assert result.unique_customers >= 0

    def test_apply_order_filters_date_range(self, db_session, sample_orders):
        """Test date range filtering"""
        service = SalesReportService(db_session)

        from modules.orders.models.order_models import Order, OrderItem

        base_query = db_session.query(Order).join(OrderItem)

        filters = SalesFilterRequest(
            date_from=date.today() - timedelta(days=3),
            date_to=date.today() - timedelta(days=1),
        )

        filtered_query = service._apply_order_filters(base_query, filters)
        orders = filtered_query.all()

        # All returned orders should be within the date range
        for order in orders:
            assert order.created_at.date() >= filters.date_from
            assert order.created_at.date() <= filters.date_to + timedelta(days=1)

    def test_apply_order_filters_staff(
        self, db_session, sample_orders, sample_staff_member
    ):
        """Test staff filtering"""
        service = SalesReportService(db_session)

        from modules.orders.models.order_models import Order, OrderItem

        base_query = db_session.query(Order).join(OrderItem)

        filters = SalesFilterRequest(staff_ids=[sample_staff_member.id])

        filtered_query = service._apply_order_filters(base_query, filters)
        orders = filtered_query.all()

        # All returned orders should belong to the specified staff
        for order in orders:
            assert order.staff_id == sample_staff_member.id

    def test_apply_order_filters_order_value(self, db_session, sample_orders):
        """Test order value filtering"""
        service = SalesReportService(db_session)

        from modules.orders.models.order_models import Order, OrderItem

        base_query = db_session.query(Order).join(OrderItem)

        filters = SalesFilterRequest(
            min_order_value=Decimal("20.00"), max_order_value=Decimal("50.00")
        )

        filtered_query = service._apply_order_filters(base_query, filters)
        orders = filtered_query.all()

        # All returned orders should be within the value range
        for order in orders:
            assert order.total_amount >= filters.min_order_value
            assert order.total_amount <= filters.max_order_value

    def test_calculate_growth_percentage(self, db_session):
        """Test growth percentage calculation"""
        service = SalesReportService(db_session)

        # Test normal growth
        growth = service._calculate_growth_percentage(110, 100)
        assert growth == Decimal("10")

        # Test negative growth
        growth = service._calculate_growth_percentage(90, 100)
        assert growth == Decimal("-10")

        # Test zero previous value
        growth = service._calculate_growth_percentage(100, 0)
        assert growth == Decimal("0")

        # Test None previous value
        growth = service._calculate_growth_percentage(100, None)
        assert growth == Decimal("0")

    def test_format_period_data(self, db_session):
        """Test period data formatting"""
        service = SalesReportService(db_session)

        calc_result = SalesCalculationResult(
            total_orders=100,
            total_revenue=Decimal("1500.50"),
            total_items_sold=250,
            average_order_value=Decimal("15.01"),
            total_discounts=Decimal("50.00"),
            total_tax=Decimal("120.04"),
            net_revenue=Decimal("1450.50"),
            unique_customers=75,
        )

        formatted = service._format_period_data(calc_result)

        assert formatted["total_orders"] == 100
        assert formatted["total_revenue"] == 1500.50
        assert formatted["total_items_sold"] == 250
        assert formatted["average_order_value"] == 15.01
        assert formatted["unique_customers"] == 75

    def test_error_handling_invalid_filters(self, db_session):
        """Test error handling for invalid filters"""
        service = SalesReportService(db_session)

        # Test with invalid date range
        invalid_filters = SalesFilterRequest(
            date_from=date.today(),
            date_to=date.today() - timedelta(days=1),  # End before start
        )

        # The service should handle this gracefully
        try:
            summary = service.generate_sales_summary(invalid_filters)
            # If it doesn't raise an error, that's also acceptable
            assert summary is not None
        except ValueError:
            # If it raises a validation error, that's expected
            pass

    def test_trends_data_structure(self, db_session, sample_orders):
        """Test trends data structure"""
        service = SalesReportService(db_session)

        current_date = date.today()
        revenue_trend, order_trend = service._get_trend_data(current_date)

        assert isinstance(revenue_trend, list)
        assert isinstance(order_trend, list)
        assert len(revenue_trend) == 30  # 30 days of data
        assert len(order_trend) == 30

        # Check structure of trend data points
        if revenue_trend:
            trend_point = revenue_trend[0]
            assert "date" in trend_point
            assert "value" in trend_point
            assert isinstance(trend_point["value"], float)

        if order_trend:
            trend_point = order_trend[0]
            assert "date" in trend_point
            assert "value" in trend_point
            assert isinstance(trend_point["value"], int)


class TestSalesCalculationResult:
    """Test the SalesCalculationResult dataclass"""

    def test_initialization(self):
        """Test SalesCalculationResult initialization"""
        result = SalesCalculationResult(
            total_orders=100,
            total_revenue=Decimal("1500.00"),
            total_items_sold=250,
            average_order_value=Decimal("15.00"),
            total_discounts=Decimal("50.00"),
            total_tax=Decimal("120.00"),
            net_revenue=Decimal("1450.00"),
            unique_customers=75,
        )

        assert result.total_orders == 100
        assert result.total_revenue == Decimal("1500.00")
        assert result.total_items_sold == 250
        assert result.average_order_value == Decimal("15.00")
        assert result.total_discounts == Decimal("50.00")
        assert result.total_tax == Decimal("120.00")
        assert result.net_revenue == Decimal("1450.00")
        assert result.unique_customers == 75
        assert result.new_customers == 0  # Default value
        assert result.returning_customers == 0  # Default value

    def test_with_customer_breakdown(self):
        """Test SalesCalculationResult with customer breakdown"""
        result = SalesCalculationResult(
            total_orders=100,
            total_revenue=Decimal("1500.00"),
            total_items_sold=250,
            average_order_value=Decimal("15.00"),
            total_discounts=Decimal("50.00"),
            total_tax=Decimal("120.00"),
            net_revenue=Decimal("1450.00"),
            unique_customers=75,
            new_customers=25,
            returning_customers=50,
        )

        assert result.new_customers == 25
        assert result.returning_customers == 50
        assert (
            result.new_customers + result.returning_customers == result.unique_customers
        )
