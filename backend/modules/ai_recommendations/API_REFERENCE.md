# AI Recommendations API Reference

## Mock Endpoints Notice

⚠️ **Important**: Several endpoints in this module currently return mock/demonstration data. These are clearly marked with the ⚠️ symbol and include an `is_mock_data: true` field in their responses. These endpoints are placeholders for future ML/AI integrations.

## Pricing Recommendation Endpoints

### 1. Generate Bulk Pricing Recommendations

```http
POST /api/ai-recommendations/pricing/generate
```

Generates AI-powered pricing recommendations for menu items.

#### Request

```json
{
  "menu_item_ids": [1, 2, 3],          // Optional: Specific items
  "category_ids": [1, 2],             // Optional: All items in categories
  "optimization_goal": "maximize_profit", // Options: maximize_profit, maximize_revenue, balanced
  "strategies_to_use": [              // Optional: Specific strategies
    "dynamic",
    "demand_based",
    "competition_based",
    "cost_plus",
    "seasonal"
  ],
  "max_price_increase_percent": 20.0, // Default: 20%
  "max_price_decrease_percent": 15.0, // Default: 15%
  "round_to_nearest": "0.05",         // Default: 0.05
  "time_horizon_days": 7,             // Default: 7 days
  "min_confidence_score": 0.7         // Default: 0.7
}
```

#### Response

```json
{
  "request_id": "pr_550e8400-e29b-41d4-a716-446655440000",
  "timestamp": "2025-01-29T10:30:00Z",
  "total_items_analyzed": 25,
  "total_recommendations": 12,
  "recommendations": [
    {
      "menu_item_id": 101,
      "item_name": "Grilled Salmon",
      "category_name": "Main Courses",
      "current_price": "24.99",
      "recommended_price": "27.49",
      "min_recommended_price": "26.99",
      "max_recommended_price": "28.99",
      "price_change_percentage": 10.0,
      "expected_demand_change": -3.5,
      "expected_revenue_impact": 6.2,
      "expected_profit_impact": 8.1,
      "confidence_score": 0.85,
      "strategy_used": "demand_based",
      "factors_considered": [
        "high_demand",
        "low_price_sensitivity",
        "premium_positioning",
        "competitor_pricing"
      ],
      "primary_reason": "High demand with inelastic pricing allows for revenue optimization",
      "detailed_reasoning": [
        "Current demand is 35% above category average",
        "Price elasticity coefficient of -0.4 indicates low sensitivity",
        "Competitor average price is $28.50",
        "Last price increase was 8 months ago"
      ],
      "risks": [
        "Potential customer perception issue if increase is too sudden",
        "May need promotional campaign to ease transition"
      ],
      "implementation_notes": "Consider phased rollout over 2 weeks"
    }
  ],
  "summary": {
    "avg_price_change_percent": 7.5,
    "total_expected_revenue_impact": "$4,250",
    "total_expected_profit_impact": "$5,100",
    "recommendations_by_strategy": {
      "demand_based": 5,
      "dynamic": 4,
      "cost_plus": 3
    }
  },
  "cache_ttl_seconds": 3600
}
```

#### Error Responses

- `400 Bad Request`: Invalid parameters or constraints
- `403 Forbidden`: Insufficient permissions
- `404 Not Found`: Menu items or categories not found
- `500 Internal Server Error`: Processing error

---

### 2. Get Category Pricing Recommendations

```http
GET /api/ai-recommendations/pricing/categories/{category_id}
```

Convenience endpoint for category-specific pricing recommendations.

#### Parameters

- `category_id` (path): Menu category ID
- `max_price_change` (query): Maximum price change percentage (default: 20)
- `optimization_goal` (query): Goal for optimization (default: maximize_profit)
- `include_inactive` (query): Include inactive items (default: false)

---

### 3. Apply Pricing Recommendation ⚠️

```http
POST /api/ai-recommendations/pricing/apply/{recommendation_id}
```

**Note**: Currently returns mock implementation. Actual price updates pending integration.

#### Request

```json
{
  "effective_date": "2025-02-01",
  "notes": "Applying recommendation based on Q1 analysis",
  "notify_customers": true
}
```

#### Response

```json
{
  "is_mock_data": true,
  "recommendation_id": "pr_123",
  "status": "pending_implementation",
  "message": "This is a mock response. Actual implementation pending.",
  "rollback_token": "mock_rb_token_123"
}
```

---

### 4. Get Price Elasticity Insights ⚠️

```http
GET /api/ai-recommendations/pricing/elasticity/insights
```

**Note**: Returns demonstration data. ML-based elasticity calculation planned for Q2 2025.

