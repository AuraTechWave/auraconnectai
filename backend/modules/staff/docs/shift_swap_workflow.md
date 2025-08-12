# Shift Swap Workflow Documentation

## Overview

The enhanced shift swap workflow provides a comprehensive system for staff members to request shift swaps with automated approval rules and manager oversight. The system supports both shift-to-shift swaps and direct assignment to specific staff members.

## Features

### 1. Auto-Approval System
- Configurable rules for automatic swap approval
- Multiple criteria including tenure, advance notice, and performance
- Priority-based rule evaluation
- Blackout date support

### 2. Multi-Level Approval
- Automatic approval for eligible swaps
- Manager approval for complex cases
- Secondary approval support for high-impact swaps
- Rejection with detailed reasoning

### 3. Notification System
- Real-time notifications to all parties
- Response deadline tracking
- Reminder notifications for pending approvals
- Notification history tracking

### 4. Analytics & Reporting
- Swap history and trends
- Approval rate statistics
- Common swap reasons analysis
- Monthly trend tracking

## API Endpoints

### Shift Swap Management

#### Request a Shift Swap
```http
POST /api/v1/staff/swaps
```

Request body:
```json
{
    "from_shift_id": 123,
    "to_shift_id": 456,  // Optional - for shift-to-shift swap
    "to_staff_id": 789,  // Optional - for direct assignment
    "reason": "Personal emergency",
    "urgency": "urgent",  // "urgent", "normal", "flexible"
    "preferred_response_by": "2025-08-14T12:00:00Z"  // Optional
}
```

Response:
```json
{
    "id": 1001,
    "requester_id": 100,
    "requester_name": "John Doe",
    "from_shift_id": 123,
    "from_shift_details": {
        "date": "2025-08-15",
        "start_time": "2025-08-15T09:00:00Z",
        "end_time": "2025-08-15T17:00:00Z",
        "role": "Server",
        "location": "Main Restaurant"
    },
    "to_shift_id": 456,
    "to_shift_details": {
        "date": "2025-08-15",
        "start_time": "2025-08-15T10:00:00Z",
        "end_time": "2025-08-15T18:00:00Z",
        "role": "Server",
        "location": "Main Restaurant",
        "staff_name": "Jane Smith"
    },
    "status": "pending",
    "reason": "Personal emergency",
    "auto_approval_eligible": true,
    "auto_approval_reason": "Auto-approved by rule: Standard Auto-Approval",
    "response_deadline": "2025-08-14T12:00:00Z",
    "created_at": "2025-08-13T10:30:00Z"
}
```

#### List Shift Swaps
```http
GET /api/v1/staff/swaps
```

Query parameters:
- `status`: Filter by status (pending, approved, rejected, cancelled)
- `requester_id`: Filter by requester
- `staff_id`: Show swaps where user is requester or target
- `date_from`: Filter by shift date from
- `date_to`: Filter by shift date to
- `pending_approval`: Show only swaps pending approval
- `page`: Page number (default: 1)
- `per_page`: Items per page (default: 20, max: 100)

#### Get Shift Swap Details
```http
GET /api/v1/staff/swaps/{swap_id}
```

#### Approve/Reject Shift Swap
```http
PUT /api/v1/staff/swaps/{swap_id}/approve
```

Request body:
```json
{
    "status": "approved",  // or "rejected"
    "manager_notes": "Approved - coverage available",
    "rejection_reason": "Insufficient coverage"  // Required if rejecting
}
```

#### Cancel Shift Swap
```http
DELETE /api/v1/staff/swaps/{swap_id}
```

#### Get Pending Approvals
```http
GET /api/v1/staff/swaps/pending/approvals
```

Returns all pending swap requests that need manager approval.

### Swap Approval Rules

#### Create Approval Rule
```http
POST /api/v1/staff/swap-rules
```

Request body:
```json
{
    "rule_name": "Standard Auto-Approval",
    "is_active": true,
    "priority": 10,
    "max_hours_difference": 2.0,
    "same_role_required": true,
    "same_location_required": true,
    "min_advance_notice_hours": 24,
    "max_advance_notice_hours": 168,
    "min_tenure_days": 90,
    "max_swaps_per_month": 3,
    "no_recent_violations": true,
    "performance_rating_min": 3.5,
    "blackout_dates": ["2025-12-24", "2025-12-25"],
    "restricted_shifts": ["holiday", "special_event"],
    "peak_hours_restricted": false,
    "requires_manager_approval": false,
    "requires_both_staff_consent": true,
    "approval_timeout_hours": 48
}
```

#### List Approval Rules
```http
GET /api/v1/staff/swap-rules
```

Query parameters:
- `is_active`: Filter by active status

