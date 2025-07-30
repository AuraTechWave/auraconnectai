# POS Analytics API Documentation

## Overview

The POS Analytics API provides comprehensive analytics and reporting for Point of Sale operations in the admin dashboard. It offers real-time insights into POS provider performance, terminal health, transaction metrics, and operational issues.

## Base URL

```
/api/analytics/pos
```

## Authentication

All endpoints require authentication and appropriate permissions:
- `analytics.view` - View analytics data
- `analytics.manage` - Manage alerts and refresh data
- `analytics.export` - Export analytics reports

Include the authentication token in the Authorization header:

```
Authorization: Bearer <token>
```

## Endpoints

### 1. POS Analytics Dashboard

Get comprehensive POS analytics dashboard data.

**Endpoint:** `POST /analytics/pos/dashboard`

**Request Body:**

```json
{
  "time_range": "last_24_hours",  // Options: last_hour, last_24_hours, last_7_days, last_30_days, custom
  "start_date": "2025-01-01T00:00:00Z",  // Required if time_range is "custom"
  "end_date": "2025-01-30T23:59:59Z",    // Required if time_range is "custom"
  "provider_ids": [1, 2],  // Optional: Filter by specific providers
  "terminal_ids": ["POS-001", "POS-002"],  // Optional: Filter by terminals
  "include_offline": true  // Default: true
}
```

**Response:**

```json
{
  "total_providers": 3,
  "active_providers": 3,
  "total_terminals": 15,
  "online_terminals": 13,
  "total_transactions": 1250,
  "successful_transactions": 1200,
  "transaction_success_rate": 96.0,
  "total_transaction_value": "125000.00",
  "average_transaction_value": "100.00",
  "overall_uptime": 99.5,
  "average_sync_time_ms": 250.5,
  "average_webhook_time_ms": 150.3,
  "providers": [
    {
      "provider_id": 1,
      "provider_name": "Square POS",
      "provider_code": "square",
      "is_active": true,
      "total_terminals": 5,
      "active_terminals": 4,
      "offline_terminals": 1,
      "total_transactions": 500,
      "successful_transactions": 485,
      "failed_transactions": 15,
      "transaction_success_rate": 97.0,
      "total_transaction_value": "50000.00",
      "total_syncs": 480,
      "sync_success_rate": 95.8,
      "average_sync_time_ms": 245.0,
      "total_webhooks": 520,
      "webhook_success_rate": 98.5,
      "overall_health_status": "healthy",
      "uptime_percentage": 99.8,
      "active_alerts": 0
    }
  ],
  "healthy_terminals": 10,
  "degraded_terminals": 2,
  "critical_terminals": 1,
  "offline_terminals": 2,
  "transaction_trends": [
    {
      "timestamp": "2025-01-30T14:00:00Z",
      "transaction_count": 45,
      "transaction_value": "4500.00",
      "success_rate": 95.6,
      "average_value": "100.00"
    }
  ],
  "active_alerts": [
    {
      "alert_id": "550e8400-e29b-41d4-a716-446655440000",
      "alert_type": "terminal_offline",
      "severity": "warning",
      "provider_id": 1,
      "provider_name": "Square POS",
      "terminal_id": "POS-005",
      "title": "Terminal Offline",
      "description": "Terminal POS-005 has been offline for 30 minutes",
      "is_active": true,
      "acknowledged": false,
      "created_at": "2025-01-30T13:30:00Z"
    }
  ],
  "generated_at": "2025-01-30T15:00:00Z",
  "time_range": "2025-01-29T15:00:00Z to 2025-01-30T15:00:00Z"
}
```

### 2. Provider Details

Get detailed analytics for a specific POS provider.

**Endpoint:** `POST /analytics/pos/provider/{provider_id}/details`

**Request Body:**

```json
{
  "provider_id": 1,
  "time_range": "last_24_hours",
  "include_terminals": true,
  "include_errors": true
}
```

**Response:**

