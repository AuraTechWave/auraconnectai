# backend/modules/ai_recommendations/tests/test_integration.py

import pytest
from datetime import datetime, date, timedelta
from decimal import Decimal
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from fastapi.testclient import TestClient

from core.database import Base
from core.menu_models import MenuItem, MenuCategory
from modules.orders.models.order_models import Order, OrderItem
from modules.staff.models.staff_models import StaffMember, Role
from modules.staff.models.shift_models import Shift

from ..services.pricing_recommendation_service import PricingRecommendationService
from ..services.staffing_recommendation_service import StaffingRecommendationService
from ..schemas.pricing_schemas import BulkPricingRequest, PricingStrategy
from ..schemas.staffing_schemas import StaffingOptimizationRequest


class TestAIRecommendationsIntegration:
    """Integration tests for AI recommendations with real database"""

    @pytest.fixture
    def test_db(self):
        """Create test database"""
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
        # Create categories
        category = MenuCategory(
            id=1, name="Main Dishes", description="Main course items", is_active=True
        )
        test_db.add(category)

        # Create menu items
        items = []
        for i in range(1, 6):
            item = MenuItem(
                id=i,
                name=f"Test Item {i}",
                price=10.00 + i * 2,
                category_id=1,
                is_active=True,
                is_available=True,
            )
            items.append(item)
            test_db.add(item)

        # Create roles
        roles = [
            Role(id=1, name="Manager"),
            Role(id=2, name="Chef"),
            Role(id=3, name="Server"),
            Role(id=4, name="Dishwasher"),
        ]
        for role in roles:
            test_db.add(role)

        # Create staff members
        staff = []
        for i, role in enumerate(roles, 1):
            member = StaffMember(
                id=i,
                name=f"Staff {i}",
                email=f"staff{i}@test.com",
                role_id=role.id,
                status="active",
            )
            staff.append(member)
            test_db.add(member)

        test_db.commit()

        # Create historical orders
        base_date = datetime.now() - timedelta(days=30)

        for day in range(30):
            current_date = base_date + timedelta(days=day)

            # Create 10-20 orders per day
            num_orders = 10 + (day % 10)

            for order_num in range(num_orders):
                order = Order(
                    customer_id=order_num % 5 + 1,
                    staff_id=staff[order_num % len(staff)].id,
                    order_date=current_date.replace(
                        hour=10 + (order_num % 12), minute=order_num % 60
                    ),
                    status="completed",
                    total_amount=Decimal(str(20 + order_num % 30)),
                    tax_amount=Decimal("2.00"),
                    discount_amount=Decimal("0.00"),
                )
                test_db.add(order)
                test_db.flush()

                # Add order items
                for item_idx in range(1, 3):
                    order_item = OrderItem(
                        order_id=order.id,
                        product_id=items[(order_num + item_idx) % len(items)].id,
                        product_name=items[(order_num + item_idx) % len(items)].name,
                        quantity=1 + (order_num % 3),
                        unit_price=items[(order_num + item_idx) % len(items)].price,
                        total_price=items[(order_num + item_idx) % len(items)].price
                        * (1 + (order_num % 3)),
                    )
                    test_db.add(order_item)

        test_db.commit()

        return {"category": category, "items": items, "roles": roles, "staff": staff}

    @pytest.mark.asyncio
    async def test_pricing_recommendations_with_real_data(self, test_db, sample_data):
        """Test pricing recommendations with real database data"""
        service = PricingRecommendationService(test_db)

        request = BulkPricingRequest(
            category_ids=[1],
            optimization_goal=PricingStrategy.DYNAMIC,
            max_price_increase_percent=15.0,
            max_price_decrease_percent=10.0,
            time_horizon_days=7,
        )

        result = await service.generate_bulk_recommendations(request)

        assert result is not None
        assert result.total_items_analyzed == 5  # 5 items in category
        assert len(result.recommendations) > 0

        # Check recommendation details
        for rec in result.recommendations:
            assert rec.menu_item_id in [item.id for item in sample_data["items"]]
            assert rec.confidence_score > 0
            assert rec.strategy_used in [
                PricingStrategy.DYNAMIC,
                PricingStrategy.COST_PLUS,
            ]
            assert len(rec.factors_considered) > 0
            assert rec.primary_reason != ""

    @pytest.mark.asyncio
    async def test_staffing_recommendations_with_real_data(self, test_db, sample_data):
        """Test staffing recommendations with real database data"""
        service = StaffingRecommendationService(test_db)

        request = StaffingOptimizationRequest(
            start_date=date.today(),
            end_date=date.today() + timedelta(days=6),
            service_level_target=0.90,
            buffer_percentage=10.0,
        )

        result = await service.generate_staffing_recommendations(request)

        assert result is not None
        assert result.period_start == request.start_date
        assert result.period_end == request.end_date
        assert len(result.daily_recommendations) == 7

        # Check daily recommendations
        for daily in result.daily_recommendations:
            assert daily.date >= request.start_date
            assert daily.date <= request.end_date
            assert len(daily.staff_requirements) > 0
            assert daily.estimated_labor_cost > 0
            assert 0 <= daily.labor_percentage <= 100

    @pytest.mark.asyncio
    async def test_pricing_impact_calculation(self, test_db, sample_data):
        """Test accurate pricing impact calculations"""
        service = PricingRecommendationService(test_db)

        # Get specific item
        item = sample_data["items"][0]

        request = BulkPricingRequest(
            menu_item_ids=[item.id],
            optimization_goal=PricingStrategy.DEMAND_BASED,
            time_horizon_days=7,
        )

        result = await service.generate_bulk_recommendations(request)

        if result.recommendations:
            rec = result.recommendations[0]

            # Verify impact calculations
            price_change = (
                (rec.recommended_price - rec.current_price) / rec.current_price * 100
            )
            assert abs(price_change - rec.price_change_percentage) < 0.1

            # Check bounds
            assert (
                rec.min_recommended_price
                <= rec.recommended_price
                <= rec.max_recommended_price
            )

    @pytest.mark.asyncio
    async def test_demand_forecast_accuracy(self, test_db, sample_data):
        """Test demand forecasting accuracy"""
        service = StaffingRecommendationService(test_db)

        # Generate forecast for tomorrow
        tomorrow = date.today() + timedelta(days=1)
        forecasts = await service._generate_demand_forecasts(tomorrow, tomorrow)

        assert tomorrow in forecasts
        assert len(forecasts[tomorrow]) == 24  # 24 hours

        # Check forecast reasonableness
        for forecast in forecasts[tomorrow]:
            assert forecast.predicted_orders >= 0
            assert forecast.predicted_revenue >= 0
            assert (
                forecast.orders_lower_bound
                <= forecast.predicted_orders
                <= forecast.orders_upper_bound
            )
            assert 0 <= forecast.confidence_level <= 1

    @pytest.mark.asyncio
    async def test_caching_behavior(self, test_db, sample_data):
        """Test that caching works correctly"""
        service = PricingRecommendationService(test_db)

        request = BulkPricingRequest(menu_item_ids=[1], time_horizon_days=7)

        # First call - should cache
        with patch("backend.core.cache.cache_service.get") as mock_get:
            with patch("backend.core.cache.cache_service.set") as mock_set:
                mock_get.return_value = None  # Cache miss

                result1 = await service.generate_bulk_recommendations(request)

                mock_get.assert_called_once()
                mock_set.assert_called_once()

        # Second call - should use cache
        with patch("backend.core.cache.cache_service.get") as mock_get:
            mock_get.return_value = result1.dict()  # Cache hit

            result2 = await service.generate_bulk_recommendations(request)

            mock_get.assert_called_once()
            assert result2.request_id == result1.request_id


class TestPerformanceAndScalability:
    """Test performance with larger datasets"""

    @pytest.mark.asyncio
    @pytest.mark.performance
    async def test_large_dataset_performance(self, test_db):
        """Test performance with many menu items"""
        import time

        # Create 100 menu items
        category = MenuCategory(id=1, name="Test", is_active=True)
        test_db.add(category)

        for i in range(100):
            item = MenuItem(
                id=i + 1,
                name=f"Item {i+1}",
                price=10.00 + (i % 20),
                category_id=1,
                is_active=True,
            )
            test_db.add(item)

        test_db.commit()

        service = PricingRecommendationService(test_db)

        request = BulkPricingRequest(category_ids=[1], time_horizon_days=7)

        start_time = time.time()
        result = await service.generate_bulk_recommendations(request)
        end_time = time.time()

        execution_time = end_time - start_time

        assert result.total_items_analyzed == 100
        assert execution_time < 5.0  # Should complete within 5 seconds

        print(
            f"Processed {result.total_items_analyzed} items in {execution_time:.2f} seconds"
        )
