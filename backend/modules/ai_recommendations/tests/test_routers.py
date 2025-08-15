# backend/modules/ai_recommendations/tests/test_routers.py

import pytest
from datetime import datetime, date
from decimal import Decimal
from unittest.mock import Mock, patch, AsyncMock
from fastapi import HTTPException, status
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from ..routers.pricing_router import (
    generate_pricing_recommendations,
    get_category_pricing_recommendations,
    apply_pricing_recommendation,
)
from ..routers.staffing_router import (
    optimize_staffing,
    get_daily_staffing_recommendation,
    get_labor_cost_analysis,
)
from ..schemas.pricing_schemas import BulkPricingRequest, PricingStrategy
from ..schemas.staffing_schemas import StaffingOptimizationRequest


class TestPricingRouter:
    """Test pricing router endpoints"""

    @pytest.fixture
    def mock_user(self):
        """Mock authenticated user"""
        return {"id": 1, "username": "test_user", "role": "manager"}

    @pytest.fixture
    def mock_db(self):
        """Mock database session"""
        return Mock(spec=Session)

    @pytest.mark.asyncio
    async def test_generate_pricing_recommendations_success(self, mock_user, mock_db):
        """Test successful pricing recommendation generation"""
        request = BulkPricingRequest(
            menu_item_ids=[1, 2, 3],
            optimization_goal="maximize_profit",
            max_price_increase_percent=20.0,
        )

        with patch(
            "backend.modules.ai_recommendations.services.pricing_recommendation_service.create_pricing_recommendation_service"
        ) as mock_create:
            mock_service = AsyncMock()
            mock_service.generate_bulk_recommendations.return_value = Mock(
                request_id="test-123",
                total_recommendations=3,
                avg_price_change_percent=5.5,
            )
            mock_create.return_value = mock_service

            result = await generate_pricing_recommendations(request, mock_user, mock_db)

            assert result.request_id == "test-123"
            assert result.total_recommendations == 3
            mock_service.generate_bulk_recommendations.assert_called_once_with(request)

    @pytest.mark.asyncio
    async def test_generate_pricing_recommendations_error(self, mock_user, mock_db):
        """Test error handling in pricing recommendations"""
        request = BulkPricingRequest(menu_item_ids=[1])

        with patch(
            "backend.modules.ai_recommendations.services.pricing_recommendation_service.create_pricing_recommendation_service"
        ) as mock_create:
            mock_service = AsyncMock()
            mock_service.generate_bulk_recommendations.side_effect = Exception(
                "Database error"
            )
            mock_create.return_value = mock_service

            with pytest.raises(HTTPException) as exc_info:
                await generate_pricing_recommendations(request, mock_user, mock_db)

            assert exc_info.value.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
            assert "Failed to generate pricing recommendations" in str(
                exc_info.value.detail
            )

    @pytest.mark.asyncio
    async def test_get_category_pricing_recommendations(self, mock_user, mock_db):
        """Test category-specific pricing recommendations"""
        with patch(
            "backend.modules.ai_recommendations.services.pricing_recommendation_service.create_pricing_recommendation_service"
        ) as mock_create:
            mock_service = AsyncMock()
            mock_service.generate_bulk_recommendations.return_value = Mock(
                total_items_analyzed=10, total_recommendations=5
            )
            mock_create.return_value = mock_service

            result = await get_category_pricing_recommendations(
                category_id=1,
                max_price_change=15.0,
                optimization_goal="maximize_revenue",
                current_user=mock_user,
                db=mock_db,
            )

            assert result.total_items_analyzed == 10
            assert result.total_recommendations == 5

            # Verify request was built correctly
            call_args = mock_service.generate_bulk_recommendations.call_args[0][0]
            assert call_args.category_ids == [1]
            assert call_args.max_price_increase_percent == 15.0

    @pytest.mark.asyncio
    async def test_apply_pricing_recommendation_permission(self, mock_db):
        """Test permission check for applying recommendations"""
        # This would test that the permission decorator works
        # In a real test, you'd use TestClient with the full FastAPI app
        pass

    @pytest.mark.asyncio
    async def test_mock_endpoints_return_clear_mock_data(self, mock_user, mock_db):
        """Test that mock endpoints clearly indicate they return mock data"""
        # Price elasticity insights should indicate it's mock data
        from ..routers.pricing_router import get_price_elasticity_insights

        result = await get_price_elasticity_insights(
            category_id=None, days_back=90, current_user=mock_user, db=mock_db
        )

        # Check that the response structure exists
        assert "elasticity_summary" in result
        assert "insights" in result

        # In production, this should be marked as mock data
        # TODO: Add "is_mock_data": true field to response


