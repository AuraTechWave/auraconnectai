# backend/modules/analytics/services/predictive_models.py

"""
Time series forecasting models for predictive analytics.

Implements various forecasting algorithms including ARIMA, Prophet,
exponential smoothing, and ensemble methods.
"""

import logging
import numpy as np
import pandas as pd
from typing import Dict, List, Tuple, Optional, Any
from datetime import datetime, timedelta
from abc import ABC, abstractmethod
from statsmodels.tsa.arima.model import ARIMA
from statsmodels.tsa.holtwinters import ExponentialSmoothing
from statsmodels.tsa.seasonal import seasonal_decompose
from statsmodels.tsa.stattools import adfuller
from sklearn.metrics import mean_absolute_error, mean_squared_error
from scipy import stats
import warnings

warnings.filterwarnings('ignore')

logger = logging.getLogger(__name__)


class BaseForecastModel(ABC):
    """Base class for all forecasting models"""
    
    def __init__(self, confidence_level: float = 0.95):
        self.confidence_level = confidence_level
        self.model = None
        self.is_fitted = False
        self.training_history = []
        self.model_params = {}
        
    @abstractmethod
    def fit(self, data: pd.Series, **kwargs) -> None:
        """Fit the model to historical data"""
        pass
    
    @abstractmethod
    def predict(self, steps: int) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
        """
        Make predictions for future time steps.
        
        Returns:
            Tuple of (predictions, lower_bounds, upper_bounds)
        """
        pass
    
    def evaluate(self, actual: pd.Series, predicted: pd.Series) -> Dict[str, float]:
        """Evaluate model performance"""
        mae = mean_absolute_error(actual, predicted)
        mse = mean_squared_error(actual, predicted)
        rmse = np.sqrt(mse)
        mape = np.mean(np.abs((actual - predicted) / actual)) * 100
        
        return {
            'mae': mae,
            'mse': mse,
            'rmse': rmse,
            'mape': mape
        }
    
    def detect_seasonality(self, data: pd.Series) -> Dict[str, Any]:
        """Detect seasonality patterns in the data"""
        if len(data) < 24:  # Need at least 2 cycles
            return {'seasonal': False}
        
        try:
            # Perform seasonal decomposition
            decomposition = seasonal_decompose(data, model='additive', period=None)
            
            # Calculate seasonality strength
            var_seasonal = np.var(decomposition.seasonal)
            var_residual = np.var(decomposition.resid.dropna())
            seasonality_strength = max(0, 1 - var_residual / (var_residual + var_seasonal))
            
            return {
                'seasonal': seasonality_strength > 0.1,
                'strength': seasonality_strength,
                'period': len(decomposition.seasonal) // 2  # Estimated period
            }
        except Exception as e:
            logger.warning(f"Seasonality detection failed: {e}")
            return {'seasonal': False}


class ARIMAModel(BaseForecastModel):
    """ARIMA (AutoRegressive Integrated Moving Average) model"""
    
    def __init__(self, order: Tuple[int, int, int] = None, **kwargs):
        super().__init__(**kwargs)
        self.order = order or (1, 1, 1)  # Default ARIMA(1,1,1)
        
    def fit(self, data: pd.Series, auto_select: bool = True) -> None:
        """Fit ARIMA model to the data"""
        try:
            if auto_select:
                # Auto-select best ARIMA parameters
                self.order = self._select_best_order(data)
                
            self.model = ARIMA(data, order=self.order)
            self.fitted_model = self.model.fit()
            self.is_fitted = True
            self.training_history = data.copy()
            
            logger.info(f"ARIMA model fitted with order {self.order}")
            
        except Exception as e:
            logger.error(f"ARIMA fitting failed: {e}")
            raise
    
    def predict(self, steps: int) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
        """Generate predictions with confidence intervals"""
        if not self.is_fitted:
            raise ValueError("Model must be fitted before prediction")
        
        # Get forecast
        forecast = self.fitted_model.forecast(steps=steps)
        
        # Calculate confidence intervals
        forecast_df = self.fitted_model.get_forecast(steps=steps)
        confidence_int = forecast_df.conf_int(alpha=1-self.confidence_level)
        
        predictions = forecast.values
        lower_bounds = confidence_int.iloc[:, 0].values
        upper_bounds = confidence_int.iloc[:, 1].values
        
        return predictions, lower_bounds, upper_bounds
    
    def _select_best_order(self, data: pd.Series) -> Tuple[int, int, int]:
        """Auto-select best ARIMA order using AIC"""
        # Check stationarity
        adf_result = adfuller(data)
        d = 0 if adf_result[1] < 0.05 else 1
        
        # Grid search for best parameters
        best_aic = np.inf
        best_order = (1, d, 1)
        
        for p in range(0, 3):
            for q in range(0, 3):
                if p == 0 and q == 0:
                    continue
                try:
                    model = ARIMA(data, order=(p, d, q))
                    fitted = model.fit()
                    if fitted.aic < best_aic:
                        best_aic = fitted.aic
                        best_order = (p, d, q)
                except:
                    continue
        
        return best_order


