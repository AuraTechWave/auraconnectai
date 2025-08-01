# backend/modules/analytics/services/demand_prediction_service.py

"""
Demand Prediction Service for forecasting product and category demand.

Analyzes historical sales data, external factors, and seasonality patterns
to generate accurate demand forecasts.
"""

import logging
import pandas as pd
import numpy as np
from typing import Dict, List, Optional, Tuple, Any
from datetime import datetime, date, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import func, and_, text
import uuid

from core.database import get_db
from modules.analytics.schemas.predictive_analytics_schemas import (
    DemandForecastRequest, DemandForecast, PredictionPoint, ForecastMetadata,
    PredictionConfidence, ModelType, SeasonalityType, TimeGranularity
)
from modules.analytics.services.predictive_models import (
    ModelFactory, BaseForecastModel, EnsembleModel
)
from modules.analytics.models.analytics_models import (
    SalesAnalyticsSnapshot, AggregationPeriod
)
from modules.orders.models.order_models import Order, OrderItem
from core.inventory_models import Inventory
from core.menu_models import MenuItem, MenuCategory
# Custom exceptions - using standard Python exceptions instead
class InsufficientDataError(ValueError):
    pass

class ForecastModelError(RuntimeError):
    pass

class DataQualityError(ValueError):
    pass
from modules.analytics.constants import (
    MIN_DATA_POINTS_FOR_FORECAST, CACHE_TTL_SECONDS,
    WEATHER_IMPACT_THRESHOLDS
)
from modules.analytics.services.cache_service import (
    get_historical_cache, get_model_cache
)

logger = logging.getLogger(__name__)


