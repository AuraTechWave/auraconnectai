# Staff Scheduling API Documentation

## Overview

The Staff Scheduling API provides comprehensive scheduling management for restaurant staff, including shift templates, automated scheduling, conflict detection, swap requests, and analytics.

## Base URL

```
/api/v1/staff
```

## Authentication

All endpoints require JWT authentication token in the Authorization header:

```
Authorization: Bearer <token>
```

## Endpoints

### Shift Templates

#### Create Shift Template
```http
POST /templates
```

Creates a new shift template for recurring shifts.

**Request Body:**
```json
{
  "location_id": 1,
  "name": "Morning Shift",
  "shift_type": "regular",
  "start_time": "08:00",
  "end_time": "16:00",
  "min_staff": 3,
  "max_staff": 5,
  "break_minutes": 30,
  "roles": ["server", "cook"],
  "recurrence_type": "weekly",
  "recurrence_days": [1, 2, 3, 4, 5],
  "color": "#4CAF50"
}
```

**Response:**
```json
{
  "id": 1,
  "location_id": 1,
  "name": "Morning Shift",
  "created_at": "2024-02-08T10:00:00Z"
}
```

#### List Shift Templates
```http
GET /templates?location_id=1&is_active=true
```

**Response:**
```json
[
  {
    "id": 1,
    "name": "Morning Shift",
    "start_time": "08:00",
    "end_time": "16:00",
    "min_staff": 3,
    "max_staff": 5,
    "is_active": true
  }
]
```

### Shift Management

#### Create Shift
```http
POST /shifts
```

Creates a new shift assignment with automatic validation.

**Request Body:**
```json
{
  "staff_id": 1,
  "location_id": 1,
  "date": "2024-02-15",
  "start_time": "2024-02-15T08:00:00",
  "end_time": "2024-02-15T16:00:00",
  "template_id": 1,
  "notes": "Cover for John"
}
```

**Response:**
```json
{
  "id": 123,
  "staff_id": 1,
  "status": "scheduled",
  "estimated_cost": 120.00,
  "validation": {
    "conflicts": [],
    "availability": true,
    "weekly_hours": 32
  }
}
```

#### Get Schedule
```http
GET /schedule?location_id=1&start_date=2024-02-12&end_date=2024-02-18
```

**Response:**
```json
{
  "shifts": [
    {
      "id": 123,
      "staff_member": {
        "id": 1,
        "name": "John Doe"
      },
      "date": "2024-02-15",
      "start_time": "08:00",
      "end_time": "16:00",
      "status": "scheduled",
      "estimated_cost": 120.00
    }
  ],
  "summary": {
    "total_shifts": 25,
    "total_hours": 200,
    "total_cost": 3000.00,
    "coverage_percentage": 85
  }
}
```

#### Publish Schedule
```http
POST /schedule/publish
```

Publishes draft schedules and sends notifications to staff.

**Request Body:**
```json
{
  "location_id": 1,
  "start_date": "2024-02-12",
  "end_date": "2024-02-18",
  "notify_staff": true
}
```

**Response:**
```json
{
  "published_count": 25,
  "notified_staff": 15,
  "status": "success"
}
```

### Auto-Scheduling

#### Generate Schedule
```http
POST /schedule/auto-generate
```

Automatically generates an optimal schedule based on templates and constraints.

**Request Body:**
```json
{
  "location_id": 1,
  "start_date": "2024-02-19",
  "end_date": "2024-02-25",
  "options": {
    "respect_availability": true,
    "minimize_overtime": true,
    "distribute_hours_evenly": true,
    "max_consecutive_days": 5
  }
}
```

**Response:**
```json
{
  "generated_shifts": 35,
  "coverage_achieved": 92.5,
  "warnings": [
    "Unable to fill 2 evening shifts due to availability"
  ],
  "summary": {
    "total_hours": 280,
    "estimated_cost": 4200.00
  }
}
```

### Staff Availability

#### Set Availability
```http
POST /availability
```

Sets recurring or specific date availability.

**Request Body:**
```json
{
  "staff_id": 1,
  "type": "recurring",
  "day_of_week": 1,
  "start_time": "08:00",
  "end_time": "18:00",
  "status": "available",
  "effective_from": "2024-02-01"
}
```

