# backend/modules/analytics/tests/test_predictive_analytics.py

"""
Comprehensive tests for Predictive Analytics functionality.

Tests forecasting models, demand prediction, stock optimization,
and real-time updates.
"""

import pytest
import asyncio
import numpy as np
import pandas as pd
from datetime import datetime, date, timedelta
from decimal import Decimal
from unittest.mock import Mock, patch, AsyncMock
from typing import List, Dict, Any

from modules.analytics.services.predictive_models import (
    ARIMAModel,
    ExponentialSmoothingModel,
    MovingAverageModel,
    ProphetModel,
    EnsembleModel,
    ModelFactory,
)
from modules.analytics.services.demand_prediction_service import (
    DemandPredictionService,
    ExternalFactorsAnalyzer,
)
from modules.analytics.services.stock_optimization_service import (
    StockOptimizationService,
    InventoryCostCalculator,
)
from modules.analytics.services.forecast_monitoring_service import (
    ForecastMonitoringService,
)
from modules.analytics.schemas.predictive_analytics_schemas import (
    DemandForecastRequest,
    StockOptimizationRequest,
    TimeGranularity,
    ModelType,
    PredictionConfidence,
)
from sqlalchemy import func


class TestPredictiveModels:
    """Test time series forecasting models"""

    @pytest.fixture
    def sample_time_series(self):
        """Generate sample time series data"""
        np.random.seed(42)
        dates = pd.date_range(start="2024-01-01", periods=90, freq="D")
        trend = np.linspace(100, 150, 90)
        seasonal = 10 * np.sin(2 * np.pi * np.arange(90) / 7)
        noise = np.random.normal(0, 5, 90)
        values = trend + seasonal + noise

        return pd.Series(values, index=dates)

    def test_arima_model_fitting(self, sample_time_series):
        """Test ARIMA model fitting and prediction"""
        model = ARIMAModel(order=(1, 1, 1))
        model.fit(sample_time_series)

        assert model.is_fitted
        assert model.order == (1, 1, 1)

        # Test prediction
        predictions, lower, upper = model.predict(steps=7)

        assert len(predictions) == 7
        assert len(lower) == 7
        assert len(upper) == 7
        assert all(lower[i] <= predictions[i] <= upper[i] for i in range(7))

    def test_arima_auto_order_selection(self, sample_time_series):
        """Test automatic ARIMA order selection"""
        model = ARIMAModel()
        model.fit(sample_time_series, auto_select=True)

        assert model.is_fitted
        assert model.order != (1, 1, 1)  # Should select different order

    def test_exponential_smoothing_model(self, sample_time_series):
        """Test Exponential Smoothing model"""
        model = ExponentialSmoothingModel(seasonal_periods=7)
        model.fit(sample_time_series)

        assert model.is_fitted
        assert model.seasonal_periods == 7

        predictions, lower, upper = model.predict(steps=14)

        assert len(predictions) == 14
        # Check seasonality is captured
        assert np.std(predictions) > 0  # Should have variation

    def test_moving_average_model(self, sample_time_series):
        """Test Moving Average model"""
        model = MovingAverageModel(window=7, weighted=True)
        model.fit(sample_time_series)

        assert model.is_fitted
        assert len(model.weights) == 7
        assert np.sum(model.weights) == pytest.approx(1.0)

        predictions, lower, upper = model.predict(steps=7)
        assert len(predictions) == 7

    @pytest.mark.skipif(
        not pytest.importorskip("prophet"), reason="Prophet not installed"
    )
    def test_prophet_model(self, sample_time_series):
        """Test Prophet model integration"""
        model = ProphetModel()
        model.fit(sample_time_series)

        assert model.is_fitted

        predictions, lower, upper = model.predict(steps=7)
        assert len(predictions) == 7

    def test_ensemble_model(self, sample_time_series):
        """Test Ensemble model combining multiple models"""
        models = [
            ARIMAModel(order=(1, 0, 1)),
            ExponentialSmoothingModel(),
            MovingAverageModel(window=5),
        ]

        ensemble = EnsembleModel(models=models)
        ensemble.fit(sample_time_series)

        assert ensemble.is_fitted
        assert len(ensemble.models) <= 3  # Some might fail
        assert len(ensemble.weights) == len(ensemble.models)

        predictions, lower, upper = ensemble.predict(steps=7)
        assert len(predictions) == 7

    def test_model_evaluation_metrics(self, sample_time_series):
        """Test model evaluation metrics calculation"""
        model = MovingAverageModel(window=3)
        model.fit(sample_time_series[:-7])

        # Predict last 7 days
        predictions, _, _ = model.predict(steps=7)
        actual = sample_time_series[-7:].values

        metrics = model.evaluate(pd.Series(actual), pd.Series(predictions))

        assert "mae" in metrics
        assert "mse" in metrics
        assert "rmse" in metrics
        assert "mape" in metrics
        assert all(v >= 0 for v in metrics.values())

    def test_seasonality_detection(self, sample_time_series):
        """Test seasonality detection"""
        model = ARIMAModel()
        seasonality = model.detect_seasonality(sample_time_series)

        assert "seasonal" in seasonality
        assert seasonality["seasonal"] == True  # Should detect weekly pattern
        assert "strength" in seasonality
        assert 0 <= seasonality["strength"] <= 1

    def test_model_factory(self):
        """Test model factory creation"""
        # Test creating each model type
        for model_type in [
            "arima",
            "exponential_smoothing",
            "moving_average",
            "ensemble",
        ]:
            model = ModelFactory.create_model(model_type)
            assert model is not None

        # Test invalid model type
        with pytest.raises(ValueError):
            ModelFactory.create_model("invalid_model")

    def test_auto_model_selection(self, sample_time_series):
        """Test automatic model selection based on data"""
        # Short series
        short_series = sample_time_series[:10]
        model = ModelFactory.auto_select_model(short_series)
        assert isinstance(model, MovingAverageModel)

        # Medium series
        medium_series = sample_time_series[:40]
        model = ModelFactory.auto_select_model(medium_series)
        assert isinstance(model, ExponentialSmoothingModel)

        # Long series
        model = ModelFactory.auto_select_model(sample_time_series)
        assert isinstance(model, EnsembleModel)


