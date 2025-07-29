# Promotion System API Documentation

## Overview

The Promotion System provides comprehensive functionality for managing promotions, coupons, referral programs, A/B testing, and analytics. This API is designed for high-volume, production environments with enterprise-grade features.

## Base URL

```
https://api.auraconnect.ai/api/v1
```

## Authentication

All API endpoints require authentication using Bearer tokens:

```http
Authorization: Bearer YOUR_ACCESS_TOKEN
```

## Rate Limiting

The API implements rate limiting to ensure fair usage:

- **General API requests**: 100 requests per hour per client
- **Coupon operations**: 10 requests per hour per client (strict limit to prevent brute force)
- **Discount calculations**: 50 requests per hour per client
- **Bulk operations**: 5 requests per hour per client

Rate limit headers are included in responses:
```http
X-RateLimit-Limit: 100
X-RateLimit-Remaining: 95
X-RateLimit-Reset: 2024-01-01T12:00:00Z
```

## Idempotency

For mutation operations (POST, PUT, PATCH), you can provide an idempotency key to ensure the same operation isn't performed twice:

```http
Idempotency-Key: unique-operation-identifier
```

## Error Handling

The API uses standard HTTP status codes and returns detailed error information:

```json
{
    "error": "Validation failed",
    "detail": "Promotion name is required",
    "code": "VALIDATION_ERROR",
    "timestamp": "2024-01-01T12:00:00Z"
}
```

Common status codes:
- `200` - Success
- `201` - Created
- `400` - Bad Request
- `401` - Unauthorized
- `403` - Forbidden
- `404` - Not Found
- `422` - Validation Error
- `429` - Rate Limit Exceeded
- `500` - Internal Server Error

---

# Promotions API

## Create Promotion

Create a new promotion with comprehensive configuration options.

**POST** `/promotions/`

### Request Body

```json
{
    "name": "Summer Sale 2024",
    "description": "Great summer discounts on all products",
    "promotion_type": "percentage_discount",
    "discount_type": "percentage",
    "discount_value": 25.0,
    "start_date": "2024-06-01T00:00:00Z",
    "end_date": "2024-08-31T23:59:59Z",
    "max_uses": 1000,
    "minimum_order_amount": 50.0,
    "maximum_discount_amount": 100.0,
    "priority": 5,
    "can_stack": true,
    "target_customer_segments": ["premium", "loyal"],
    "applicable_categories": [1, 2, 3],
    "metadata": {
        "campaign_id": "SUMMER2024",
        "marketing_channel": "email"
    }
}
```

### Request Fields

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `name` | string | Yes | Promotion name (max 200 chars) |
| `description` | string | No | Detailed description |
| `promotion_type` | enum | Yes | Type of promotion |
| `discount_type` | enum | Yes | How discount is calculated |
| `discount_value` | float | Yes | Discount amount/percentage |
| `start_date` | datetime | Yes | When promotion becomes active |
| `end_date` | datetime | Yes | When promotion expires |
| `max_uses` | integer | No | Maximum total uses (null = unlimited) |
| `minimum_order_amount` | float | No | Minimum order value required |
| `maximum_discount_amount` | float | No | Cap on discount amount |
| `priority` | integer | No | Priority for stacking (higher = applied first) |
| `can_stack` | boolean | No | Whether promotion can stack with others |
| `target_customer_segments` | array | No | Customer segments to target |
| `applicable_categories` | array | No | Product category IDs |
| `metadata` | object | No | Additional metadata |

### Promotion Types

- `percentage_discount` - Percentage off order total
- `fixed_amount_discount` - Fixed dollar amount off
- `buy_one_get_one` - BOGO offers
- `tiered_discount` - Discount based on order amount tiers
- `free_shipping` - Free shipping promotion
- `cashback` - Cashback rewards

### Response

```json
{
    "id": 123,
    "uuid": "550e8400-e29b-41d4-a716-446655440000",
    "name": "Summer Sale 2024",
    "status": "draft",
    "created_at": "2024-01-01T12:00:00Z",
    "updated_at": "2024-01-01T12:00:00Z",
    // ... other fields
}
```

