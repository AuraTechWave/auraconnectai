# backend/modules/analytics/tests/test_ai_insights_integration.py

import pytest
from datetime import datetime, date, timedelta
from decimal import Decimal
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from core.database import Base
from modules.orders.models.order_models import Order, OrderItem
from modules.staff.models.staff_models import StaffMember
from modules.customers.models.customer_models import Customer
from modules.menu.models.menu_models import Product, Category

from ..services.ai_insights_service import AIInsightsService
from ..schemas.ai_insights_schemas import (
    InsightRequest, InsightType, ConfidenceLevel
)


class TestAIInsightsIntegration:
    """Integration tests for AI Insights with real database"""
    
    @pytest.fixture
    def test_db(self):
        """Create a test database session"""
        engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(bind=engine)
        
        SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
        db = SessionLocal()
        
        yield db
        
        db.close()
        Base.metadata.drop_all(bind=engine)
    
    @pytest.fixture
    def sample_data(self, test_db):
        """Create sample data for testing"""
        # Create staff
        staff1 = StaffMember(
            id=1,
            first_name="John",
            last_name="Doe",
            email="john@example.com",
            username="johndoe",
            hashed_password="hashed",
            role="manager",
            is_active=True
        )
        test_db.add(staff1)
        
        # Create customers
        customers = []
        for i in range(1, 11):
            customer = Customer(
                id=i,
                name=f"Customer {i}",
                email=f"customer{i}@example.com",
                phone=f"555-000{i}"
            )
            customers.append(customer)
            test_db.add(customer)
        
        # Create categories and products
        category = Category(
            id=1,
            name="Main Dishes",
            description="Main course items"
        )
        test_db.add(category)
        
        products = []
        for i in range(1, 6):
            product = Product(
                id=i,
                name=f"Product {i}",
                category_id=1,
                price=Decimal(str(10 + i * 2)),
                is_available=True
            )
            products.append(product)
            test_db.add(product)
        
        test_db.commit()
        
        # Create orders with various patterns
        orders = []
        
        # Create orders across different times and days
        base_date = datetime.now() - timedelta(days=30)
        
        for day in range(30):
            current_date = base_date + timedelta(days=day)
            
            # Morning orders (low activity)
            for hour in range(9, 11):
                if day % 3 == 0:  # Every 3rd day
                    order = Order(
                        customer_id=customers[day % 10].id,
                        staff_id=staff1.id,
                        order_date=current_date.replace(hour=hour),
                        status="completed",
                        total_amount=Decimal('25.00'),
                        tax_amount=Decimal('2.50'),
                        discount_amount=Decimal('0.00')
                    )
                    test_db.add(order)
                    test_db.flush()
                    
                    # Add order item
                    item = OrderItem(
                        order_id=order.id,
                        product_id=products[0].id,
                        product_name=products[0].name,
                        quantity=1,
                        unit_price=products[0].price,
                        total_price=products[0].price
                    )
                    test_db.add(item)
            
            # Lunch rush (high activity)
            for hour in range(12, 14):
                for _ in range(5):  # Multiple orders per hour
                    order = Order(
                        customer_id=customers[day % 10].id,
                        staff_id=staff1.id,
                        order_date=current_date.replace(hour=hour, minute=(day * 10) % 60),
                        status="completed",
                        total_amount=Decimal(str(30 + day % 20)),
                        tax_amount=Decimal('3.00'),
                        discount_amount=Decimal('0.00')
                    )
                    test_db.add(order)
                    test_db.flush()
                    
                    # Add trending products
                    trending_product = products[day % 5]
                    item = OrderItem(
                        order_id=order.id,
                        product_id=trending_product.id,
                        product_name=trending_product.name,
                        quantity=2,
                        unit_price=trending_product.price,
                        total_price=trending_product.price * 2
                    )
                    test_db.add(item)
            
            # Dinner rush (moderate to high activity)
            for hour in range(18, 20):
                for _ in range(3):  # Moderate orders
                    order = Order(
                        customer_id=customers[day % 10].id,
                        staff_id=staff1.id,
                        order_date=current_date.replace(hour=hour, minute=(day * 15) % 60),
                        status="completed",
                        total_amount=Decimal(str(40 + day % 30)),
                        tax_amount=Decimal('4.00'),
                        discount_amount=Decimal('0.00')
                    )
                    test_db.add(order)
                    test_db.flush()
                    
                    # Add items with patterns
                    if day < 15:
                        # First half of month - Product 1 popular
                        product = products[0]
                    else:
                        # Second half - Product 2 rising
                        product = products[1]
                    
                    item = OrderItem(
                        order_id=order.id,
                        product_id=product.id,
                        product_name=product.name,
                        quantity=1,
                        unit_price=product.price,
                        total_price=product.price
                    )
                    test_db.add(item)
        
        # Create an anomaly day (spike)
        anomaly_date = datetime.now() - timedelta(days=7)
        for _ in range(20):  # Unusually high number of orders
            order = Order(
                customer_id=customers[0].id,
                staff_id=staff1.id,
                order_date=anomaly_date.replace(hour=15),
                status="completed",
                total_amount=Decimal('100.00'),
                tax_amount=Decimal('10.00'),
                discount_amount=Decimal('0.00')
            )
            test_db.add(order)
        
        test_db.commit()
        
        return {
            "staff": staff1,
            "customers": customers,
            "products": products,
            "category": category
        }
    
    @pytest.mark.asyncio
    async def test_full_insight_generation(self, test_db, sample_data):
        """Test full insight generation with real data"""
        service = AIInsightsService(test_db)
        
        request = InsightRequest(
            insight_types=[
                InsightType.PEAK_TIME,
                InsightType.PRODUCT_TREND,
                InsightType.CUSTOMER_PATTERN,
                InsightType.ANOMALY
            ],
            date_from=datetime.now().date() - timedelta(days=30),
            date_to=datetime.now().date(),
            force_refresh=True
        )
        
        result = await service.generate_insights(request)
        
        # Verify peak times
        assert result.peak_times is not None
        assert result.peak_times.primary_peak is not None
        assert result.peak_times.primary_peak.hour in [12, 13]  # Lunch rush
        assert len(result.peak_times.recommendations) > 0
        
        # Verify product trends
        assert result.product_insights is not None
        assert len(result.product_insights.top_rising) > 0
        assert len(result.product_insights.recommendations) > 0
        
        # Verify customer patterns
        assert result.customer_insights is not None
        assert result.customer_insights.repeat_customer_rate > 0
        assert len(result.customer_insights.recommendations) > 0
        
        # Verify anomaly detection
        assert result.anomalies is not None
        assert len(result.anomalies) > 0  # Should detect the spike
        
        # Verify overall recommendations
        assert len(result.overall_recommendations) > 0
    
    @pytest.mark.asyncio
    async def test_time_range_filtering(self, test_db, sample_data):
        """Test insights with different time ranges"""
        service = AIInsightsService(test_db)
        
        # Test last 7 days
        request_7days = InsightRequest(
            insight_types=[InsightType.PEAK_TIME],
            date_from=datetime.now().date() - timedelta(days=7),
            date_to=datetime.now().date(),
            force_refresh=True
        )
        
        result_7days = await service.generate_insights(request_7days)
        
        # Test last 30 days
        request_30days = InsightRequest(
            insight_types=[InsightType.PEAK_TIME],
            date_from=datetime.now().date() - timedelta(days=30),
            date_to=datetime.now().date(),
            force_refresh=True
        )
        
        result_30days = await service.generate_insights(request_30days)
        
        # Both should have peak times detected
        assert result_7days.peak_times is not None
        assert result_30days.peak_times is not None
        
        # 30-day analysis should have higher confidence
        assert result_30days.peak_times.confidence.value >= result_7days.peak_times.confidence.value
    
    @pytest.mark.asyncio  
    async def test_product_trend_detection(self, test_db, sample_data):
        """Test product trend detection with changing patterns"""
        service = AIInsightsService(test_db)
        
        # Create additional orders to establish trends
        # Make Product 3 rising in recent days
        recent_date = datetime.now() - timedelta(days=3)
        
        for day in range(3):
            for _ in range(10):
                order = Order(
                    customer_id=sample_data["customers"][0].id,
                    staff_id=sample_data["staff"].id,
                    order_date=recent_date + timedelta(days=day),
                    status="completed",
                    total_amount=Decimal('50.00'),
                    tax_amount=Decimal('5.00'),
                    discount_amount=Decimal('0.00')
                )
                test_db.add(order)
                test_db.flush()
                
                # Add Product 3 heavily
                item = OrderItem(
                    order_id=order.id,
                    product_id=sample_data["products"][2].id,
                    product_name=sample_data["products"][2].name,
                    quantity=3,
                    unit_price=sample_data["products"][2].price,
                    total_price=sample_data["products"][2].price * 3
                )
                test_db.add(item)
        
        test_db.commit()
        
        request = InsightRequest(
            insight_types=[InsightType.PRODUCT_TREND],
            date_from=datetime.now().date() - timedelta(days=14),
            date_to=datetime.now().date(),
            force_refresh=True
        )
        
        result = await service.generate_insights(request)
        
        assert result.product_insights is not None
        assert len(result.product_insights.top_rising) > 0
        
        # Product 3 should be in rising trends
        rising_product_names = [p.product_name for p in result.product_insights.top_rising]
        assert "Product 3" in rising_product_names
    
    @pytest.mark.asyncio
    async def test_customer_retention_analysis(self, test_db, sample_data):
        """Test customer retention pattern detection"""
        service = AIInsightsService(test_db)
        
        # Create some repeat customers
        repeat_customer = sample_data["customers"][0]
        one_time_customer = sample_data["customers"][5]
        
        # Add multiple orders for repeat customer
        for day in range(5):
            order = Order(
                customer_id=repeat_customer.id,
                staff_id=sample_data["staff"].id,
                order_date=datetime.now() - timedelta(days=day * 5),
                status="completed",
                total_amount=Decimal('30.00'),
                tax_amount=Decimal('3.00'),
                discount_amount=Decimal('0.00')
            )
            test_db.add(order)
        
        # Add single order for one-time customer
        order = Order(
            customer_id=one_time_customer.id,
            staff_id=sample_data["staff"].id,
            order_date=datetime.now() - timedelta(days=20),
            status="completed",
            total_amount=Decimal('25.00'),
            tax_amount=Decimal('2.50'),
            discount_amount=Decimal('0.00')
        )
        test_db.add(order)
        
        test_db.commit()
        
        request = InsightRequest(
            insight_types=[InsightType.CUSTOMER_PATTERN],
            date_from=datetime.now().date() - timedelta(days=30),
            date_to=datetime.now().date(),
            force_refresh=True
        )
        
        result = await service.generate_insights(request)
        
        assert result.customer_insights is not None
        assert 0 < result.customer_insights.repeat_customer_rate < 1
        assert "one_time" in result.customer_insights.lifetime_value_trends
        assert len(result.customer_insights.recommendations) > 0
    
    @pytest.mark.asyncio
    async def test_weekly_pattern_analysis(self, test_db, sample_data):
        """Test weekly pattern detection in peak times"""
        service = AIInsightsService(test_db)
        
        # Add weekend-specific patterns
        weekend_dates = []
        current = datetime.now()
        
        # Find last 4 weekends
        for _ in range(30):
            if current.weekday() in [5, 6]:  # Saturday, Sunday
                weekend_dates.append(current)
            current -= timedelta(days=1)
        
        # Create higher activity on weekends
        for weekend_date in weekend_dates[:8]:  # Use last 4 weekends
            for hour in range(10, 22):  # All day activity
                for _ in range(3):
                    order = Order(
                        customer_id=sample_data["customers"][0].id,
                        staff_id=sample_data["staff"].id,
                        order_date=weekend_date.replace(hour=hour),
                        status="completed",
                        total_amount=Decimal('45.00'),
                        tax_amount=Decimal('4.50'),
                        discount_amount=Decimal('0.00')
                    )
                    test_db.add(order)
        
        test_db.commit()
        
        request = InsightRequest(
            insight_types=[InsightType.PEAK_TIME],
            date_from=datetime.now().date() - timedelta(days=30),
            date_to=datetime.now().date(),
            force_refresh=True
        )
        
        result = await service.generate_insights(request)
        
        assert result.peak_times is not None
        assert len(result.peak_times.weekly_pattern) > 0
        assert "Saturday" in result.peak_times.weekly_pattern
        assert "Sunday" in result.peak_times.weekly_pattern


