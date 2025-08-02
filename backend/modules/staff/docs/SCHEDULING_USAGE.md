# Staff Scheduling System - Usage Guide

## Overview

The AuraConnect Staff Scheduling System provides comprehensive scheduling management for restaurant staff, including automated scheduling, conflict detection, shift swaps, and analytics.

## Table of Contents
1. [Getting Started](#getting-started)
2. [Basic Operations](#basic-operations)
3. [Advanced Features](#advanced-features)
4. [Code Examples](#code-examples)
5. [Best Practices](#best-practices)

## Getting Started

### Prerequisites
- Backend server running with PostgreSQL
- User with appropriate role (Admin/Manager for most operations)
- Authentication token

### Initial Setup

1. **Run migrations**
   ```bash
   cd backend
   alembic upgrade head
   ```

2. **Verify permissions**
   - Admin: Full access to all scheduling features
   - Manager: Can manage schedules for their location
   - Supervisor: Can approve swaps and view analytics
   - Staff: Can view own schedule and request swaps

## Basic Operations

### 1. Create Shift Templates

Shift templates define recurring shift patterns that can be reused.

```python
# Example: Create a morning shift template
import requests

headers = {"Authorization": "Bearer <your-token>"}
template_data = {
    "location_id": 1,
    "name": "Morning Server Shift",
    "role_id": 2,  # Server role
    "start_time": "08:00",
    "end_time": "16:00",
    "min_staff": 3,
    "max_staff": 5,
    "recurrence_type": "weekly",
    "recurrence_days": ["monday", "tuesday", "wednesday", "thursday", "friday"],
    "estimated_hourly_rate": 15.00
}

response = requests.post(
    "http://localhost:8000/api/v1/staff/templates",
    json=template_data,
    headers=headers
)
```

### 2. Create Individual Shifts

```python
# Create a shift for a specific staff member
shift_data = {
    "staff_id": 123,
    "location_id": 1,
    "date": "2024-02-15",
    "start_time": "2024-02-15T08:00:00",
    "end_time": "2024-02-15T16:00:00",
    "template_id": 1,  # Optional: link to template
    "hourly_rate": 15.00,
    "notes": "Cover for sick leave"
}

response = requests.post(
    "http://localhost:8000/api/v1/staff/shifts",
    json=shift_data,
    headers=headers
)

# The system automatically:
# - Validates shift times
# - Checks for conflicts
# - Verifies staff availability
# - Calculates estimated cost
```

### 3. Set Staff Availability

```python
# Set recurring availability
availability_data = {
    "staff_id": 123,
    "day_of_week": "monday",
    "start_time": "08:00",
    "end_time": "18:00",
    "status": "available",
    "effective_from": "2024-02-01"
}

# Mark specific date as unavailable
unavailable_data = {
    "staff_id": 123,
    "specific_date": "2024-02-20",
    "status": "unavailable",
    "reason": "Personal day off"
}
```

## Advanced Features

### 1. Auto-Generate Schedule

Generate an optimal schedule based on templates and constraints:

```python
# Generate schedule for next week
generation_request = {
    "location_id": 1,
    "start_date": "2024-02-19",
    "end_date": "2024-02-25",
    "auto_assign": True,
    "options": {
        "respect_availability": True,
        "minimize_overtime": True,
        "distribute_hours_evenly": True,
        "max_consecutive_days": 5
    }
}

response = requests.post(
    "http://localhost:8000/api/v1/staff/schedule/generate",
    json=generation_request,
    headers=headers
)
```

### 2. Publish Schedule

Once shifts are created and reviewed, publish them to notify staff:

```python
publish_request = {
    "location_id": 1,
    "start_date": "2024-02-19",
    "end_date": "2024-02-25",
    "notify_staff": True
}

response = requests.post(
    "http://localhost:8000/api/v1/staff/schedule/publish",
    json=publish_request,
    headers=headers
)
```

### 3. Handle Shift Swaps

Staff can request to swap shifts:

```python
# Request a swap
swap_request = {
    "to_staff_id": 456,  # Who should take the shift
    "reason": "Doctor appointment"
}

response = requests.post(
    f"http://localhost:8000/api/v1/staff/shifts/{shift_id}/swap",
    json=swap_request,
    headers=headers
)

# Manager approves the swap
approval = {
    "status": "approved",
    "manager_notes": "Approved - ensure proper handover"
}

response = requests.put(
    f"http://localhost:8000/api/v1/staff/swaps/{swap_id}/approve",
    json=approval,
    headers=headers
)
```

### 4. View Analytics

Get insights into scheduling patterns and costs:

```python
# Get staffing analytics
params = {
    "location_id": 1,
    "start_date": "2024-02-01",
    "end_date": "2024-02-29"
}

response = requests.get(
    "http://localhost:8000/api/v1/staff/analytics/staffing",
    params=params,
    headers=headers
)

# Response includes:
# - Daily coverage percentages
# - Labor costs
# - Hours by role
# - Overtime analysis
```

## Code Examples

### Example 1: Complete Weekly Scheduling Flow

```python
import requests
from datetime import datetime, timedelta

class SchedulingManager:
    def __init__(self, base_url, token):
        self.base_url = base_url
        self.headers = {"Authorization": f"Bearer {token}"}
    
    def schedule_week(self, location_id, week_start):
        """Complete flow to schedule a week"""
        
        # 1. Generate schedule from templates
        print("Generating schedule...")
        generation_response = self._generate_schedule(location_id, week_start)
        
        # 2. Review and adjust if needed
        shifts = self._get_draft_shifts(location_id, week_start)
        print(f"Generated {len(shifts)} shifts")
        
        # 3. Check coverage
        analytics = self._get_analytics(location_id, week_start)
        if analytics["average_coverage"] < 80:
            print("Warning: Low coverage detected")
            # Add more shifts or adjust
        
        # 4. Publish schedule
        print("Publishing schedule...")
        publish_response = self._publish_schedule(location_id, week_start)
        
        return {
            "shifts_created": len(shifts),
            "coverage": analytics["average_coverage"],
            "total_cost": analytics["total_cost"]
        }
    
    def _generate_schedule(self, location_id, week_start):
        week_end = week_start + timedelta(days=6)
        
        response = requests.post(
            f"{self.base_url}/schedule/generate",
            json={
                "location_id": location_id,
                "start_date": week_start.isoformat(),
                "end_date": week_end.isoformat(),
                "auto_assign": True
            },
            headers=self.headers
        )
        return response.json()
```

### Example 2: Conflict Resolution

```python
def handle_scheduling_conflict(shift_data, conflicts):
    """Handle scheduling conflicts intelligently"""
    
    if not conflicts:
        return shift_data
    
    for conflict in conflicts:
        if conflict["type"] == "overlap":
            # Adjust times to avoid overlap
            if conflict["severity"] == "warning":
                # Minor overlap - adjust by 15 minutes
                shift_data["start_time"] = adjust_time(
                    shift_data["start_time"], 
                    minutes=15
                )
            else:
                # Major overlap - find alternative slot
                alternative = find_alternative_slot(
                    shift_data["staff_id"],
                    shift_data["date"]
                )
                if alternative:
                    shift_data.update(alternative)
                else:
                    raise ValueError("No alternative slot available")
        
        elif conflict["type"] == "availability":
            # Find alternative staff member
            alternative_staff = find_available_staff(
                shift_data["date"],
                shift_data["start_time"],
                shift_data["end_time"],
                shift_data["role_id"]
            )
            if alternative_staff:
                shift_data["staff_id"] = alternative_staff["id"]
            else:
                # Mark as unassigned for manual resolution
                shift_data["staff_id"] = None
    
    return shift_data
```

### Example 3: Custom Validation

```python
from backend.modules.staff.services.scheduling_service import SchedulingService

class CustomSchedulingService(SchedulingService):
    """Extended service with custom business rules"""
    
    def validate_shift_assignment(self, staff_id, start_time, end_time, template_id=None):
        # Call parent validation
        valid, reason = super().validate_shift_assignment(
            staff_id, start_time, end_time, template_id
        )
        
        if not valid:
            return valid, reason
        
        # Add custom validations
        
        # 1. Check certification requirements
        if template_id:
            template = self.get_template(template_id)
            if template.requires_certification:
                if not self.staff_has_certification(staff_id, template.certification_id):
                    return False, "Staff member lacks required certification"
        
        # 2. Check consecutive days limit
        consecutive_days = self.count_consecutive_days(staff_id, start_time.date())
        if consecutive_days >= 6:
            return False, "Cannot schedule more than 6 consecutive days"
        
        # 3. Check minimum rest period
        last_shift = self.get_last_shift(staff_id, start_time.date())
        if last_shift:
            rest_hours = (start_time - last_shift.end_time).total_seconds() / 3600
            if rest_hours < 8:
                return False, "Minimum 8 hours rest required between shifts"
        
        return True, None
```

## Best Practices

### 1. Scheduling Strategy

- **Plan Ahead**: Generate schedules at least 2 weeks in advance
- **Use Templates**: Create templates for common shift patterns
- **Set Constraints**: Define min/max hours per staff member
- **Review Coverage**: Always check analytics before publishing

### 2. Performance Tips

- **Batch Operations**: Create multiple shifts in one request
- **Use Caching**: Analytics are cached for 5 minutes
- **Paginate**: Use pagination for large date ranges
- **Index Usage**: Queries are optimized for date ranges

### 3. Conflict Management

- **Proactive Checks**: Validate before creating shifts
- **Handle Warnings**: Address minor conflicts before they escalate
- **Document Changes**: Always add notes when modifying shifts
- **Communication**: Use the notification system effectively

### 4. Data Management

```python
# Regular cleanup of old data
def cleanup_old_schedules(months_to_keep=6):
    cutoff_date = datetime.now() - timedelta(days=months_to_keep * 30)
    
    # Archive completed shifts
    archive_shifts(status="completed", before_date=cutoff_date)
    
    # Clean up cancelled/draft shifts
    delete_shifts(status=["cancelled", "draft"], before_date=cutoff_date)
```

### 5. Integration Examples

```python
# Integrate with payroll system
def sync_to_payroll(start_date, end_date):
    completed_shifts = get_completed_shifts(start_date, end_date)
    
    payroll_data = []
    for shift in completed_shifts:
        payroll_data.append({
            "employee_id": shift.staff_id,
            "date": shift.date,
            "hours": calculate_hours(shift),
            "rate": shift.hourly_rate,
            "overtime": is_overtime(shift)
        })
    
    return send_to_payroll_system(payroll_data)
```

## Troubleshooting

### Common Issues

1. **"Shift conflicts detected"**
   - Check existing shifts for the staff member
   - Verify availability settings
   - Review consecutive day limits

2. **"Insufficient permissions"**
   - Verify user role
   - Check location assignment for managers
   - Ensure token is valid

3. **"No staff available"**
   - Review availability settings
   - Check staff work hour limits
   - Verify role assignments

### Debug Mode

Enable detailed logging:

```python
import logging

logging.getLogger("scheduling").setLevel(logging.DEBUG)

# This will show:
# - Conflict detection details
# - Availability calculations
# - Auto-scheduling decisions
```

## Migration from Legacy System

If migrating from an older scheduling system:

1. Export existing schedules
2. Map staff IDs and roles
3. Import historical data (optional)
4. Set up templates based on patterns
5. Configure availability
6. Run test schedules before going live

## Support

For additional help:
- API Documentation: `/docs` endpoint
- Email: dev-support@auraconnect.ai
- GitHub Issues: https://github.com/auraconnect/scheduling/issues