#### Get Staff Availability
```http
GET /availability/{staff_id}?date=2024-02-15
```

**Response:**
```json
{
  "recurring": [
    {
      "day_of_week": 1,
      "start_time": "08:00",
      "end_time": "18:00",
      "status": "available"
    }
  ],
  "specific_dates": [
    {
      "date": "2024-02-15",
      "status": "unavailable",
      "reason": "Personal day"
    }
  ]
}
```

### Shift Swaps

#### Request Shift Swap
```http
POST /shifts/{shift_id}/swap
```

**Request Body:**
```json
{
  "to_staff_id": 2,
  "reason": "Family emergency"
}
```

**Response:**
```json
{
  "swap_id": 45,
  "status": "pending",
  "requires_approval": true
}
```

#### Approve/Reject Swap
```http
PUT /swaps/{swap_id}/approve
```

**Request Body:**
```json
{
  "approved": true,
  "notes": "Approved - ensure proper handover"
}
```

### Analytics

#### Get Staffing Analytics
```http
GET /analytics/staffing?location_id=1&start_date=2024-02-01&end_date=2024-02-29
```

**Response:**
```json
{
  "period_summary": {
    "total_scheduled_hours": 3200,
    "total_labor_cost": 48000.00,
    "average_coverage": 87.5,
    "overtime_hours": 120
  },
  "daily_metrics": [
    {
      "date": "2024-02-01",
      "scheduled_staff": 12,
      "required_staff": 14,
      "coverage_percentage": 85.7,
      "estimated_labor_cost": 1680.00
    }
  ],
  "staff_metrics": [
    {
      "staff_id": 1,
      "name": "John Doe",
      "total_hours": 160,
      "average_hours_per_week": 40,
      "shifts_count": 20
    }
  ]
}
```

#### Get Labor Cost Report
```http
GET /analytics/labor-cost?location_id=1&month=2024-02
```

**Response:**
```json
{
  "total_cost": 48000.00,
  "by_role": {
    "server": 18000.00,
    "cook": 22000.00,
    "manager": 8000.00
  },
  "by_week": [
    {
      "week": 1,
      "cost": 12000.00,
      "hours": 800
    }
  ],
  "overtime_cost": 2400.00,
  "average_hourly_cost": 15.00
}
```

## Error Responses

All endpoints return standard error responses:

```json
{
  "detail": "Error description",
  "code": "ERROR_CODE",
  "field_errors": {
    "field_name": ["Error message"]
  }
}
```

Common error codes:
- `SHIFT_CONFLICT`: Overlapping shifts detected
- `AVAILABILITY_CONFLICT`: Staff not available
- `MAX_HOURS_EXCEEDED`: Would exceed weekly hour limit
- `INSUFFICIENT_COVERAGE`: Not enough staff scheduled
- `INVALID_TIME_RANGE`: Invalid start/end times

## Webhooks

The scheduling system can send webhooks for the following events:

- `schedule.published`: When a schedule is published
- `shift.created`: When a new shift is created
- `shift.cancelled`: When a shift is cancelled
- `swap.requested`: When a swap is requested
- `swap.approved`: When a swap is approved

## Rate Limits

- General endpoints: 100 requests per minute
- Auto-scheduling: 10 requests per hour
- Analytics: 50 requests per minute

## Best Practices

1. **Batch Operations**: Use batch endpoints when creating multiple shifts
2. **Caching**: Analytics endpoints support ETags for caching
3. **Pagination**: List endpoints support pagination with `limit` and `offset`
4. **Date Formats**: Use ISO 8601 format for all dates and times
5. **Validation**: Always check validation responses before committing schedules

## Performance Considerations

- Schedule queries are optimized with database indexes on:
  - `location_id + date`
  - `staff_id + date`
  - `status`
- Analytics results are cached for 5 minutes
- Use date ranges wisely - queries over 3 months may be slower

## Migration Guide

For migrating from the legacy scheduling system:

1. Export existing schedules using the legacy export endpoint
2. Map staff IDs to the new system
3. Use the batch import endpoint with validation mode first
4. Review and fix any validation errors
5. Perform the actual import

## Support

For API support, contact:
- Email: api-support@auraconnect.ai
- Documentation: https://docs.auraconnect.ai/scheduling
- Status Page: https://status.auraconnect.ai