class DemandPredictionService:
    """Service for predicting product and category demand"""
    
    def __init__(self, db: Session):
        self.db = db
        self.historical_cache = get_historical_cache()
        self.model_cache_service = get_model_cache()
        self.external_factors = ExternalFactorsAnalyzer()
        
    async def forecast_demand(
        self,
        request: DemandForecastRequest
    ) -> DemandForecast:
        """
        Generate demand forecast for a product or category.
        
        Args:
            request: Demand forecast request parameters
            
        Returns:
            DemandForecast object with predictions and insights
        """
        try:
            # Get historical data
            historical_data = self._get_historical_demand(
                request.entity_type,
                request.entity_id,
                request.time_granularity
            )
            
            if len(historical_data) < MIN_DATA_POINTS_FOR_FORECAST:
                raise InsufficientDataError(
                    required_points=MIN_DATA_POINTS_FOR_FORECAST,
                    available_points=len(historical_data),
                    entity_type=request.entity_type,
                    entity_id=request.entity_id
                )
            
            # Prepare time series data
            time_series = self._prepare_time_series(historical_data)
            
            # Apply external factors if requested
            if request.include_external_factors:
                time_series = self._apply_external_factors(
                    time_series,
                    request.external_factors
                )
            
            # Select or create model
            model = self._get_or_create_model(
                request.entity_type,
                request.entity_id,
                request.model_type,
                time_series
            )
            
            # Generate predictions
            predictions, lower_bounds, upper_bounds = model.predict(
                request.horizon_days
            )
            
            # Create prediction points
            prediction_points = self._create_prediction_points(
                predictions,
                lower_bounds,
                upper_bounds,
                request.time_granularity
            )
            
            # Detect patterns and generate insights
            seasonality_patterns = model.detect_seasonality(time_series)
            insights = self._generate_insights(
                time_series,
                predictions,
                seasonality_patterns
            )
            
            # Calculate forecast metadata
            metadata = self._create_forecast_metadata(
                model,
                time_series,
                predictions,
                seasonality_patterns
            )
            
            # Generate recommendations
            recommendations = self._generate_recommendations(
                predictions,
                time_series,
                request
            )
            
            # Get entity name
            entity_name = self._get_entity_name(
                request.entity_type,
                request.entity_id
            )
            
            return DemandForecast(
                entity_id=request.entity_id,
                entity_type=request.entity_type,
                entity_name=entity_name,
                predictions=prediction_points,
                metadata=metadata,
                insights=insights,
                recommended_actions=recommendations
            )
            
        except InsufficientDataError:
            raise  # Re-raise as is
        except ForecastModelError:
            raise  # Re-raise as is
        except Exception as e:
            logger.error(f"Demand forecasting failed: {e}", exc_info=True)
            raise ForecastModelError(
                model_type=request.model_type or "auto",
                reason=str(e),
                entity_type=request.entity_type,
                entity_id=request.entity_id
            )
    
    def _get_historical_demand(
        self,
        entity_type: str,
        entity_id: Optional[int],
        granularity: TimeGranularity
    ) -> pd.DataFrame:
        """Retrieve historical demand data with caching"""
        
        # Check cache first
        cached_data = self.historical_cache.get_historical_data(
            entity_type, entity_id, granularity.value
        )
        if cached_data is not None:
            logger.debug(f"Using cached historical data for {entity_type}:{entity_id}")
            return cached_data
        
        # Determine date range
        end_date = date.today()
        if granularity == TimeGranularity.HOURLY:
            start_date = end_date - timedelta(days=30)
        elif granularity == TimeGranularity.DAILY:
            start_date = end_date - timedelta(days=180)
        elif granularity == TimeGranularity.WEEKLY:
            start_date = end_date - timedelta(days=365)
        else:  # Monthly
            start_date = end_date - timedelta(days=730)
        
        # Build query based on entity type
        if entity_type == "product":
            query = self._build_product_demand_query(
                entity_id,
                start_date,
                end_date,
                granularity
            )
        elif entity_type == "category":
            query = self._build_category_demand_query(
                entity_id,
                start_date,
                end_date,
                granularity
            )
        else:  # overall
            query = self._build_overall_demand_query(
                start_date,
                end_date,
                granularity
            )
        
        # Execute query and return DataFrame
        result = self.db.execute(text(query))
        df = pd.DataFrame(result.fetchall())
        
        if df.empty:
            raise ValueError("No historical data found")
        
        df['date'] = pd.to_datetime(df['date'])
        df.set_index('date', inplace=True)
        
        # Cache the data
        self.historical_cache.cache_historical_data(
            entity_type, entity_id, granularity.value, df
        )
        
        return df
    
    def _build_product_demand_query(
        self,
        product_id: int,
        start_date: date,
        end_date: date,
        granularity: TimeGranularity
    ) -> str:
        """Build SQL query for product demand data"""
        
        date_trunc = {
            TimeGranularity.HOURLY: "hour",
            TimeGranularity.DAILY: "day",
            TimeGranularity.WEEKLY: "week",
            TimeGranularity.MONTHLY: "month"
        }[granularity]
        
        return f"""
        SELECT 
            DATE_TRUNC('{date_trunc}', o.created_at) as date,
            SUM(oi.quantity) as demand,
            COUNT(DISTINCT o.id) as order_count,
            AVG(oi.unit_price) as avg_price
        FROM order_items oi
        JOIN orders o ON oi.order_id = o.id
        WHERE oi.menu_item_id = {product_id}
            AND o.created_at >= '{start_date}'
            AND o.created_at <= '{end_date}'
            AND o.status NOT IN ('cancelled', 'failed')
        GROUP BY DATE_TRUNC('{date_trunc}', o.created_at)
        ORDER BY date
        """
    
    def _build_category_demand_query(
        self,
        category_id: int,
        start_date: date,
        end_date: date,
        granularity: TimeGranularity
    ) -> str:
        """Build SQL query for category demand data"""
        
        date_trunc = {
            TimeGranularity.HOURLY: "hour",
            TimeGranularity.DAILY: "day",
            TimeGranularity.WEEKLY: "week",
            TimeGranularity.MONTHLY: "month"
        }[granularity]
        
        return f"""
        SELECT 
            DATE_TRUNC('{date_trunc}', o.created_at) as date,
            SUM(oi.quantity) as demand,
            COUNT(DISTINCT o.id) as order_count,
            COUNT(DISTINCT oi.menu_item_id) as product_variety
        FROM order_items oi
        JOIN orders o ON oi.order_id = o.id
        JOIN menu_items mi ON oi.menu_item_id = mi.id
        WHERE mi.category_id = {category_id}
            AND o.created_at >= '{start_date}'
            AND o.created_at <= '{end_date}'
            AND o.status NOT IN ('cancelled', 'failed')
        GROUP BY DATE_TRUNC('{date_trunc}', o.created_at)
        ORDER BY date
        """
    
    def _build_overall_demand_query(
        self,
        start_date: date,
        end_date: date,
        granularity: TimeGranularity
    ) -> str:
        """Build SQL query for overall demand data"""
        
        date_trunc = {
            TimeGranularity.HOURLY: "hour",
            TimeGranularity.DAILY: "day",
            TimeGranularity.WEEKLY: "week",
            TimeGranularity.MONTHLY: "month"
        }[granularity]
        
        return f"""
        SELECT 
            DATE_TRUNC('{date_trunc}', created_at) as date,
            COUNT(*) as demand,
            SUM(total_amount) as revenue,
            COUNT(DISTINCT customer_id) as unique_customers
        FROM orders
        WHERE created_at >= '{start_date}'
            AND created_at <= '{end_date}'
            AND status NOT IN ('cancelled', 'failed')
        GROUP BY DATE_TRUNC('{date_trunc}', created_at)
        ORDER BY date
        """
    
    def _prepare_time_series(self, data: pd.DataFrame) -> pd.Series:
        """Prepare time series data for modeling"""
        # Use demand as primary metric
        ts = data['demand'].astype(float)
        
        # Fill missing dates with zeros
        ts = ts.asfreq('D', fill_value=0)
        
        # Apply smoothing if needed
        if len(ts) > 14:
            ts = ts.rolling(window=3, center=True).mean().fillna(ts)
        
        return ts
    
    def _apply_external_factors(
        self,
        time_series: pd.Series,
        external_factors: Optional[Dict[str, Any]]
    ) -> pd.Series:
        """Apply external factors to the time series"""
        if not external_factors:
            return time_series
        
        # Apply weather impact
        if 'weather' in external_factors:
            weather_impact = self.external_factors.apply_weather_impact(
                time_series,
                external_factors['weather']
            )
            time_series = time_series * weather_impact
        
        # Apply event impact
        if 'events' in external_factors:
            event_impact = self.external_factors.apply_event_impact(
                time_series,
                external_factors['events']
            )
            time_series = time_series * event_impact
        
        # Apply holiday impact
        if 'holidays' in external_factors:
            holiday_impact = self.external_factors.apply_holiday_impact(
                time_series,
                external_factors['holidays']
            )
            time_series = time_series * holiday_impact
        
        return time_series
    
    def _get_or_create_model(
        self,
        entity_type: str,
        entity_id: Optional[int],
        model_type: Optional[ModelType],
        time_series: pd.Series
    ) -> BaseForecastModel:
        """Get cached model or create new one"""
        model_type_str = model_type.value if model_type else "auto"
        
        # Check cache first
        cached_model = self.model_cache_service.get_model(
            entity_type, entity_id, model_type_str
        )
        
        if cached_model:
            logger.debug(f"Using cached model for {entity_type}:{entity_id}:{model_type_str}")
            # Update with latest data
            cached_model.fit(time_series)
            return cached_model
        
        # Create new model
        if model_type:
            model = ModelFactory.create_model(model_type.value)
        else:
            model = ModelFactory.auto_select_model(time_series)
        
        model.fit(time_series)
        
        # Cache the model
        self.model_cache_service.cache_model(
            entity_type, entity_id, model_type_str, model
        )
        
        return model
    
    def _create_prediction_points(
        self,
        predictions: np.ndarray,
        lower_bounds: np.ndarray,
        upper_bounds: np.ndarray,
        granularity: TimeGranularity
    ) -> List[PredictionPoint]:
        """Create prediction point objects"""
        points = []
        
        # Determine time delta
        delta = {
            TimeGranularity.HOURLY: timedelta(hours=1),
            TimeGranularity.DAILY: timedelta(days=1),
            TimeGranularity.WEEKLY: timedelta(weeks=1),
            TimeGranularity.MONTHLY: timedelta(days=30)
        }[granularity]
        
        current_time = datetime.now()
        
        for i in range(len(predictions)):
            timestamp = current_time + (i + 1) * delta
            
            # Calculate confidence level based on prediction interval
            interval_width = upper_bounds[i] - lower_bounds[i]
            avg_value = (predictions[i] + 1e-10)  # Avoid division by zero
            confidence = max(0, min(1, 1 - interval_width / (2 * avg_value)))
            
            points.append(PredictionPoint(
                timestamp=timestamp,
                predicted_value=max(0, predictions[i]),  # Ensure non-negative
                lower_bound=max(0, lower_bounds[i]) if lower_bounds is not None else None,
                upper_bound=max(0, upper_bounds[i]) if upper_bounds is not None else None,
                confidence_level=confidence
            ))
        
        return points
    
    def _generate_insights(
        self,
        historical: pd.Series,
        predictions: np.ndarray,
        seasonality: Dict[str, Any]
    ) -> List[str]:
        """Generate insights from the forecast"""
        insights = []
        
        # Trend analysis
        hist_mean = historical.mean()
        pred_mean = predictions.mean()
        
        if pred_mean > hist_mean * 1.1:
            insights.append(f"Demand is expected to increase by {((pred_mean/hist_mean - 1) * 100):.1f}% on average")
        elif pred_mean < hist_mean * 0.9:
            insights.append(f"Demand is expected to decrease by {((1 - pred_mean/hist_mean) * 100):.1f}% on average")
        else:
            insights.append("Demand is expected to remain stable")
        
        # Seasonality insights
        if seasonality.get('seasonal'):
            strength = seasonality.get('strength', 0)
            if strength > 0.5:
                insights.append(f"Strong seasonal pattern detected with {strength:.1%} strength")
            elif strength > 0.2:
                insights.append(f"Moderate seasonal pattern detected")
        
        # Volatility insights
        hist_std = historical.std()
        hist_cv = hist_std / hist_mean if hist_mean > 0 else 0
        
        if hist_cv > 0.5:
            insights.append("High demand volatility observed - consider safety stock")
        elif hist_cv < 0.2:
            insights.append("Stable demand pattern with low volatility")
        
        # Peak demand insights
        max_pred_idx = np.argmax(predictions)
        max_pred_value = predictions[max_pred_idx]
        
        if max_pred_value > hist_mean * 1.5:
            insights.append(f"Peak demand expected on day {max_pred_idx + 1} ({max_pred_value:.0f} units)")
        
        return insights
    
    def _create_forecast_metadata(
        self,
        model: BaseForecastModel,
        time_series: pd.Series,
        predictions: np.ndarray,
        seasonality: Dict[str, Any]
    ) -> ForecastMetadata:
        """Create forecast metadata"""
        # Determine model type
        model_type_map = {
            'ARIMAModel': ModelType.ARIMA,
            'ExponentialSmoothingModel': ModelType.EXPONENTIAL_SMOOTHING,
            'MovingAverageModel': ModelType.MOVING_AVERAGE,
            'ProphetModel': ModelType.PROPHET,
            'EnsembleModel': ModelType.ENSEMBLE
        }
        
        model_type = model_type_map.get(
            model.__class__.__name__,
            ModelType.ENSEMBLE
        )
        
        # Calculate accuracy metrics (on training data)
        if len(time_series) > 20:
            # Use last 20% for validation
            n_test = len(time_series) // 5
            train_data = time_series[:-n_test]
            test_data = time_series[-n_test:]
            
            # Refit and predict
            temp_model = ModelFactory.create_model(model_type.value)
            temp_model.fit(train_data)
            test_preds, _, _ = temp_model.predict(n_test)
            
            # Calculate metrics
            mae = np.mean(np.abs(test_data.values - test_preds))
            mape = np.mean(np.abs((test_data.values - test_preds) / test_data.values)) * 100
            rmse = np.sqrt(np.mean((test_data.values - test_preds) ** 2))
            
            accuracy_metrics = {
                'mae': float(mae),
                'mape': float(mape),
                'rmse': float(rmse)
            }
        else:
            accuracy_metrics = {
                'mae': 0.0,
                'mape': 0.0,
                'rmse': 0.0
            }
        
        # Determine confidence level
        avg_mape = accuracy_metrics.get('mape', 0)
        if avg_mape < 10:
            confidence = PredictionConfidence.VERY_HIGH
        elif avg_mape < 20:
            confidence = PredictionConfidence.HIGH
        elif avg_mape < 30:
            confidence = PredictionConfidence.MEDIUM
        else:
            confidence = PredictionConfidence.LOW
        
        # Detect seasonality types
        seasonality_types = []
        if seasonality.get('seasonal'):
            period = seasonality.get('period', 0)
            if period == 7:
                seasonality_types.append(SeasonalityType.WEEKLY)
            elif period == 30:
                seasonality_types.append(SeasonalityType.MONTHLY)
            elif period == 365:
                seasonality_types.append(SeasonalityType.YEARLY)
            else:
                seasonality_types.append(SeasonalityType.CUSTOM)
        
        return ForecastMetadata(
            model_used=model_type,
            training_period={
                'start': time_series.index[0].date(),
                'end': time_series.index[-1].date()
            },
            seasonality_detected=seasonality_types,
            accuracy_metrics=accuracy_metrics,
            confidence=confidence
        )
    
    def _generate_recommendations(
        self,
        predictions: np.ndarray,
        historical: pd.Series,
        request: DemandForecastRequest
    ) -> List[Dict[str, Any]]:
        """Generate actionable recommendations"""
        recommendations = []
        
        # Average predictions
        avg_prediction = predictions.mean()
        avg_historical = historical.mean()
        
        # Stock recommendations
        if avg_prediction > avg_historical * 1.2:
            recommendations.append({
                'action': 'increase_stock',
                'priority': 'high',
                'description': f'Increase stock levels by {((avg_prediction/avg_historical - 1) * 100):.0f}%',
                'expected_impact': 'Prevent stockouts and lost sales'
            })
        elif avg_prediction < avg_historical * 0.8:
            recommendations.append({
                'action': 'reduce_stock',
                'priority': 'medium',
                'description': f'Reduce stock levels by {((1 - avg_prediction/avg_historical) * 100):.0f}%',
                'expected_impact': 'Reduce holding costs and waste'
            })
        
        # Promotion recommendations
        min_pred_idx = np.argmin(predictions)
        min_pred_value = predictions[min_pred_idx]
        
        if min_pred_value < avg_historical * 0.7:
            recommendations.append({
                'action': 'run_promotion',
                'priority': 'medium',
                'description': f'Consider promotions around day {min_pred_idx + 1} when demand is low',
                'expected_impact': 'Boost sales during slow periods'
            })
        
        # Staffing recommendations
        max_pred_idx = np.argmax(predictions)
        max_pred_value = predictions[max_pred_idx]
        
        if max_pred_value > avg_historical * 1.5:
            recommendations.append({
                'action': 'increase_staffing',
                'priority': 'high',
                'description': f'Increase staff on day {max_pred_idx + 1} for peak demand',
                'expected_impact': 'Maintain service quality during busy periods'
            })
        
        return recommendations
    
    def _get_entity_name(self, entity_type: str, entity_id: Optional[int]) -> str:
        """Get the name of the entity"""
        if entity_type == "overall":
            return "Overall Business"
        
        if entity_type == "product" and entity_id:
            product = self.db.query(MenuItem).filter_by(id=entity_id).first()
            return product.name if product else f"Product #{entity_id}"
        
        if entity_type == "category" and entity_id:
            category = self.db.query(MenuCategory).filter_by(id=entity_id).first()
            return category.name if category else f"Category #{entity_id}"
        
        return f"{entity_type.capitalize()} #{entity_id}"


