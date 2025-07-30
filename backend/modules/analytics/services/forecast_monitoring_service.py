# backend/modules/analytics/services/forecast_monitoring_service.py

"""
Forecast Monitoring Service for tracking prediction accuracy.

Monitors forecast performance, calculates accuracy metrics,
and provides insights for model improvement.
"""

import logging
import pandas as pd
import numpy as np
from typing import Dict, List, Optional, Tuple, Any
from datetime import datetime, date, timedelta
from decimal import Decimal
from sqlalchemy.orm import Session
from sqlalchemy import func, and_, text
import uuid
import json

from backend.core.database import get_db
from backend.modules.analytics.schemas.predictive_analytics_schemas import (
    ForecastAccuracyReport, ModelPerformance, ForecastComparison,
    TrendAnalysis, PredictiveInsight, PredictionAlert,
    PredictionConfidence, ModelType
)
from backend.modules.analytics.models.analytics_models import (
    ForecastHistory, ForecastPerformance
)

logger = logging.getLogger(__name__)


class ForecastMonitoringService:
    """Service for monitoring and evaluating forecast accuracy"""
    
    def __init__(self, db: Session):
        self.db = db
        self.alert_thresholds = {
            'mape_critical': 30,  # >30% error is critical
            'mape_warning': 20,   # >20% error is warning
            'bias_threshold': 0.1, # >10% systematic bias
            'volatility_spike': 2.0  # 2x normal volatility
        }
        
    async def track_forecast_accuracy(
        self,
        entity_type: str,
        entity_id: Optional[int],
        predictions: List[Dict[str, Any]],
        actuals: List[Dict[str, Any]]
    ) -> ForecastComparison:
        """
        Track and compare forecast predictions against actual values.
        
        Args:
            entity_type: Type of entity (product, category, overall)
            entity_id: ID of the entity
            predictions: List of predictions with timestamps
            actuals: List of actual values with timestamps
            
        Returns:
            ForecastComparison with accuracy metrics
        """
        try:
            # Convert to DataFrames for easier analysis
            pred_df = pd.DataFrame(predictions)
            actual_df = pd.DataFrame(actuals)
            
            # Align data by timestamp
            merged_df = self._align_predictions_actuals(pred_df, actual_df)
            
            if merged_df.empty:
                raise ValueError("No overlapping data for comparison")
            
            # Calculate accuracy metrics
            accuracy_metrics = self._calculate_accuracy_metrics(
                merged_df['predicted'],
                merged_df['actual']
            )
            
            # Perform deviation analysis
            deviation_analysis = self._analyze_deviations(merged_df)
            
            # Store performance metrics
            self._store_performance_metrics(
                entity_type,
                entity_id,
                accuracy_metrics,
                len(merged_df)
            )
            
            # Get entity name
            entity_name = self._get_entity_name(entity_type, entity_id)
            
            return ForecastComparison(
                entity_id=entity_id,
                entity_name=entity_name,
                comparison_period={
                    'start': merged_df.index.min().date(),
                    'end': merged_df.index.max().date()
                },
                predictions=[{
                    'timestamp': idx,
                    'predicted_value': row['predicted'],
                    'lower_bound': row.get('lower_bound'),
                    'upper_bound': row.get('upper_bound')
                } for idx, row in merged_df.iterrows()],
                actuals=[{
                    'timestamp': idx,
                    'value': row['actual']
                } for idx, row in merged_df.iterrows()],
                accuracy_metrics=accuracy_metrics,
                deviation_analysis=deviation_analysis
            )
            
        except Exception as e:
            logger.error(f"Forecast accuracy tracking failed: {e}", exc_info=True)
            raise
    
    def _align_predictions_actuals(
        self,
        predictions: pd.DataFrame,
        actuals: pd.DataFrame
    ) -> pd.DataFrame:
        """Align predictions and actuals by timestamp"""
        # Ensure timestamp columns
        predictions['timestamp'] = pd.to_datetime(predictions['timestamp'])
        actuals['timestamp'] = pd.to_datetime(actuals['timestamp'])
        
        # Set timestamp as index
        predictions.set_index('timestamp', inplace=True)
        actuals.set_index('timestamp', inplace=True)
        
        # Merge on index
        merged = pd.merge(
            predictions[['predicted_value', 'lower_bound', 'upper_bound']],
            actuals[['value']],
            left_index=True,
            right_index=True,
            how='inner'
        )
        
        # Rename columns
        merged.columns = ['predicted', 'lower_bound', 'upper_bound', 'actual']
        
        return merged
    
    def _calculate_accuracy_metrics(
        self,
        predicted: pd.Series,
        actual: pd.Series
    ) -> Dict[str, float]:
        """Calculate various accuracy metrics"""
        # Remove any NaN values
        mask = ~(predicted.isna() | actual.isna())
        predicted = predicted[mask]
        actual = actual[mask]
        
        if len(predicted) == 0:
            return {
                'mae': 0,
                'mape': 0,
                'rmse': 0,
                'bias': 0,
                'r_squared': 0
            }
        
        # Mean Absolute Error
        mae = np.mean(np.abs(actual - predicted))
        
        # Mean Absolute Percentage Error
        mape = np.mean(np.abs((actual - predicted) / (actual + 1e-10))) * 100
        
        # Root Mean Square Error
        rmse = np.sqrt(np.mean((actual - predicted) ** 2))
        
        # Bias (systematic over/under prediction)
        bias = np.mean(predicted - actual)
        
        # R-squared
        ss_res = np.sum((actual - predicted) ** 2)
        ss_tot = np.sum((actual - actual.mean()) ** 2)
        r_squared = 1 - (ss_res / (ss_tot + 1e-10))
        
        # Additional metrics
        metrics = {
            'mae': float(mae),
            'mape': float(mape),
            'rmse': float(rmse),
            'bias': float(bias),
            'bias_percentage': float(bias / (actual.mean() + 1e-10) * 100),
            'r_squared': float(max(0, r_squared)),
            'mean_actual': float(actual.mean()),
            'mean_predicted': float(predicted.mean()),
            'std_actual': float(actual.std()),
            'std_predicted': float(predicted.std())
        }
        
        # Directional accuracy (% of times we got the direction right)
        if len(actual) > 1:
            actual_direction = np.sign(actual.diff()[1:])
            predicted_direction = np.sign(predicted.diff()[1:])
            directional_accuracy = np.mean(actual_direction == predicted_direction) * 100
            metrics['directional_accuracy'] = float(directional_accuracy)
        
        return metrics
    
    def _analyze_deviations(self, merged_df: pd.DataFrame) -> Dict[str, Any]:
        """Analyze patterns in forecast deviations"""
        deviations = merged_df['actual'] - merged_df['predicted']
        percentage_deviations = deviations / (merged_df['actual'] + 1e-10) * 100
        
        analysis = {
            'max_over_prediction': {
                'value': float(deviations.min()),
                'percentage': float(percentage_deviations.min()),
                'date': deviations.idxmin().isoformat() if not deviations.empty else None
            },
            'max_under_prediction': {
                'value': float(deviations.max()),
                'percentage': float(percentage_deviations.max()),
                'date': deviations.idxmax().isoformat() if not deviations.empty else None
            },
            'systematic_bias': 'over_predicting' if deviations.mean() < 0 else 'under_predicting',
            'volatility_ratio': float(merged_df['predicted'].std() / (merged_df['actual'].std() + 1e-10))
        }
        
        # Check if predictions fall within confidence intervals
        if 'lower_bound' in merged_df.columns and 'upper_bound' in merged_df.columns:
            within_bounds = (
                (merged_df['actual'] >= merged_df['lower_bound']) & 
                (merged_df['actual'] <= merged_df['upper_bound'])
            )
            analysis['confidence_interval_accuracy'] = float(within_bounds.mean() * 100)
        
        # Detect patterns
        patterns = []
        
        # Check for worsening accuracy over time
        recent_deviations = percentage_deviations.tail(7).abs().mean()
        overall_deviations = percentage_deviations.abs().mean()
        
        if recent_deviations > overall_deviations * 1.5:
            patterns.append("accuracy_degrading")
        
        # Check for day-of-week patterns
        if len(deviations) >= 14:
            dow_deviations = deviations.groupby(deviations.index.dayofweek).mean()
            if dow_deviations.std() > dow_deviations.mean() * 0.5:
                patterns.append("day_of_week_bias")
        
        analysis['detected_patterns'] = patterns
        
        return analysis
    
    def _store_performance_metrics(
        self,
        entity_type: str,
        entity_id: Optional[int],
        metrics: Dict[str, float],
        sample_size: int
    ) -> None:
        """Store performance metrics in database"""
        try:
            performance = ForecastPerformance(
                entity_type=entity_type,
                entity_id=entity_id,
                mae=metrics['mae'],
                mape=metrics['mape'],
                rmse=metrics['rmse'],
                r_squared=metrics['r_squared'],
                bias=metrics['bias'],
                sample_size=sample_size,
                evaluation_date=date.today(),
                metrics_json=json.dumps(metrics)
            )
            
            self.db.add(performance)
            self.db.commit()
            
        except Exception as e:
            logger.error(f"Failed to store performance metrics: {e}")
            self.db.rollback()
    
    async def generate_accuracy_report(
        self,
        start_date: date,
        end_date: date,
        entity_type: Optional[str] = None
    ) -> ForecastAccuracyReport:
        """Generate comprehensive forecast accuracy report"""
        try:
            # Get all performance records for the period
            query = self.db.query(ForecastPerformance).filter(
                and_(
                    ForecastPerformance.evaluation_date >= start_date,
                    ForecastPerformance.evaluation_date <= end_date
                )
            )
            
            if entity_type:
                query = query.filter(ForecastPerformance.entity_type == entity_type)
            
            performances = query.all()
            
            if not performances:
                raise ValueError("No performance data found for the specified period")
            
            # Calculate overall accuracy
            overall_mape = np.mean([p.mape for p in performances])
            overall_accuracy = 100 - overall_mape
            
            # Group by model type (inferred from entity type)
            model_performances = self._aggregate_model_performances(performances)
            
            # Accuracy by category
            accuracy_by_category = self._calculate_accuracy_by_category(performances)
            
            # Top/bottom performing products
            accuracy_by_product = self._get_product_accuracy_ranking(performances)
            
            # Generate improvement recommendations
            recommendations = self._generate_improvement_recommendations(
                performances,
                overall_mape
            )
            
            return ForecastAccuracyReport(
                report_id=str(uuid.uuid4()),
                period={'start': start_date, 'end': end_date},
                overall_accuracy=float(overall_accuracy),
                model_performances=model_performances,
                accuracy_by_category=accuracy_by_category,
                accuracy_by_product=accuracy_by_product[:20],  # Top 20
                improvement_recommendations=recommendations
            )
            
        except Exception as e:
            logger.error(f"Failed to generate accuracy report: {e}", exc_info=True)
            raise
    
    def _aggregate_model_performances(
        self,
        performances: List[ForecastPerformance]
    ) -> List[ModelPerformance]:
        """Aggregate performances by model type"""
        # Group by entity type (proxy for model type)
        model_groups = {}
        
        for perf in performances:
            key = perf.entity_type
            if key not in model_groups:
                model_groups[key] = []
            model_groups[key].append(perf)
        
        model_performances = []
        
        for entity_type, perfs in model_groups.items():
            # Calculate aggregate metrics
            mae = np.mean([p.mae for p in perfs])
            mape = np.mean([p.mape for p in perfs])
            rmse = np.mean([p.rmse for p in perfs])
            r_squared = np.mean([p.r_squared for p in perfs])
            
            # Determine model type based on typical usage
            if entity_type == "product":
                model_type = ModelType.ENSEMBLE
            elif entity_type == "category":
                model_type = ModelType.EXPONENTIAL_SMOOTHING
            else:
                model_type = ModelType.ARIMA
            
            model_performances.append(ModelPerformance(
                model_type=model_type,
                entity_type=entity_type,
                mae=float(mae),
                mape=float(mape),
                rmse=float(rmse),
                r_squared=float(r_squared),
                training_samples=sum(p.sample_size for p in perfs),
                evaluation_period={
                    'start': min(p.evaluation_date for p in perfs),
                    'end': max(p.evaluation_date for p in perfs)
                },
                last_updated=datetime.now()
            ))
        
        return model_performances
    
    def _calculate_accuracy_by_category(
        self,
        performances: List[ForecastPerformance]
    ) -> Dict[str, float]:
        """Calculate accuracy metrics by category"""
        category_accuracy = {}
        
        # Group by entity type
        for entity_type in ['product', 'category', 'overall']:
            type_perfs = [p for p in performances if p.entity_type == entity_type]
            if type_perfs:
                avg_mape = np.mean([p.mape for p in type_perfs])
                category_accuracy[entity_type] = 100 - avg_mape
        
        return category_accuracy
    
    def _get_product_accuracy_ranking(
        self,
        performances: List[ForecastPerformance]
    ) -> List[Dict[str, Any]]:
        """Get products ranked by forecast accuracy"""
        product_perfs = [p for p in performances if p.entity_type == 'product' and p.entity_id]
        
        # Group by product
        product_groups = {}
        for perf in product_perfs:
            if perf.entity_id not in product_groups:
                product_groups[perf.entity_id] = []
            product_groups[perf.entity_id].append(perf)
        
        # Calculate average accuracy per product
        product_accuracies = []
        
        for product_id, perfs in product_groups.items():
            avg_mape = np.mean([p.mape for p in perfs])
            product_name = self._get_entity_name('product', product_id)
            
            product_accuracies.append({
                'product_id': product_id,
                'product_name': product_name,
                'accuracy': 100 - avg_mape,
                'mape': avg_mape,
                'sample_size': sum(p.sample_size for p in perfs)
            })
        
        # Sort by accuracy (descending)
        product_accuracies.sort(key=lambda x: x['accuracy'], reverse=True)
        
        return product_accuracies
    
    def _generate_improvement_recommendations(
        self,
        performances: List[ForecastPerformance],
        overall_mape: float
    ) -> List[str]:
        """Generate recommendations for improving forecast accuracy"""
        recommendations = []
        
        # Check overall accuracy
        if overall_mape > self.alert_thresholds['mape_critical']:
            recommendations.append(
                "Critical: Overall forecast accuracy is below 70%. "
                "Consider reviewing and retraining all models."
            )
        elif overall_mape > self.alert_thresholds['mape_warning']:
            recommendations.append(
                "Warning: Overall forecast accuracy is below 80%. "
                "Focus on improving models for high-volume products."
            )
        
        # Check for systematic bias
        biases = [p.bias for p in performances if p.bias is not None]
        if biases:
            avg_bias = np.mean(biases)
            if abs(avg_bias) > self.alert_thresholds['bias_threshold']:
                direction = "over-predicting" if avg_bias > 0 else "under-predicting"
                recommendations.append(
                    f"Systematic bias detected: Models are consistently {direction}. "
                    "Consider adjusting model parameters or adding bias correction."
                )
        
        # Check model variety
        entity_types = set(p.entity_type for p in performances)
        if len(entity_types) == 1:
            recommendations.append(
                "Consider using different models for different product types "
                "to improve overall accuracy."
            )
        
        # Check data recency
        latest_eval = max(p.evaluation_date for p in performances)
        if (date.today() - latest_eval).days > 7:
            recommendations.append(
                "Models haven't been evaluated in over a week. "
                "Consider more frequent accuracy monitoring."
            )
        
        # Product-specific recommendations
        product_perfs = [p for p in performances if p.entity_type == 'product']
        if product_perfs:
            poor_performers = [p for p in product_perfs if p.mape > 30]
            if len(poor_performers) > len(product_perfs) * 0.2:
                recommendations.append(
                    f"{len(poor_performers)} products have poor forecast accuracy. "
                    "Consider product-specific model tuning or alternative approaches."
                )
        
        return recommendations
    
    async def detect_forecast_anomalies(
        self,
        entity_type: str,
        entity_id: Optional[int],
        recent_days: int = 7
    ) -> List[PredictionAlert]:
        """Detect anomalies in recent forecasts"""
        alerts = []
        
        try:
            # Get recent forecast performance
            recent_date = date.today() - timedelta(days=recent_days)
            
            performances = self.db.query(ForecastPerformance).filter(
                and_(
                    ForecastPerformance.entity_type == entity_type,
                    ForecastPerformance.entity_id == entity_id,
                    ForecastPerformance.evaluation_date >= recent_date
                )
            ).all()
            
            if not performances:
                return alerts
            
            # Check for accuracy degradation
            if len(performances) >= 3:
                recent_mape = np.mean([p.mape for p in performances[-3:]])
                historical_mape = np.mean([p.mape for p in performances[:-3]])
                
                if recent_mape > historical_mape * 1.5:
                    alerts.append(PredictionAlert(
                        alert_id=str(uuid.uuid4()),
                        alert_type="accuracy_degradation",
                        severity="high",
                        entity_id=entity_id,
                        entity_name=self._get_entity_name(entity_type, entity_id),
                        message=f"Forecast accuracy has degraded by {((recent_mape/historical_mape - 1) * 100):.0f}%",
                        predicted_impact={
                            'recent_mape': recent_mape,
                            'historical_mape': historical_mape,
                            'degradation_factor': recent_mape / historical_mape
                        },
                        recommended_actions=[
                            "Retrain the forecasting model with recent data",
                            "Check for changes in demand patterns",
                            "Review external factors affecting demand"
                        ],
                        expires_at=datetime.now() + timedelta(days=3)
                    ))
            
            # Check for high volatility
            if len(performances) >= 2:
                mape_values = [p.mape for p in performances]
                volatility = np.std(mape_values) / (np.mean(mape_values) + 1e-10)
                
                if volatility > 0.5:
                    alerts.append(PredictionAlert(
                        alert_id=str(uuid.uuid4()),
                        alert_type="high_volatility",
                        severity="medium",
                        entity_id=entity_id,
                        entity_name=self._get_entity_name(entity_type, entity_id),
                        message="Forecast accuracy is highly volatile",
                        predicted_impact={
                            'volatility_coefficient': volatility,
                            'mape_std': np.std(mape_values)
                        },
                        recommended_actions=[
                            "Consider ensemble models for more stable predictions",
                            "Increase forecast update frequency",
                            "Review data quality and outliers"
                        ],
                        expires_at=datetime.now() + timedelta(days=7)
                    ))
            
            return alerts
            
        except Exception as e:
            logger.error(f"Anomaly detection failed: {e}")
            return alerts
    
    def _get_entity_name(self, entity_type: str, entity_id: Optional[int]) -> str:
        """Get entity name from database"""
        if entity_type == "overall":
            return "Overall Business"
        
        # Implementation depends on your entity models
        return f"{entity_type.capitalize()} #{entity_id}"


