# Staff Management Module

## Overview

The Staff Management module provides comprehensive employee management capabilities including advanced scheduling, biometric authentication, role-based permissions, and attendance tracking.

## Features

### Core Features
- **Employee Management**: Complete employee profiles with roles and permissions
- **Advanced Scheduling**: Template-based scheduling with conflict detection
- **Biometric Authentication**: Secure face recognition for clock-in/clock-out
- **Shift Management**: Real-time shift tracking with swap requests
- **Availability Management**: Staff availability preferences and time-off requests
- **Performance Metrics**: Analytics and reporting for staffing decisions

### Scheduling Features
- **Shift Templates**: Reusable templates for common shift patterns
- **Auto-Scheduling**: Intelligent shift assignment based on availability
- **Conflict Detection**: Automatic detection of scheduling conflicts
- **Shift Swaps**: Employee-initiated swap requests with manager approval
- **Break Management**: Configurable break tracking
- **Labor Cost Estimation**: Real-time cost calculations

## Database Schema

### Enhanced Scheduling Tables
- `enhanced_shifts` - Main shift records
- `shift_templates` - Reusable shift patterns
- `staff_availability` - Employee availability preferences
- `shift_swaps` - Swap request tracking
- `shift_breaks` - Break management
- `schedule_publications` - Published schedule tracking

## API Endpoints

### Scheduling Endpoints
```
POST   /api/v1/staff/schedule/templates      # Create shift template
GET    /api/v1/staff/schedule/templates      # List templates
PUT    /api/v1/staff/schedule/templates/{id} # Update template

POST   /api/v1/staff/schedule/shifts         # Create shift
GET    /api/v1/staff/schedule/shifts         # List shifts
PUT    /api/v1/staff/schedule/shifts/{id}    # Update shift
DELETE /api/v1/staff/schedule/shifts/{id}    # Delete/cancel shift

POST   /api/v1/staff/schedule/availability   # Set availability
GET    /api/v1/staff/schedule/availability   # Get availability

POST   /api/v1/staff/schedule/swaps          # Request swap
PUT    /api/v1/staff/schedule/swaps/{id}/approve # Approve/reject swap

POST   /api/v1/staff/schedule/generate       # Auto-generate schedule
POST   /api/v1/staff/schedule/publish        # Publish schedule

GET    /api/v1/staff/schedule/analytics/staffing # Staffing analytics
GET    /api/v1/staff/schedule/analytics/conflicts # Conflict check
```

### Biometric Endpoints
```
POST   /api/v1/staff/biometric/register      # Register biometric data
POST   /api/v1/staff/biometric/verify        # Verify identity
POST   /api/v1/staff/biometric/clock-in      # Clock in with biometric
POST   /api/v1/staff/biometric/clock-out     # Clock out with biometric
DELETE /api/v1/staff/biometric/{staff_id}    # Remove biometric data
```

## Database Migrations

### Running Migrations

1. **Check Current Migration Status**:
   ```bash
   cd backend
   alembic current
   ```

2. **Apply Scheduling Migration**:
   ```bash
   alembic upgrade add_staff_scheduling
   ```

3. **Verify Migration**:
   ```bash
   # Check that all tables were created
   psql -d your_database -c "\dt enhanced_shifts;"
   psql -d your_database -c "\dt shift_templates;"
   psql -d your_database -c "\dt staff_availability;"
   ```

### Migration Notes
- The scheduling migration creates all necessary tables and indexes
- Enum types are created for shift status, types, and other categorical data
- All foreign key relationships are properly established
- Indexes are added for common query patterns

## Workflows

### 1. Setting Up Shift Templates
```python
# Create a morning shift template
POST /api/v1/staff/schedule/templates
{
    "name": "Morning Shift",
    "role_id": 1,
    "location_id": 1,
    "start_time": "06:00",
    "end_time": "14:00",
    "recurrence_type": "weekly",
    "recurrence_days": [0, 1, 2, 3, 4],  # Mon-Fri
    "min_staff": 2,
    "preferred_staff": 3
}
```

### 2. Auto-Generate Weekly Schedule
```python
# Generate schedule from templates
POST /api/v1/staff/schedule/generate
{
    "start_date": "2024-02-12",
    "end_date": "2024-02-18",
    "location_id": 1,
    "auto_assign": true
}
```

### 3. Managing Shift Swaps
```python
# Step 1: Employee requests swap
POST /api/v1/staff/schedule/swaps
{
    "from_shift_id": 123,
    "to_shift_id": 456,  # Or use to_staff_id
    "reason": "Doctor appointment"
}

# Step 2: Manager approves
PUT /api/v1/staff/schedule/swaps/1/approve
{
    "status": "approved",
    "manager_notes": "Approved - coverage confirmed"
}
```

### 4. Publishing Schedule
```python
# Publish draft shifts and notify staff
POST /api/v1/staff/schedule/publish
{
    "start_date": "2024-02-12",
    "end_date": "2024-02-18",
    "location_id": 1,
    "send_notifications": true,
    "notes": "Weekly schedule published"
}
```

### 5. Biometric Clock-In Flow
```python
# Step 1: Register biometric (one-time)
POST /api/v1/staff/biometric/register
{
    "staff_id": 123,
    "biometric_data": "base64_encoded_face_data"
}

# Step 2: Daily clock-in
POST /api/v1/staff/biometric/clock-in
{
    "biometric_data": "base64_encoded_face_data",
    "location": "Front entrance"
}
```

## Role-Based Permissions

### Permission Levels
- **Admin**: Full access to all scheduling features
- **Manager**: Create/edit schedules, approve swaps, view analytics
- **Supervisor**: Limited scheduling rights, approve swaps
- **Staff**: View own schedule, request swaps, set availability

### Protected Actions
- Creating/editing templates (Manager+)
- Publishing schedules (Manager+)
- Approving swap requests (Supervisor+)
- Viewing analytics (Manager+)
- Auto-generating schedules (Manager+)

## Performance Considerations

### Database Indexes
The migration creates indexes on:
- `enhanced_shifts`: staff_id, location_id, date, status
- `shift_templates`: location_id, is_active
- `staff_availability`: staff_id
- Composite indexes for common query patterns

### Query Optimization
- Use eager loading to prevent N+1 queries
- Analytics queries are cached for 5 minutes
- Batch operations for creating multiple shifts

## Development Tips

### Testing Scheduling Logic
```python
# Test conflict detection
from modules.staff.services.scheduling_service import SchedulingService

service = SchedulingService(db)
conflicts = service.detect_conflicts(
    staff_id=1,
    start_time=datetime(2024, 2, 12, 9, 0),
    end_time=datetime(2024, 2, 12, 17, 0)
)
```

### Common Issues

1. **Migration Errors**: 
   - Ensure enum types don't already exist
   - Check foreign key references are valid

2. **Swap Validation**:
   - Shifts must be from same location/role
   - Target staff must be available
   - Cannot swap completed/cancelled shifts

3. **Performance**:
   - Use pagination for large shift queries
   - Cache analytics data
   - Use bulk operations for mass updates

## Future Enhancements

### Planned Features
- [ ] Push notifications for schedule changes
- [ ] Mobile app integration
- [ ] Advanced forecasting based on historical data
- [ ] Integration with payroll for automatic hour calculation
- [ ] Multi-location staff sharing
- [ ] Skill-based scheduling

### In Progress
- Notification system implementation (see [NOTIFICATION_SYSTEM_TODO.md](docs/NOTIFICATION_SYSTEM_TODO.md))
- Enhanced conflict resolution algorithms
- Real-time schedule updates via WebSocket