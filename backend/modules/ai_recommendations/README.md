# AI Recommendations Module

## Overview

The AI Recommendations module provides intelligent, data-driven recommendations for menu pricing optimization and staffing level management. This module analyzes historical data, market conditions, and business metrics to help restaurants maximize profitability while maintaining optimal service levels.

## Architecture

### Module Structure

```
ai_recommendations/
├── __init__.py              # Module initialization
├── schemas/                 # Data models and validation
│   ├── __init__.py
│   ├── pricing_schemas.py   # Pricing recommendation models
│   └── staffing_schemas.py  # Staffing recommendation models
├── services/                # Business logic
│   ├── __init__.py
│   ├── pricing_recommendation_service.py   # Pricing algorithms
│   └── staffing_recommendation_service.py  # Staffing algorithms
├── routers/                 # API endpoints
│   ├── __init__.py
│   ├── pricing_router.py    # Pricing endpoints
│   └── staffing_router.py   # Staffing endpoints
└── tests/                   # Comprehensive test suite
    ├── __init__.py
    ├── test_pricing_service.py
    ├── test_staffing_service.py
    ├── test_routers.py
    └── test_integration.py
```

### Key Components

1. **Pricing Recommendation Service**
   - Dynamic pricing based on demand, competition, and costs
   - Multiple pricing strategies (demand-based, cost-plus, seasonal)
   - Price elasticity estimation
   - Revenue and profit impact analysis

2. **Staffing Recommendation Service**
   - Demand forecasting using historical patterns
   - Role-based staff requirement calculations
   - Labor cost optimization
   - Shift pattern recognition

### Integration Points

- **Analytics Module**: Provides historical insights and demand patterns
- **Menu Module**: Access to menu items and categories
- **Orders Module**: Historical order data for demand analysis
- **Staff Module**: Current staff data and shift information
- **Cache Service**: Performance optimization for frequent queries

## API Documentation

### Pricing Endpoints

#### Generate Bulk Pricing Recommendations

```http
POST /api/ai-recommendations/pricing/generate
```

Generates pricing recommendations for multiple menu items.

**Request Body:**
```json
{
  "menu_item_ids": [1, 2, 3],
  "category_ids": [1],
  "optimization_goal": "maximize_profit",
  "strategies_to_use": ["dynamic", "demand_based"],
  "max_price_increase_percent": 20.0,
  "max_price_decrease_percent": 15.0,
  "time_horizon_days": 7
}
```

**Response:**
```json
{
  "request_id": "pr_123456",
  "timestamp": "2025-01-29T10:00:00Z",
  "total_items_analyzed": 3,
  "total_recommendations": 2,
  "recommendations": [
    {
      "menu_item_id": 1,
      "item_name": "Grilled Salmon",
      "current_price": "24.99",
      "recommended_price": "27.49",
      "price_change_percentage": 10.0,
      "expected_revenue_impact": 8.5,
      "confidence_score": 0.85,
      "strategy_used": "demand_based",
      "primary_reason": "High demand with inelastic pricing"
    }
  ]
}
```

#### Get Category Pricing Recommendations

```http
GET /api/ai-recommendations/pricing/categories/{category_id}
```

Get pricing recommendations for all items in a category.

**Query Parameters:**
- `max_price_change`: Maximum price change percentage (default: 20)
- `optimization_goal`: Goal for optimization (default: maximize_profit)

#### Price Elasticity Insights (⚠️ MOCK DATA)

```http
GET /api/ai-recommendations/pricing/elasticity/insights
```

**Note:** This endpoint currently returns mock data for demonstration purposes.

**Response:**
```json
{
  "is_mock_data": true,
  "elasticity_summary": {
    "highly_elastic_items": 5,
    "elastic_items": 12,
    "unit_elastic_items": 8,
    "inelastic_items": 15,
    "highly_inelastic_items": 3
  },
  "insights": [
    {
      "category": "Appetizers",
      "avg_elasticity": -1.2,
      "recommendation": "Consider moderate price increases"
    }
  ]
}
```

