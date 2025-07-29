# backend/modules/ai_recommendations/tests/test_staffing_service.py

import pytest
from datetime import datetime, date, time, timedelta
from decimal import Decimal
from unittest.mock import Mock, patch, AsyncMock
from sqlalchemy.orm import Session

from backend.modules.staff.models.staff_models import StaffMember, Role
from backend.modules.staff.models.shift_models import Shift
from backend.modules.orders.models.order_models import Order

from ..schemas.staffing_schemas import (
    StaffingOptimizationRequest, StaffRole, ShiftType, DayOfWeek,
    StaffingLevel, DemandForecast, StaffRequirement
)
from ..services.staffing_recommendation_service import (
    StaffingRecommendationService, create_staffing_recommendation_service
)


class TestStaffingRecommendationService:
    """Test suite for staffing recommendation service"""
    
    @pytest.fixture
    def mock_db(self):
        """Create mock database session"""
        return Mock(spec=Session)
    
    @pytest.fixture
    def service(self, mock_db):
        """Create service instance"""
        return StaffingRecommendationService(mock_db)
    
    @pytest.fixture
    def sample_request(self):
        """Create sample staffing request"""
        return StaffingOptimizationRequest(
            start_date=date(2025, 2, 1),
            end_date=date(2025, 2, 7),
            primary_goal="minimize_cost",
            service_level_target=0.90,
            max_weekly_hours_per_staff=40,
            min_shift_length_hours=4.0,
            max_shift_length_hours=10.0,
            buffer_percentage=10.0
        )
    
    @pytest.fixture
    def sample_forecast(self):
        """Create sample demand forecast"""
        return DemandForecast(
            date=date(2025, 2, 1),
            hour=12,
            predicted_orders=45,
            predicted_revenue=Decimal("675.50"),
            predicted_customers=38,
            orders_lower_bound=35,
            orders_upper_bound=55,
            confidence_level=0.90
        )
    
    @pytest.mark.asyncio
    async def test_generate_staffing_recommendations(self, service, mock_db, sample_request):
        """Test staffing recommendation generation"""
        # Mock demand forecasts
        with patch.object(service, '_generate_demand_forecasts') as mock_forecasts:
            mock_forecasts.return_value = {
                date(2025, 2, 1): [Mock(predicted_orders=30, predicted_revenue=450, predicted_customers=25) for _ in range(24)]
            }
            
            # Mock patterns
            with patch.object(service, '_identify_staffing_patterns') as mock_patterns:
                mock_patterns.return_value = []
                
                # Mock cache
                with patch('backend.core.cache.cache_service.get') as mock_cache_get:
                    mock_cache_get.return_value = None
                    
                    with patch('backend.core.cache.cache_service.set') as mock_cache_set:
                        # Mock daily recommendation generation
                        with patch.object(service, '_generate_daily_recommendation') as mock_daily:
                            mock_daily.return_value = Mock(
                                date=date(2025, 2, 1),
                                estimated_labor_cost=Decimal("1000"),
                                labor_percentage=25.0,
                                staffing_level=StaffingLevel.OPTIMAL
                            )
                            
                            result = await service.generate_staffing_recommendations(sample_request)
                            
                            assert result is not None
                            assert result.period_start == sample_request.start_date
                            assert result.period_end == sample_request.end_date
                            assert len(result.daily_recommendations) == 7
                            mock_cache_set.assert_called_once()
    
    def test_get_historical_demand_data(self, service, mock_db):
        """Test historical demand data retrieval"""
        # Mock query result
        mock_result = [
            Mock(date=date(2025, 1, 1), hour=12, day_of_week=0, 
                 order_count=50, revenue=Decimal("750"), customer_count=40)
        ]
        
        mock_db.query.return_value.filter.return_value.group_by.return_value.all.return_value = mock_result
        
        data = service._get_historical_demand_data(date(2025, 1, 1), date(2025, 1, 31))
        
        assert len(data) == 1
        assert data[0]['order_count'] == 50
        assert data[0]['hour'] == 12
    
    def test_get_historical_average(self, service):
        """Test historical average calculation"""
        historical_data = [
            {'day_of_week': 0, 'hour': 12, 'order_count': 40, 'revenue': 600, 'customer_count': 35},
            {'day_of_week': 0, 'hour': 12, 'order_count': 50, 'revenue': 750, 'customer_count': 42},
            {'day_of_week': 0, 'hour': 12, 'order_count': 45, 'revenue': 675, 'customer_count': 38},
            {'day_of_week': 1, 'hour': 12, 'order_count': 30, 'revenue': 450, 'customer_count': 25}
        ]
        
        avg = service._get_historical_average(historical_data, 0, 12)  # Monday, noon
        
        assert avg['avg_orders'] == 45.0  # (40+50+45)/3
        assert avg['avg_revenue'] == 675.0
        assert avg['avg_customers'] == 38.33333333333333
    
    def test_apply_forecast_adjustments(self, service):
        """Test forecast adjustments"""
        base_forecast = {
            'avg_orders': 40,
            'avg_revenue': 600,
            'avg_customers': 35
        }
        
        # Regular day
        forecast = service._apply_forecast_adjustments(
            base_forecast,
            date(2025, 2, 3),  # Monday
            12
        )
        
        assert forecast.predicted_orders == 40  # 40 * 1.02 growth
        assert forecast.is_holiday is False
        assert forecast.confidence_level == 0.85
        
        # Holiday
        holiday_forecast = service._apply_forecast_adjustments(
            base_forecast,
            date(2025, 7, 4),  # July 4th
            12
        )
        
        assert holiday_forecast.predicted_orders > 50  # Holiday boost
        assert holiday_forecast.is_holiday is True
    
    def test_calculate_staff_requirements(self, service):
        """Test staff requirement calculations"""
        forecasts = [
            DemandForecast(
                date=date(2025, 2, 1),
                hour=h,
                predicted_orders=30 if h < 12 else 60,
                predicted_revenue=Decimal("450") if h < 12 else Decimal("900"),
                predicted_customers=25 if h < 12 else 50,
                orders_lower_bound=20,
                orders_upper_bound=70,
                confidence_level=0.90
            ) for h in range(24)
        ]
        
        request = StaffingOptimizationRequest(
            start_date=date(2025, 2, 1),
            end_date=date(2025, 2, 1),
            buffer_percentage=10.0
        )
        
        requirements = service._calculate_staff_requirements(forecasts, request)
        
        # Check all roles have requirements
        assert len(requirements) == len(StaffRole)
        
        # Check chef requirement (peak demand 60 orders, productivity 15 orders/hour)
        chef_req = next(r for r in requirements if r.role == StaffRole.CHEF)
        assert chef_req.min_required >= 1  # Minimum staff
        assert chef_req.optimal >= chef_req.min_required
        assert chef_req.max_useful >= chef_req.optimal
    
    def test_assess_staffing_level(self, service):
        """Test staffing level assessment"""
        # Optimal staffing
        gap_optimal = {
            StaffRole.CHEF: 0,
            StaffRole.SERVER: 1,
            StaffRole.DISHWASHER: 0
        }
        assert service._assess_staffing_level(gap_optimal) == StaffingLevel.OPTIMAL
        
        # Understaffed
        gap_under = {
            StaffRole.CHEF: 2,
            StaffRole.SERVER: 3,
            StaffRole.DISHWASHER: 1
        }
        assert service._assess_staffing_level(gap_under) == StaffingLevel.UNDERSTAFFED
        
        # Severely understaffed (critical role missing)
        gap_severe = {
            StaffRole.CHEF: 1,  # Critical role
            StaffRole.SERVER: 2,
            StaffRole.MANAGER: 1  # Critical role
        }
        assert service._assess_staffing_level(gap_severe) == StaffingLevel.SEVERELY_UNDERSTAFFED
        
        # Overstaffed
        gap_over = {
            StaffRole.CHEF: -1,
            StaffRole.SERVER: -2,
            StaffRole.DISHWASHER: -1
        }
        assert service._assess_staffing_level(gap_over) == StaffingLevel.OVERSTAFFED
    
    def test_calculate_labor_cost(self, service):
        """Test labor cost calculation"""
        requirements = [
            StaffRequirement(
                role=StaffRole.CHEF,
                min_required=1,
                optimal=2,
                max_useful=3
            ),
            StaffRequirement(
                role=StaffRole.SERVER,
                min_required=2,
                optimal=4,
                max_useful=6
            ),
            StaffRequirement(
                role=StaffRole.DISHWASHER,
                min_required=1,
                optimal=1,
                max_useful=2
            )
        ]
        
        cost = service._calculate_labor_cost(requirements)
        
        # 2 chefs * $22/hr * 8 hrs = $352
        # 4 servers * $10/hr * 8 hrs = $320
        # 1 dishwasher * $13/hr * 8 hrs = $104
        # Total = $776
        assert cost == Decimal("776.00")
    
    def test_identify_priority_roles(self, service):
        """Test priority role identification"""
        gap = {
            StaffRole.MANAGER: 1,
            StaffRole.CHEF: 2,
            StaffRole.SERVER: 3,
            StaffRole.BUSSER: 1,
            StaffRole.HOST: -1  # Overstaffed
        }
        
        priorities = service._identify_priority_roles(gap)
        
        # Critical roles should come first
        assert priorities[0] == StaffRole.MANAGER
        assert priorities[1] == StaffRole.CHEF
        assert priorities[2] == StaffRole.SERVER
        assert StaffRole.HOST not in priorities  # Negative gap
    
    def test_is_holiday(self, service):
        """Test holiday detection"""
        assert service._is_holiday(date(2025, 1, 1)) is True  # New Year
        assert service._is_holiday(date(2025, 7, 4)) is True  # July 4th
        assert service._is_holiday(date(2025, 12, 25)) is True  # Christmas
        assert service._is_holiday(date(2025, 2, 15)) is False  # Regular day
    
    @pytest.mark.asyncio
    async def test_identify_staffing_patterns(self, service, mock_db):
        """Test staffing pattern identification"""
        # Mock insights service
        with patch.object(service.insights_service, 'generate_insights') as mock_insights:
            mock_insights_result = Mock()
            mock_insights_result.peak_times = Mock(
                primary_peak=Mock(hour=12),
                secondary_peak=Mock(hour=18)
            )
            mock_insights.return_value = mock_insights_result
            
            patterns = await service._identify_staffing_patterns(
                date(2025, 1, 1),
                date(2025, 1, 31)
            )
            
            assert len(patterns) == 2  # Weekday and weekend
            assert patterns[0].pattern_name == "Weekday Standard"
            assert patterns[1].pattern_name == "Weekend Standard"
    
    def test_get_current_schedule(self, service, mock_db):
        """Test current schedule retrieval"""
        # Mock shift query
        mock_db.query.return_value.join.return_value.join.return_value.filter.return_value.group_by.return_value.all.return_value = [
            ("Manager", 1),
            ("Chef", 2),
            ("Server", 4)
        ]
        
        schedule = service._get_current_schedule(date(2025, 2, 1))
        
        assert schedule[StaffRole.MANAGER] == 1
        assert schedule[StaffRole.CHEF] == 2
        assert schedule[StaffRole.SERVER] == 4
        assert schedule[StaffRole.DISHWASHER] == 0  # Not scheduled
    
    def test_service_factory(self, mock_db):
        """Test service factory function"""
        service = create_staffing_recommendation_service(mock_db)
        assert isinstance(service, StaffingRecommendationService)
        assert service.db == mock_db