```json
{
  "provider": {
    // Provider summary (same as dashboard)
  },
  "sync_metrics": {
    "total_syncs": 480,
    "successful_syncs": 460,
    "failed_syncs": 20,
    "pending_syncs": 5,
    "success_rate": 95.8,
    "average_sync_time_ms": 245.0,
    "sync_status_breakdown": {
      "synced": 460,
      "failed": 20,
      "pending": 5
    },
    "recent_failures": [
      {
        "order_id": 1234,
        "error": "Network timeout",
        "timestamp": "2025-01-30T14:45:00Z"
      }
    ]
  },
  "webhook_metrics": {
    "total_webhooks": 520,
    "successful_webhooks": 512,
    "failed_webhooks": 8,
    "pending_webhooks": 0,
    "success_rate": 98.5,
    "average_processing_time_ms": 150.0,
    "event_type_breakdown": {
      "payment.updated": 300,
      "payment.created": 220
    }
  },
  "error_analysis": {
    "total_errors": 28,
    "error_rate": 2.2,
    "error_types": [
      {"type": "network_timeout", "count": 15, "percentage": 53.6},
      {"type": "validation_error", "count": 8, "percentage": 28.6},
      {"type": "authentication_failed", "count": 5, "percentage": 17.8}
    ],
    "trending_errors": [],
    "affected_terminals": [
      {"terminal_id": "POS-003", "error_count": 12},
      {"terminal_id": "POS-005", "error_count": 10}
    ]
  },
  "performance_metrics": {
    "response_time_p50": 200.0,
    "response_time_p95": 450.0,
    "response_time_p99": 800.0,
    "average_response_time": 225.0,
    "transactions_per_minute": 20.8,
    "syncs_per_minute": 20.0,
    "webhooks_per_minute": 21.7,
    "peak_load_percentage": 65.0,
    "capacity_utilization": 45.0
  },
  "terminals": [
    // List of terminal summaries
  ],
  "hourly_trends": [],
  "daily_trends": [],
  "recent_transactions": [],
  "recent_errors": [],
  "generated_at": "2025-01-30T15:00:00Z",
  "time_range": "last_24_hours"
}
```

### 3. Terminal Details

Get detailed analytics for a specific POS terminal.

**Endpoint:** `POST /analytics/pos/terminal/{terminal_id}/details`

**Request Body:**

```json
{
  "terminal_id": "POS-001",
  "time_range": "last_24_hours"
}
```

### 4. Compare Providers

Compare analytics metrics across multiple POS providers.

**Endpoint:** `POST /analytics/pos/compare`

**Request Body:**

```json
{
  "provider_ids": [1, 2, 3],  // Min: 2, Max: 5
  "time_range": "last_7_days",
  "metrics": ["transactions", "success_rate", "sync_performance", "uptime"]
}
```

### 5. Active Alerts

Get active POS analytics alerts.

**Endpoint:** `GET /analytics/pos/alerts/active`

**Query Parameters:**
- `severity` - Filter by severity (info, warning, critical)
- `provider_id` - Filter by provider
- `terminal_id` - Filter by terminal
- `limit` - Maximum alerts to return (default: 50, max: 200)

**Response:**

```json
{
  "alerts": [
    {
      "alert_id": "550e8400-e29b-41d4-a716-446655440000",
      "alert_type": "high_error_rate",
      "severity": "warning",
      "provider_id": 1,
      "provider_name": "Square POS",
      "terminal_id": "POS-002",
      "title": "High Error Rate Detected",
      "description": "Terminal POS-002 has error rate above threshold",
      "metric_value": 15.5,
      "threshold_value": 10.0,
      "acknowledged": false,
      "created_at": "2025-01-30T14:00:00Z"
    }
  ],
  "total_count": 3,
  "filters": {
    "severity": "warning",
    "provider_id": 1,
    "terminal_id": null
  }
}
```

### 6. Acknowledge Alert

Acknowledge a POS analytics alert.

**Endpoint:** `POST /analytics/pos/alerts/{alert_id}/acknowledge`

**Query Parameters:**
- `notes` - Optional acknowledgment notes

**Response:**

```json
{
  "success": true,
  "message": "Alert acknowledged successfully",
  "alert_id": "550e8400-e29b-41d4-a716-446655440000"
}
```

### 7. Terminal Health Summary

Get summary of terminal health status.

**Endpoint:** `GET /analytics/pos/health/terminals`

**Query Parameters:**
- `provider_id` - Filter by provider
- `health_status` - Filter by health status (healthy, degraded, critical, offline)

**Response:**

```json
{
  "summary": {
    "Square POS": {
      "total": 5,
      "healthy": 3,
      "degraded": 1,
      "critical": 0,
      "offline": 1
    },
    "Stripe Terminal": {
      "total": 8,
      "healthy": 7,
      "degraded": 0,
      "critical": 0,
      "offline": 1
    }
  },
  "total_terminals": 13,
  "filters": {
    "provider_id": null,
    "health_status": null
  }
}
```

### 8. Transaction Trends

Get transaction trend data for charts.

**Endpoint:** `GET /analytics/pos/trends/transactions`

**Query Parameters:**
- `time_range` - Time range (default: last_7_days)
- `provider_id` - Filter by provider
- `terminal_id` - Filter by terminal
- `granularity` - Data granularity (hourly, daily, weekly)

**Response:**

