# backend/modules/analytics/tests/conftest.py

import pytest
from datetime import datetime, date, timedelta
from decimal import Decimal
from sqlalchemy.orm import Session
from fastapi.testclient import TestClient

from backend.modules.analytics.models.analytics_models import (
    SalesAnalyticsSnapshot, ReportTemplate, ReportExecution, 
    SalesMetric, AggregationPeriod, ReportType
)
from backend.modules.analytics.schemas.analytics_schemas import SalesFilterRequest
from backend.modules.orders.models.order_models import Order, OrderItem, Category
from backend.modules.staff.models.staff_models import StaffMember, Role
from backend.modules.customers.models.customer_models import Customer


@pytest.fixture
def sample_staff_member(db_session: Session):
    """Create a sample staff member for testing"""
    role = Role(name="Server", permissions="basic")
    db_session.add(role)
    db_session.flush()
    
    staff = StaffMember(
        name="John Doe",
        email="john.doe@example.com",
        phone="555-1234",
        role_id=role.id,
        start_date=datetime.now()
    )
    db_session.add(staff)
    db_session.commit()
    return staff


@pytest.fixture
def sample_customer(db_session: Session):
    """Create a sample customer for testing"""
    customer = Customer(
        name="Jane Smith",
        email="jane.smith@example.com",
        phone="555-5678",
        is_active=True
    )
    db_session.add(customer)
    db_session.commit()
    return customer


@pytest.fixture
def sample_category(db_session: Session):
    """Create a sample category for testing"""
    category = Category(
        name="Beverages",
        description="Hot and cold beverages"
    )
    db_session.add(category)
    db_session.commit()
    return category


@pytest.fixture
def sample_orders(db_session: Session, sample_staff_member, sample_customer, sample_category):
    """Create sample orders for testing"""
    orders = []
    
    # Create orders over the last 7 days
    base_date = datetime.now() - timedelta(days=7)
    
    for i in range(10):
        order_date = base_date + timedelta(days=i % 7, hours=i % 12)
        
        order = Order(
            staff_id=sample_staff_member.id,
            customer_id=sample_customer.id,
            category_id=sample_category.id,
            table_no=i % 5 + 1,
            status="completed",
            customer_notes=f"Order {i}",
            subtotal=Decimal(f"{20.00 + i * 5}"),
            discount_amount=Decimal(f"{i * 0.5}"),
            tax_amount=Decimal(f"{(20.00 + i * 5) * 0.08}"),
            total_amount=Decimal(f"{(20.00 + i * 5) * 1.08 - i * 0.5}"),
            final_amount=Decimal(f"{(20.00 + i * 5) * 1.08 - i * 0.5}"),
            created_at=order_date,
            updated_at=order_date
        )
        
        db_session.add(order)
        db_session.flush()
        
        # Add order items
        for j in range(2):  # 2 items per order
            item = OrderItem(
                order_id=order.id,
                menu_item_id=100 + j,  # Mock menu item IDs
                quantity=1 + j % 2,
                price=Decimal(f"{10.00 + j * 2.5}"),
                notes=f"Item {j} for order {i}"
            )
            db_session.add(item)
        
        orders.append(order)
    
    db_session.commit()
    return orders


@pytest.fixture
def sample_sales_snapshots(db_session: Session, sample_staff_member, sample_category):
    """Create sample sales analytics snapshots"""
    snapshots = []
    base_date = date.today() - timedelta(days=30)
    
    for i in range(30):
        snapshot_date = base_date + timedelta(days=i)
        
        snapshot = SalesAnalyticsSnapshot(
            snapshot_date=snapshot_date,
            period_type=AggregationPeriod.DAILY,
            staff_id=sample_staff_member.id,
            category_id=sample_category.id,
            total_orders=10 + i % 5,
            total_revenue=Decimal(f"{500.00 + i * 25}"),
            total_items_sold=20 + i % 10,
            average_order_value=Decimal(f"{45.00 + i}"),
            total_discounts=Decimal(f"{i * 2.5}"),
            total_tax=Decimal(f"{(500.00 + i * 25) * 0.08}"),
            net_revenue=Decimal(f"{(500.00 + i * 25) * 0.92 - i * 2.5}"),
            unique_customers=8 + i % 3,
            new_customers=1 + i % 2,
            returning_customers=7 + i % 2,
            orders_handled=10 + i % 5,
            average_processing_time=Decimal(f"{15.5 + i * 0.1}"),
            calculated_at=datetime.now()
        )
        
        db_session.add(snapshot)
        snapshots.append(snapshot)
    
    db_session.commit()
    return snapshots