class ExponentialSmoothingModel(BaseForecastModel):
    """Exponential Smoothing (Holt-Winters) model"""
    
    def __init__(self, seasonal_periods: int = None, **kwargs):
        super().__init__(**kwargs)
        self.seasonal_periods = seasonal_periods
        self.trend = 'add'
        self.seasonal = 'add' if seasonal_periods else None
        
    def fit(self, data: pd.Series, **kwargs) -> None:
        """Fit exponential smoothing model"""
        try:
            # Detect seasonality if not specified
            if self.seasonal_periods is None:
                seasonality = self.detect_seasonality(data)
                if seasonality['seasonal']:
                    self.seasonal_periods = seasonality.get('period', 7)
                    self.seasonal = 'add'
            
            self.model = ExponentialSmoothing(
                data,
                trend=self.trend,
                seasonal=self.seasonal,
                seasonal_periods=self.seasonal_periods
            )
            
            self.fitted_model = self.model.fit()
            self.is_fitted = True
            self.training_history = data.copy()
            
            logger.info(f"Exponential Smoothing fitted with seasonal_periods={self.seasonal_periods}")
            
        except Exception as e:
            logger.error(f"Exponential Smoothing fitting failed: {e}")
            raise
    
    def predict(self, steps: int) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
        """Generate predictions with confidence intervals"""
        if not self.is_fitted:
            raise ValueError("Model must be fitted before prediction")
        
        # Get forecast
        predictions = self.fitted_model.forecast(steps=steps).values
        
        # Calculate prediction intervals using residuals
        residuals = self.fitted_model.resid
        sigma = np.std(residuals)
        
        # Calculate confidence intervals
        z_score = stats.norm.ppf((1 + self.confidence_level) / 2)
        margin = z_score * sigma * np.sqrt(1 + np.arange(1, steps + 1) / len(self.training_history))
        
        lower_bounds = predictions - margin
        upper_bounds = predictions + margin
        
        return predictions, lower_bounds, upper_bounds


class MovingAverageModel(BaseForecastModel):
    """Simple and Weighted Moving Average models"""
    
    def __init__(self, window: int = 7, weighted: bool = False, **kwargs):
        super().__init__(**kwargs)
        self.window = window
        self.weighted = weighted
        self.last_values = None
        
    def fit(self, data: pd.Series, **kwargs) -> None:
        """Fit moving average model"""
        if len(data) < self.window:
            raise ValueError(f"Data length must be at least {self.window}")
        
        self.training_history = data.copy()
        self.last_values = data.tail(self.window).values
        self.is_fitted = True
        
        # Calculate weights for weighted moving average
        if self.weighted:
            self.weights = np.arange(1, self.window + 1)
            self.weights = self.weights / self.weights.sum()
        else:
            self.weights = np.ones(self.window) / self.window
    
    def predict(self, steps: int) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
        """Generate predictions"""
        if not self.is_fitted:
            raise ValueError("Model must be fitted before prediction")
        
        predictions = []
        current_values = self.last_values.copy()
        
        for _ in range(steps):
            # Calculate weighted average
            pred = np.sum(current_values * self.weights)
            predictions.append(pred)
            
            # Update sliding window
            current_values = np.roll(current_values, -1)
            current_values[-1] = pred
        
        predictions = np.array(predictions)
        
        # Simple confidence intervals based on historical variance
        historical_std = np.std(self.training_history)
        z_score = stats.norm.ppf((1 + self.confidence_level) / 2)
        margin = z_score * historical_std
        
        lower_bounds = predictions - margin
        upper_bounds = predictions + margin
        
        return predictions, lower_bounds, upper_bounds


class ProphetModel(BaseForecastModel):
    """Facebook Prophet model wrapper"""
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.changepoint_prior_scale = 0.05
        self.seasonality_prior_scale = 10
        
    def fit(self, data: pd.Series, **kwargs) -> None:
        """Fit Prophet model"""
        try:
            # Import Prophet (optional dependency)
            from prophet import Prophet
            
            # Prepare data for Prophet
            df = pd.DataFrame({
                'ds': data.index,
                'y': data.values
            })
            
            # Initialize and fit model
            self.model = Prophet(
                changepoint_prior_scale=self.changepoint_prior_scale,
                seasonality_prior_scale=self.seasonality_prior_scale,
                interval_width=self.confidence_level
            )
            
            # Add seasonality components
            if len(data) >= 365:
                self.model.add_seasonality(name='yearly', period=365.25, fourier_order=10)
            if len(data) >= 30:
                self.model.add_seasonality(name='monthly', period=30.5, fourier_order=5)
            
            self.model.fit(df)
            self.is_fitted = True
            self.training_history = data.copy()
            
            logger.info("Prophet model fitted successfully")
            
        except ImportError:
            logger.error("Prophet not installed. Using fallback model.")
            # Fallback to exponential smoothing
            fallback = ExponentialSmoothingModel()
            fallback.fit(data)
            self.model = fallback
            self.is_fitted = True
            
        except Exception as e:
            logger.error(f"Prophet fitting failed: {e}")
            raise
    
    def predict(self, steps: int) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
        """Generate predictions with Prophet"""
        if not self.is_fitted:
            raise ValueError("Model must be fitted before prediction")
        
        # Check if using fallback model
        if isinstance(self.model, ExponentialSmoothingModel):
            return self.model.predict(steps)
        
        # Create future dataframe
        last_date = self.training_history.index[-1]
        future_dates = pd.date_range(
            start=last_date + timedelta(days=1),
            periods=steps,
            freq='D'
        )
        
        future_df = pd.DataFrame({'ds': future_dates})
        
        # Make predictions
        forecast = self.model.predict(future_df)
        
        predictions = forecast['yhat'].values
        lower_bounds = forecast['yhat_lower'].values
        upper_bounds = forecast['yhat_upper'].values
        
        return predictions, lower_bounds, upper_bounds