# Performance tests
class TestAIInsightsPerformance:
    """Performance tests for AI Insights"""
    
    @pytest.mark.asyncio
    @pytest.mark.performance
    async def test_large_dataset_performance(self, test_db):
        """Test performance with large dataset"""
        import time
        
        # Create large dataset
        staff = StaffMember(
            id=1,
            first_name="Test",
            last_name="Staff",
            email="test@example.com",
            username="teststaff",
            hashed_password="hashed",
            role="staff",
            is_active=True
        )
        test_db.add(staff)
        
        # Create 1000 orders
        base_date = datetime.now() - timedelta(days=90)
        
        for i in range(1000):
            order = Order(
                customer_id=i % 100 + 1,
                staff_id=1,
                order_date=base_date + timedelta(hours=i),
                status="completed",
                total_amount=Decimal(str(20 + i % 50)),
                tax_amount=Decimal('2.00'),
                discount_amount=Decimal('0.00')
            )
            test_db.add(order)
        
        test_db.commit()
        
        service = AIInsightsService(test_db)
        
        request = InsightRequest(
            insight_types=[InsightType.PEAK_TIME, InsightType.ANOMALY],
            date_from=base_date.date(),
            date_to=datetime.now().date(),
            force_refresh=True
        )
        
        start_time = time.time()
        result = await service.generate_insights(request)
        end_time = time.time()
        
        processing_time = end_time - start_time
        
        # Should complete within reasonable time (5 seconds)
        assert processing_time < 5.0
        assert result.peak_times is not None
        assert isinstance(result.anomalies, list)