@pytest.fixture
def sample_report_template(db_session: Session, sample_staff_member):
    """Create a sample report template"""
    template = ReportTemplate(
        name="Weekly Sales Report",
        description="Standard weekly sales performance report",
        report_type=ReportType.SALES_SUMMARY,
        filters_config={
            "period_type": "weekly",
            "include_staff": True,
            "include_categories": True
        },
        columns_config={
            "columns": ["date", "revenue", "orders", "avg_order_value"]
        },
        sorting_config={
            "sort_by": "date",
            "sort_order": "desc"
        },
        created_by=sample_staff_member.id,
        is_public=True,
        usage_count=5,
        last_used_at=datetime.now() - timedelta(days=1)
    )
    
    db_session.add(template)
    db_session.commit()
    return template


@pytest.fixture
def sample_report_execution(db_session: Session, sample_report_template, sample_staff_member):
    """Create a sample report execution"""
    execution = ReportExecution(
        template_id=sample_report_template.id,
        report_type=ReportType.SALES_SUMMARY,
        executed_by=sample_staff_member.id,
        parameters={
            "date_from": "2024-01-01",
            "date_to": "2024-01-07",
            "staff_ids": [sample_staff_member.id]
        },
        execution_time_ms=1250,
        total_records=150,
        file_path="/tmp/reports/weekly_sales_20240107.pdf",
        file_format="pdf",
        file_size_bytes=245760,
        status="completed",
        cache_key="sales_summary_20240107",
        expires_at=datetime.now() + timedelta(hours=6)
    )
    
    db_session.add(execution)
    db_session.commit()
    return execution


@pytest.fixture
def sample_sales_metrics(db_session: Session):
    """Create sample sales metrics for testing"""
    metrics = []
    base_date = date.today()
    
    metric_configs = [
        ("daily_revenue", "sales", "currency"),
        ("daily_orders", "sales", "count"),
        ("hourly_revenue", "sales", "currency"),
        ("customer_count", "customers", "count"),
        ("avg_order_value", "sales", "currency")
    ]
    
    for metric_name, category, unit in metric_configs:
        for i in range(7):  # Last 7 days
            metric_date = base_date - timedelta(days=i)
            
            metric = SalesMetric(
                metric_name=metric_name,
                metric_category=category,
                metric_date=metric_date,
                metric_hour=12 if "hourly" in metric_name else None,
                entity_type="global",
                value_numeric=Decimal(f"{100 + i * 10}"),
                value_integer=100 + i * 10 if unit == "count" else None,
                previous_value=Decimal(f"{95 + i * 9}"),
                change_percentage=Decimal("5.26"),
                unit=unit,
                tags={"source": "test", "period": "daily"}
            )
            
            db_session.add(metric)
            metrics.append(metric)
    
    db_session.commit()
    return metrics


@pytest.fixture
def sample_sales_filter():
    """Create a sample sales filter request"""
    return SalesFilterRequest(
        date_from=date.today() - timedelta(days=7),
        date_to=date.today(),
        period_type=AggregationPeriod.DAILY,
        include_discounts=True,
        include_tax=True,
        only_completed_orders=True
    )


@pytest.fixture
def sample_sales_filter_with_entities(sample_staff_member, sample_category):
    """Create a sales filter with specific entity filters"""
    return SalesFilterRequest(
        date_from=date.today() - timedelta(days=30),
        date_to=date.today(),
        staff_ids=[sample_staff_member.id],
        category_ids=[sample_category.id],
        period_type=AggregationPeriod.DAILY,
        include_discounts=True,
        include_tax=True,
        only_completed_orders=True,
        min_order_value=Decimal("10.00"),
        max_order_value=Decimal("1000.00")
    )


@pytest.fixture
def auth_headers_staff():
    """Create authentication headers for staff user"""
    return {
        "Authorization": "Bearer staff_token_123",
        "Content-Type": "application/json"
    }


@pytest.fixture
def mock_staff_user(sample_staff_member):
    """Mock staff user for authentication"""
    return {
        "id": sample_staff_member.id,
        "name": sample_staff_member.name,
        "email": sample_staff_member.email,
        "role": "staff"
    }