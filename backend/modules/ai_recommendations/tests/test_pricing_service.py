# backend/modules/ai_recommendations/tests/test_pricing_service.py

import pytest
from datetime import datetime, date, timedelta
from decimal import Decimal
from unittest.mock import Mock, patch, AsyncMock
from sqlalchemy.orm import Session

from core.menu_models import MenuItem, MenuCategory
from modules.orders.models.order_models import Order, OrderItem

from ..schemas.pricing_schemas import (
    BulkPricingRequest,
    PricingStrategy,
    PriceOptimizationGoal,
    DemandLevel,
    PriceElasticity,
    MenuItemPricingContext,
)
from ..services.pricing_recommendation_service import (
    PricingRecommendationService,
    create_pricing_recommendation_service,
)


class TestPricingRecommendationService:
    """Test suite for pricing recommendation service"""

    @pytest.fixture
    def mock_db(self):
        """Create mock database session"""
        return Mock(spec=Session)

    @pytest.fixture
    def service(self, mock_db):
        """Create service instance"""
        return PricingRecommendationService(mock_db)

    @pytest.fixture
    def sample_menu_item(self):
        """Create sample menu item"""
        item = Mock(spec=MenuItem)
        item.id = 1
        item.name = "Test Item"
        item.price = 10.99
        item.category_id = 1
        item.is_active = True
        item.deleted_at = None
        return item

    @pytest.fixture
    def sample_request(self):
        """Create sample pricing request"""
        return BulkPricingRequest(
            menu_item_ids=[1, 2, 3],
            optimization_goal=PriceOptimizationGoal.MAXIMIZE_PROFIT,
            strategies_to_use=[PricingStrategy.DYNAMIC, PricingStrategy.DEMAND_BASED],
            max_price_increase_percent=20.0,
            max_price_decrease_percent=15.0,
            time_horizon_days=7,
        )

    @pytest.mark.asyncio
    async def test_generate_bulk_recommendations(
        self, service, mock_db, sample_request, sample_menu_item
    ):
        """Test bulk recommendation generation"""
        # Mock menu items query
        mock_query = Mock()
        mock_query.filter.return_value = mock_query
        mock_query.all.return_value = [sample_menu_item]
        mock_db.query.return_value = mock_query

        # Mock insights service
        with patch.object(service, "_get_market_insights") as mock_insights:
            mock_insights.return_value = {"peak_times": None, "product_trends": None}

            # Mock pricing context
            with patch.object(service, "_build_pricing_context") as mock_context:
                mock_context.return_value = MenuItemPricingContext(
                    menu_item_id=1,
                    current_price=Decimal("10.99"),
                    base_cost=Decimal("3.50"),
                    avg_daily_sales=25.0,
                    sales_trend=0.1,
                    inventory_level=75.0,
                    current_demand=DemandLevel.NORMAL,
                    price_elasticity=PriceElasticity.UNIT_ELASTIC,
                )

                # Mock cache
                with patch("backend.core.cache.cache_service.get") as mock_cache_get:
                    mock_cache_get.return_value = None

                    with patch(
                        "backend.core.cache.cache_service.set"
                    ) as mock_cache_set:
                        result = await service.generate_bulk_recommendations(
                            sample_request
                        )

                        assert result is not None
                        assert result.total_items_analyzed == 1
                        assert len(result.recommendations) >= 0
                        mock_cache_set.assert_called_once()

    def test_calculate_sales_trend(self, service, mock_db):
        """Test sales trend calculation"""
        # Mock recent sales
        mock_db.query.return_value.join.return_value.filter.return_value.scalar.side_effect = [
            50,
            40,
        ]

        trend = service._calculate_sales_trend(1)

        assert trend == 0.25  # (50-40)/40 = 0.25
        assert -1.0 <= trend <= 1.0

    def test_assess_demand_level(self, service):
        """Test demand level assessment"""
        # Test various scenarios
        assert service._assess_demand_level(25, 0.6, {}) == DemandLevel.VERY_HIGH
        assert service._assess_demand_level(18, 0.3, {}) == DemandLevel.HIGH
        assert service._assess_demand_level(12, 0.0, {}) == DemandLevel.NORMAL
        assert service._assess_demand_level(4, -0.3, {}) == DemandLevel.VERY_LOW
        assert service._assess_demand_level(8, -0.1, {}) == DemandLevel.LOW

    def test_estimate_price_elasticity(self, service):
        """Test price elasticity estimation"""
        # Low price item
        low_price_item = Mock(price=8.99)
        assert (
            service._estimate_price_elasticity(low_price_item, Mock())
            == PriceElasticity.ELASTIC
        )

        # High price item
        high_price_item = Mock(price=35.99)
        assert (
            service._estimate_price_elasticity(high_price_item, Mock())
            == PriceElasticity.INELASTIC
        )

        # Medium price item
        medium_price_item = Mock(price=18.99)
        assert (
            service._estimate_price_elasticity(medium_price_item, Mock())
            == PriceElasticity.UNIT_ELASTIC
        )

    def test_demand_based_pricing(self, service):
        """Test demand-based pricing calculation"""
        context = MenuItemPricingContext(
            menu_item_id=1,
            current_price=Decimal("20.00"),
            base_cost=Decimal("6.00"),
            avg_daily_sales=30.0,
            sales_trend=0.5,
            inventory_level=50.0,
            current_demand=DemandLevel.HIGH,
            price_elasticity=PriceElasticity.INELASTIC,
        )

        price, reasoning = service._demand_based_pricing(context)

        assert price == Decimal("21.60")  # 20.00 * 1.08
        assert "High demand" in reasoning["primary"]
        assert len(reasoning["details"]) > 0

    def test_cost_plus_pricing(self, service):
        """Test cost-plus pricing calculation"""
        context = MenuItemPricingContext(
            menu_item_id=1,
            current_price=Decimal("15.00"),
            base_cost=Decimal("5.00"),
            avg_daily_sales=20.0,
            sales_trend=0.0,
            inventory_level=60.0,
            current_demand=DemandLevel.NORMAL,
            price_elasticity=PriceElasticity.UNIT_ELASTIC,
        )

        price, reasoning = service._cost_plus_pricing(context)

        expected_price = Decimal("5.00") / Decimal("0.30")  # 70% margin
        assert abs(price - expected_price) < Decimal("0.01")
        assert "Cost-plus" in reasoning["primary"]

    def test_apply_pricing_constraints(self, service):
        """Test pricing constraint application"""
        request = BulkPricingRequest(
            max_price_increase_percent=10.0,
            max_price_decrease_percent=5.0,
            round_to_nearest=Decimal("0.05"),
        )

        # Test increase constraint
        constrained = service._apply_pricing_constraints(
            Decimal("10.00"), Decimal("12.00"), request  # 20% increase
        )
        assert constrained == Decimal("11.00")  # Limited to 10% increase

        # Test decrease constraint
        constrained = service._apply_pricing_constraints(
            Decimal("10.00"), Decimal("9.00"), request  # 10% decrease
        )
        assert constrained == Decimal("9.50")  # Limited to 5% decrease

    def test_round_price(self, service):
        """Test price rounding"""
        assert service._round_price(Decimal("10.12"), Decimal("0.05")) == Decimal(
            "10.10"
        )
        assert service._round_price(Decimal("10.13"), Decimal("0.05")) == Decimal(
            "10.15"
        )
        assert service._round_price(Decimal("10.17"), Decimal("0.05")) == Decimal(
            "10.15"
        )
        assert service._round_price(Decimal("10.18"), Decimal("0.05")) == Decimal(
            "10.20"
        )

        assert service._round_price(Decimal("10.24"), Decimal("0.25")) == Decimal(
            "10.25"
        )
        assert service._round_price(Decimal("10.12"), Decimal("0.25")) == Decimal(
            "10.00"
        )
        assert service._round_price(Decimal("10.37"), Decimal("0.25")) == Decimal(
            "10.25"
        )
        assert service._round_price(Decimal("10.38"), Decimal("0.25")) == Decimal(
            "10.50"
        )

    def test_estimate_price_change_impact(self, service):
        """Test price change impact estimation"""
        context = MenuItemPricingContext(
            menu_item_id=1,
            current_price=Decimal("10.00"),
            base_cost=Decimal("3.00"),
            avg_daily_sales=100.0,
            sales_trend=0.0,
            inventory_level=50.0,
            current_demand=DemandLevel.NORMAL,
            price_elasticity=PriceElasticity.ELASTIC,  # -1.5 coefficient
        )

        impacts = service._estimate_price_change_impact(context, Decimal("11.00"))

        # 10% price increase with -1.5 elasticity = -15% demand
        assert impacts["demand_change"] == pytest.approx(-15.0, rel=0.01)

        # Revenue impact: (1.1) * (0.85) - 1 = -0.065 = -6.5%
        assert impacts["revenue_impact"] == pytest.approx(-6.5, rel=0.1)

    def test_assess_pricing_risks(self, service):
        """Test pricing risk assessment"""
        context = MenuItemPricingContext(
            menu_item_id=1,
            current_price=Decimal("10.00"),
            base_cost=Decimal("3.00"),
            avg_daily_sales=50.0,
            sales_trend=0.0,
            inventory_level=15.0,  # Low inventory
            current_demand=DemandLevel.HIGH,
            price_elasticity=PriceElasticity.HIGHLY_ELASTIC,
            competitor_prices=[Decimal("9.00"), Decimal("9.50"), Decimal("10.00")],
            customer_rating=3.5,  # Low rating
        )

        # Large price increase
        risks = service._assess_pricing_risks(context, Decimal("12.00"))

        assert any("customer shock" in risk for risk in risks)
        assert any("elastic" in risk for risk in risks)
        assert any("competitors" in risk for risk in risks)
        assert any("lower-rated" in risk for risk in risks)

    def test_calculate_confidence_score(self, service):
        """Test confidence score calculation"""
        # Low data context
        low_data_context = MenuItemPricingContext(
            menu_item_id=1,
            current_price=Decimal("10.00"),
            base_cost=Decimal("3.00"),
            avg_daily_sales=2.0,  # Low sales
            sales_trend=0.8,  # Volatile trend
            inventory_level=50.0,
            current_demand=DemandLevel.NORMAL,
            price_elasticity=PriceElasticity.UNIT_ELASTIC,
        )

        low_confidence = service._calculate_confidence_score(low_data_context)
        assert low_confidence < 0.7

        # High data context
        high_data_context = MenuItemPricingContext(
            menu_item_id=1,
            current_price=Decimal("10.00"),
            base_cost=Decimal("3.00"),
            avg_daily_sales=50.0,  # Good sales
            sales_trend=0.1,  # Stable trend
            inventory_level=50.0,
            current_demand=DemandLevel.NORMAL,
            price_elasticity=PriceElasticity.UNIT_ELASTIC,
            competitor_prices=[Decimal("9.50"), Decimal("10.50")],
            customer_rating=4.5,
        )

        high_confidence = service._calculate_confidence_score(high_data_context)
        assert high_confidence > 0.8

    def test_service_factory(self, mock_db):
        """Test service factory function"""
        service = create_pricing_recommendation_service(mock_db)
        assert isinstance(service, PricingRecommendationService)
        assert service.db == mock_db