#### Parameters

- `category_id` (query): Filter by category
- `days_back` (query): Historical days to analyze (default: 90)

#### Response

```json
{
  "is_mock_data": true,
  "generated_at": "2025-01-29T10:30:00Z",
  "elasticity_summary": {
    "highly_elastic_items": 5,
    "elastic_items": 12,
    "unit_elastic_items": 8,
    "inelastic_items": 15,
    "highly_inelastic_items": 3,
    "total_items_analyzed": 43
  },
  "insights": [
    {
      "category": "Appetizers",
      "category_id": 1,
      "avg_elasticity": -1.2,
      "elasticity_range": {
        "min": -2.1,
        "max": -0.4
      },
      "interpretation": "Moderately elastic",
      "recommendation": "Small price increases (3-5%) unlikely to significantly impact demand",
      "high_performers": [
        {
          "item_name": "Calamari",
          "elasticity": -0.4,
          "current_price": "12.99"
        }
      ]
    }
  ],
  "methodology_note": "Elasticity calculations based on simplified demand curves. Advanced ML models coming Q2 2025."
}
```

---

### 5. Get Competitor Price Analysis ⚠️

```http
GET /api/ai-recommendations/pricing/competitor-analysis
```

**Note**: Mock endpoint. External data integration planned for Q3 2025.

#### Response

```json
{
  "is_mock_data": true,
  "last_updated": "2025-01-29T00:00:00Z",
  "disclaimer": "This is demonstration data. Real competitor analysis requires external data sources.",
  "market_position": "competitive",
  "overall_price_index": 0.98,
  "categories": [
    {
      "name": "Appetizers",
      "our_avg_price": "11.50",
      "market_avg_price": "12.25",
      "price_index": 0.94,
      "recommendation": "Prices below market average - opportunity for selective increases"
    }
  ],
  "data_sources_note": "Future integration with market data providers planned"
}
```

---

## Staffing Recommendation Endpoints

### 1. Optimize Staffing

```http
POST /api/ai-recommendations/staffing/optimize
```

Generates optimal staffing recommendations based on demand forecasts.

#### Request

```json
{
  "start_date": "2025-02-01",
  "end_date": "2025-02-07",
  "primary_goal": "minimize_cost",     // Options: minimize_cost, maximize_service, balanced
  "service_level_target": 0.90,        // Target service level (0-1)
  "constraints": {
    "max_weekly_hours_per_staff": 40,
    "min_shift_length_hours": 4.0,
    "max_shift_length_hours": 10.0,
    "required_breaks": {
      "duration_minutes": 30,
      "after_hours": 6
    }
  },
  "buffer_percentage": 10.0,           // Safety buffer for demand
  "include_flexibility_analysis": true
}
```

#### Response

```json
{
  "request_id": "st_660e8400-e29b-41d4-a716-446655440000",
  "generated_at": "2025-01-29T10:30:00Z",
  "period_start": "2025-02-01",
  "period_end": "2025-02-07",
  "optimization_goal": "minimize_cost",
  "total_recommended_hours": 280.0,
  "total_estimated_cost": "5250.00",
  "average_labor_percentage": 26.5,
  "service_level_achievement": 0.92,
  "daily_recommendations": [
    {
      "date": "2025-02-01",
      "day_of_week": "Saturday",
      "is_holiday": false,
      "demand_forecasts": [
        {
          "hour": 12,
          "predicted_orders": 65,
          "predicted_revenue": "975.50",
          "confidence_level": 0.88
        }
      ],
      "staff_requirements": [
        {
          "role": "manager",
          "min_required": 1,
          "optimal": 1,
          "max_useful": 2,
          "current_scheduled": 1,
          "gap": 0
        },
        {
          "role": "chef",
          "min_required": 2,
          "optimal": 3,
          "max_useful": 4,
          "current_scheduled": 2,
          "gap": 1
        }
      ],
      "shift_recommendations": [
        {
          "shift_type": "morning",
          "start_time": "06:00",
          "end_time": "14:00",
          "staff_assignments": [
            {"role": "manager", "count": 1},
            {"role": "chef", "count": 2},
            {"role": "server", "count": 3}
          ],
          "expected_demand_coverage": 0.95
        }
      ],
      "estimated_labor_cost": "875.00",
      "labor_percentage": 28.5,
      "staffing_level": "optimal",
      "risks": []
    }
  ],
  "patterns_identified": [
    {
      "pattern_name": "Weekend Rush",
      "days_affected": ["Saturday", "Sunday"],
      "peak_hours": [12, 13, 18, 19],
      "recommended_adjustment": "Increase server staff by 25% during peak"
    }
  ],
  "optimization_opportunities": [
    {
      "opportunity": "Cross-training",
      "potential_savings": "350.00",
      "description": "Cross-train 2 servers for host duties to improve flexibility"
    }
  ]
}
```