---

## Get Promotion

Retrieve a specific promotion by ID.

**GET** `/promotions/{promotion_id}`

### Response

```json
{
    "id": 123,
    "uuid": "550e8400-e29b-41d4-a716-446655440000",
    "name": "Summer Sale 2024",
    "description": "Great summer discounts on all products",
    "promotion_type": "percentage_discount",
    "discount_type": "percentage",
    "discount_value": 25.0,
    "status": "active",
    "start_date": "2024-06-01T00:00:00Z",
    "end_date": "2024-08-31T23:59:59Z",
    "max_uses": 1000,
    "current_uses": 150,
    "minimum_order_amount": 50.0,
    "priority": 5,
    "can_stack": true,
    "created_at": "2024-01-01T12:00:00Z",
    "updated_at": "2024-01-01T12:30:00Z"
}
```

---

## List Promotions

Retrieve a paginated list of promotions with filtering and sorting.

**GET** `/promotions/`

### Query Parameters

| Parameter | Type | Description |
|-----------|------|-------------|
| `status` | string | Filter by status (active, draft, paused, etc.) |
| `promotion_type` | string | Filter by promotion type |
| `search` | string | Search in name and description |
| `page` | integer | Page number (default: 1) |
| `per_page` | integer | Items per page (default: 20, max: 100) |
| `sort_by` | string | Sort field (name, created_at, priority, etc.) |
| `sort_order` | string | Sort direction (asc, desc) |
| `start_date_from` | datetime | Filter promotions starting after this date |
| `start_date_to` | datetime | Filter promotions starting before this date |

### Response

```json
{
    "items": [
        {
            "id": 123,
            "name": "Summer Sale 2024",
            "status": "active",
            "discount_value": 25.0,
            "current_uses": 150,
            "max_uses": 1000,
            "created_at": "2024-01-01T12:00:00Z"
        }
    ],
    "pagination": {
        "page": 1,
        "per_page": 20,
        "total_items": 45,
        "total_pages": 3,
        "has_next": true,
        "has_prev": false
    }
}
```

---

## Update Promotion

Update an existing promotion.

**PUT** `/promotions/{promotion_id}`

### Request Body

Same as create promotion, but all fields are optional. Only provided fields will be updated.

---

## Activate Promotion

Activate a draft promotion.

**POST** `/promotions/{promotion_id}/activate`

### Response

```json
{
    "success": true,
    "message": "Promotion activated successfully",
    "promotion": {
        "id": 123,
        "status": "active",
        "activated_at": "2024-01-01T12:00:00Z"
    }
}
```

---

## Calculate Discount

Calculate the discount amount for a specific promotion and order.

**POST** `/promotions/{promotion_id}/calculate-discount`

### Request Body

```json
{
    "order_items": [
        {
            "product_id": 1,
            "quantity": 2,
            "unit_price": 29.99,
            "subtotal": 59.98,
            "category_id": 5
        }
    ],
    "customer_id": 456,
    "existing_discounts": 10.0
}
```

### Response

```json
{
    "discount_amount": 15.0,
    "applicable": true,
    "reason": "25% discount applied to eligible items",
    "calculation_details": {
        "base_amount": 59.98,
        "discount_percentage": 25.0,
        "maximum_discount": 100.0,
        "applied_discount": 15.0
    }
}
```

---

# Coupons API

## Create Coupon

Create a single coupon for a promotion.

**POST** `/coupons/{promotion_id}`

### Request Body

```json
{
    "code": "SUMMER25",
    "max_uses": 100,
    "max_uses_per_customer": 1,
    "expires_at": "2024-08-31T23:59:59Z",
    "metadata": {
        "campaign": "summer_email"
    }
}
```

---

## Create Bulk Coupons

Generate multiple coupons at once.

**POST** `/coupons/bulk/{promotion_id}`

### Request Body

```json
{
    "count": 1000,
    "coupon_config": {
        "max_uses": 1,
        "max_uses_per_customer": 1,
        "expires_at": "2024-08-31T23:59:59Z",
        "code_length": 8,
        "code_prefix": "SUMMER",
        "exclude_ambiguous": true
    }
}
```