class TestPricingSchemaValidation:
    """Test pricing schema validation"""

    def test_bulk_pricing_request_validation(self):
        """Test request validation"""
        # Valid request
        request = BulkPricingRequest(
            menu_item_ids=[1, 2, 3],
            max_price_increase_percent=25.0,
            max_price_decrease_percent=20.0,
            round_to_nearest=Decimal("0.05"),
        )
        assert request.max_price_increase_percent == 25.0

        # Invalid rounding value
        with pytest.raises(ValueError):
            BulkPricingRequest(
                menu_item_ids=[1], round_to_nearest=Decimal("0.07")  # Invalid
            )

    def test_pricing_context_validation(self):
        """Test pricing context validation"""
        # Valid context
        context = MenuItemPricingContext(
            menu_item_id=1,
            current_price=Decimal("10.99"),
            base_cost=Decimal("3.50"),
            avg_daily_sales=25.0,
            sales_trend=-0.5,
            inventory_level=75.0,
            current_demand=DemandLevel.HIGH,
            price_elasticity=PriceElasticity.ELASTIC,
        )
        assert context.current_price > 0
        assert 0 <= context.inventory_level <= 100

        # Invalid inventory level
        with pytest.raises(ValueError):
            MenuItemPricingContext(
                menu_item_id=1,
                current_price=Decimal("10.99"),
                base_cost=Decimal("3.50"),
                avg_daily_sales=25.0,
                sales_trend=0.0,
                inventory_level=150.0,  # > 100
                current_demand=DemandLevel.NORMAL,
                price_elasticity=PriceElasticity.UNIT_ELASTIC,
            )

    def test_pricing_recommendation_fields(self):
        """Test recommendation field constraints"""
        from ..schemas.pricing_schemas import PricingRecommendation

        # Valid recommendation
        rec = PricingRecommendation(
            menu_item_id=1,
            item_name="Test Item",
            current_price=Decimal("10.00"),
            recommended_price=Decimal("11.00"),
            min_recommended_price=Decimal("10.50"),
            max_recommended_price=Decimal("11.50"),
            price_change_percentage=10.0,
            expected_demand_change=-5.0,
            expected_revenue_impact=4.5,
            expected_profit_impact=6.2,
            confidence_score=0.85,
            strategy_used=PricingStrategy.DEMAND_BASED,
            factors_considered=["demand", "inventory"],
            primary_reason="High demand",
            detailed_reasoning=["Demand is 20% above average"],
            risks=[],
        )

        assert 0 <= rec.confidence_score <= 1
        assert rec.recommended_price > 0