---

### 2. Get Daily Staffing Recommendation

```http
GET /api/ai-recommendations/staffing/daily/{date}
```

Get detailed staffing recommendation for a specific date.

#### Parameters

- `date` (path): Target date (YYYY-MM-DD)
- `include_flexibility` (query): Include flexibility analysis (default: false)
- `compare_to_current` (query): Compare with current schedule (default: true)

---

### 3. Get Weekly Staffing Recommendation

```http
GET /api/ai-recommendations/staffing/weekly
```

Get staffing recommendations for the upcoming week.

#### Parameters

- `start_date` (query): Week start date (default: next Monday)
- `include_patterns` (query): Include pattern analysis (default: true)

---

### 4. Get Labor Cost Analysis

```http
GET /api/ai-recommendations/staffing/labor-cost/analysis
```

Analyze labor costs and identify optimization opportunities.

#### Parameters

- `start_date` (query): Analysis start date
- `end_date` (query): Analysis end date  
- `compare_to_budget` (query): Compare with budget targets (default: false)
- `group_by` (query): Grouping option (day, week, role)

#### Response

```json
{
  "period": {
    "start": "2025-02-01",
    "end": "2025-02-07"
  },
  "days_analyzed": 7,
  "current_staffing": {
    "total_hours": 260.0,
    "total_cost": "4875.00",
    "avg_labor_percentage": 24.5,
    "understaffed_periods": 12,
    "overstaffed_periods": 8
  },
  "recommended_staffing": {
    "total_hours": 280.0,
    "total_cost": "5250.00",
    "avg_labor_percentage": 26.5,
    "service_level": 0.92
  },
  "cost_breakdown_by_role": [
    {
      "role": "manager",
      "current_hours": 56,
      "recommended_hours": 56,
      "hourly_rate": "25.00",
      "current_cost": "1400.00",
      "recommended_cost": "1400.00"
    }
  ],
  "optimization_opportunities": [
    {
      "type": "shift_consolidation",
      "description": "Combine two 4-hour shifts into one 8-hour shift",
      "potential_savings": "75.00",
      "implementation_difficulty": "easy"
    }
  ],
  "high_cost_periods": [
    {
      "date": "2025-02-01",
      "hour": 19,
      "labor_percentage": 32.5,
      "reason": "Overstaffed relative to actual demand"
    }
  ]
}
```

---

### 5. Get Staffing Patterns ⚠️

```http
GET /api/ai-recommendations/staffing/patterns
```

**Note**: Basic pattern recognition only. ML-based pattern analysis planned for Q3 2025.

#### Response

```json
{
  "is_mock_data": true,
  "patterns": [
    {
      "pattern_id": "p_001",
      "name": "Weekday Lunch Rush",
      "confidence": 0.75,
      "characteristics": {
        "days": ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"],
        "peak_hours": [12, 13],
        "avg_order_increase": "45%",
        "duration_minutes": 120
      },
      "staffing_impact": {
        "additional_servers_needed": 2,
        "additional_kitchen_staff_needed": 1
      },
      "frequency": "daily",
      "last_observed": "2025-01-28"
    }
  ],
  "analysis_note": "Pattern detection using basic statistical analysis. Advanced ML models coming Q3 2025."
}
```

---

## Common Response Headers

 All endpoints include these headers:

```http
X-Request-ID: 550e8400-e29b-41d4-a716-446655440000
X-RateLimit-Limit: 100
X-RateLimit-Remaining: 98
X-RateLimit-Reset: 1706526600
Cache-Control: private, max-age=3600
```

## Rate Limiting

- **Default Limit**: 100 requests per minute per user
- **Bulk Operations**: Count as 5 requests
- **Premium Accounts**: 500 requests per minute

## Webhooks

Configure webhooks to receive notifications:

```json
{
  "event": "recommendation.generated",
  "data": {
    "request_id": "pr_550e8400",
    "type": "pricing",
    "items_affected": 25,
    "high_confidence_count": 12
  }
}
```

## SDKs and Code Examples

Official SDKs available:
- Python: `pip install auraconnect-ai`
- JavaScript: `npm install @auraconnect/ai-recommendations`
- Go: `go get github.com/auraconnect/ai-sdk-go`

See [SDK Documentation](https://github.com/auraconnectai/sdk-docs) for examples.