# backend/modules/analytics/tests/test_edge_cases.py

import pytest
from datetime import datetime, date, timedelta
from decimal import Decimal
import asyncio
from sqlalchemy.orm import Session

from modules.analytics.services.sales_report_service import SalesReportService
from modules.analytics.services.export_service import ExportService
from modules.analytics.services.trend_service import TrendService
from modules.analytics.schemas.analytics_schemas import (
    SalesFilterRequest, SalesReportRequest
)
from modules.orders.models.order_models import Order, OrderItem
from modules.staff.models.staff_models import StaffMember
from modules.analytics.models.analytics_models import SalesAnalyticsSnapshot


class TestLargeDatasets:
    """Test cases for handling large datasets efficiently"""
    
    @pytest.fixture
    def large_dataset(self, db_session: Session):
        """Create a large dataset for testing"""
        # Create 100 staff members
        staff_members = []
        for i in range(100):
            staff = StaffMember(
                name=f"Staff {i}",
                email=f"staff{i}@test.com",
                role="server",
                is_active=True
            )
            db_session.add(staff)
            staff_members.append(staff)
        
        db_session.flush()
        
        # Create 10,000 orders over the last 30 days
        base_date = datetime.now().date() - timedelta(days=30)
        orders = []
        
        for day in range(30):
            current_date = base_date + timedelta(days=day)
            # Create 333 orders per day
            for order_num in range(333):
                staff = staff_members[order_num % 100]  # Distribute among staff
                
                order = Order(
                    order_date=current_date,
                    staff_id=staff.id,
                    total_amount=Decimal(f"{50 + (order_num % 100)}.99"),
                    status="completed",
                    customer_id=f"customer_{order_num % 1000}"
                )
                db_session.add(order)
                
                # Add 1-5 items per order
                for item_num in range(1, (order_num % 5) + 2):
                    item = OrderItem(
                        order=order,
                        product_id=item_num,
                        product_name=f"Product {item_num}",
                        quantity=1,
                        unit_price=Decimal(f"{10 + item_num}.99"),
                        total_price=Decimal(f"{10 + item_num}.99")
                    )
                    db_session.add(item)
                
                orders.append(order)
        
        db_session.commit()
        return {"staff": staff_members, "orders": orders}
    
    def test_large_dataset_performance(self, db_session: Session, large_dataset):
        """Test performance with large datasets"""
        service = SalesReportService(db_session)
        
        # Test summary generation
        start_time = datetime.now()
        filters = SalesFilterRequest(
            date_from=datetime.now().date() - timedelta(days=30),
            date_to=datetime.now().date()
        )
        summary = service.generate_sales_summary(filters)
        duration = (datetime.now() - start_time).total_seconds()
        
        # Should complete within 5 seconds even with 10k orders
        assert duration < 5.0
        assert summary.total_orders == 9990  # 333 * 30 days
        assert summary.unique_customers == 1000
    
    def test_top_performers_with_large_dataset(self, db_session: Session, large_dataset):
        """Test top performers calculation with large dataset"""
        service = SalesReportService(db_session)
        
        filters = SalesFilterRequest(
            date_from=datetime.now().date() - timedelta(days=30),
            date_to=datetime.now().date()
        )
        
        # Get top 10 performers
        start_time = datetime.now()
        performers = service.generate_staff_performance_report(
            filters, page=1, per_page=10
        )
        duration = (datetime.now() - start_time).total_seconds()
        
        # Should complete within 3 seconds
        assert duration < 3.0
        assert len(performers) == 10
        
        # Verify rankings are correct
        for i in range(len(performers) - 1):
            assert performers[i].total_revenue_generated >= performers[i+1].total_revenue_generated
    
    def test_pagination_with_large_dataset(self, db_session: Session, large_dataset):
        """Test pagination with large dataset"""
        service = SalesReportService(db_session)
        
        filters = SalesFilterRequest(
            date_from=datetime.now().date() - timedelta(days=30),
            date_to=datetime.now().date()
        )
        
        # Test different page sizes
        for page_size in [10, 50, 100, 500]:
            result = service.generate_detailed_sales_report(
                filters, page=1, per_page=page_size
            )
            
            assert len(result.items) <= page_size
            assert result.total_items == 9990
            assert result.total_pages == (9990 + page_size - 1) // page_size