#### Competitor Price Analysis (⚠️ MOCK DATA)

```http
GET /api/ai-recommendations/pricing/competitor-analysis
```

**Note:** This endpoint currently returns mock data. Future integration with external data sources planned.

### Staffing Endpoints

#### Optimize Staffing

```http
POST /api/ai-recommendations/staffing/optimize
```

Generate optimal staffing recommendations for a date range.

**Request Body:**
```json
{
  "start_date": "2025-02-01",
  "end_date": "2025-02-07",
  "primary_goal": "minimize_cost",
  "service_level_target": 0.90,
  "max_weekly_hours_per_staff": 40,
  "buffer_percentage": 10.0
}
```

**Response:**
```json
{
  "request_id": "st_789012",
  "period_start": "2025-02-01",
  "period_end": "2025-02-07",
  "total_recommended_hours": 280.0,
  "total_estimated_cost": "5250.00",
  "daily_recommendations": [
    {
      "date": "2025-02-01",
      "day_of_week": "Saturday",
      "staff_requirements": [
        {
          "role": "chef",
          "min_required": 2,
          "optimal": 3,
          "max_useful": 4
        }
      ],
      "shift_recommendations": [
        {
          "shift_type": "morning",
          "start_time": "06:00",
          "end_time": "14:00",
          "staff_assignments": [
            {"role": "chef", "count": 2}
          ]
        }
      ]
    }
  ]
}
```

#### Get Daily Staffing Recommendation

```http
GET /api/ai-recommendations/staffing/daily/{date}
```

Get staffing recommendations for a specific date.

#### Labor Cost Analysis

```http
GET /api/ai-recommendations/staffing/labor-cost/analysis
```

Analyze labor costs and optimization opportunities.

#### Staffing Patterns (⚠️ MOCK DATA)

```http
GET /api/ai-recommendations/staffing/patterns
```

**Note:** Pattern recognition currently uses simplified algorithms. Machine learning integration planned.

## Usage Examples

### Example 1: Optimize Pricing for High-Demand Items

```python
# Python client example
import requests

# Identify high-demand items from analytics
high_demand_items = [101, 102, 103]

# Generate pricing recommendations
response = requests.post(
    "https://api.auraconnect.ai/ai-recommendations/pricing/generate",
    json={
        "menu_item_ids": high_demand_items,
        "optimization_goal": "maximize_revenue",
        "strategies_to_use": ["demand_based", "dynamic"],
        "max_price_increase_percent": 15.0,
        "time_horizon_days": 14
    },
    headers={"Authorization": "Bearer YOUR_TOKEN"}
)

recommendations = response.json()
for rec in recommendations["recommendations"]:
    if rec["confidence_score"] > 0.8:
        print(f"{rec['item_name']}: ${rec['current_price']} → ${rec['recommended_price']}")
        print(f"Expected revenue impact: {rec['expected_revenue_impact']}%")
```

### Example 2: Optimize Weekend Staffing

```python
# Optimize staffing for busy weekend
response = requests.post(
    "https://api.auraconnect.ai/ai-recommendations/staffing/optimize",
    json={
        "start_date": "2025-02-01",  # Saturday
        "end_date": "2025-02-02",    # Sunday
        "primary_goal": "balanced",
        "service_level_target": 0.95,  # Higher target for weekends
        "buffer_percentage": 15.0      # Extra buffer for unexpected rush
    },
    headers={"Authorization": "Bearer YOUR_TOKEN"}
)

staffing = response.json()
for day in staffing["daily_recommendations"]:
    print(f"\n{day['date']} - {day['day_of_week']}:")
    print(f"Estimated labor cost: ${day['estimated_labor_cost']}")
    print(f"Staffing level: {day['staffing_level']}")
    
    for req in day["staff_requirements"]:
        print(f"  {req['role']}: {req['optimal']} staff needed")
```

### Example 3: Analyze Price Sensitivity