### Response

```json
{
    "success": true,
    "coupons_created": 1000,
    "generation_time": "2.5s",
    "coupons": [
        {
            "id": 1001,
            "code": "SUMMERX4K9",
            "status": "active",
            "max_uses": 1,
            "created_at": "2024-01-01T12:00:00Z"
        }
        // ... more coupons
    ]
}
```

---

## Validate Coupon

Check if a coupon is valid for a customer.

**POST** `/coupons/validate/{coupon_code}`

### Request Body

```json
{
    "customer_id": 456,
    "order_amount": 75.00
}
```

### Response

```json
{
    "is_valid": true,
    "reason": "Valid",
    "coupon": {
        "id": 1001,
        "code": "SUMMER25",
        "promotion_id": 123,
        "max_uses": 100,
        "current_uses": 45,
        "expires_at": "2024-08-31T23:59:59Z"
    },
    "promotion": {
        "id": 123,
        "name": "Summer Sale 2024",
        "discount_value": 25.0
    }
}
```

---

# Referral Programs API

## Create Referral Program

**POST** `/referrals/programs/`

### Request Body

```json
{
    "name": "Friend Referral Program",
    "description": "Refer friends and earn rewards",
    "referrer_reward_type": "points",
    "referrer_reward_value": 100,
    "referee_reward_type": "discount",
    "referee_reward_value": 10.0,
    "status": "active",
    "max_referrals_per_customer": 10,
    "referral_conditions": {
        "min_referee_purchase": 25.0,
        "referee_must_be_new_customer": true
    }
}
```

### Reward Types

- `points` - Loyalty points
- `discount` - Percentage discount
- `fixed_amount` - Fixed dollar amount
- `free_shipping` - Free shipping voucher
- `cashback` - Cash reward

---

## Generate Referral Code

**POST** `/referrals/programs/{program_id}/generate-code/{customer_id}`

### Response

```json
{
    "referral_code": "REF-ALICE-X9K4",
    "referral_url": "https://app.example.com/signup?ref=REF-ALICE-X9K4",
    "qr_code_url": "https://api.example.com/qr/REF-ALICE-X9K4",
    "expires_at": "2024-12-31T23:59:59Z"
}
```

---

## Process Referral

Handle when someone uses a referral code.

**POST** `/referrals/process`

### Request Body

```json
{
    "referral_code": "REF-ALICE-X9K4",
    "referee_customer_id": 789,
    "referee_order_id": 456
}
```

---

# A/B Testing API

## Create A/B Test

Create a new A/B test with control and variant promotions.

**POST** `/ab-testing/create`

### Request Body

```json
{
    "test_name": "Discount Amount Test",
    "control_promotion": {
        "name": "Control - 10% Off",
        "promotion_type": "percentage_discount",
        "discount_type": "percentage",
        "discount_value": 10.0,
        "start_date": "2024-06-01T00:00:00Z",
        "end_date": "2024-06-30T23:59:59Z",
        "max_uses": 10000
    },
    "variant_promotions": [
        {
            "name": "Variant A - 15% Off",
            "promotion_type": "percentage_discount",
            "discount_type": "percentage",
            "discount_value": 15.0,
            "start_date": "2024-06-01T00:00:00Z",
            "end_date": "2024-06-30T23:59:59Z",
            "max_uses": 10000
        },
        {
            "name": "Variant B - $20 Off",
            "promotion_type": "fixed_amount_discount",
            "discount_type": "fixed_amount",
            "discount_value": 20.0,
            "minimum_order_amount": 100.0,
            "start_date": "2024-06-01T00:00:00Z",
            "end_date": "2024-06-30T23:59:59Z",
            "max_uses": 10000
        }
    ],
    "test_config": {
        "control_traffic_percentage": 34,
        "variant_traffic_percentages": [33, 33],
        "duration_days": 30,
        "minimum_sample_size": 1000,
        "success_metric": "conversion_rate",
        "confidence_level": 95
    }
}
```

### Response