class EnsembleModel(BaseForecastModel):
    """Ensemble of multiple forecasting models"""
    
    def __init__(self, models: List[BaseForecastModel] = None, **kwargs):
        super().__init__(**kwargs)
        self.models = models or [
            ARIMAModel(),
            ExponentialSmoothingModel(),
            MovingAverageModel(window=7, weighted=True)
        ]
        self.weights = None
        
    def fit(self, data: pd.Series, optimize_weights: bool = True) -> None:
        """Fit all models in the ensemble"""
        successful_models = []
        
        for model in self.models:
            try:
                model.fit(data)
                successful_models.append(model)
                logger.info(f"Successfully fitted {model.__class__.__name__}")
            except Exception as e:
                logger.warning(f"Failed to fit {model.__class__.__name__}: {e}")
        
        if not successful_models:
            raise ValueError("No models could be fitted successfully")
        
        self.models = successful_models
        self.is_fitted = True
        self.training_history = data.copy()
        
        # Optimize weights if requested
        if optimize_weights and len(data) > 20:
            self._optimize_weights(data)
        else:
            # Equal weights
            self.weights = np.ones(len(self.models)) / len(self.models)
    
    def predict(self, steps: int) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
        """Generate ensemble predictions"""
        if not self.is_fitted:
            raise ValueError("Model must be fitted before prediction")
        
        all_predictions = []
        all_lower_bounds = []
        all_upper_bounds = []
        
        # Get predictions from each model
        for model in self.models:
            preds, lower, upper = model.predict(steps)
            all_predictions.append(preds)
            all_lower_bounds.append(lower)
            all_upper_bounds.append(upper)
        
        # Combine predictions using weights
        predictions = np.zeros(steps)
        lower_bounds = np.zeros(steps)
        upper_bounds = np.zeros(steps)
        
        for i, weight in enumerate(self.weights):
            predictions += weight * all_predictions[i]
            lower_bounds += weight * all_lower_bounds[i]
            upper_bounds += weight * all_upper_bounds[i]
        
        return predictions, lower_bounds, upper_bounds
    
    def _optimize_weights(self, data: pd.Series) -> None:
        """Optimize ensemble weights using cross-validation"""
        # Simple weight optimization based on recent performance
        n_test = min(14, len(data) // 5)
        train_data = data[:-n_test]
        test_data = data[-n_test:]
        
        errors = []
        
        for model in self.models:
            try:
                # Refit on training data
                model.fit(train_data)
                
                # Predict on test data
                preds, _, _ = model.predict(n_test)
                
                # Calculate error
                mae = mean_absolute_error(test_data, preds)
                errors.append(mae)
            except:
                errors.append(np.inf)
        
        # Convert errors to weights (inverse of errors)
        errors = np.array(errors)
        weights = 1 / (errors + 1e-10)
        self.weights = weights / weights.sum()
        
        # Refit all models on full data
        for model in self.models:
            model.fit(data)


class ModelFactory:
    """Factory for creating forecast models"""
    
    @staticmethod
    def create_model(model_type: str, **kwargs) -> BaseForecastModel:
        """Create a forecast model based on type"""
        models = {
            'arima': ARIMAModel,
            'exponential_smoothing': ExponentialSmoothingModel,
            'moving_average': MovingAverageModel,
            'prophet': ProphetModel,
            'ensemble': EnsembleModel
        }
        
        model_class = models.get(model_type.lower())
        if not model_class:
            raise ValueError(f"Unknown model type: {model_type}")
        
        return model_class(**kwargs)
    
    @staticmethod
    def auto_select_model(data: pd.Series) -> BaseForecastModel:
        """Automatically select the best model based on data characteristics"""
        data_length = len(data)
        
        # For very short series, use moving average
        if data_length < 14:
            return MovingAverageModel(window=min(7, data_length // 2))
        
        # For medium series, use exponential smoothing
        if data_length < 50:
            return ExponentialSmoothingModel()
        
        # For longer series, try ensemble
        return EnsembleModel()