class TestDemandPredictionService:
    """Test demand prediction service"""

    @pytest.fixture
    def mock_db(self):
        """Mock database session"""
        return Mock()

    @pytest.fixture
    def demand_service(self, mock_db):
        """Create demand prediction service"""
        return DemandPredictionService(mock_db)

    @pytest.mark.asyncio
    async def test_forecast_demand_success(self, demand_service, mock_db):
        """Test successful demand forecasting"""
        # Mock historical data query
        mock_historical_data = pd.DataFrame(
            {
                "date": pd.date_range(start="2024-01-01", periods=30, freq="D"),
                "demand": np.random.poisson(100, 30),
                "order_count": np.random.poisson(20, 30),
                "avg_price": np.random.uniform(10, 20, 30),
            }
        )

        with patch.object(
            demand_service, "_get_historical_demand", return_value=mock_historical_data
        ):
            request = DemandForecastRequest(
                entity_id=1,
                entity_type="product",
                horizon_days=7,
                time_granularity=TimeGranularity.DAILY,
            )

            forecast = await demand_service.forecast_demand(request)

            assert forecast.entity_id == 1
            assert forecast.entity_type == "product"
            assert len(forecast.predictions) == 7
            assert forecast.metadata.model_used in ModelType
            assert len(forecast.insights) > 0
            assert len(forecast.recommended_actions) > 0

    @pytest.mark.asyncio
    async def test_forecast_with_external_factors(self, demand_service, mock_db):
        """Test demand forecasting with external factors"""
        mock_historical_data = pd.DataFrame(
            {
                "date": pd.date_range(start="2024-01-01", periods=30, freq="D"),
                "demand": np.random.poisson(100, 30),
            }
        )

        with patch.object(
            demand_service, "_get_historical_demand", return_value=mock_historical_data
        ):
            request = DemandForecastRequest(
                entity_id=1,
                entity_type="product",
                horizon_days=7,
                include_external_factors=True,
                external_factors={
                    "weather": {"temperature": 35, "rainy": False},
                    "events": [{"date": "2024-02-01", "impact_multiplier": 1.5}],
                    "holidays": [{"date": "2024-02-14", "impact_multiplier": 1.3}],
                },
            )

            forecast = await demand_service.forecast_demand(request)
            assert forecast is not None

    @pytest.mark.asyncio
    async def test_insufficient_historical_data(self, demand_service, mock_db):
        """Test handling of insufficient historical data"""
        mock_historical_data = pd.DataFrame(
            {
                "date": pd.date_range(start="2024-01-01", periods=5, freq="D"),
                "demand": [10, 20, 15, 18, 22],
            }
        )

        with patch.object(
            demand_service, "_get_historical_demand", return_value=mock_historical_data
        ):
            request = DemandForecastRequest(
                entity_id=1, entity_type="product", horizon_days=7
            )

            with pytest.raises(ValueError, match="Insufficient historical data"):
                await demand_service.forecast_demand(request)

    def test_external_factors_analyzer(self):
        """Test external factors analysis"""
        analyzer = ExternalFactorsAnalyzer()

        # Test weather impact
        ts = pd.Series([100] * 7, index=pd.date_range("2024-01-01", periods=7))
        weather_impact = analyzer.apply_weather_impact(ts, {"temperature": 35})
        assert all(weather_impact == 1.1)  # Hot weather increases demand

        # Test event impact
        events = [{"date": "2024-01-03", "impact_multiplier": 2.0}]
        event_impact = analyzer.apply_event_impact(ts, events)
        assert event_impact.iloc[2] == 2.0  # Event day
        assert event_impact.iloc[0] == 1.0  # Non-event day

        # Test holiday impact
        holidays = [{"date": "2024-01-05", "impact_multiplier": 1.5}]
        holiday_impact = analyzer.apply_holiday_impact(ts, holidays)
        assert holiday_impact.iloc[4] == 1.5  # Holiday
        assert holiday_impact.iloc[3] == 1.1  # Pre-holiday