```json
{
    "test_id": "ab_1704110400_1234",
    "test_name": "Discount Amount Test",
    "status": "draft",
    "control_promotion": {
        "id": 501,
        "name": "Control - 10% Off",
        "variant_id": "control",
        "traffic_percentage": 34
    },
    "variant_promotions": [
        {
            "id": 502,
            "name": "Variant A - 15% Off",
            "variant_id": "variant_1",
            "traffic_percentage": 33
        },
        {
            "id": 503,
            "name": "Variant B - $20 Off",
            "variant_id": "variant_2",
            "traffic_percentage": 33
        }
    ],
    "total_promotions": 3,
    "created_at": "2024-01-01T12:00:00Z"
}
```

---

## Start A/B Test

**POST** `/ab-testing/{test_id}/start`

---

## Assign User to Variant

Get variant assignment for a user (deterministic based on user ID).

**POST** `/ab-testing/{test_id}/assign`

### Request Body

```json
{
    "customer_id": 456,
    "session_id": "optional-for-anonymous-users"
}
```

### Response

```json
{
    "test_id": "ab_1704110400_1234",
    "customer_id": 456,
    "assigned_variant": "variant_1",
    "promotion_id": 502,
    "assigned_at": "2024-01-01T12:00:00Z",
    "assignment_hash": 42
}
```

---

## Get A/B Test Results

**GET** `/ab-testing/{test_id}/results`

### Response

```json
{
    "test_id": "ab_1704110400_1234",
    "test_name": "Discount Amount Test",
    "test_status": "active",
    "started_at": "2024-06-01T00:00:00Z",
    "variant_results": [
        {
            "variant_id": "control",
            "variant_type": "control",
            "promotion_id": 501,
            "promotion_name": "Control - 10% Off",
            "traffic_percentage": 34,
            "metrics": {
                "impressions": 5000,
                "conversions": 250,
                "conversion_rate": 5.0,
                "unique_customers": 230,
                "total_discount": 2500.0,
                "total_revenue": 25000.0,
                "avg_order_value": 108.7,
                "roi_percentage": 900.0
            },
            "status": "active"
        },
        {
            "variant_id": "variant_1",
            "variant_type": "variant",
            "promotion_id": 502,
            "promotion_name": "Variant A - 15% Off",
            "traffic_percentage": 33,
            "metrics": {
                "impressions": 4800,
                "conversions": 280,
                "conversion_rate": 5.83,
                "unique_customers": 265,
                "total_discount": 4200.0,
                "total_revenue": 28000.0,
                "avg_order_value": 100.0,
                "roi_percentage": 566.7
            },
            "status": "active"
        }
    ],
    "statistical_analysis": {
        "control_variant": "control",
        "variant_comparisons": [
            {
                "variant_id": "variant_1",
                "significance": "significant",
                "confidence_level": 96.5,
                "improvement": 16.6
            }
        ],
        "overall_significance": "significant"
    },
    "winner": {
        "variant_id": "variant_1",
        "variant_type": "variant",
        "conversion_rate": 5.83,
        "improvement_over_control": 16.6
    },
    "generated_at": "2024-01-01T12:00:00Z"
}
```

---

# Analytics API

## Performance Report

Get comprehensive performance analytics for promotions.

**GET** `/analytics/performance-report`

### Query Parameters

| Parameter | Type | Description |
|-----------|------|-------------|
| `start_date` | datetime | Report start date |
| `end_date` | datetime | Report end date |
| `promotion_ids` | array | Specific promotion IDs |
| `include_inactive` | boolean | Include inactive promotions |

### Response