class TestStaffingSchemaValidation:
    """Test staffing schema validation"""
    
    def test_staffing_optimization_request_validation(self):
        """Test request validation"""
        # Valid request
        request = StaffingOptimizationRequest(
            start_date=date(2025, 2, 1),
            end_date=date(2025, 2, 7),
            max_weekly_hours_per_staff=40,
            min_shift_length_hours=4.0,
            max_shift_length_hours=10.0
        )
        assert request.max_weekly_hours_per_staff == 40
        
        # Invalid date range (end before start)
        with pytest.raises(ValueError):
            StaffingOptimizationRequest(
                start_date=date(2025, 2, 7),
                end_date=date(2025, 2, 1)
            )
        
        # Invalid date range (too long)
        with pytest.raises(ValueError):
            StaffingOptimizationRequest(
                start_date=date(2025, 1, 1),
                end_date=date(2025, 5, 1)  # > 90 days
            )
    
    def test_demand_forecast_validation(self):
        """Test demand forecast validation"""
        # Valid forecast
        forecast = DemandForecast(
            date=date(2025, 2, 1),
            hour=12,
            predicted_orders=45,
            predicted_revenue=Decimal("675.50"),
            predicted_customers=38,
            orders_lower_bound=35,
            orders_upper_bound=55,
            confidence_level=0.90
        )
        
        assert 0 <= forecast.hour <= 23
        assert forecast.predicted_orders >= 0
        assert 0 <= forecast.confidence_level <= 1
        
        # Invalid hour
        with pytest.raises(ValueError):
            DemandForecast(
                date=date(2025, 2, 1),
                hour=25,  # Invalid
                predicted_orders=45,
                predicted_revenue=Decimal("675.50"),
                predicted_customers=38,
                orders_lower_bound=35,
                orders_upper_bound=55
            )
    
    def test_staff_requirement_validation(self):
        """Test staff requirement validation"""
        # Valid requirement
        req = StaffRequirement(
            role=StaffRole.CHEF,
            min_required=1,
            optimal=2,
            max_useful=3
        )
        
        assert req.min_required <= req.optimal <= req.max_useful
        
        # Invalid optimal (less than min)
        with pytest.raises(ValueError):
            StaffRequirement(
                role=StaffRole.CHEF,
                min_required=3,
                optimal=2,  # < min_required
                max_useful=4
            )
        
        # Invalid max_useful (less than optimal)
        with pytest.raises(ValueError):
            StaffRequirement(
                role=StaffRole.CHEF,
                min_required=1,
                optimal=3,
                max_useful=2  # < optimal
            )