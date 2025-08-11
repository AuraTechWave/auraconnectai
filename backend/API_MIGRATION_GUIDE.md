# API Migration Guide - New Modules (v1)

## Overview
This guide covers the new API endpoints introduced in the insights, settings, and loyalty modules. All endpoints follow RESTful conventions and are versioned under `/api/v1/`.

## No Breaking Changes
**Important**: This update introduces only new functionality. No existing APIs have been modified or removed.

## New API Endpoints

### Insights Module (`/api/v1/insights`)

#### Core Endpoints
- `GET /api/v1/insights` - List insights with filtering
- `POST /api/v1/insights` - Create new insight
- `GET /api/v1/insights/{id}` - Get specific insight
- `PUT /api/v1/insights/{id}` - Update insight
- `DELETE /api/v1/insights/{id}` - Soft delete insight

#### Batch Operations
- `POST /api/v1/insights/batch/acknowledge` - Acknowledge multiple insights
- `POST /api/v1/insights/batch/dismiss` - Dismiss multiple insights

#### Ratings & Actions
- `POST /api/v1/insights/{id}/rate` - Rate insight usefulness
- `GET /api/v1/insights/{id}/ratings` - Get insight ratings
- `POST /api/v1/insights/{id}/action` - Mark insight as actioned

#### Analytics & Export
- `GET /api/v1/insights/analytics` - Get insights analytics
- `GET /api/v1/insights/export` - Export insights (CSV/JSON)

### Settings Module (`/api/v1/settings`)

#### Settings Management
- `POST /api/v1/settings` - Create setting
- `GET /api/v1/settings/{key}` - Get setting by key
- `PUT /api/v1/settings/{id}` - Update setting
- `DELETE /api/v1/settings/{id}` - Delete setting
- `POST /api/v1/settings/bulk` - Bulk update settings

#### Feature Flags
- `GET /api/v1/settings/features` - List feature flags
- `POST /api/v1/settings/features` - Create feature flag
- `GET /api/v1/settings/features/{key}/evaluate` - Evaluate feature flag
- `PUT /api/v1/settings/features/{key}/toggle` - Toggle feature flag

#### API Keys
- `GET /api/v1/settings/api-keys` - List API keys
- `POST /api/v1/settings/api-keys` - Generate API key
- `DELETE /api/v1/settings/api-keys/{id}` - Revoke API key

#### Webhooks
- `GET /api/v1/settings/webhooks` - List webhooks
- `POST /api/v1/settings/webhooks` - Create webhook
- `POST /api/v1/settings/webhooks/{id}/test` - Test webhook
- `POST /api/v1/settings/webhooks/{id}/rotate-secret` - Rotate webhook secret

### Loyalty Module (`/api/v1/loyalty`)

#### Customer Loyalty
- `GET /api/v1/loyalty/customers/{id}/loyalty` - Get customer loyalty stats
- `GET /api/v1/loyalty/customers/{id}/points/history` - Get points history
- `GET /api/v1/loyalty/customers/{id}/rewards` - Get customer rewards

#### Points Management
- `POST /api/v1/loyalty/customers/{id}/points/add` - Add points
- `POST /api/v1/loyalty/points/adjust` - Adjust points manually
- `POST /api/v1/loyalty/points/transfer` - Transfer points between customers

#### Reward Templates
- `GET /api/v1/loyalty/templates` - List reward templates
- `POST /api/v1/loyalty/templates` - Create reward template
- `GET /api/v1/loyalty/templates/{id}` - Get template details
- `PUT /api/v1/loyalty/templates/{id}` - Update template
- `DELETE /api/v1/loyalty/templates/{id}` - Deactivate template

#### Reward Management
- `POST /api/v1/loyalty/rewards/search` - Search customer rewards
- `POST /api/v1/loyalty/rewards/issue/manual` - Issue reward manually
- `POST /api/v1/loyalty/rewards/issue/bulk` - Bulk issue rewards
- `POST /api/v1/loyalty/rewards/validate` - Validate reward code
- `POST /api/v1/loyalty/rewards/redeem` - Redeem reward