#### Update Approval Rule
```http
PUT /api/v1/staff/swap-rules/{rule_id}
```

#### Delete Approval Rule
```http
DELETE /api/v1/staff/swap-rules/{rule_id}
```

### Analytics & History

#### Get Swap History Statistics
```http
GET /api/v1/staff/swaps/history/stats
```

Query parameters:
- `start_date`: Start date for statistics
- `end_date`: End date for statistics

Response:
```json
{
    "total_swaps": 150,
    "approved_swaps": 120,
    "rejected_swaps": 20,
    "pending_swaps": 5,
    "cancelled_swaps": 5,
    "average_approval_time_hours": 3.5,
    "most_common_reasons": [
        {"reason": "Personal emergency", "count": 45},
        {"reason": "Sick", "count": 30},
        {"reason": "Family commitment", "count": 25}
    ],
    "swap_trends": [
        {
            "month": "2025-07",
            "total": 50,
            "approved": 40,
            "rejected": 7,
            "auto_approved": 25
        },
        {
            "month": "2025-08",
            "total": 45,
            "approved": 38,
            "rejected": 5,
            "auto_approved": 28
        }
    ]
}
```

## Workflow Examples

### 1. Simple Shift Swap (Auto-Approved)

1. Staff member requests swap between similar shifts
2. System checks auto-approval rules
3. If eligible, swap is automatically approved
4. Both staff members receive notifications
5. Shifts are updated in the system

### 2. Complex Swap (Manager Approval)

1. Staff member requests swap with different hours/roles
2. System determines manager approval needed
3. Manager receives notification with deadline
4. Manager reviews and approves/rejects
5. All parties receive notification of decision
6. If approved, shifts are updated

### 3. Emergency Swap Request

1. Staff member marks swap as "urgent"
2. Response deadline set to 24 hours
3. Managers receive priority notification
4. Expedited review process
5. Quick decision and notification

## Configuration

### Auto-Approval Rules

Rules are evaluated in priority order (highest first). The first matching rule that allows auto-approval will be applied.

Example configurations:

#### Basic Auto-Approval Rule
```json
{
    "rule_name": "Same Day/Role Swaps",
    "priority": 10,
    "max_hours_difference": 0,
    "same_role_required": true,
    "same_location_required": true,
    "min_advance_notice_hours": 24,
    "min_tenure_days": 30,
    "max_swaps_per_month": 5
}
```

#### Flexible Hours Rule
```json
{
    "rule_name": "Flexible Hours Swap",
    "priority": 5,
    "max_hours_difference": 4,
    "same_role_required": true,
    "same_location_required": false,
    "min_advance_notice_hours": 48,
    "min_tenure_days": 180,
    "max_swaps_per_month": 2,
    "performance_rating_min": 4.0
}
```

### Notification Configuration

Notifications are sent via the configured notification service (email, SMS, push notifications).

Notification types:
- **Swap Request**: Sent to target staff (if specific)
- **Approval Request**: Sent to managers
- **Approval/Rejection**: Sent to requester and target
- **Cancellation**: Sent to all involved parties
- **Reminder**: Sent for pending approvals near deadline

## Security & Permissions

### Required Permissions

- **request_swap**: Create swap requests (all staff)
- **view_own_swaps**: View own swap requests (all staff)
- **approve_swap**: Approve/reject swaps (managers/supervisors)
- **view_all_swaps**: View all swap requests (managers/admins)
- **manage_swap_rules**: Create/update approval rules (admins)

### Access Control

- Staff can only swap their own shifts
- Staff can only view swaps they're involved in
- Managers can view/approve swaps for their locations
- Admins have full access to all swaps and rules

## Best Practices

1. **Set Clear Rules**: Define auto-approval rules that match your business needs
2. **Monitor Usage**: Review swap statistics regularly
3. **Adjust Limits**: Update monthly limits based on usage patterns
4. **Blackout Dates**: Set blackout dates for busy periods
5. **Response Times**: Set appropriate response deadlines
6. **Performance Integration**: Link swap eligibility to performance ratings
7. **Audit Trail**: All swap actions are logged for compliance

## Troubleshooting

### Common Issues

1. **Auto-approval not working**
   - Check rule configuration and priority
   - Verify staff meets all criteria
   - Check for blackout dates

2. **Notifications not sent**
   - Verify notification service configuration
   - Check staff notification preferences
   - Review notification logs

3. **Swap conflicts**
   - Check for scheduling conflicts
   - Verify availability settings
   - Review shift requirements

### Error Codes

- `400`: Invalid swap request (validation error)
- `403`: Permission denied
- `404`: Shift or swap not found
- `409`: Conflict (e.g., shift already swapped)