class TestExportEndpoints:
    """Test cases for export functionality"""
    
    @pytest.fixture
    def sample_report_data(self, db_session: Session):
        """Create sample data for export tests"""
        # Create staff
        staff = StaffMember(
            name="Test Staff",
            email="test@example.com",
            role="server",
            is_active=True
        )
        db_session.add(staff)
        db_session.flush()
        
        # Create orders
        for i in range(10):
            order = Order(
                order_date=datetime.now().date(),
                staff_id=staff.id,
                total_amount=Decimal("100.00"),
                status="completed",
                customer_id=f"customer_{i}"
            )
            db_session.add(order)
        
        db_session.commit()
        return staff
    
    @pytest.mark.asyncio
    async def test_csv_export(self, db_session: Session, sample_report_data):
        """Test CSV export functionality"""
        export_service = ExportService(db_session)
        
        request = SalesReportRequest(
            report_type="sales_summary",
            filters=SalesFilterRequest(
                date_from=datetime.now().date() - timedelta(days=7),
                date_to=datetime.now().date()
            ),
            export_format="csv"
        )
        
        response = await export_service.export_sales_report(
            request=request,
            format_type="csv",
            executed_by=sample_report_data.id
        )
        
        assert response.status_code == 200
        assert response.media_type == "text/csv"
        assert "attachment" in response.headers.get("Content-Disposition", "")
    
    @pytest.mark.asyncio
    async def test_pdf_export(self, db_session: Session, sample_report_data):
        """Test PDF export functionality"""
        export_service = ExportService(db_session)
        
        request = SalesReportRequest(
            report_type="sales_summary",
            filters=SalesFilterRequest(
                date_from=datetime.now().date() - timedelta(days=7),
                date_to=datetime.now().date()
            ),
            export_format="pdf"
        )
        
        try:
            response = await export_service.export_sales_report(
                request=request,
                format_type="pdf",
                executed_by=sample_report_data.id
            )
            
            assert response.status_code == 200
            assert response.media_type == "application/pdf"
        except ImportError:
            # Skip if ReportLab not installed
            pytest.skip("ReportLab not available")
    
    @pytest.mark.asyncio
    async def test_excel_export(self, db_session: Session, sample_report_data):
        """Test Excel export functionality"""
        export_service = ExportService(db_session)
        
        request = SalesReportRequest(
            report_type="staff_performance",
            filters=SalesFilterRequest(
                date_from=datetime.now().date() - timedelta(days=30),
                date_to=datetime.now().date()
            ),
            export_format="xlsx"
        )
        
        try:
            response = await export_service.export_sales_report(
                request=request,
                format_type="xlsx",
                executed_by=sample_report_data.id
            )
            
            assert response.status_code == 200
            assert response.media_type == "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        except ImportError:
            # Skip if OpenPyXL not installed
            pytest.skip("OpenPyXL not available")


class TestTrendEndpoints:
    """Test cases for trend endpoints with different granularities"""
    
    @pytest.fixture
    def trend_data(self, db_session: Session):
        """Create data for trend testing"""
        # Create staff
        staff = StaffMember(
            name="Trend Test Staff",
            email="trend@test.com",
            role="server",
            is_active=True
        )
        db_session.add(staff)
        db_session.flush()
        
        # Create hourly snapshots for today
        today = datetime.now().date()
        for hour in range(24):
            snapshot = SalesAnalyticsSnapshot(
                snapshot_date=today,
                period_type="hourly",
                hour=hour,
                staff_id=staff.id,
                total_revenue=Decimal(f"{100 + hour * 10}"),
                total_orders=10 + hour,
                unique_customers=5 + hour // 2,
                average_order_value=Decimal("10.00")
            )
            db_session.add(snapshot)
        
        # Create daily snapshots for last 30 days
        for day in range(30):
            snapshot_date = today - timedelta(days=day)
            snapshot = SalesAnalyticsSnapshot(
                snapshot_date=snapshot_date,
                period_type="daily",
                staff_id=staff.id,
                total_revenue=Decimal(f"{1000 + day * 50}"),
                total_orders=100 + day * 5,
                unique_customers=50 + day * 2,
                average_order_value=Decimal("10.00")
            )
            db_session.add(snapshot)
        
        db_session.commit()
        return staff
    
    def test_hourly_trend(self, db_session: Session, trend_data):
        """Test hourly trend calculation"""
        trend_service = TrendService(db_session)
        
        today = datetime.now().date()
        trend_points = trend_service.get_revenue_trend(
            start_date=today,
            end_date=today,
            granularity="hourly"
        )
        
        assert len(trend_points) == 24
        
        # Verify trend is calculated correctly
        for i, point in enumerate(trend_points):
            expected_revenue = 100 + i * 10
            assert float(point.value) == expected_revenue
    
    def test_daily_trend(self, db_session: Session, trend_data):
        """Test daily trend calculation"""
        trend_service = TrendService(db_session)
        
        end_date = datetime.now().date()
        start_date = end_date - timedelta(days=7)
        
        trend_points = trend_service.get_revenue_trend(
            start_date=start_date,
            end_date=end_date,
            granularity="daily"
        )
        
        assert len(trend_points) == 8  # 7 days + today
        
        # Verify trend values
        for point in trend_points:
            assert point.value > 0
            if point.previous_value:
                assert point.change_percentage is not None
    
    def test_weekly_trend(self, db_session: Session, trend_data):
        """Test weekly trend calculation"""
        trend_service = TrendService(db_session)
        
        end_date = datetime.now().date()
        start_date = end_date - timedelta(days=28)
        
        trend_points = trend_service.get_revenue_trend(
            start_date=start_date,
            end_date=end_date,
            granularity="weekly"
        )
        
        assert len(trend_points) == 5  # 4 full weeks + current week
        
        # Each week should aggregate the daily values
        for point in trend_points:
            assert point.value > 0
    
    def test_trend_with_filters(self, db_session: Session, trend_data):
        """Test trend calculation with staff filters"""
        trend_service = TrendService(db_session)
        
        end_date = datetime.now().date()
        start_date = end_date - timedelta(days=7)
        
        # With staff filter
        trend_points = trend_service.get_order_trend(
            start_date=start_date,
            end_date=end_date,
            granularity="daily",
            staff_ids=[trend_data.id]
        )
        
        assert len(trend_points) > 0
        
        # Without staff filter (should return empty if no other staff)
        trend_points_no_filter = trend_service.get_order_trend(
            start_date=start_date,
            end_date=end_date,
            granularity="daily",
            staff_ids=[999999]  # Non-existent staff
        )
        
        assert len(trend_points_no_filter) == 0