# Add these models to your analytics_models.py

class ForecastHistory(Base, TimestampMixin):
    """History of all forecasts made"""
    __tablename__ = "forecast_history"
    
    id = Column(Integer, primary_key=True, index=True)
    forecast_id = Column(String, unique=True, index=True)
    entity_type = Column(String, nullable=False, index=True)
    entity_id = Column(Integer, nullable=True, index=True)
    model_type = Column(String, nullable=False)
    forecast_date = Column(Date, nullable=False)
    horizon_days = Column(Integer, nullable=False)
    predictions_json = Column(text, nullable=False)  # JSON array of predictions
    metadata_json = Column(text, nullable=True)  # Additional metadata


class ForecastPerformance(Base, TimestampMixin):
    """Tracked performance metrics for forecasts"""
    __tablename__ = "forecast_performance"
    
    id = Column(Integer, primary_key=True, index=True)
    entity_type = Column(String, nullable=False, index=True)
    entity_id = Column(Integer, nullable=True, index=True)
    evaluation_date = Column(Date, nullable=False, index=True)
    mae = Column(Float, nullable=False)
    mape = Column(Float, nullable=False)
    rmse = Column(Float, nullable=False)
    r_squared = Column(Float, nullable=True)
    bias = Column(Float, nullable=True)
    sample_size = Column(Integer, nullable=False)
    metrics_json = Column(text, nullable=True)  # Additional metrics as JSON
    
    __table_args__ = (
        Index('idx_forecast_performance_entity', 'entity_type', 'entity_id', 'evaluation_date'),
    )