class TestStockOptimizationService:
    """Test stock optimization service"""

    @pytest.fixture
    def mock_db(self):
        """Mock database session"""
        db = Mock()

        # Mock product query
        mock_products = [
            Mock(id=1, name="Product A", cost=10, price=20, is_available=True),
            Mock(id=2, name="Product B", cost=15, price=30, is_available=True),
        ]
        db.query().filter().all.return_value = mock_products

        # Mock inventory query
        mock_inventory = Mock(quantity=50, unit="units", threshold=20)
        db.query().filter_by().first.return_value = mock_inventory

        return db

    @pytest.fixture
    def stock_service(self, mock_db):
        """Create stock optimization service"""
        return StockOptimizationService(mock_db)

    @pytest.mark.asyncio
    async def test_optimize_stock_levels(self, stock_service, mock_db):
        """Test stock level optimization"""
        # Mock demand forecast
        mock_forecast = {
            "mean_demand": 10,
            "std_demand": 2,
            "max_demand": 15,
            "predictions": [10, 11, 9, 12, 10, 11, 10],
            "lower_bounds": [8, 9, 7, 10, 8, 9, 8],
            "upper_bounds": [12, 13, 11, 14, 12, 13, 12],
        }

        with patch.object(
            stock_service, "_get_product_demand_forecast", return_value=mock_forecast
        ):
            request = StockOptimizationRequest(
                product_ids=[1, 2],
                service_level=0.95,
                lead_time_days=2,
                optimization_objective="balanced",
            )

            result = await stock_service.optimize_stock_levels(request)

            assert len(result.recommendations) == 2
            assert result.total_investment_required > 0
            assert 0 <= result.expected_service_level <= 1

            # Check recommendation structure
            rec = result.recommendations[0]
            assert rec.product_id in [1, 2]
            assert rec.recommended_stock > 0
            assert rec.reorder_point > 0
            assert rec.safety_stock >= 0
            assert 0 <= rec.expected_stockout_risk <= 1

    @pytest.mark.asyncio
    async def test_budget_constraint_optimization(self, stock_service, mock_db):
        """Test optimization with budget constraint"""
        mock_forecast = {
            "mean_demand": 10,
            "std_demand": 2,
            "max_demand": 15,
            "predictions": [10] * 7,
            "lower_bounds": [8] * 7,
            "upper_bounds": [12] * 7,
        }

        with patch.object(
            stock_service, "_get_product_demand_forecast", return_value=mock_forecast
        ):
            request = StockOptimizationRequest(
                product_ids=[1, 2],
                service_level=0.95,
                budget_constraint=Decimal("500"),  # Low budget
            )

            result = await stock_service.optimize_stock_levels(request)

            assert result.total_investment_required <= Decimal("500")

    def test_eoq_calculation(self, stock_service):
        """Test Economic Order Quantity calculation"""
        product = Mock(cost=10, price=20)
        annual_demand = 100
        holding_cost_rate = 0.2
        ordering_cost = 50

        eoq = stock_service._calculate_eoq(
            product, annual_demand, holding_cost_rate, ordering_cost
        )

        # EOQ = sqrt(2 * D * S / H)
        # D = 100 * 365 = 36500
        # S = 50
        # H = 10 * 0.2 = 2
        expected_eoq = np.sqrt(2 * 36500 * 50 / 2)

        assert eoq == pytest.approx(expected_eoq, rel=0.01)

    def test_inventory_cost_calculator(self, mock_db):
        """Test inventory cost calculations"""
        calculator = InventoryCostCalculator(mock_db)

        product = Mock(cost=10, price=20)

        # Test holding cost
        holding_cost = calculator.calculate_holding_cost(
            product, stock_level=100, demand_rate=10
        )

        # Average inventory = 50, annual cost = 50 * 10 * 0.2 = 100
        # Daily cost = 100 / 365
        expected_daily_holding = 100 / 365

        assert float(holding_cost) == pytest.approx(expected_daily_holding, rel=0.01)

        # Test stockout cost
        stockout_cost = calculator.calculate_stockout_cost(
            product, stockout_probability=0.05, demand_rate=10
        )

        # Expected stockouts = 10 * 0.05 = 0.5
        # Profit margin = 20 - 10 = 10
        # Penalty = 10 * 3 = 30
        # Daily cost = 0.5 * 30 = 15

        assert float(stockout_cost) == pytest.approx(15, rel=0.01)