```python
# Check price elasticity before making changes
response = requests.get(
    "https://api.auraconnect.ai/ai-recommendations/pricing/elasticity/insights",
    params={"category_id": 5},  # Desserts category
    headers={"Authorization": "Bearer YOUR_TOKEN"}
)

elasticity = response.json()
if elasticity["is_mock_data"]:
    print("Note: Using demonstration data")

for insight in elasticity["insights"]:
    if insight["avg_elasticity"] < -1.5:  # Highly elastic
        print(f"{insight['category']}: Customers are price-sensitive")
        print(f"Recommendation: {insight['recommendation']}")
```

## Configuration

### Environment Variables

```bash
# Pricing optimization settings
AI_PRICING_DEFAULT_MARGIN=0.70          # Default target margin (70%)
AI_PRICING_MAX_INCREASE=50.0            # Maximum allowed price increase (%)
AI_PRICING_MAX_DECREASE=30.0            # Maximum allowed price decrease (%)
AI_PRICING_CACHE_TTL=3600               # Cache TTL in seconds

# Staffing optimization settings
AI_STAFFING_FORECAST_HORIZON=90         # Days of historical data to analyze
AI_STAFFING_MIN_SHIFT_HOURS=4.0         # Minimum shift length
AI_STAFFING_MAX_SHIFT_HOURS=10.0        # Maximum shift length
AI_STAFFING_OVERTIME_THRESHOLD=40       # Weekly hours before overtime

# Feature flags
AI_ENABLE_ML_MODELS=false               # Enable ML model integration
AI_ENABLE_EXTERNAL_DATA=false           # Enable external data sources
```

### Permissions

All endpoints require authentication and appropriate permissions:

- **View Recommendations**: `analytics.view` permission
- **Apply Recommendations**: `analytics.admin` permission
- **Configure Settings**: `system.admin` permission

## Performance Considerations

1. **Caching Strategy**
   - Recommendations are cached for 1 hour by default
   - Cache keys include all request parameters
   - Cache is invalidated on menu or pricing changes

2. **Query Optimization**
   - Bulk operations process up to 100 items at once
   - Historical data queries are limited to 90 days
   - Demand forecasts use aggregated hourly data

3. **Scalability**
   - Async processing for large datasets
   - Configurable timeouts for long-running operations
   - Rate limiting: 100 requests per minute per user

## Limitations and Future Enhancements

### Current Limitations

1. **Mock Data Endpoints**
   - Price elasticity calculations use simplified models
   - Competitor analysis returns demonstration data
   - Weather impact analysis not yet implemented

2. **Algorithm Limitations**
   - Demand forecasting uses moving averages (ML models planned)
   - Seasonality detection is rule-based
   - No real-time adjustment capabilities

### Planned Enhancements

1. **Q2 2025**
   - Machine learning model integration
   - Real-time demand adjustment
   - External data source integration (weather, events)

2. **Q3 2025**
   - A/B testing framework for pricing
   - Multi-location optimization
   - Advanced staffing patterns with ML

3. **Q4 2025**
   - Automated recommendation application
   - Predictive maintenance for equipment
   - Customer segment-based pricing

## Troubleshooting

### Common Issues

1. **"No recommendations generated"**
   - Ensure items have sufficient historical data (7+ days)
   - Check that items are active and available
   - Verify pricing constraints aren't too restrictive

2. **"Insufficient data for analysis"**
   - Minimum 7 days of order history required
   - At least 10 orders per item for reliable analysis
   - Staff recommendations need shift history

3. **"Cache timeout errors"**
   - Large datasets may exceed timeout
   - Try smaller date ranges or item batches
   - Contact support for limit increases

### Debug Mode

Enable debug logging for detailed analysis:

```python
import logging
logging.basicConfig(level=logging.DEBUG)
```

## Support

For issues or questions:
- API Documentation: https://docs.auraconnect.ai/api/ai-recommendations
- Support Email: support@auraconnect.ai
- GitHub Issues: https://github.com/auraconnectai/auraconnect/issues