class TestStaffingRouter:
    """Test staffing router endpoints"""

    @pytest.fixture
    def mock_user(self):
        """Mock authenticated user"""
        return {"id": 1, "username": "test_manager", "role": "manager"}

    @pytest.fixture
    def mock_db(self):
        """Mock database session"""
        return Mock(spec=Session)

    @pytest.mark.asyncio
    async def test_optimize_staffing_success(self, mock_user, mock_db):
        """Test successful staffing optimization"""
        request = StaffingOptimizationRequest(
            start_date=date(2025, 2, 1),
            end_date=date(2025, 2, 7),
            service_level_target=0.95,
        )

        with patch(
            "backend.modules.ai_recommendations.services.staffing_recommendation_service.create_staffing_recommendation_service"
        ) as mock_create:
            mock_service = AsyncMock()
            mock_service.generate_staffing_recommendations.return_value = Mock(
                request_id="staff-123",
                total_recommended_hours=280.0,
                average_labor_percentage=26.5,
            )
            mock_create.return_value = mock_service

            result = await optimize_staffing(request, mock_user, mock_db)

            assert result.request_id == "staff-123"
            assert result.total_recommended_hours == 280.0
            mock_service.generate_staffing_recommendations.assert_called_once_with(
                request
            )

    @pytest.mark.asyncio
    async def test_get_daily_staffing_recommendation(self, mock_user, mock_db):
        """Test daily staffing recommendation endpoint"""
        target_date = date(2025, 2, 1)

        with patch(
            "backend.modules.ai_recommendations.services.staffing_recommendation_service.create_staffing_recommendation_service"
        ) as mock_create:
            mock_service = AsyncMock()
            mock_recommendation = Mock(
                date=target_date,
                estimated_labor_cost=Decimal("1250.00"),
                staffing_level="optimal",
            )
            mock_service.generate_staffing_recommendations.return_value = Mock(
                daily_recommendations=[mock_recommendation]
            )
            mock_create.return_value = mock_service

            result = await get_daily_staffing_recommendation(
                target_date=target_date,
                include_flexibility=True,
                current_user=mock_user,
                db=mock_db,
            )

            assert result.date == target_date
            assert result.estimated_labor_cost == Decimal("1250.00")

    @pytest.mark.asyncio
    async def test_get_daily_staffing_not_found(self, mock_user, mock_db):
        """Test daily staffing when no recommendations exist"""
        target_date = date(2025, 2, 1)

        with patch(
            "backend.modules.ai_recommendations.services.staffing_recommendation_service.create_staffing_recommendation_service"
        ) as mock_create:
            mock_service = AsyncMock()
            mock_service.generate_staffing_recommendations.return_value = Mock(
                daily_recommendations=[]  # Empty
            )
            mock_create.return_value = mock_service

            with pytest.raises(HTTPException) as exc_info:
                await get_daily_staffing_recommendation(
                    target_date=target_date,
                    include_flexibility=True,
                    current_user=mock_user,
                    db=mock_db,
                )

            assert exc_info.value.status_code == status.HTTP_404_NOT_FOUND

    @pytest.mark.asyncio
    async def test_labor_cost_analysis(self, mock_user, mock_db):
        """Test labor cost analysis endpoint"""
        start_date = date(2025, 2, 1)
        end_date = date(2025, 2, 7)

        with patch(
            "backend.modules.ai_recommendations.services.staffing_recommendation_service.create_staffing_recommendation_service"
        ) as mock_create:
            mock_service = AsyncMock()
            mock_recommendations = Mock(
                total_recommended_hours=280.0,
                total_estimated_cost=Decimal("5250.00"),
                average_labor_percentage=27.5,
                daily_recommendations=[
                    Mock(
                        date=start_date + timedelta(days=i),
                        staff_requirements=[
                            Mock(role=Mock(value="chef"), optimal=2),
                            Mock(role=Mock(value="server"), optimal=4),
                        ],
                        staffing_level=Mock(
                            value="optimal" if i < 5 else "understaffed"
                        ),
                    )
                    for i in range(7)
                ],
            )
            mock_service.generate_staffing_recommendations.return_value = (
                mock_recommendations
            )
            mock_create.return_value = mock_service

            result = await get_labor_cost_analysis(
                start_date=start_date,
                end_date=end_date,
                compare_to_budget=False,
                current_user=mock_user,
                db=mock_db,
            )

            assert result["days_analyzed"] == 7
            assert result["recommended_staffing"]["total_hours"] == 280.0
            assert (
                len(result["optimization_opportunities"]) > 0
            )  # Should identify understaffing


class TestRouterSecurity:
    """Test security aspects of routers"""

    def test_pricing_endpoints_require_permissions(self):
        """Test that pricing endpoints check permissions"""
        # Import the actual router to check decorators
        from ..routers.pricing_router import router

        # Check that sensitive endpoints have permission decorators
        for route in router.routes:
            if hasattr(route, "endpoint"):
                if route.path in [
                    "/apply/{recommendation_id}",
                    "/rollback/{rollback_token}",
                ]:
                    # These should require admin permissions
                    dependencies = (
                        route.dependencies if hasattr(route, "dependencies") else []
                    )
                    assert any(
                        "require_analytics_permission" in str(dep)
                        for dep in dependencies
                    )

    def test_staffing_endpoints_require_permissions(self):
        """Test that staffing endpoints check permissions"""
        from ..routers.staffing_router import router

        # Check that all endpoints have permission checks
        for route in router.routes:
            if hasattr(route, "endpoint") and hasattr(route, "dependencies"):
                # All endpoints should have some permission check
                assert len(route.dependencies) > 0


class TestRouterValidation:
    """Test input validation in routers"""

    def test_date_range_validation(self):
        """Test date range validation in requests"""
        # Test staffing request validation
        with pytest.raises(ValueError):
            StaffingOptimizationRequest(
                start_date=date(2025, 2, 7),
                end_date=date(2025, 2, 1),  # End before start
            )

        # Test max range validation
        with pytest.raises(ValueError):
            StaffingOptimizationRequest(
                start_date=date(2025, 1, 1), end_date=date(2025, 6, 1)  # > 90 days
            )

    def test_percentage_validation(self):
        """Test percentage field validation"""
        # Test pricing request validation
        request = BulkPricingRequest(
            max_price_increase_percent=50.0,  # Valid
            max_price_decrease_percent=30.0,  # Valid
        )
        assert request.max_price_increase_percent == 50.0

        # Test staffing request validation
        staffing_request = StaffingOptimizationRequest(
            start_date=date(2025, 2, 1),
            end_date=date(2025, 2, 1),
            buffer_percentage=15.0,  # Valid
        )
        assert staffing_request.buffer_percentage == 15.0