```json
{
  "trends": [
    {
      "timestamp": "2025-01-30T14:00:00Z",
      "transaction_count": 45,
      "transaction_value": 4500.0,
      "success_rate": 95.6,
      "average_value": 100.0
    }
  ],
  "time_range": "last_7_days",
  "granularity": "hourly",
  "data_points": 168
}
```

### 9. Export Analytics

Export POS analytics data to file.

**Endpoint:** `POST /analytics/pos/export`

**Request Body:**

```json
{
  "report_type": "summary",  // Options: summary, detailed, transactions, errors
  "format": "csv",  // Options: csv, xlsx, pdf
  "time_range": "last_7_days",
  "provider_ids": [1, 2],  // Optional
  "terminal_ids": ["POS-001"],  // Optional
  "include_charts": false  // For PDF exports only
}
```

**Response:** File download

### 10. Refresh Analytics Data

Manually trigger refresh of POS analytics data.

**Endpoint:** `POST /analytics/pos/refresh`

**Query Parameters:**
- `provider_id` - Specific provider to refresh (optional)

**Response:**

```json
{
  "success": true,
  "message": "Analytics refresh triggered",
  "task_id": "550e8400-e29b-41d4-a716-446655440000",
  "provider_id": 1
}
```

## Status Codes

| Status Code | Description |
|-------------|-------------|
| 200 | Success |
| 202 | Accepted (for async operations) |
| 400 | Bad Request |
| 401 | Unauthorized |
| 403 | Forbidden - Insufficient permissions |
| 404 | Not Found |
| 500 | Internal Server Error |

## Error Responses

All error responses follow this format:

```json
{
  "detail": "Error message describing what went wrong"
}
```

## Time Ranges

The API supports the following predefined time ranges:
- `last_hour` - Last 60 minutes
- `last_24_hours` - Last 24 hours
- `last_7_days` - Last 7 days
- `last_30_days` - Last 30 days
- `custom` - Custom date range (requires start_date and end_date)

## Health Status Values

Terminal and provider health statuses:
- `healthy` - Operating normally
- `degraded` - Performance issues detected
- `critical` - Serious issues requiring attention
- `offline` - Not responding

## Alert Severity Levels

- `info` - Informational alerts
- `warning` - Warning conditions
- `critical` - Critical issues requiring immediate attention

## Best Practices

1. **Caching**: Dashboard data is cached for performance. Use the refresh endpoint sparingly.
2. **Time Ranges**: Use appropriate time ranges to avoid overwhelming the system with data.
3. **Filtering**: Apply filters to reduce data volume and improve response times.
4. **Polling**: For real-time updates, poll the dashboard endpoint at reasonable intervals (recommended: 30-60 seconds).
5. **Alert Management**: Acknowledge alerts promptly to maintain a clean alert queue.

## Integration Example

```python
import requests
from datetime import datetime, timedelta

class POSAnalyticsClient:
    def __init__(self, base_url, auth_token):
        self.base_url = base_url
        self.headers = {
            "Authorization": f"Bearer {auth_token}",
            "Content-Type": "application/json"
        }
    
    def get_dashboard(self, time_range="last_24_hours"):
        """Get POS analytics dashboard"""
        response = requests.post(
            f"{self.base_url}/analytics/pos/dashboard",
            json={"time_range": time_range},
            headers=self.headers
        )
        response.raise_for_status()
        return response.json()
    
    def get_provider_details(self, provider_id):
        """Get detailed provider analytics"""
        response = requests.post(
            f"{self.base_url}/analytics/pos/provider/{provider_id}/details",
            json={
                "provider_id": provider_id,
                "time_range": "last_24_hours",
                "include_terminals": True
            },
            headers=self.headers
        )
        response.raise_for_status()
        return response.json()
    
    def acknowledge_alert(self, alert_id, notes=None):
        """Acknowledge an alert"""
        params = {"notes": notes} if notes else {}
        response = requests.post(
            f"{self.base_url}/analytics/pos/alerts/{alert_id}/acknowledge",
            params=params,
            headers=self.headers
        )
        response.raise_for_status()
        return response.json()

# Usage
client = POSAnalyticsClient("https://api.auraconnect.ai/api", "your-auth-token")

# Get dashboard
dashboard = client.get_dashboard()
print(f"Total transactions: {dashboard['total_transactions']}")
print(f"Success rate: {dashboard['transaction_success_rate']}%")

# Check alerts
if dashboard['active_alerts']:
    for alert in dashboard['active_alerts']:
        print(f"Alert: {alert['title']} - {alert['severity']}")
        
        # Acknowledge critical alerts
        if alert['severity'] == 'critical':
            client.acknowledge_alert(alert['alert_id'], "Investigating")
```