```json
{
    "report_period": {
        "start_date": "2024-06-01T00:00:00Z",
        "end_date": "2024-06-30T23:59:59Z",
        "duration_days": 30
    },
    "summary_metrics": {
        "total_promotions": 25,
        "active_promotions": 18,
        "total_usage": 5420,
        "total_revenue": 542000.0,
        "total_discount": 81300.0,
        "average_discount_per_order": 15.0,
        "unique_customers": 3200,
        "conversion_rate": 12.5,
        "roi_percentage": 566.7
    },
    "promotion_details": [
        {
            "promotion_id": 123,
            "promotion_name": "Summer Sale 2024",
            "promotion_type": "percentage_discount",
            "usage_metrics": {
                "total_usage": 450,
                "unique_customers": 380,
                "usage_trend": "increasing"
            },
            "financial_metrics": {
                "total_revenue": 45000.0,
                "total_discount": 11250.0,
                "average_order_value": 100.0,
                "roi_percentage": 300.0
            },
            "engagement_metrics": {
                "impressions": 5000,
                "clicks": 800,
                "conversion_rate_percentage": 9.0,
                "click_through_rate": 16.0
            }
        }
    ],
    "trends": {
        "daily_usage": [
            {"date": "2024-06-01", "usage": 180, "revenue": 18000.0},
            {"date": "2024-06-02", "usage": 195, "revenue": 19500.0}
        ]
    },
    "top_performers": {
        "by_usage": [
            {"promotion_id": 123, "promotion_name": "Summer Sale", "usage": 450}
        ],
        "by_revenue": [
            {"promotion_id": 123, "promotion_name": "Summer Sale", "revenue": 45000.0}
        ],
        "by_roi": [
            {"promotion_id": 124, "promotion_name": "Flash Sale", "roi": 800.0}
        ]
    }
}
```

---

## Executive Summary

Get high-level executive summary with insights and recommendations.

**GET** `/analytics/executive-summary`

### Response

```json
{
    "period": {
        "start_date": "2024-06-01T00:00:00Z",
        "end_date": "2024-06-30T23:59:59Z"
    },
    "key_metrics": {
        "total_revenue_impact": 542000.0,
        "cost_of_discounts": 81300.0,
        "net_revenue_increase": 460700.0,
        "overall_roi": 566.7,
        "customer_acquisition": 1200,
        "customer_retention_improvement": 15.5
    },
    "insights": [
        {
            "type": "performance",
            "title": "Strong ROI Performance",
            "description": "Promotion campaigns achieved 566% ROI, significantly above industry average",
            "impact": "positive",
            "confidence": "high"
        },
        {
            "type": "opportunity",
            "title": "Untapped Customer Segments",
            "description": "Premium customers show 40% higher conversion but only 15% of promotions target them",
            "impact": "opportunity",
            "confidence": "medium"
        }
    ],
    "recommendations": [
        {
            "priority": "high",
            "category": "optimization",
            "title": "Increase Premium Customer Targeting",
            "description": "Create more promotions targeting premium customer segment",
            "expected_impact": "25% revenue increase",
            "implementation_effort": "medium"
        }
    ],
    "performance_comparison": {
        "vs_previous_period": {
            "revenue_change": 23.5,
            "roi_change": 15.2,
            "customer_acquisition_change": 18.7
        },
        "vs_industry_benchmark": {
            "roi_vs_benchmark": 142.3,
            "conversion_rate_vs_benchmark": 108.5
        }
    }
}
```

---

# Automation API

## Create Automated Promotion

Create a promotion that activates based on triggers.

**POST** `/automation/create`

### Request Body

```json
{
    "name": "Birthday Special",
    "trigger_type": "customer_lifecycle",
    "trigger_conditions": {
        "event_type": "birthday",
        "days_before": 3
    },
    "promotion_config": {
        "name": "Happy Birthday Special",
        "description": "Special birthday discount",
        "promotion_type": "percentage_discount",
        "discount_type": "percentage",
        "discount_value": 25.0,
        "start_date": "2024-01-01T00:00:00Z",
        "end_date": "2024-12-31T23:59:59Z",
        "max_uses": 1000
    },
    "automation_options": {
        "duration_hours": 48,
        "max_triggers": 1,
        "cooldown_hours": 168
    }
}
```

### Trigger Types and Conditions

#### Customer Lifecycle
```json
{
    "trigger_type": "customer_lifecycle",
    "trigger_conditions": {
        "event_type": "signup|birthday|win_back",
        "days_inactive": 30  // for win_back
    }
}
```

#### Purchase Behavior
```json
{
    "trigger_type": "purchase_behavior",
    "trigger_conditions": {
        "behavior_type": "high_value_purchase|category_purchase",
        "order_threshold": 100.0,
        "category_ids": [1, 2, 3]
    }
}
```