#### Order Integration
- `POST /api/v1/loyalty/orders/complete` - Process order completion rewards

## Authentication Requirements

All endpoints require authentication via JWT token in the Authorization header:
```
Authorization: Bearer <jwt-token>
```

### Required Permissions

#### Insights Module
- `INSIGHTS_VIEW` - View insights
- `INSIGHTS_MANAGE` - Create/update insights
- `INSIGHTS_ADMIN` - Delete insights, manage rules

#### Settings Module
- `SETTINGS_VIEW` - View settings
- `SETTINGS_MANAGE` - Create/update settings
- `SETTINGS_ADMIN` - Manage API keys, webhooks

#### Loyalty Module
- `LOYALTY_VIEW` - View loyalty data
- `LOYALTY_MANAGE` - Manage points, issue rewards
- `LOYALTY_ADMIN` - Manage templates, campaigns

## Request/Response Examples

### Create Insight
```bash
POST /api/v1/insights
Content-Type: application/json

{
  "title": "Low Inventory Alert",
  "description": "Tomatoes running low - only 5kg remaining",
  "domain": "inventory",
  "severity": "high",
  "is_actionable": true,
  "impact_score": 8.5,
  "source": "inventory_monitor"
}

Response (201):
{
  "id": 123,
  "title": "Low Inventory Alert",
  "domain": "inventory",
  "severity": "high",
  "created_at": "2024-01-11T10:00:00Z",
  "thread_id": 45
}
```

### Evaluate Feature Flag
```bash
GET /api/v1/settings/features/new_checkout_flow/evaluate

Response (200):
{
  "enabled": true,
  "key": "new_checkout_flow",
  "user_in_rollout": true,
  "rollout_percentage": 50
}
```

### Redeem Loyalty Reward
```bash
POST /api/v1/loyalty/rewards/redeem
Content-Type: application/json

{
  "reward_code": "SAVE10ABC",
  "order_id": 12345,
  "order_amount": 100.00
}

Response (200):
{
  "success": true,
  "reward_id": 789,
  "discount_amount": 10.00,
  "final_order_amount": 90.00,
  "message": "Reward redeemed successfully"
}
```

## Rate Limiting

- Insights creation: 100/hour per user
- Settings updates: 500/hour per restaurant
- Reward redemption: 50/hour per customer
- API key generation: 10/day per user

## Error Responses

All errors follow standard format:
```json
{
  "error": {
    "code": "RESOURCE_NOT_FOUND",
    "message": "Insight not found",
    "details": {"id": 123}
  }
}
```

Common HTTP status codes:
- `400` - Bad Request (validation errors)
- `401` - Unauthorized (missing/invalid token)
- `403` - Forbidden (insufficient permissions)
- `404` - Not Found
- `409` - Conflict (duplicate resource)
- `422` - Unprocessable Entity (business logic errors)
- `429` - Too Many Requests (rate limited)

## Pagination

List endpoints support pagination:
```
GET /api/v1/insights?page=1&size=20&sort=created_at&order=desc
```

Response includes pagination metadata:
```json
{
  "items": [...],
  "total": 150,
  "page": 1,
  "pages": 8,
  "size": 20
}
```

## Filtering

Most list endpoints support filtering:
```
GET /api/v1/insights?domain=inventory&severity=high&is_active=true
GET /api/v1/loyalty/templates?reward_type=percentage_discount&is_active=true
```

## Webhook Events

New webhook events available:
- `insight.created`
- `insight.threshold_exceeded`
- `loyalty.points_earned`
- `loyalty.reward_redeemed`
- `loyalty.tier_upgraded`
- `settings.changed`
- `feature_flag.toggled`

## SDK Support

SDKs will be updated to support new endpoints:
- Python SDK: `pip install auraconnect-sdk>=2.0.0`
- JavaScript SDK: `npm install @auraconnect/sdk@^2.0.0`
- Mobile SDKs: Updates pending

## Support

For questions or issues:
- Documentation: https://docs.auraconnect.ai/api/v1
- Support: support@auraconnect.ai
- Status: https://status.auraconnect.ai