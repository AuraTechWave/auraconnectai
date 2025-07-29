# backend/modules/analytics/tests/test_ai_insights.py

import pytest
from datetime import datetime, date, timedelta
from decimal import Decimal
from unittest.mock import Mock, patch, AsyncMock
from sqlalchemy.orm import Session

from ..services.ai_insights_service import AIInsightsService, create_ai_insights_service
from ..schemas.ai_insights_schemas import (
    InsightRequest, InsightType, ConfidenceLevel,
    PeakTimeInsight, ProductInsight, CustomerInsight,
    TimePattern, ProductTrend, CustomerPattern,
    SeasonalityPattern, AnomalyDetection, AIInsightSummary
)
from backend.modules.orders.models.order_models import Order, OrderItem
from backend.modules.staff.models.staff_models import StaffMember


class TestAIInsightsService:
    """Test suite for AI Insights Service"""
    
    @pytest.fixture
    def mock_db(self):
        """Create a mock database session"""
        return Mock(spec=Session)
    
    @pytest.fixture
    def insights_service(self, mock_db):
        """Create an AI insights service instance"""
        return AIInsightsService(mock_db)
    
    @pytest.fixture
    def sample_request(self):
        """Create a sample insight request"""
        return InsightRequest(
            insight_types=[InsightType.PEAK_TIME, InsightType.PRODUCT_TREND],
            date_from=date(2025, 1, 1),
            date_to=date(2025, 1, 29),
            min_confidence=ConfidenceLevel.MEDIUM,
            include_recommendations=True,
            force_refresh=False
        )
    
    @pytest.mark.asyncio
    async def test_generate_insights_with_cache(self, insights_service, sample_request, mock_db):
        """Test generating insights with cache hit"""
        # Mock cache service
        with patch('backend.core.cache.cache_service.get') as mock_cache_get:
            mock_cache_get.return_value = {
                "generated_at": datetime.utcnow().isoformat(),
                "analysis_period": {"start": "2025-01-01", "end": "2025-01-29"},
                "peak_times": {
                    "insight_type": "peak_time",
                    "primary_peak": {
                        "hour": 12,
                        "intensity": 0.95,
                        "order_count": 45,
                        "revenue": "2500.00",
                        "customer_count": 38
                    },
                    "confidence": "high",
                    "recommendations": ["Schedule more staff during 12:00-13:00"]
                },
                "overall_recommendations": ["Optimize staffing for peak hours"],
                "next_update": (datetime.now() + timedelta(hours=24)).isoformat()
            }
            
            result = await insights_service.generate_insights(sample_request)
            
            assert isinstance(result, AIInsightSummary)
            assert result.peak_times is not None
            assert result.peak_times.primary_peak.hour == 12
            mock_cache_get.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_analyze_peak_times(self, insights_service, mock_db):
        """Test peak time analysis"""
        # Mock hourly data query result
        mock_hourly_data = [
            Mock(hour=12, day_of_week=1, order_count=50, revenue=Decimal('3000'), customer_count=40),
            Mock(hour=12, day_of_week=2, order_count=48, revenue=Decimal('2900'), customer_count=38),
            Mock(hour=13, day_of_week=1, order_count=45, revenue=Decimal('2700'), customer_count=35),
            Mock(hour=18, day_of_week=1, order_count=60, revenue=Decimal('3600'), customer_count=50),
            Mock(hour=18, day_of_week=2, order_count=58, revenue=Decimal('3500'), customer_count=48),
            Mock(hour=10, day_of_week=1, order_count=20, revenue=Decimal('1200'), customer_count=15),
            Mock(hour=10, day_of_week=2, order_count=22, revenue=Decimal('1300'), customer_count=17),
        ]
        
        mock_db.query.return_value.filter.return_value.group_by.return_value.all.return_value = mock_hourly_data
        
        result = await insights_service._analyze_peak_times(
            date(2025, 1, 1),
            date(2025, 1, 29)
        )
        
        assert isinstance(result, PeakTimeInsight)
        assert result.primary_peak.hour == 18  # Highest average orders
        assert result.confidence in [ConfidenceLevel.HIGH, ConfidenceLevel.MEDIUM]
        assert len(result.recommendations) > 0
        assert len(result.quiet_periods) > 0
        assert "Monday" in result.weekly_pattern
    
    @pytest.mark.asyncio
    async def test_analyze_product_trends(self, insights_service, mock_db):
        """Test product trend analysis"""
        # Mock current period data
        current_data = {
            1: {'name': 'Product A', 'quantity': 100, 'revenue': Decimal('1000'), 'order_count': 50, 'rank': 1},
            2: {'name': 'Product B', 'quantity': 80, 'revenue': Decimal('800'), 'order_count': 40, 'rank': 2},
            3: {'name': 'Product C', 'quantity': 60, 'revenue': Decimal('600'), 'order_count': 30, 'rank': 3},
            4: {'name': 'Product D', 'quantity': 120, 'revenue': Decimal('1200'), 'order_count': 60, 'rank': 4},
        }
        
        # Mock previous period data  
        previous_data = {
            1: {'name': 'Product A', 'quantity': 80, 'revenue': Decimal('800'), 'order_count': 40, 'rank': 2},
            2: {'name': 'Product B', 'quantity': 100, 'revenue': Decimal('1000'), 'order_count': 50, 'rank': 1},
            3: {'name': 'Product C', 'quantity': 60, 'revenue': Decimal('600'), 'order_count': 30, 'rank': 3},
            # Product D is new
        }
        
        with patch.object(insights_service, '_get_product_metrics') as mock_get_metrics:
            mock_get_metrics.side_effect = [current_data, previous_data]
            
            result = await insights_service._analyze_product_trends(
                date(2025, 1, 1),
                date(2025, 1, 29)
            )
            
            assert isinstance(result, ProductInsight)
            assert len(result.top_rising) > 0
            assert len(result.top_falling) > 0
            assert len(result.recommendations) > 0
            
            # Check if Product A is rising (80 -> 100)
            rising_products = [t.product_name for t in result.top_rising]
            assert 'Product A' in rising_products
            
            # Check if Product B is falling (100 -> 80)
            falling_products = [t.product_name for t in result.top_falling]
            assert 'Product B' in falling_products
    
    @pytest.mark.asyncio
    async def test_analyze_customer_patterns(self, insights_service, mock_db):
        """Test customer pattern analysis"""
        # Mock customer data
        mock_customer_data = [
            Mock(customer_id=1, order_count=1, total_spent=Decimal('50'), 
                 first_order=datetime(2025, 1, 1), last_order=datetime(2025, 1, 1)),
            Mock(customer_id=2, order_count=5, total_spent=Decimal('250'), 
                 first_order=datetime(2025, 1, 1), last_order=datetime(2025, 1, 15)),
            Mock(customer_id=3, order_count=10, total_spent=Decimal('500'), 
                 first_order=datetime(2024, 12, 1), last_order=datetime(2025, 1, 20)),
            Mock(customer_id=4, order_count=1, total_spent=Decimal('40'), 
                 first_order=datetime(2024, 11, 1), last_order=datetime(2024, 11, 1)),  # At risk
        ]
        
        mock_db.query.return_value.filter.return_value.group_by.return_value.all.return_value = mock_customer_data
        
        result = await insights_service._analyze_customer_patterns(
            date(2025, 1, 1),
            date(2025, 1, 29)
        )
        
        assert isinstance(result, CustomerInsight)
        assert 0 <= result.repeat_customer_rate <= 1
        assert result.average_order_frequency >= 0
        assert len(result.recommendations) > 0
        assert "one_time" in result.lifetime_value_trends
        assert "regular" in result.lifetime_value_trends
    
    @pytest.mark.asyncio
    async def test_detect_seasonality(self, insights_service, mock_db):
        """Test seasonality detection"""
        # Mock monthly data with seasonal pattern
        mock_monthly_data = [
            Mock(month=1, revenue=Decimal('10000'), order_count=200),
            Mock(month=2, revenue=Decimal('11000'), order_count=220),
            Mock(month=3, revenue=Decimal('12000'), order_count=240),
            Mock(month=4, revenue=Decimal('15000'), order_count=300),  # High season
            Mock(month=5, revenue=Decimal('16000'), order_count=320),  # High season
            Mock(month=6, revenue=Decimal('14000'), order_count=280),
        ]
        
        mock_db.query.return_value.filter.return_value.group_by.return_value.all.return_value = mock_monthly_data
        
        result = await insights_service._detect_seasonality(
            date(2025, 1, 1),
            date(2025, 6, 30)
        )
        
        assert isinstance(result, list)
        assert all(isinstance(p, SeasonalityPattern) for p in result)
        
        # Should detect high season in April and May
        high_season_months = [p.start_month for p in result]
        assert 4 in high_season_months or 5 in high_season_months
    
    @pytest.mark.asyncio
    async def test_detect_anomalies(self, insights_service, mock_db):
        """Test anomaly detection"""
        # Mock daily data with anomalies
        mock_daily_data = [
            Mock(date=date(2025, 1, 1), revenue=Decimal('1000'), order_count=20),
            Mock(date=date(2025, 1, 2), revenue=Decimal('1100'), order_count=22),
            Mock(date=date(2025, 1, 3), revenue=Decimal('1050'), order_count=21),
            Mock(date=date(2025, 1, 4), revenue=Decimal('3000'), order_count=60),  # Anomaly - spike
            Mock(date=date(2025, 1, 5), revenue=Decimal('200'), order_count=4),    # Anomaly - drop
            Mock(date=date(2025, 1, 6), revenue=Decimal('1080'), order_count=21),
            Mock(date=date(2025, 1, 7), revenue=Decimal('1120'), order_count=22),
        ]
        
        mock_db.query.return_value.filter.return_value.group_by.return_value.all.return_value = mock_daily_data
        
        result = await insights_service._detect_anomalies(
            date(2025, 1, 1),
            date(2025, 1, 7)
        )
        
        assert isinstance(result, list)
        assert all(isinstance(a, AnomalyDetection) for a in result)
        assert len(result) >= 2  # Should detect at least the spike and drop
        
        # Check anomaly types
        anomaly_types = [a.anomaly_type for a in result]
        assert any("spike" in t for t in anomaly_types)
        assert any("drop" in t for t in anomaly_types)
    
    @pytest.mark.asyncio
    async def test_comprehensive_insights(self, insights_service, mock_db, sample_request):
        """Test comprehensive insight generation"""
        # Update request to include all insight types
        sample_request.insight_types = [
            InsightType.PEAK_TIME,
            InsightType.PRODUCT_TREND,
            InsightType.CUSTOMER_PATTERN,
            InsightType.SEASONALITY,
            InsightType.ANOMALY
        ]
        
        # Mock all the individual analysis methods
        with patch.object(insights_service, '_analyze_peak_times') as mock_peak:
            with patch.object(insights_service, '_analyze_product_trends') as mock_product:
                with patch.object(insights_service, '_analyze_customer_patterns') as mock_customer:
                    with patch.object(insights_service, '_detect_seasonality') as mock_seasonality:
                        with patch.object(insights_service, '_detect_anomalies') as mock_anomalies:
                            with patch('backend.core.cache.cache_service.set') as mock_cache_set:
                                
                                # Set up return values
                                mock_peak.return_value = PeakTimeInsight(
                                    primary_peak=TimePattern(
                                        hour=12, intensity=0.9, order_count=40,
                                        revenue=Decimal('2000'), customer_count=30
                                    ),
                                    weekly_pattern={},
                                    confidence=ConfidenceLevel.HIGH,
                                    recommendations=["Peak time recommendation"]
                                )
                                
                                mock_product.return_value = ProductInsight(
                                    top_rising=[], top_falling=[], stable_performers=[],
                                    new_trending=[], confidence=ConfidenceLevel.MEDIUM,
                                    analysis_period={"start": date(2025, 1, 1), "end": date(2025, 1, 29)},
                                    recommendations=["Product recommendation"]
                                )
                                
                                mock_customer.return_value = CustomerInsight(
                                    patterns_detected=[], repeat_customer_rate=0.4,
                                    average_order_frequency=2.5, churn_risk_segments=[],
                                    lifetime_value_trends={}, confidence=ConfidenceLevel.HIGH,
                                    recommendations=["Customer recommendation"]
                                )
                                
                                mock_seasonality.return_value = []
                                mock_anomalies.return_value = []
                                
                                result = await insights_service.generate_insights(sample_request)
                                
                                # Verify all methods were called
                                mock_peak.assert_called_once()
                                mock_product.assert_called_once()
                                mock_customer.assert_called_once()
                                mock_seasonality.assert_called_once()
                                mock_anomalies.assert_called_once()
                                
                                # Verify result structure
                                assert isinstance(result, AIInsightSummary)
                                assert result.peak_times is not None
                                assert result.product_insights is not None
                                assert result.customer_insights is not None
                                assert len(result.overall_recommendations) == 6  # 2 from each type
                                
                                # Verify caching
                                mock_cache_set.assert_called_once()
    
    def test_service_factory(self, mock_db):
        """Test service factory function"""
        service = create_ai_insights_service(mock_db)
        assert isinstance(service, AIInsightsService)
        assert service.db == mock_db
    
    @pytest.mark.asyncio
    async def test_edge_cases(self, insights_service, mock_db):
        """Test edge cases and error handling"""
        # Test with no data
        mock_db.query.return_value.filter.return_value.group_by.return_value.all.return_value = []
        
        # Peak times with no data
        result = await insights_service._analyze_peak_times(
            date(2025, 1, 1),
            date(2025, 1, 29)
        )
        assert result.primary_peak is None
        assert result.confidence == ConfidenceLevel.HIGH  # Default when no data
        
        # Seasonality with insufficient data
        mock_db.query.return_value.filter.return_value.group_by.return_value.all.return_value = [
            Mock(month=1, revenue=Decimal('1000'), order_count=20)
        ]
        
        result = await insights_service._detect_seasonality(
            date(2025, 1, 1),
            date(2025, 1, 31)
        )
        assert result == []  # No patterns with only 1 month of data