#### Inventory Level
```json
{
    "trigger_type": "inventory_level",
    "trigger_conditions": {
        "trigger_type": "low_stock|overstock",
        "threshold_percentage": 20
    }
}
```

#### Seasonal Event
```json
{
    "trigger_type": "seasonal_event",
    "trigger_conditions": {
        "event_type": "black_friday|christmas|new_year",
        "days_before": 3
    }
}
```

---

## Process Triggers

Manually trigger processing of automation rules (typically run by scheduler).

**POST** `/automation/process-triggers`

### Request Body

```json
{
    "trigger_type": "customer_lifecycle"  // optional filter
}
```

---

# Scheduling API

## Schedule Promotion

Create a promotion with advanced scheduling options.

**POST** `/scheduling/schedule`

### Request Body

```json
{
    "name": "Weekly Flash Sale",
    "description": "Every Friday flash sale",
    "promotion_type": "percentage_discount",
    "discount_type": "percentage",
    "discount_value": 30.0,
    "start_date": "2024-06-01T00:00:00Z",
    "end_date": "2024-12-31T23:59:59Z",
    "max_uses": 500,
    "schedule_options": {
        "recurrence_pattern": "weekly",
        "recurrence_interval": 1,
        "recurrence_days": [4],  // Friday = 4
        "max_occurrences": 26,
        "auto_activate": true,
        "auto_deactivate": true
    }
}
```

### Recurrence Patterns

#### Daily
```json
{
    "recurrence_pattern": "daily",
    "recurrence_interval": 2  // every 2 days
}
```

#### Weekly
```json
{
    "recurrence_pattern": "weekly",
    "recurrence_interval": 1,
    "recurrence_days": [1, 3, 5]  // Monday, Wednesday, Friday
}
```

#### Monthly
```json
{
    "recurrence_pattern": "monthly",
    "recurrence_interval": 1,
    "recurrence_days": [1, 15]  // 1st and 15th of each month
}
```

#### Custom (Cron)
```json
{
    "recurrence_pattern": "custom",
    "cron_expression": "0 9 * * 1-5"  // 9 AM, Monday to Friday
}
```

---

## Get Promotion Calendar

**GET** `/scheduling/calendar`

### Query Parameters

| Parameter | Type | Description |
|-----------|------|-------------|
| `year` | integer | Calendar year |
| `month` | integer | Calendar month (optional) |

### Response

```json
{
    "year": 2024,
    "month": 6,
    "period": {
        "start_date": "2024-06-01T00:00:00Z",
        "end_date": "2024-06-30T23:59:59Z"
    },
    "total_scheduled": 15,
    "calendar": {
        "2024-06-01": [
            {
                "id": 123,
                "name": "Monthly Sale",
                "is_recurring": true
            }
        ],
        "2024-06-07": [
            {
                "id": 124,
                "name": "Weekly Flash Sale",
                "is_recurring": true
            }
        ]
    }
}
```

---

# Data Structures

## Promotion Object

```json
{
    "id": 123,
    "uuid": "550e8400-e29b-41d4-a716-446655440000",
    "name": "Summer Sale 2024",
    "description": "Great summer discounts",
    "promotion_type": "percentage_discount",
    "discount_type": "percentage",
    "discount_value": 25.0,
    "status": "active",
    "start_date": "2024-06-01T00:00:00Z",
    "end_date": "2024-08-31T23:59:59Z",
    "max_uses": 1000,
    "current_uses": 150,
    "minimum_order_amount": 50.0,
    "maximum_discount_amount": 100.0,
    "priority": 5,
    "can_stack": true,
    "target_customer_segments": ["premium", "loyal"],
    "applicable_categories": [1, 2, 3],
    "impressions": 5000,
    "clicks": 800,
    "conversions": 150,
    "conversion_rate": 3.0,
    "revenue_generated": 15000.0,
    "metadata": {
        "campaign_id": "SUMMER2024",
        "ab_test": {
            "test_id": "ab_123",
            "variant_id": "control"
        }
    },
    "created_at": "2024-01-01T12:00:00Z",
    "updated_at": "2024-01-01T12:30:00Z"
}
```