class ExternalFactorsAnalyzer:
    """Analyzer for external factors affecting demand"""
    
    def apply_weather_impact(
        self,
        time_series: pd.Series,
        weather_data: Dict[str, Any]
    ) -> pd.Series:
        """Apply weather-based adjustments to demand"""
        # Simple weather impact model
        impact_series = pd.Series(1.0, index=time_series.index)
        
        # Temperature impact (example)
        if 'temperature' in weather_data:
            temp = weather_data['temperature']
            if temp > 30:  # Hot weather
                impact_series *= 1.1  # 10% increase for cold items
            elif temp < 10:  # Cold weather
                impact_series *= 1.15  # 15% increase for hot items
        
        # Rain impact
        if weather_data.get('rainy', False):
            impact_series *= 0.85  # 15% decrease on rainy days
        
        return impact_series
    
    def apply_event_impact(
        self,
        time_series: pd.Series,
        events: List[Dict[str, Any]]
    ) -> pd.Series:
        """Apply event-based adjustments to demand"""
        impact_series = pd.Series(1.0, index=time_series.index)
        
        for event in events:
            event_date = pd.to_datetime(event['date'])
            if event_date in impact_series.index:
                # Apply event multiplier
                impact_series[event_date] *= event.get('impact_multiplier', 1.5)
        
        return impact_series
    
    def apply_holiday_impact(
        self,
        time_series: pd.Series,
        holidays: List[Dict[str, Any]]
    ) -> pd.Series:
        """Apply holiday-based adjustments to demand"""
        impact_series = pd.Series(1.0, index=time_series.index)
        
        for holiday in holidays:
            holiday_date = pd.to_datetime(holiday['date'])
            if holiday_date in impact_series.index:
                # Apply holiday multiplier
                impact_series[holiday_date] *= holiday.get('impact_multiplier', 1.3)
                
                # Apply pre-holiday effect
                for i in range(1, 3):
                    pre_date = holiday_date - timedelta(days=i)
                    if pre_date in impact_series.index:
                        impact_series[pre_date] *= 1.1
        
        return impact_series