# Test for API router
class TestAIInsightsRouter:
    """Test suite for AI Insights API Router"""
    
    @pytest.fixture
    def mock_current_user(self):
        """Create a mock current user with permissions"""
        user = Mock(spec=StaffMember)
        user.id = 1
        user.username = "test_user"
        return user
    
    @pytest.mark.asyncio
    async def test_generate_insights_endpoint(self, mock_current_user, mock_db):
        """Test the generate insights endpoint"""
        from ..routers.ai_insights_router import generate_ai_insights
        
        with patch('backend.modules.staff.services.permission_service.has_permission') as mock_permission:
            with patch('backend.modules.analytics.services.ai_insights_service.create_ai_insights_service') as mock_create:
                mock_permission.return_value = True
                
                mock_service = AsyncMock()
                mock_service.generate_insights.return_value = AIInsightSummary(
                    generated_at=datetime.utcnow(),
                    analysis_period={"start": date(2025, 1, 1), "end": date(2025, 1, 29)},
                    overall_recommendations=["Test recommendation"],
                    next_update=datetime.utcnow() + timedelta(hours=24)
                )
                mock_create.return_value = mock_service
                
                request = InsightRequest(
                    insight_types=[InsightType.PEAK_TIME],
                    force_refresh=False
                )
                
                result = await generate_ai_insights(request, mock_current_user, mock_db)
                
                assert result.success is True
                assert result.processing_time >= 0
                assert isinstance(result.insights, AIInsightSummary)
    
    @pytest.mark.asyncio
    async def test_permission_denied(self, mock_current_user, mock_db):
        """Test permission denied scenario"""
        from ..routers.ai_insights_router import generate_ai_insights
        from fastapi import HTTPException
        
        with patch('backend.modules.staff.services.permission_service.has_permission') as mock_permission:
            mock_permission.return_value = False
            
            request = InsightRequest(
                insight_types=[InsightType.PEAK_TIME],
                force_refresh=False
            )
            
            with pytest.raises(HTTPException) as exc_info:
                await generate_ai_insights(request, mock_current_user, mock_db)
            
            assert exc_info.value.status_code == 403
            assert "permission" in str(exc_info.value.detail).lower()