class TestForecastMonitoringService:
    """Test forecast monitoring and accuracy tracking"""

    @pytest.fixture
    def mock_db(self):
        """Mock database session"""
        return Mock()

    @pytest.fixture
    def monitoring_service(self, mock_db):
        """Create forecast monitoring service"""
        return ForecastMonitoringService(mock_db)

    @pytest.mark.asyncio
    async def test_track_forecast_accuracy(self, monitoring_service, mock_db):
        """Test forecast accuracy tracking"""
        predictions = [
            {
                "timestamp": "2024-01-01",
                "predicted_value": 100,
                "lower_bound": 90,
                "upper_bound": 110,
            },
            {
                "timestamp": "2024-01-02",
                "predicted_value": 105,
                "lower_bound": 95,
                "upper_bound": 115,
            },
            {
                "timestamp": "2024-01-03",
                "predicted_value": 98,
                "lower_bound": 88,
                "upper_bound": 108,
            },
        ]

        actuals = [
            {"timestamp": "2024-01-01", "value": 102},
            {"timestamp": "2024-01-02", "value": 108},
            {"timestamp": "2024-01-03", "value": 95},
        ]

        comparison = await monitoring_service.track_forecast_accuracy(
            "product", 1, predictions, actuals
        )

        assert comparison.entity_id == 1
        assert len(comparison.predictions) == 3
        assert len(comparison.actuals) == 3
        assert "mae" in comparison.accuracy_metrics
        assert "mape" in comparison.accuracy_metrics
        assert "bias" in comparison.accuracy_metrics
        assert comparison.deviation_analysis is not None

    def test_accuracy_metrics_calculation(self, monitoring_service):
        """Test accuracy metrics calculation"""
        predicted = pd.Series([100, 105, 98, 102, 110])
        actual = pd.Series([102, 108, 95, 100, 115])

        metrics = monitoring_service._calculate_accuracy_metrics(predicted, actual)

        assert metrics["mae"] > 0
        assert metrics["mape"] > 0
        assert metrics["rmse"] > 0
        assert -1 <= metrics["r_squared"] <= 1
        assert "directional_accuracy" in metrics

    def test_deviation_analysis(self, monitoring_service):
        """Test deviation pattern analysis"""
        data = pd.DataFrame(
            {
                "predicted": [100, 105, 98, 102, 110],
                "actual": [102, 108, 95, 100, 115],
                "lower_bound": [90, 95, 88, 92, 100],
                "upper_bound": [110, 115, 108, 112, 120],
            },
            index=pd.date_range("2024-01-01", periods=5),
        )

        analysis = monitoring_service._analyze_deviations(data)

        assert "max_over_prediction" in analysis
        assert "max_under_prediction" in analysis
        assert "systematic_bias" in analysis
        assert "volatility_ratio" in analysis
        assert "confidence_interval_accuracy" in analysis
        assert "detected_patterns" in analysis

    @pytest.mark.asyncio
    async def test_anomaly_detection(self, monitoring_service, mock_db):
        """Test forecast anomaly detection"""
        # Mock recent poor performance
        mock_performances = [
            Mock(mape=10, evaluation_date=date.today() - timedelta(days=i))
            for i in range(5, 0, -1)
        ] + [
            Mock(mape=25, evaluation_date=date.today())  # Recent degradation
        ]

        mock_db.query().filter().all.return_value = mock_performances

        alerts = await monitoring_service.detect_forecast_anomalies(
            "product", 1, recent_days=7
        )

        assert len(alerts) > 0
        assert alerts[0].alert_type == "accuracy_degradation"
        assert alerts[0].severity == "high"


