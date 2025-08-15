# backend/modules/analytics/constants.py

"""
Constants for analytics module.

Centralizes all configuration values and thresholds.
"""

# Batch Processing Limits
MAX_BATCH_SIZE = 100  # Maximum entities per batch forecast
MAX_PRODUCTS_PER_OPTIMIZATION = 50  # Maximum products per stock optimization
MAX_EXPORT_ROWS = 100000  # Maximum rows for report export

# Time Limits
MAX_HISTORICAL_DAYS = 365  # Maximum days of historical data to analyze
DEFAULT_HORIZON_DAYS = 7  # Default forecast horizon
MIN_HORIZON_DAYS = 1
MAX_HORIZON_DAYS = 90

# Cache Configuration
CACHE_TTL_SECONDS = 300  # 5 minutes cache TTL for forecasts
REPORT_CACHE_TTL = 3600  # 1 hour cache for reports
MODEL_CACHE_TTL = 1800  # 30 minutes cache for trained models

# Model Configuration
MIN_DATA_POINTS_FOR_FORECAST = 7  # Minimum historical points needed
MIN_DATA_POINTS_FOR_SEASONAL = 30  # Minimum points for seasonal detection
MODEL_SELECTION_THRESHOLDS = {
    "short_series": 20,  # Use simple models
    "medium_series": 60,  # Use advanced models
    "long_series": 180,  # Use ensemble models
}

# Stock Optimization
DEFAULT_SERVICE_LEVEL = 0.95  # 95% service level
MIN_SERVICE_LEVEL = 0.80
MAX_SERVICE_LEVEL = 0.99
DEFAULT_LEAD_TIME_DAYS = 2
DEFAULT_HOLDING_COST_RATE = 0.20  # 20% annual holding cost

# Accuracy Thresholds
MIN_ACCURACY_THRESHOLD = 0.70  # 70% minimum acceptable accuracy
GOOD_ACCURACY_THRESHOLD = 0.85  # 85% good accuracy
EXCELLENT_ACCURACY_THRESHOLD = 0.95  # 95% excellent accuracy

# Alert Thresholds
STOCKOUT_CRITICAL_DAYS = 2  # Days until stockout for critical alert
STOCKOUT_WARNING_DAYS = 7  # Days until stockout for warning
OVERSTOCK_THRESHOLD = 5.0  # 5x normal demand = overstock
ACCURACY_DEGRADATION_THRESHOLD = 0.15  # 15% drop triggers alert

# Anomaly Detection
ANOMALY_DETECTION_WINDOW_DAYS = 7  # Look back window for anomalies
ANOMALY_STD_MULTIPLIER = 2.5  # Standard deviations for anomaly
MIN_SAMPLES_FOR_ANOMALY = 5  # Minimum samples needed

# Performance Monitoring
SLOW_QUERY_THRESHOLD_MS = 1000  # 1 second for slow query warning
MAX_FORECAST_COMPUTATION_TIME_MS = 5000  # 5 seconds max per forecast

# Real-time Updates
REALTIME_UPDATE_INTERVALS = {
    "demand_forecast": 300,  # 5 minutes
    "stock_alert": 60,  # 1 minute
    "insight": 600,  # 10 minutes
    "anomaly_check": 900,  # 15 minutes
}

# Rate Limiting
RATE_LIMIT_REQUESTS_PER_MINUTE = {
    "forecast": 60,
    "batch_forecast": 10,
    "optimization": 30,
    "export": 5,
}

# Export Configuration
EXPORT_FORMATS = ["csv", "xlsx", "json", "pdf"]
MAX_EXPORT_FILE_SIZE_MB = 50
EXPORT_CHUNK_SIZE = 10000  # Rows per chunk for streaming

# Severity Levels
SEVERITY_LEVELS = {"low": 1, "medium": 2, "high": 3, "critical": 4}

# External Factors
WEATHER_IMPACT_THRESHOLDS = {
    "hot": {"temp": 30, "multiplier": 1.1},  # >30°C increases demand by 10%
    "cold": {"temp": 10, "multiplier": 0.9},  # <10°C decreases demand by 10%
    "rain": {"multiplier": 0.85},  # Rain decreases demand by 15%
}

# Model Types (for validation)
VALID_MODEL_TYPES = [
    "arima",
    "exponential_smoothing",
    "prophet",
    "moving_average",
    "ensemble",
]

# Entity Types
VALID_ENTITY_TYPES = ["product", "category", "overall", "location"]

# Time Granularities
VALID_TIME_GRANULARITIES = ["hourly", "daily", "weekly", "monthly"]

# Optimization Objectives
VALID_OPTIMIZATION_OBJECTIVES = ["minimize_cost", "maximize_service", "balanced"]

# Database Query Limits
MAX_QUERY_RESULTS = 10000  # Maximum results per query
CHUNK_SIZE_FOR_BATCH_INSERT = 1000  # Records per batch insert

# Logging Configuration
LOG_SLOW_OPERATIONS = True
LOG_ACCURACY_METRICS = True
LOG_CACHE_HITS = False  # Set to True for debugging

# Feature Flags
ENABLE_PROPHET_MODEL = True  # Requires additional dependency
ENABLE_NEURAL_MODELS = False  # Future enhancement
ENABLE_AUTO_RETRAIN = True  # Automatic model retraining
ENABLE_EXTERNAL_FACTORS = True  # Weather, events, etc.

# Validation Rules
MIN_PRODUCT_NAME_LENGTH = 3
MAX_PRODUCT_NAME_LENGTH = 100
MIN_FORECAST_VALUE = 0  # No negative forecasts
MAX_FORECAST_VALUE = 1000000  # Sanity check

# Error Messages
ERROR_MESSAGES = {
    "insufficient_data": "Insufficient historical data for forecasting. Need at least {min_points} data points.",
    "invalid_entity": "Entity {entity_type} with ID {entity_id} not found.",
    "forecast_failed": "Failed to generate forecast. Please try again later.",
    "optimization_failed": "Stock optimization failed. Check product data and try again.",
    "invalid_date_range": "Invalid date range. End date must be after start date.",
    "rate_limit_exceeded": "Rate limit exceeded. Please wait {retry_after} seconds.",
    "unauthorized": "You don't have permission to access this resource.",
}