## Coupon Object

```json
{
    "id": 1001,
    "promotion_id": 123,
    "code": "SUMMER25",
    "status": "active",
    "max_uses": 100,
    "current_uses": 45,
    "max_uses_per_customer": 1,
    "expires_at": "2024-08-31T23:59:59Z",
    "metadata": {
        "campaign": "summer_email",
        "batch_id": "batch_001"
    },
    "created_at": "2024-01-01T12:00:00Z",
    "updated_at": "2024-01-01T12:00:00Z"
}
```

## Order Items Format

```json
[
    {
        "product_id": 1,
        "quantity": 2,
        "unit_price": 29.99,
        "subtotal": 59.98,
        "category_id": 5,
        "brand_id": 10,
        "metadata": {
            "sku": "PROD001",
            "weight": 1.5
        }
    }
]
```

---

# Webhooks

The Promotion System can send webhooks for important events:

## Webhook Events

- `promotion.created`
- `promotion.activated`
- `promotion.paused`
- `promotion.ended`
- `coupon.used`
- `referral.completed`
- `ab_test.started`
- `ab_test.ended`

## Webhook Payload

```json
{
    "event": "promotion.activated",
    "timestamp": "2024-01-01T12:00:00Z",
    "data": {
        "promotion": {
            "id": 123,
            "name": "Summer Sale 2024",
            "status": "active"
        }
    },
    "signature": "sha256=..."
}
```

---

# SDK Examples

## JavaScript/Node.js

```javascript
const AuraPromotions = require('@auraconnect/promotions-sdk');

const client = new AuraPromotions({
    apiKey: 'your-api-key',
    baseUrl: 'https://api.auraconnect.ai'
});

// Create promotion
const promotion = await client.promotions.create({
    name: 'Summer Sale',
    promotion_type: 'percentage_discount',
    discount_value: 25.0,
    // ... other fields
});

// Calculate discount
const discount = await client.promotions.calculateDiscount(promotion.id, {
    order_items: orderItems,
    customer_id: customerId
});

// Apply discount with idempotency
const result = await client.orders.applyDiscount(orderId, {
    promotion_ids: [promotion.id],
    idempotency_key: 'unique-operation-id'
});
```

## Python

```python
from auraconnect_promotions import PromotionsClient

client = PromotionsClient(
    api_key='your-api-key',
    base_url='https://api.auraconnect.ai'
)

# Create A/B test
ab_test = client.ab_testing.create(
    test_name='Discount Amount Test',
    control_promotion={
        'name': 'Control - 10% Off',
        'discount_value': 10.0
    },
    variant_promotions=[{
        'name': 'Variant - 15% Off',
        'discount_value': 15.0
    }],
    test_config={
        'control_traffic_percentage': 50,
        'variant_traffic_percentages': [50]
    }
)

# Assign user to variant
assignment = client.ab_testing.assign_user(
    test_id=ab_test['test_id'],
    customer_id=user_id
)
```

---

# Best Practices

## Performance Optimization

1. **Use Caching**: The API automatically caches frequently accessed data
2. **Batch Operations**: Use bulk endpoints for creating multiple coupons
3. **Pagination**: Always use pagination for list endpoints
4. **Filtering**: Use specific filters to reduce response size

## Security

1. **Idempotency Keys**: Always provide idempotency keys for mutation operations
2. **Rate Limiting**: Respect rate limits and implement exponential backoff
3. **Validation**: Validate all input data before sending requests
4. **Monitoring**: Monitor API usage and error rates

## A/B Testing

1. **Sample Size**: Ensure adequate sample size before concluding tests
2. **Statistical Significance**: Wait for statistical significance before making decisions
3. **Test Duration**: Run tests for appropriate duration (typically 1-4 weeks)
4. **Single Metric**: Focus on one primary success metric per test

## Automation

1. **Monitoring**: Monitor automated promotions for unexpected behavior
2. **Limits**: Set appropriate limits on automated promotion triggers
3. **Testing**: Test automation rules thoroughly before production deployment
4. **Fallbacks**: Implement fallback mechanisms for automation failures