class TestPredictiveAPIs:
    """Test API endpoints for predictive analytics"""

    @pytest.fixture
    def client(self, test_app):
        """Test client"""
        return test_app

    @pytest.mark.asyncio
    async def test_demand_forecast_endpoint(self, client, mock_auth):
        """Test demand forecast API endpoint"""
        request_data = {
            "entity_id": 1,
            "entity_type": "product",
            "horizon_days": 7,
            "time_granularity": "daily",
            "include_confidence_intervals": True,
        }

        response = client.post(
            "/analytics/predictive/demand-forecast",
            json=request_data,
            headers={"Authorization": "Bearer test_token"},
        )

        assert response.status_code == 200
        data = response.json()
        assert "predictions" in data
        assert "metadata" in data
        assert "insights" in data

    @pytest.mark.asyncio
    async def test_stock_optimization_endpoint(self, client, mock_auth):
        """Test stock optimization API endpoint"""
        request_data = {
            "product_ids": [1, 2, 3],
            "service_level": 0.95,
            "optimization_objective": "balanced",
            "include_safety_stock": True,
        }

        response = client.post(
            "/analytics/predictive/stock-optimization",
            json=request_data,
            headers={"Authorization": "Bearer test_token"},
        )

        assert response.status_code == 200
        data = response.json()
        assert "recommendations" in data
        assert "total_investment_required" in data
        assert "expected_service_level" in data


class TestRealTimePredictions:
    """Test real-time prediction updates"""

    @pytest.mark.asyncio
    async def test_websocket_connection(self, test_app):
        """Test WebSocket connection for real-time updates"""
        # This would test WebSocket functionality
        # Implementation depends on your WebSocket testing setup
        pass

    @pytest.mark.asyncio
    async def test_prediction_subscription(self):
        """Test subscription to prediction updates"""
        from modules.analytics.services.predictive_realtime_service import (
            predictive_realtime_service,
        )

        client_id = "test_client"
        entity_type = "product"
        entity_ids = [1, 2, 3]

        await predictive_realtime_service.subscribe_to_predictions(
            client_id, entity_type, entity_ids
        )

        assert client_id in predictive_realtime_service.active_subscriptions
        assert len(predictive_realtime_service.active_subscriptions[client_id]) == 3


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
